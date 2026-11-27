"""The agent: the default way to talk to the RAG (D7).

Per question:
    1. Plan: the LLM sees the domains, the conversation so far and the
       question, and calls the `search` tool with a complete,
       self-contained query (pronouns resolved: this is where follow-up
       questions get rewritten). It may search up to max_steps times and
       stops by not calling the tool again.
    2. Fallback: if it never produces a valid call, the original
       question is searched as it is (deterministic, like direct mode).
    3. Answer: the gathered sources go to the same grounded generator as
       the direct flow, with the domain's rules (citations, CV prompt,
       private data, "not found" message), in the user's language.
    4. Memory: the turn is added to the session.

Every model can be the agent (src/agent/toolcalls.py handles each
model's tool convention); the benchmark shows which ones do it well.
"""
import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional, Sequence

from src.agent.memory import Session, Turn
from src.agent.toolcalls import SEARCH_TOOL, parse_tool_calls, render
from src.models import MinimalSource
from src.rag.generator import (
    Generator, clean_output, is_not_found, not_found_for,
)
from src.rag.language import detect_language
from src.rag.pipeline import build_context_blocks
from src.rag.router import parse_domains
from src.server.tools import RagTools

AGENT_PROMPT = (
    "You are the assistant of a retrieval system (RAG). You never answer "
    "from your own knowledge: you search, and another step writes the "
    "answer from what you found.\n"
    "Knowledge domains:\n{domains}\n"
    "Every new question needs at least one search, even if the "
    "conversation seems to answer it. "
    "Call the search tool with a complete, self-contained question: "
    "replace pronouns and references (he, she, it, there, that club, "
    "¿y ...?) with what they refer to in the conversation. Set "
    "\"domains\" when you know which domain holds the answer. After "
    "searching, when the results are enough, reply with the single word "
    "DONE."
)
# Output tokens of one planning step (a tool call is short).
STEP_TOKENS = 128
# Characters of each source shown back to the planner.
RESULT_PREVIEW = 300
# What the generator answers after the fallback (see Agent.__init__).
FALLBACK_ANSWERS = ("mixed", "original")
# What the generator answers after the model's own searches.
ANSWER_WITH = ("rewrite", "original", "context", "both")


@dataclass
class AgentAnswer:
    """Result of one agent turn.

    Attributes:
        question: The user's question, as asked.
        text: Final answer (or the domain's "not found" message).
        sources: Sources given to the generator, in [n] order.
        not_found: Whether the answer means "not found".
        domain: Domain the answer came from (or the closest one).
        queries: Searches made, in order (the rewritten questions).
        steps: Planning calls to the LLM.
        fallback: True when the agent made no valid tool call and the
            original question was searched instead.
        retries: Safety nets used: "all-domains" (the model's domain
            choice found nothing, retried within the user's filter) and
            "original-question" (its rewrite found nothing).
        raw_steps: The planner's raw outputs (for debugging).
        seconds_agent / seconds_generation: Planning+search time and
            final answer time.
    """

    question: str
    text: str
    sources: list[MinimalSource] = field(default_factory=list)
    not_found: bool = False
    domain: Optional[str] = None
    queries: list[str] = field(default_factory=list)
    steps: int = 0
    fallback: bool = False
    raw_steps: list[str] = field(default_factory=list)
    seconds_agent: float = 0.0
    seconds_generation: float = 0.0
    retries: list[str] = field(default_factory=list)


