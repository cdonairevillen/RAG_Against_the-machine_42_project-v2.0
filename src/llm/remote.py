"""An LLM behind an OpenAI-compatible API (Phase 10, 10a).

Same interface as the local `Generator` (src/rag/generator.py), so the
pipeline, the agent, the API and the benchmarks use either one:
    answer_with_text / stream_answer  the grounded answer, with the same
                                      messages (build_messages) and the
                                      same clean-up (clean_output).
    tool_step                         one planning step of the agent,
                                      with the API's native tool calls.
    count_tokens / fit_sources        the context budget (estimated: an
                                      API model's tokenizer is not here).
    cancel                            the web's Stop button.

The API applies the model's own chat template. The key is read from the
environment or .env on the server and never leaves it.
"""
import json
import os
import time
from threading import Event
from typing import Any, Iterator, Optional

import httpx

from src.agent.toolcalls import load_json, parse_tool_calls
from src.config import GenerationConfig
from src.rag.generator import THINK_BLOCK, build_messages, clean_output
from src.rag.language import detect_language
from src.rag.loops import BOUNDARY, find_loop

# Characters per token used to estimate the context budget without the
# model's tokenizer (a little under the ~4 of English text, so the
# estimate errs on the short side).
CHARS_PER_TOKEN = 3.5
# A planning step needs room for the JSON of a call, whatever the agent's
# STEP_TOKENS (sized for the local models).
MIN_STEP_TOKENS = 256


class RemoteUnavailable(RuntimeError):
    """The API did not answer: rate limit, server error, timeout or a
    rejected request, after the configured retries. The web falls back
    to a local model (RAG_API_FALLBACK_MODEL)."""


def read_key(variable: str, env_file: str = ".env") -> str:
    """An API key from the environment or the .env file."""
    if os.environ.get(variable):
        return os.environ[variable]
    if os.path.isfile(env_file):
        with open(env_file, encoding="utf-8") as fh:
            for line in fh:
                name, _, value = line.strip().partition("=")
                if name == variable:
                    return value.strip().strip('"').strip("'")
    raise ValueError(f"{variable} is not set (environment or .env)")


def call_key(name: Any, arguments: Any) -> str:
    """A tool call's identity, to find the provider's extra fields
    again when the call is sent back."""
    return json.dumps({"name": name, "arguments": arguments},
                      ensure_ascii=False, sort_keys=True)


def api_messages(messages: list[dict[str, Any]],
                 extras: Optional[dict[str, dict[str, Any]]] = None
                 ) -> list[dict[str, Any]]:
    """The agent's messages in the API's tool-calling format.

    The agent keeps its history the local way: an assistant message with
    the raw output (<tool_call>{json}</tool_call>) followed by one 'tool'
    message per call. The API wants the calls structured, each with an
    id that its result repeats.

    Args:
        messages: The agent's history.
        extras: Provider fields of earlier calls, by `call_key`, sent
            back as they came (Gemini requires its `thought_signature`).
    """
    out: list[dict[str, Any]] = []
    pending: list[str] = []
    number = 0
    for i, message in enumerate(messages):
        role, content = message["role"], message.get("content") or ""
        if role == "assistant":
            calls = parse_tool_calls(content)
            # Only the calls that got a result (the agent skips calls
            # without a query): the API rejects a call left unanswered.
            answered = 0
            for later in messages[i + 1:]:
                if later["role"] != "tool":
                    break
                answered += 1
            calls = calls[:answered]
            if calls:
                structured = []
                for call in calls:
                    number += 1
                    pending.append(f"call_{number}")
                    structured.append({
                        **(extras or {}).get(
                            call_key(call["name"], call["arguments"]), {}),
                        "id": f"call_{number}", "type": "function",
                        "function": {
                            "name": call["name"],
                            "arguments": json.dumps(call["arguments"],
                                                    ensure_ascii=False),
                        },
                    })
                out.append({"role": "assistant", "content": None,
                            "tool_calls": structured})
                continue
        if role == "tool":
            if pending:
                out.append({"role": "tool", "tool_call_id": pending.pop(0),
                            "content": content})
            else:
                out.append({"role": "user",
                            "content": "Tool result:\n" + content})
            continue
        out.append({"role": role, "content": content})
    return out


