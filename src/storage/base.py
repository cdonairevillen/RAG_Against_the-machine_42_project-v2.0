from typing import Protocol

from src.ingestion.chunk import Chunk


class ChunkStore(Protocol):
    """Persistence for a domain's parent and child chunks.

    Implementations hold one isolated collection per domain, so a domain
    can be re-indexed without touching the others.
    """

    def replace(self, domain: str, chunks: list[Chunk]) -> None:
        """Drop everything stored for a domain and write `chunks`."""
        ...

    def load(self, domain: str) -> list[Chunk]:
        """Return every chunk of a domain, sorted by (level, ordinal)."""
        ...

    def get(self, domain: str, ids: list[str]) -> list[Chunk]:
        """Return the chunks with the given ids (unknown ids skipped)."""
        ...

    def count(self, domain: str) -> int:
        """Return how many chunks are stored for a domain (0 if none)."""
        ...
