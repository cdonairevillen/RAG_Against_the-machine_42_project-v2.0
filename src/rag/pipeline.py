import time
from dataclasses import dataclass, field
from typing import Callable, Optional, Sequence

from src.rag.generator import (
    Generator, clean_output, is_not_found, not_found_for,
)
from src.config import get_config
from src.rag.domain_rules import DomainRules
from src.models import MinimalSource
from src.rag.retriever import Retriever
from src.rag.router import DomainRouter


@dataclass
class RagAnswer:
    """Result of answering one question.

    Attributes:
        question: The question asked.
        text: Final answer (citing sources as [n]), with private data
            masked, or the domain's "not found" message.
        sources: Sources given to the generator, in [n] order. Empty
            when the relevance gate judged the question out of domain.
        not_found: Whether the answer means "not found".
        seconds_retrieval: Time spent retrieving.
        seconds_generation: Time spent generating.
    """

    question: str
    text: str
    sources: list[MinimalSource] = field(default_factory=list)
    not_found: bool = False
    seconds_retrieval: float = 0.0
    seconds_generation: float = 0.0


def build_context_blocks(sources: list[MinimalSource],
                         parent_map: dict,
                         rules: Optional[DomainRules] = None) -> list[str]:
    """Context blocks for the generator, one per source, in order.

    Args:
        sources: Retrieved parent sources.
        parent_map: (file_path, first_char) -> parent Chunk, as returned
            by Retriever.get_parent_chunk_map().
        rules: When given, each block has its domain's private data
            masked, so the LLM never reads it.

    Returns:
        '--- file: path ---\\ntext' blocks (unknown sources skipped).
    """
    blocks: list[str] = []
    for src in sources:
        parent = parent_map.get((src.file_path, src.first_character_index))
        if parent:
            text = rules.redact(parent.text, parent.domain) if rules \
                else parent.text
            blocks.append(f"--- file: {src.file_path} ---\n{text}")
    return blocks


class RagPipeline:
    """The single question-answering flow, shared by the CLI, the web
    interface and the generation benchmark.

    retrieve (search_for_generation: search_smart + relevance gate) ->
    context blocks -> generate (optionally streamed). The retriever is
    one domain's Retriever or a DomainRouter over several.
    """

    def __init__(self, retriever: Retriever | DomainRouter,
                 generator: Generator,
                 rules: Optional[DomainRules] = None) -> None:
        self.retriever = retriever
        self.generator = generator
        # Private data and "not found" message of each domain (rag.toml).
        self.rules = rules or DomainRules(get_config())

    def answered_domain(self) -> Optional[str]:
        """Domain the last question was answered from (or closest to,
        when the gate rejected it)."""
        if isinstance(self.retriever, DomainRouter):
            route = self.retriever.last_route
            return route[0][0] if route else None
        return self.retriever.domain or None

    def not_found(self, question: str) -> str:
        """The "not found" answer of the domain the question went to."""
        return self.rules.not_found_message(
            self.answered_domain(), question
        ) or not_found_for(question)

    def answer(self, question: str, k: int = 5,
               on_piece: Optional[Callable[[str], None]] = None,
               domains: Optional[str | Sequence[str]] = None) -> RagAnswer:
        """Answer a question from the indexed knowledge base.

        Args:
            question: The user's question.
            k: Sources passed to the generator.
            on_piece: When given, called with each piece of the answer as
                it is generated (streaming); the returned RagAnswer still
                holds the final, normalised text.
            domains: Domain filter for a DomainRouter (ignored by a
                single-domain Retriever).

        Returns:
            The answer, its sources and timings.
        """
        start = time.perf_counter()
        if isinstance(self.retriever, DomainRouter):
            sources = self.retriever.search_for_generation(
                question, k=k, domains=domains
            )
        else:
            sources = self.retriever.search_for_generation(question, k=k)
        seconds_retrieval = time.perf_counter() - start
        blocks = build_context_blocks(
            sources, self.retriever.get_parent_chunk_map(), self.rules
        )
        if not blocks:
            message = self.not_found(question)
            if on_piece:
                on_piece(message)
            return RagAnswer(question, message, [], True,
                             seconds_retrieval)

        domain = self.answered_domain()
        rules = self.rules.prompt_rules(
            domain, getattr(self.generator, "model_name", ""))
        style = self.rules.style_rule(domain)
        own = {"style_rule": style} if style is not None else {}
        start = time.perf_counter()
        if on_piece:
            pieces = []
            for piece in self.generator.stream_answer(question, blocks,
                                                      rules, **own):
                pieces.append(piece)
                on_piece(piece)
            text = clean_output("".join(pieces))
        else:
            text = self.generator.answer_with_text(question, blocks, rules,
                                                   **own)
        not_found = is_not_found(text)
        text = self.not_found(question) if not_found \
            else self.rules.redact_all(text)
        return RagAnswer(
            question, text, sources, not_found, seconds_retrieval,
            time.perf_counter() - start,
        )