class RemoteGenerator:
    """Grounded answers from a model served by an OpenAI-compatible API.

    Usage (rag.toml profile with provider = "openai"):
        generator = RemoteGenerator(load_config(
            profile="llm-nvidia-lightning").generation)
        generator.answer_with_text(question, context_blocks)

    Attributes:
        model_name: The provider's model id.
        max_new_tokens: Maximum tokens per answer (`max_tokens`).
        max_input_tokens: Budget for the whole prompt (estimated).
        last_finish_reason: The API's reason for the last answer's end
            ("stop", "length"...), for the web's "cut" mark.
    """

    def __init__(self, config: GenerationConfig) -> None:
        if not config.base_url or not config.api_key_env:
            raise ValueError("An API model needs base_url and api_key_env "
                             "(rag.toml profile).")
        self.model_name = config.model
        self.max_new_tokens = config.max_new_tokens
        self.max_input_tokens = config.max_input_tokens
        self.style_rule = config.style_rule
        self.base_url = config.base_url.rstrip("/")
        self.extra = dict(config.extra_body)
        self.retries = max(1, config.retries)
        self.min_interval = max(0.0, config.min_interval)
        self.last_request = 0.0
        self.client = httpx.Client(
            timeout=httpx.Timeout(config.timeout, connect=10.0),
            headers={"Authorization":
                     f"Bearer {read_key(config.api_key_env)}"},
        )
        self.cancel = Event()
        self.last_finish_reason = ""
        # Provider fields of the agent's tool calls (call_key -> fields).
        self.call_extras: dict[str, dict[str, Any]] = {}
        print(f"Using {self.model_name} through {self.base_url}.")

    # --- the grounded answer -------------------------------------------

    def answer_with_text(self, question: str,
                         context_blocks: list[str],
                         extra_rules: str = "",
                         language: Optional[str] = None,
                         style_rule: Optional[str] = None) -> str:
        """Same contract as Generator.answer_with_text()."""
        if not question or not question.strip():
            return "No question provided."
        if not context_blocks:
            return "No relevant sources found."
        return clean_output("".join(self.stream(self.messages(
            question, context_blocks, extra_rules, language, style_rule))))

    def stream_answer(self, question: str,
                      context_blocks: list[str],
                      extra_rules: str = "",
                      language: Optional[str] = None,
                      style_rule: Optional[str] = None) -> Iterator[str]:
        """Same contract as Generator.stream_answer(): raw pieces, the
        caller cleans the joined text."""
        if not question or not question.strip() or not context_blocks:
            yield self.answer_with_text(question, context_blocks,
                                        extra_rules, language, style_rule)
            return
        yield from self.stream(self.messages(
            question, context_blocks, extra_rules, language, style_rule))

    def messages(self, question: str, context_blocks: list[str],
                 extra_rules: str = "", language: Optional[str] = None,
                 style_rule: Optional[str] = None) -> list[dict[str, str]]:
        """The local models' messages (build_messages), sources fitted
        to the budget."""
        language = language or detect_language(question)
        style = self.style_rule if style_rule is None else style_rule
        sources = self.fit_sources(question, context_blocks, language,
                                   extra_rules, style)
        return build_messages(question, sources, language, extra_rules,
                              style)

    def count_tokens(self, text: str) -> int:
        """Estimated tokens of a text (no tokenizer for an API model)."""
        return round(len(text) / CHARS_PER_TOKEN)

    def fit_sources(self, question: str, blocks: list[str],
                    language: str, extra_rules: str = "",
                    style_rule: Optional[str] = None) -> list[str]:
        """Generator.fit_sources() with estimated tokens: sources keep
        their order, the last one that does not fit is cut."""
        fixed = sum(self.count_tokens(m["content"]) + 4 for m in
                    build_messages(question, [], language, extra_rules,
                                   self.style_rule if style_rule is None
                                   else style_rule))
        budget = self.max_input_tokens - fixed
        fitted: list[str] = []
        for block in blocks:
            cost = self.count_tokens(block) + 4
            if cost <= budget:
                fitted.append(block)
                budget -= cost
                continue
            if budget > 64:
                fitted.append(block[:int((budget - 8) * CHARS_PER_TOKEN)])
            break
        return fitted or blocks[:1]

    # --- the agent -------------------------------------------------------

    def tool_step(self, messages: list[dict[str, Any]],
                  tools: list[dict[str, Any]], max_new_tokens: int) -> str:
        """One planning step with native tool calls.

        Returns the step the way a local model writes it (text plus
        <tool_call>{json}</tool_call> per call), so the agent parses,
        logs and replays it exactly as before.
        """
        body = {
            "model": self.model_name,
            "messages": api_messages(messages, self.call_extras),
            "tools": tools, "tool_choice": "auto", "temperature": 0,
            "max_tokens": max(max_new_tokens, MIN_STEP_TOKENS),
            **self.extra,
        }
        response = self.send(body, stream=False)
        try:
            reply = response.json()
        finally:
            response.close()
        message = (reply.get("choices") or [{}])[0].get("message") or {}
        text = THINK_BLOCK.sub("", message.get("content") or "").strip()
        for call in message.get("tool_calls") or []:
            function = call.get("function") or {}
            arguments = function.get("arguments") or {}
            if isinstance(arguments, str):
                arguments = load_json(arguments) or {}
            extra = {key: value for key, value in call.items()
                     if key not in ("id", "type", "function", "index")}
            if extra:
                self.call_extras[call_key(function.get("name"),
                                          arguments)] = extra
            text += "\n<tool_call>" + json.dumps(
                {"name": function.get("name"), "arguments": arguments},
                ensure_ascii=False) + "</tool_call>"
        return text.strip()

    # --- HTTP --------------------------------------------------------------

    def stream(self, messages: list[dict[str, Any]]) -> Iterator[str]:
        """Stream an answer (SSE). Stops on `cancel` and, like the local
        models, when the answer falls into a loop."""
        body = {
            "model": self.model_name, "messages": messages,
            "max_tokens": self.max_new_tokens, "temperature": 0,
            "stream": True, **self.extra,
        }
        self.last_finish_reason = ""
        response = self.send(body, stream=True)
        text = ""
        try:
            for line in response.iter_lines():
                if self.cancel.is_set():
                    break
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                except ValueError:
                    continue
                choices = chunk.get("choices") or []
                if not choices:
                    continue
                if choices[0].get("finish_reason"):
                    self.last_finish_reason = choices[0]["finish_reason"]
                piece = (choices[0].get("delta") or {}).get("content") or ""
                if not piece:
                    continue
                text += piece
                yield piece
                if BOUNDARY.search(piece) and find_loop(text) is not None:
                    break
        except httpx.HTTPError as exc:
            # Cut mid-answer: keep what arrived. Nothing yet: the caller
            # may still answer with another model.
            if not text:
                raise RemoteUnavailable(
                    f"{self.model_name}: {type(exc).__name__}") from exc
        finally:
            response.close()

    def send(self, body: dict[str, Any], stream: bool) -> httpx.Response:
        """POST /chat/completions, retrying rate limits (429), server
        errors and timeouts with a growing wait.

        Raises:
            RemoteUnavailable: still failing after `retries` attempts, or
                a request the API rejects (bad model, key...).
        """
        url = f"{self.base_url}/chat/completions"
        reason = ""
        for attempt in range(self.retries):
            if self.cancel.is_set():
                break
            wait = self.last_request + self.min_interval - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            self.last_request = time.monotonic()
            delay = 2.0 * (attempt + 1)
            try:
                response = self.client.send(
                    self.client.build_request("POST", url, json=body),
                    stream=stream)
            except httpx.HTTPError as exc:
                reason = type(exc).__name__
            else:
                if response.status_code == 200:
                    return response
                status = response.status_code
                response.read()
                full = " ".join(response.text.split())
                detail = full[:200]
                response.close()
                reason = f"HTTP {status} {detail}".strip()
                # A used-up daily quota (Gemini: ...PerDay...) does not
                # come back by retrying: give up at once.
                if (status != 429 and status < 500) or "PerDay" in full:
                    break
                after = response.headers.get("retry-after", "")
                if after.isdigit():
                    delay = max(delay, min(float(after), 60.0))
            if attempt < self.retries - 1:
                time.sleep(delay)
        raise RemoteUnavailable(f"{self.model_name}: {reason or 'stopped'}")