class Agent:
    """Tool-calling agent over the RAG, with session memory.

    Usage:
        tools = RagTools.load()
        agent = Agent(tools)
        agent.ask("¿Dónde nació Chrystian?")
        agent.ask("¿Y en qué año?")      # rewritten with the history
        agent.session.clear()
    """

    def __init__(self, tools: RagTools, max_steps: int = 3,
                 k: int = 5, generator: Optional[Generator] = None,
                 fallback_answer: str = "mixed",
                 answer_with: Optional[str] = None) -> None:
        self.tools = tools
        # Which question the generator answers when the model searched
        # (no fallback). "rewrite": the model's first query that found
        # sources, as before (often keywords: "X birth date"); "original":
        # the user's question; "context": the user's question, followed
        # by the rewrite in brackets when there is a conversation (it
        # names what "he" or "it" refers to); "both": the user's question
        # plus the rewrite in brackets whenever they differ, first
        # questions too ("¿Qué eres? (What is this project?)"). None: the
        # model's own
        # setting (rag.toml agent_answer_with, read at every question:
        # the web swaps the model within a session).
        if answer_with is not None and answer_with not in ANSWER_WITH:
            raise ValueError(f"answer_with must be one of {ANSWER_WITH}")
        self.answer_with = answer_with
        # Plan B (8f): after the deterministic fallback, which question the
        # generator answers. "mixed": the fallback query (last query +
        # new question), as before; "original": the question as asked,
        # with the sources found by the mixed query.
        if fallback_answer not in FALLBACK_ANSWERS:
            raise ValueError(f"fallback_answer must be one of "
                             f"{FALLBACK_ANSWERS}")
        self.fallback_answer = fallback_answer
        # The LLM that plans and answers (default: the tools' one). The
        # web's model selector swaps it between questions; the session's
        # memory is kept.
        self.generator = generator or tools.get_pipeline().generator
        self.max_steps = max_steps
        self.k = k
        self.session = Session()

    def system_prompt(self) -> str:
        """The planner's instructions, listing the domains."""
        domains = "\n".join(
            f"- {d['name']}: {d['description']}"
            for d in self.tools.list_domains()
        )
        return AGENT_PROMPT.format(domains=domains)

    def search(self, query: str, domains: Optional[str | Sequence[str]]
               ) -> dict[str, Any]:
        """One search, restricted to the user's domain filter if any."""
        return self.tools.search(query, domains, self.k)

    def plan(self, question: str,
             user_domains: Optional[str | Sequence[str]]
             ) -> tuple[list[tuple[str, dict[str, Any]]], list[str], bool,
                        list[str]]:
        """Let the LLM search until it stops (or max_steps).

        Returns:
            (searches as (query, result), raw outputs, fallback used,
            safety nets used: "all-domains", "original-question").
        """
        # The history goes inside the user turn, not as earlier chat
        # turns: with past answers as assistant messages, small models
        # copy that pattern and answer without searching (measured with
        # Qwen3-0.6B).
        history = self.session.transcript()
        content = question if not history else (
            f"Conversation so far:\n{history}\n\nNew question: {question}"
        )
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": self.system_prompt()},
            {"role": "user", "content": content},
        ]
        # An API model (src/llm/remote.py) plans with the API's native tool
        # calls; a local one renders its own template (toolcalls.py).
        tool_step = getattr(self.generator, "tool_step", None)
        searches: list[tuple[str, dict[str, Any]]] = []
        raw: list[str] = []
        retries: list[str] = []
        for _ in range(self.max_steps):
            if tool_step is not None:
                output = tool_step(messages, [SEARCH_TOOL], STEP_TOKENS)
            else:
                output = self.generator.complete(
                    render(self.generator.tokenizer, messages,
                           [SEARCH_TOOL]), STEP_TOKENS
                )
            raw.append(output)
            calls = [c for c in parse_tool_calls(output)
                     if c["name"] == "search"
                     and str(c["arguments"].get("query", "")).strip()]
            if not calls:
                break
            messages.append({"role": "assistant", "content": output})
            for call in calls:
                query = str(call["arguments"]["query"]).strip()
                # The user's filter (e.g. the web's CV mode) wins over
                # the domains the model picks.
                domains = user_domains or call["arguments"].get("domains")
                if domains and not user_domains:
                    known = set(self.tools.router.domains)
                    domains = [d for d in parse_domains(str(domains))
                               if d in known] or None
                result = self.search(query, domains)
                if not result["sources"] and domains and not user_domains:
                    # Safety net 2: the domain the model picked is a hint.
                    # Nothing there: retry the same query over every
                    # domain the user allows (no filter = all, exactly
                    # what direct mode searches). Never beyond a user
                    # filter: with one, `domains` is that filter.
                    retries.append("all-domains")
                    result = self.search(query, user_domains)
                searches.append((query, result))
                messages.append({"role": "tool", "content":
                                 self.describe(result)})
        if any(r["sources"] for _, r in searches):
            return searches, raw, False, retries
        if searches:
            # Safety net 1: the model's rewrite found nothing (small
            # models turn questions into keyword fragments the gate
            # rejects). Search the question as the user asked it.
            retries.append("original-question")
            result = self.search(question, user_domains)
            searches.append((question, result))
            if result["sources"]:
                return searches, raw, False, retries
        # Deterministic fallback: the question as asked, with the last
        # query the model itself wrote in front, so a follow-up keeps its
        # subject ("¿Dónde nació Chrystian? ¿Y en qué año?"). Earlier
        # fallback queries are skipped so they do not pile up.
        last = next((t.query for t in reversed(self.session.turns)
                     if not t.fallback), "")
        query = f"{last} {question}".strip()
        if searches and query == question:
            return searches, raw, True, retries
        searches.append((query, self.search(query, user_domains)))
        return searches, raw, True, retries

    def question_to_answer(self, question: str, query: str,
                           fallback: bool, history: bool) -> str:
        """The question the generator answers (answer_with and
        fallback_answer, see __init__)."""
        if fallback:
            # Plan B: search with the mix, answer only what was asked.
            if self.fallback_answer == "original":
                return question
            return query
        mode = self.answer_with or getattr(
            self.generator, "agent_answer_with", "rewrite")
        if mode == "original":
            return question
        if mode in ("context", "both"):
            if query.strip() == question.strip() or (
                    mode == "context" and not history):
                return question
            return f"{question} ({query})"
        return query

    @staticmethod
    def describe(result: dict[str, Any]) -> str:
        """A search result as the planner reads it (short)."""
        if not result["sources"]:
            return "No relevant sources found."
        lines = [f"domain: {result['domain']}"]
        for i, src in enumerate(result["sources"][:3], 1):
            text = " ".join(src["text"].split())[:RESULT_PREVIEW]
            lines.append(f"[{i}] {src['file_path']}: {text}")
        return "\n".join(lines)

    def ask(self, question: str,
            domains: Optional[str | Sequence[str]] = None,
            on_piece: Optional[Callable[[str], None]] = None
            ) -> AgentAnswer:
        """Answer one turn of the conversation.

        Args:
            question: The user's question (may refer to earlier turns).
            domains: The user's domain filter (e.g. only "cv").
            on_piece: Streaming callback for the final answer.

        Returns:
            The answer, with the searches made and timings.
        """
        start = time.perf_counter()
        searches, raw, fallback, retries = self.plan(question, domains)
        seconds_agent = time.perf_counter() - start

        found = [(q, r) for q, r in searches if r["sources"]]
        language = detect_language(question)
        rules = self.tools.rules
        if not found:
            domain = searches[-1][1]["domain"]
            text = rules.not_found_message(domain, question) \
                or not_found_for(question)
            if on_piece:
                on_piece(text)
            return self.remember(AgentAnswer(
                question, text, [], True, domain,
                [q for q, _ in searches], len(raw), fallback, raw,
                seconds_agent, retries=retries,
            ))

        query, first = found[0]
        query = self.question_to_answer(question, query, fallback,
                                        bool(self.session.turns))
        domain = first["domain"]
        retriever = self.tools.router.retrievers.get(domain)
        limit = (retriever.answer_k if retriever else None) or self.k
        sources: list[MinimalSource] = []
        seen: set[tuple[str, int]] = set()
        for _, result in found:
            for src in result["sources"]:
                key = (src["file_path"], src["first_character_index"])
                if key not in seen and len(sources) < limit:
                    seen.add(key)
                    sources.append(MinimalSource(
                        file_path=src["file_path"],
                        first_character_index=src["first_character_index"],
                        last_character_index=src["last_character_index"],
                    ))
        sources = rules.context_order(sources, domain)
        blocks = build_context_blocks(
            sources, self.tools.router.get_parent_chunk_map(), rules
        )
        extra = rules.prompt_rules(
            domain, getattr(self.generator, "model_name", ""))
        style = rules.style_rule(domain)
        own = {"style_rule": style} if style is not None else {}
        start = time.perf_counter()
        if on_piece:
            pieces = []
            for piece in self.generator.stream_answer(
                    query, blocks, extra, language, **own):
                pieces.append(piece)
                on_piece(piece)
            text = clean_output("".join(pieces))
        else:
            text = self.generator.answer_with_text(query, blocks, extra,
                                                   language, **own)
        not_found = is_not_found(text)
        text = (rules.not_found_message(domain, question)
                or not_found_for(question)) if not_found \
            else rules.redact_all(text)
        return self.remember(AgentAnswer(
            question, text, sources, not_found, domain,
            [q for q, _ in searches], len(raw), fallback, raw,
            seconds_agent, time.perf_counter() - start, retries,
        ))

    def remember(self, answer: AgentAnswer) -> AgentAnswer:
        """Add the turn to the session and return it."""
        self.session.add(Turn(
            answer.question, answer.text,
            answer.queries[0] if answer.queries else "",
            answer.domain or "", answer.fallback,
        ))
        return answer

    @staticmethod
    def trace(answer: AgentAnswer) -> str:
        """One-line summary of what the agent did (CLI, logs)."""
        return json.dumps({
            "queries": answer.queries, "domain": answer.domain,
            "steps": answer.steps, "fallback": answer.fallback,
            "retries": answer.retries,
        }, ensure_ascii=False)
