import time
from dataclasses import dataclass, field
from typing import Callable, Optional

from src.generator import (
    NOT_FOUND_MESSAGE, Generator, clean_output, is_not_found,
)
from src.models import MinimalSource
from src.retriever import Retriever


@dataclass
class RagAnswer:
    """Result of answering one question.

    Attributes:
        question: The question asked.
        text: Final answer (citing sources as [n]) or NOT_FOUND_MESSAGE.
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
                         parent_map: dict) -> list[str]:
    """Context blocks for the generator, one per source, in order.

    Args:
        sources: Retrieved parent sources.
        parent_map: (file_path, first_char) -> parent Chunk, as returned
            by Retriever.get_parent_chunk_map().

    Returns:
        '--- file: path ---\\ntext' blocks (unknown sources skipped).
    """
    blocks: list[str] = []
    for src in sources:
        parent = parent_map.get((src.file_path, src.first_character_index))
        if parent:
            blocks.append(f"--- file: {src.file_path} ---\n{parent.text}")
    return blocks


class RagPipeline:
    """The single question-answering flow, shared by the CLI, the web
    interface and the generation benchmark.

    retrieve (search_for_generation: search_smart + relevance gate) ->
    context blocks -> generate (optionally streamed).
    """

    def __init__(self, retriever: Retriever, generator: Generator) -> None:
        self.retriever = retriever
        self.generator = generator

    def answer(self, question: str, k: int = 5,
               on_piece: Optional[Callable[[str], None]] = None
               ) -> RagAnswer:
        """Answer a question from the indexed knowledge base.

        Args:
            question: The user's question.
            k: Sources passed to the generator.
            on_piece: When given, called with each piece of the answer as
                it is generated (streaming); the returned RagAnswer still
                holds the final, normalised text.

        Returns:
            The answer, its sources and timings.
        """
        start = time.perf_counter()
        sources = self.retriever.search_for_generation(question, k=k)
        seconds_retrieval = time.perf_counter() - start
        blocks = build_context_blocks(
            sources, self.retriever.get_parent_chunk_map()
        )
        if not blocks:
            if on_piece:
                on_piece(NOT_FOUND_MESSAGE)
            return RagAnswer(question, NOT_FOUND_MESSAGE, [], True,
                             seconds_retrieval)

        start = time.perf_counter()
        if on_piece:
            pieces = []
            for piece in self.generator.stream_answer(question, blocks):
                pieces.append(piece)
                on_piece(piece)
            text = clean_output("".join(pieces))
        else:
            text = self.generator.answer_with_text(question, blocks)
        return RagAnswer(
            question, text, sources, is_not_found(text), seconds_retrieval,
            time.perf_counter() - start,
        )
