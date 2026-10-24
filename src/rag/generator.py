import re
from threading import Event, Thread
from typing import Any, Iterator, Optional

import torch
from llm_sdk import Small_LLM_Model

from src.config import GenerationConfig
from src.rag.language import LANGUAGE_NAMES, detect_language
from src.rag.loops import BOUNDARY, cut_loop, find_loop

NOT_FOUND_PATTERNS = (
    r"not found in the provided sources",
    r"i've not found",
    r"i have not found",
    r"provided sources do not contain",
    r"there is no information",
    r"no relevant information",
    r"no se encuentra en las fuentes",
    r"no (he )?encontrado (información|nada)",
    r"las fuentes (proporcionadas )?no contienen",
    # Other refusals seen in the CV benchmark (31-cv-prompt).
    r"no se (menciona|proporciona|encuentra en (los|las) "
    r"(proporcionad|fuente|source))",
    r"not (mentioned|provided|found) in the (provided )?sources",
    # Seen with Qwen3-1.7B in the web (2026-10-24).
    r"no est[áa] disponible en (los|las) fuentes",
    # Domain messages (rag.toml not_found_message, e.g. the CV mode).
    r"no dispongo de esa información",
    r"i don't have that information",
)

NOT_FOUND_MESSAGE = "Not found in the provided sources."
# The generic "not found" answer in the user's language (domains can set
# their own: rag.toml not_found_message). The prompt keeps the English
# one, which is what the model is told to reply.
NOT_FOUND_MESSAGES = {
    "en": NOT_FOUND_MESSAGE,
    "es": "No se encuentra en las fuentes proporcionadas.",
}

SYSTEM_PROMPT = (
    "You are a technical assistant that answers questions using ONLY the "
    "numbered SOURCES given by the user.\n"
    "Rules:\n"
    "1. Use only facts stated in the SOURCES. Never use prior knowledge.\n"
    "2. Cite the sources you use with their number in brackets, like "
    "[1] or [2][3], right after the sentence they support.\n"
    "3. Sources may be code: read default values, conditions and return "
    "values directly from it.\n"
    f"4. If the SOURCES do not answer the question, reply exactly: "
    f"{NOT_FOUND_MESSAGE}\n"
    "5. If the question asks where to find something, give the file path "
    "shown in that source's header.\n"
    "6. Be direct and concise: a few sentences, no preamble."
)

THINK_BLOCK = re.compile(r"<think>.*?</think>", flags=re.DOTALL)


def is_not_found(text: str) -> bool:
    """Check whether an answer means "no answer in the sources".

    Single source of truth for the CLI, the web interface and the
    Generator's own normalisation (English and Spanish phrasings).

    Args:
        text: Generated answer text.

    Returns:
        True if the text matches any NOT_FOUND_PATTERNS entry.
    """
    text_lower = text.lower()
    return any(re.search(p, text_lower) for p in NOT_FOUND_PATTERNS)


def build_messages(question: str, sources: list[str],
                   language: str,
                   extra_rules: str = "") -> list[dict[str, str]]:
    """Chat messages for a grounded answer.

    Args:
        question: The user's question.
        sources: Context blocks, numbered [1]..[n] in this order.
        language: 'es' or 'en'; the answer is requested in it.
        extra_rules: The domain's own rules (rag.toml prompt_rules),
            appended to the system prompt; empty for none.

    Returns:
        System and user messages for the chat template.
    """
    numbered = "\n\n".join(
        f"[{i}] {block}" for i, block in enumerate(sources, 1)
    )
    name = LANGUAGE_NAMES.get(language, "the language of the question")
    user = (
        f"SOURCES:\n{numbered}\n\n"
        f"QUESTION: {question}\n\n"
        f"Answer in {name}, citing the sources by number."
    )
    system = SYSTEM_PROMPT
    if extra_rules.strip():
        system += "\n" + extra_rules.strip()
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def not_found_for(question: str) -> str:
    """The generic "not found" answer in the question's language."""
    return NOT_FOUND_MESSAGES.get(detect_language(question),
                                  NOT_FOUND_MESSAGE)


def clean_output(text: str) -> str:
    """Remove reasoning traces, cut a generation loop where it starts
    (src/rag/loops.py) and normalise "not found" answers."""
    text = THINK_BLOCK.sub("", text)
    if "</think>" in text:
        # A reasoning trace without its opening tag: keep what follows.
        text = text.rsplit("</think>", 1)[1]
    text = cut_loop(text.strip())
    if is_not_found(text):
        return NOT_FOUND_MESSAGE
    return text


