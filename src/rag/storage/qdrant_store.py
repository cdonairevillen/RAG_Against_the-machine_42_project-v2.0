from typing import Any, Iterator, Optional

import numpy as np

from qdrant_client import QdrantClient, models
from tqdm import tqdm

from src.config import QdrantConfig
from src.rag.ingestion.chunk import Chunk

# Payload fields that filters run on (domain-wide scans, parent lookups).
INDEXED_FIELDS = ("level", "chunk_type", "file_path", "parent_id")
SCROLL_PAGE = 2048


def chunk_to_payload(chunk: Chunk) -> dict[str, Any]:
    """Return the Qdrant payload for a chunk (everything but its id)."""
    payload = chunk.to_dict()
    payload.pop("id")
    return payload


def point_to_chunk(point_id: Any, payload: dict[str, Any] | None) -> Chunk:
    """Rebuild a Chunk from a Qdrant point id and payload."""
    return Chunk.from_dict({**(payload or {}), "id": str(point_id)})


class QdrantChunkStore:
    """ChunkStore backed by a Qdrant server, one collection per domain.

    Qdrant is the source of truth for chunk records and their metadata.
    When dense retrieval is enabled, child points also carry a named
    vector (one name per embedding model).
    """

    def __init__(self, client: QdrantClient, config: QdrantConfig) -> None:
        self.client = client
        self.config = config

    @classmethod
    def from_config(cls, config: QdrantConfig) -> "QdrantChunkStore":
        """Connect to the server configured in rag.toml.

        Raises:
            ConnectionError: If the server cannot be reached.
        """
        client = QdrantClient(url=config.url, timeout=120)
        try:
            client.get_collections()
        except Exception as exc:
            raise ConnectionError(
                f"Qdrant is not reachable at {config.url} ({exc}). "
                f"Start it with 'make db-up'."
            ) from exc
        return cls(client, config)

    def replace(self, domain: str, chunks: list[Chunk],
                vector_name: Optional[str] = None,
                vectors: Optional[dict[str, np.ndarray]] = None) -> None:
        """Recreate the domain's collection and upload `chunks`.

        Args:
            domain: Domain whose collection is replaced.
            chunks: Parent and child chunks to store.
            vector_name: Named dense vector to create, if any.
            vectors: Chunk id -> embedding, for the chunks that have one
                (children). Points without an entry carry no vector.
        """
        name = self.config.collection(domain)
        if self.client.collection_exists(name):
            self.client.delete_collection(name)
        vectors = vectors or {}
        vectors_config: dict[str, models.VectorParams] = {}
        if vector_name and vectors:
            size = len(next(iter(vectors.values())))
            vectors_config[vector_name] = models.VectorParams(
                size=size, distance=models.Distance.COSINE
            )
        self.client.create_collection(name, vectors_config=vectors_config)
        for field_name in INDEXED_FIELDS:
            self.client.create_payload_index(
                name, field_name, models.PayloadSchemaType.KEYWORD
            )

        batch = self.config.batch_size
        for start in tqdm(range(0, len(chunks), batch),
                          desc=f"Storing {domain} in Qdrant"):
            self.client.upsert(
                name,
                points=[
                    models.PointStruct(
                        id=c.id,
                        vector=(
                            {vector_name: vectors[c.id].tolist()}
                            if vector_name and c.id in vectors else {}
                        ),
                        payload=chunk_to_payload(c),
                    )
                    for c in chunks[start:start + batch]
                ],
                wait=True,
            )

    def iter_points(self, domain: str) -> Iterator[Chunk]:
        """Yield every chunk of a domain, in no particular order."""
        name = self.config.collection(domain)
        offset = None
        while True:
            points, offset = self.client.scroll(
                name, limit=SCROLL_PAGE, offset=offset,
                with_payload=True, with_vectors=False,
            )
            for point in points:
                yield point_to_chunk(point.id, point.payload)
            if offset is None:
                break

    def load(self, domain: str) -> list[Chunk]:
        """Return every chunk of a domain, sorted by (level, ordinal)."""
        if not self.client.collection_exists(self.config.collection(domain)):
            return []
        chunks = list(self.iter_points(domain))
        chunks.sort(key=lambda c: (c.level, c.ordinal))
        return chunks

    def get(self, domain: str, ids: list[str]) -> list[Chunk]:
        """Return the chunks with the given ids, in the order requested."""
        if not ids:
            return []
        points = self.client.retrieve(
            self.config.collection(domain), ids=ids,
            with_payload=True, with_vectors=False,
        )
        by_id = {str(p.id): point_to_chunk(p.id, p.payload) for p in points}
        return [by_id[i] for i in ids if i in by_id]

    def search_dense(self, domain: str, vector_name: str,
                     query_vector: list[float], limit: int,
                     chunk_type: Optional[str] = None) -> list[int]:
        """Nearest child chunks to a query vector.

        Args:
            domain: Domain to search.
            vector_name: Named vector to search with.
            query_vector: Embedded query.
            limit: Maximum number of results.
            chunk_type: Restrict to 'code' or 'doc' children.

        Returns:
            Ordinals (BM25 rows) of the matching children, best first.
        """
        must: list[models.Condition] = [models.FieldCondition(
            key="level", match=models.MatchValue(value="child")
        )]
        if chunk_type:
            must.append(models.FieldCondition(
                key="chunk_type", match=models.MatchValue(value=chunk_type)
            ))
        result = self.client.query_points(
            self.config.collection(domain), query=query_vector,
            using=vector_name, limit=limit,
            query_filter=models.Filter(must=must),
            with_payload=["ordinal"], with_vectors=False,
        )
        return [int((p.payload or {})["ordinal"]) for p in result.points]

    def count(self, domain: str) -> int:
        """Return how many chunks are stored for a domain."""
        name = self.config.collection(domain)
        if not self.client.collection_exists(name):
            return 0
        return self.client.count(name, exact=True).count
