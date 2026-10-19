from typing import Optional, Protocol

import numpy as np

from src.ingestion.chunk import Chunk


class ChunkStore(Protocol):
    """Persistence for a domain's parent and child chunks.

    Implementations hold one isolated collection per domain, so a domain
    can be re-indexed without touching the others.
    """

    def replace(self, domain: str, chunks: list[Chunk],
                vector_name: Optional[str] = None,
                vectors: Optional[dict[str, np.ndarray]] = None) -> None:
        """Drop everything stored for a domain and write `chunks`,
        optionally with a named dense vector per chunk id."""
        ...

    def load(self, domain: str) -> list[Chunk]:
        """Return every chunk of a domain, sorted by (level, ordinal)."""
        ...

    def get(self, domain: str, ids: list[str]) -> list[Chunk]:
        """Return the chunks with the given ids (unknown ids skipped)."""
        ...

    def search_dense(self, domain: str, vector_name: str,
                     query_vector: list[float], limit: int,
                     chunk_type: Optional[str] = None) -> list[int]:
        """Ordinals of the nearest child chunks to a query vector."""
        ...

    def count(self, domain: str) -> int:
        """Return how many chunks are stored for a domain (0 if none)."""
        ...