class Generator:
    """Loads the configured LLM (Qwen/Qwen3-0.6B by default) through
    llm_sdk and generates grounded answers via greedy decoding.

    Uses the model's official chat template with thinking disabled,
    numbered sources cited as [n], and an explicit answer language
    (detected from the question). The context is budgeted in tokens,
    so the question is never truncated.

    Usage:
        generator = Generator()
        answer = generator.answer_with_text(
            "How does PagedAttention work?", context_blocks
        )

    Attributes:
        model: Loaded Small_LLM_Model instance.
        max_new_tokens: Maximum tokens to generate per answer.
        max_input_tokens: Token budget for the whole prompt.
    """

    def __init__(self, config: GenerationConfig | None = None) -> None:
        """Load the LLM. The first run downloads its weights.

        Args:
            config: Model and token limits (defaults to the base,
                Qwen/Qwen3-0.6B with 150 new tokens).
        """
        config = config or GenerationConfig()
        self.model_name = config.model
        print(f"Loading {self.model_name}...")
        self.model = Small_LLM_Model(
            model_name=self.model_name,
            trust_remote_code=config.trust_remote_code,
        )
        self.max_new_tokens = config.max_new_tokens
        self.max_input_tokens = config.max_input_tokens
        self.eos_token_ids = self.stop_token_ids()
        # Set to stop the generation in progress (the web's Stop button
        # or a closed tab); the API gives each request its own Event.
        # Never set elsewhere, so answers and benchmarks are unchanged.
        self.cancel = Event()
        print("Model loaded.")

    def stop_token_ids(self) -> list[int]:
        """Tokens that end an answer for this model.

        Qwen ends turns with <|im_end|>; other families use their own
        end-of-turn token, declared in the model's generation config.
        """
        ids: set[int] = set()
        declared = getattr(
            self.model._model.generation_config, "eos_token_id", None
        )
        if isinstance(declared, int):
            ids.add(declared)
        elif declared:
            ids.update(declared)
        if self.tokenizer.eos_token_id is not None:
            ids.add(self.tokenizer.eos_token_id)
        end_of_turn = self.tokenizer.convert_tokens_to_ids("<|im_end|>")
        unknown = self.tokenizer.unk_token_id
        if isinstance(end_of_turn, int) and end_of_turn != unknown:
            ids.add(end_of_turn)
        return sorted(ids)

    @property
    def tokenizer(self) -> Any:
        """Tokenizer of the loaded model (from the SDK)."""
        return self.model._tokenizer

    def answer_with_text(self, question: str,
                         context_blocks: list[str],
                         extra_rules: str = "",
                         language: Optional[str] = None) -> str:
        """Generate a grounded answer from pre-built context blocks.

        Args:
            question: The natural-language question.
            context_blocks: Context strings, one per source, in the
                order they are numbered and shown to the user.
            extra_rules: Domain rules added to the system prompt.
            language: Answer language ('es', 'en'); detected from the
                question when None.

        Returns:
            A concise answer citing its sources as [n], or
            NOT_FOUND_MESSAGE.
        """
        if not question or not question.strip():
            return "No question provided."
        if not context_blocks:
            return "No relevant sources found."
        return clean_output(
            self.greedy_decode(self.build_prompt(
                question, context_blocks, extra_rules, language
            ))
        )

    def stream_answer(self, question: str,
                      context_blocks: list[str],
                      extra_rules: str = "",
                      language: Optional[str] = None) -> Iterator[str]:
        """Like answer_with_text(), but yields the text as it is
        generated (same prompt and decoding).

        The pieces are raw model output: callers that need the final,
        normalised answer pass the joined text to clean_output().

        Args:
            question: The natural-language question.
            context_blocks: Context strings, one per source.
            extra_rules: Domain rules added to the system prompt.
            language: Answer language; detected when None.

        Yields:
            Successive pieces of the answer.
        """
        if not question or not question.strip() or not context_blocks:
            yield self.answer_with_text(question, context_blocks,
                                        extra_rules, language)
            return

        from transformers import TextIteratorStreamer

        streamer = TextIteratorStreamer(
            self.tokenizer, skip_prompt=True, skip_special_tokens=True
        )
        kwargs = self.generate_kwargs(
            self.build_prompt(question, context_blocks, extra_rules,
                              language)
        )
        worker = Thread(target=self.generate, kwargs={
            **kwargs, "streamer": streamer,
        })
        worker.start()
        for piece in streamer:
            if piece:
                yield piece
        worker.join()

    def build_prompt(self, question: str, context_blocks: list[str],
                     extra_rules: str = "",
                     language: Optional[str] = None) -> str:
        """Chat-formatted prompt: numbered sources trimmed to the token
        budget, answer language taken from the question, plus the
        domain's own rules when given."""
        language = language or detect_language(question)
        sources = self.fit_sources(question, context_blocks, language,
                                   extra_rules)
        return str(self.tokenizer.apply_chat_template(
            build_messages(question, sources, language, extra_rules),
            tokenize=False, add_generation_prompt=True,
            enable_thinking=False,
        ))

    def count_tokens(self, text: str) -> int:
        """Number of tokens of a text for the loaded model."""
        return len(self.tokenizer.encode(text, add_special_tokens=False))

    def fit_sources(self, question: str, blocks: list[str],
                    language: str, extra_rules: str = "") -> list[str]:
        """Trim sources so the full prompt fits max_input_tokens.

        Sources keep their order (and numbering); the last one that does
        not fit entirely is cut, and the rest are dropped. The question
        and instructions are never truncated.

        Returns:
            The sources that fit, possibly with the last one shortened.
        """
        fixed = self.count_tokens(
            self.tokenizer.apply_chat_template(
                build_messages(question, [], language, extra_rules),
                tokenize=False,
                add_generation_prompt=True, enable_thinking=False,
            )
        )
        budget = self.max_input_tokens - fixed
        fitted: list[str] = []
        for block in blocks:
            cost = self.count_tokens(block) + 4
            if cost <= budget:
                fitted.append(block)
                budget -= cost
                continue
            if budget > 64:
                ids = self.tokenizer.encode(block, add_special_tokens=False)
                fitted.append(self.tokenizer.decode(ids[:budget - 8]))
            break
        return fitted or blocks[:1]

    def greedy_decode(self, prompt: str) -> str:
        """Generate text using HuggingFace's generate() with KV-cache.

        Args:
            prompt: The full prompt string to continue from.

        Returns:
            Generated text (new tokens only, prompt excluded).
        """
        kwargs = self.generate_kwargs(prompt)
        output_ids = self.generate(**kwargs)
        new_ids = output_ids[0][kwargs["input_ids"].shape[1]:]
        return str(self.model.decode(new_ids)).strip()

    def complete(self, prompt: str, max_new_tokens: int) -> str:
        """Raw greedy continuation of a prompt, special tokens kept.

        For the agent: tool calls come wrapped in markers such as
        <tool_call> or <|tool_call|>, which decode() would drop. Only
        the end-of-turn tokens are removed.
        """
        kwargs = self.generate_kwargs(prompt)
        kwargs["max_new_tokens"] = max_new_tokens
        output_ids = self.generate(**kwargs)
        new_ids = [int(i) for i in output_ids[0][
            kwargs["input_ids"].shape[1]:
        ] if int(i) not in self.eos_token_ids]
        text = self.tokenizer.decode(new_ids, skip_special_tokens=False)
        return str(THINK_BLOCK.sub("", text)).strip()

    def generate_kwargs(self, prompt: str) -> dict[str, Any]:
        """Arguments for greedy generation of `prompt`."""
        inputs = self.tokenizer(prompt, return_tensors="pt").to(
            self.model._device
        )
        return {
            **inputs,
            "max_new_tokens": self.max_new_tokens,
            "do_sample": False,
            "pad_token_id": self.tokenizer.pad_token_id,
            "eos_token_id": self.eos_token_ids,
            "stopping_criteria": self.stopping_criteria(
                inputs["input_ids"].shape[1]
            ),
        }

    def stopping_criteria(self, prompt_length: int) -> Any:
        """Stop generating as soon as `cancel` is set (checked per token,
        read when it runs, so the API can swap the Event per request), or
        when the answer falls into a loop (checked each time a line or a
        sentence ends; clean_output then cuts the repeated part)."""
        from transformers import StoppingCriteria, StoppingCriteriaList

        generator = self

        class Looping(StoppingCriteria):
            def __call__(self, input_ids: Any, scores: Any,
                         **kwargs: Any) -> Any:
                stop = False
                last = generator.tokenizer.decode(input_ids[0, -1:])
                if BOUNDARY.search(last):
                    text = generator.tokenizer.decode(
                        input_ids[0, prompt_length:],
                        skip_special_tokens=True)
                    stop = find_loop(text) is not None
                return torch.full((input_ids.shape[0],), stop,
                                  dtype=torch.bool, device=input_ids.device)

        class Cancelled(StoppingCriteria):
            def __call__(self, input_ids: Any, scores: Any,
                         **kwargs: Any) -> Any:
                stop = generator.cancel.is_set()
                return torch.full((input_ids.shape[0],), stop,
                                  dtype=torch.bool, device=input_ids.device)

        return StoppingCriteriaList([Cancelled(), Looping()])

    def generate(self, **kwargs: Any) -> Any:
        """Run the model's generate() without gradients."""
        # The SDK types the model as PreTrainedModel, which does not
        # expose generate() to type checkers; every causal LM has it.
        causal_lm: Any = self.model._model
        with torch.no_grad():
            return causal_lm.generate(**kwargs)
