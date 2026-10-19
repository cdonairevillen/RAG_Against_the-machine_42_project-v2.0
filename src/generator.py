import re
from threading import Thread
from typing import Any, Iterator

import torch
from llm_sdk import Small_LLM_Model

from src.config import GenerationConfig
from src.language import LANGUAGE_NAMES, detect_language

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
)

NOT_FOUND_MESSAGE = "Not found in the provided sources."

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
    "5. Be direct and concise: a few sentences, no preamble."
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
                   language: str) -> list[dict[str, str]]:
    """Chat messages for a grounded answer.

    Args:
        question: The user's question.
        sources: Context blocks, numbered [1]..[n] in this order.
        language: 'es' or 'en'; the answer is requested in it.

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
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ]


def clean_output(text: str) -> str:
    """Remove reasoning traces and normalise "not found" answers."""
    text = THINK_BLOCK.sub("", text)
    if "</think>" in text:
        # A reasoning trace without its opening tag: keep what follows.
        text = text.rsplit("</think>", 1)[1]
    text = text.strip()
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
                         context_blocks: list[str]) -> str:
        """Generate a grounded answer from pre-built context blocks.

        Args:
            question: The natural-language question.
            context_blocks: Context strings, one per source, in the
                order they are numbered and shown to the user.

        Returns:
            A concise answer citing its sources as [n], or
            NOT_FOUND_MESSAGE.
        """
        if not question or not question.strip():
            return "No question provided."
        if not context_blocks:
            return "No relevant sources found."
        return clean_output(
            self.greedy_decode(self.build_prompt(question, context_blocks))
        )

    def stream_answer(self, question: str,
                      context_blocks: list[str]) -> Iterator[str]:
        """Like answer_with_text(), but yields the text as it is
        generated (same prompt and decoding).

        The pieces are raw model output: callers that need the final,
        normalised answer pass the joined text to clean_output().

        Args:
            question: The natural-language question.
            context_blocks: Context strings, one per source.

        Yields:
            Successive pieces of the answer.
        """
        if not question or not question.strip() or not context_blocks:
            yield self.answer_with_text(question, context_blocks)
            return

        from transformers import TextIteratorStreamer

        streamer = TextIteratorStreamer(
            self.tokenizer, skip_prompt=True, skip_special_tokens=True
        )
        kwargs = self.generate_kwargs(
            self.build_prompt(question, context_blocks)
        )
        worker = Thread(target=self.generate, kwargs={
            **kwargs, "streamer": streamer,
        })
        worker.start()
        for piece in streamer:
            if piece:
                yield piece
        worker.join()

    def build_prompt(self, question: str, context_blocks: list[str]) -> str:
        """Chat-formatted prompt: numbered sources trimmed to the token
        budget, answer language taken from the question."""
        language = detect_language(question)
        sources = self.fit_sources(question, context_blocks, language)
        return str(self.tokenizer.apply_chat_template(
            build_messages(question, sources, language),
            tokenize=False, add_generation_prompt=True,
            enable_thinking=False,
        ))

    def count_tokens(self, text: str) -> int:
        """Number of tokens of a text for the loaded model."""
        return len(self.tokenizer.encode(text, add_special_tokens=False))

    def fit_sources(self, question: str, blocks: list[str],
                    language: str) -> list[str]:
        """Trim sources so the full prompt fits max_input_tokens.

        Sources keep their order (and numbering); the last one that does
        not fit entirely is cut, and the rest are dropped. The question
        and instructions are never truncated.

        Returns:
            The sources that fit, possibly with the last one shortened.
        """
        fixed = self.count_tokens(
            self.tokenizer.apply_chat_template(
                build_messages(question, [], language), tokenize=False,
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
        }

    def generate(self, **kwargs: Any) -> Any:
        """Run the model's generate() without gradients."""
        # The SDK types the model as PreTrainedModel, which does not
        # expose generate() to type checkers; every causal LM has it.
        causal_lm: Any = self.model._model
        with torch.no_grad():
            return causal_lm.generate(**kwargs)
