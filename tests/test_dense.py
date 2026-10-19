import numpy as np
from qdrant_client import QdrantClient

from src.config import QdrantConfig
from src.embeddings import PRESETS, document_text, vector_name
from src.ingestion.chunk import CHILD, PARENT, Chunk
from src.models import MinimalSource
from src.retriever import Retriever, rrf_merge
from src.storage.qdrant_store import QdrantChunkStore


def source(name: str) -> MinimalSource:
    return MinimalSource(file_path=f"{name}.py", first_character_index=0,
                         last_character_index=10)


def test_rrf_merge_rewards_sources_in_several_lists() -> None:
    bm25 = [source("A"), source("B"), source("C")]
    dense = [source("C"), source("D")]

    merged = [s.file_path for s in rrf_merge([bm25, dense])]

    # C is 3rd and 1st: its two contributions beat A's single 1st place.
    assert merged[0] == "C.py"
    assert set(merged) == {"A.py", "B.py", "C.py", "D.py"}


def test_vector_name_and_presets() -> None:
    assert vector_name("intfloat/multilingual-e5-small") == (
        "intfloat_multilingual_e5_small"
    )
    assert PRESETS["intfloat/multilingual-e5-small"].query_prefix == "query: "
    assert PRESETS["Qwen/Qwen3-Embedding-0.6B"].query_prompt_name == "query"
    assert document_text("a.py", "body") == "a.py\nbody"


class FakeEmbedder:
    def __init__(self, vector: list[float]) -> None:
        self.vector = vector

    def encode_query(self, query: str) -> list[float]:
        return self.vector


def test_dense_search_returns_parents_of_nearest_children() -> None:
    store = QdrantChunkStore(QdrantClient(":memory:"), QdrantConfig())
    parents = [
        Chunk(f"parent {i}", f"f{i}.py", 0, 100, "code", id=pid,
              domain="demo", level=PARENT, ordinal=i)
        for i, pid in enumerate([
            "00000000-0000-0000-0000-000000000001",
            "00000000-0000-0000-0000-000000000002",
        ])
    ]
    children = [
        Chunk(f"child {i}", f"f{i}.py", 0, 50, "code",
              parent_id=parents[i].id,
              id=f"00000000-0000-0000-0001-00000000000{i}",
              domain="demo", level=CHILD, ordinal=i)
        for i in range(2)
    ]
    vectors = {
        children[0].id: np.array([1.0, 0.0], dtype=np.float32),
        children[1].id: np.array([0.0, 1.0], dtype=np.float32),
    }
    store.replace("demo", parents + children, vector_name="fake",
                  vectors=vectors)
    retriever = Retriever(chunks=children, bm25=None)  # type: ignore[arg-type]
    retriever.set_children(children)
    retriever.set_parents(parents)
    retriever.store = store
    retriever.domain = "demo"
    retriever.dense_name = "fake"
    retriever.embedder = FakeEmbedder([0.1, 0.9])

    found = retriever.dense_parents("anything", "code")

    assert [s.file_path for s in found] == ["f1.py", "f0.py"]
    assert retriever.dense_parents("anything", "doc") == []


def test_dense_is_off_without_embedder() -> None:
    retriever = Retriever(chunks=[], bm25=None)  # type: ignore[arg-type]

    assert retriever.dense_parents("q", "code") == []
