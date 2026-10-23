from pathlib import Path

import pytest
from qdrant_client import QdrantClient

from src.config import ChunkingConfig, PathsConfig, QdrantConfig, \
    RagConfig, SourceConfig
from src.rag.ingestion.chunk import CHILD, PARENT, Chunk
from src.rag.ingestion.pipeline import Ingester
from src.rag.ingestion.tokens import corpus_part_types
from src.rag.retriever import Retriever
from src.rag.storage.qdrant_store import QdrantChunkStore

PY_FILE = '''def load_lora_adapter(name, path):
    """Load a LoRA adapter at runtime."""
    return name, path


class PagedAttention:
    def forward(self, query):
        return query
'''

MD_FILE = (
    "# Serving\n\n"
    "Start the OpenAI compatible server with vllm serve and pass the "
    "model name. The server exposes chat and completion endpoints.\n\n"
    "## LoRA\n\n"
    "Use the /v1/load_lora_adapter endpoint to load adapters "
    "dynamically while the server is running.\n"
)


@pytest.fixture
def store() -> QdrantChunkStore:
    return QdrantChunkStore(QdrantClient(":memory:"), QdrantConfig())


def make_chunk(level: str, ordinal: int, symbols: str = "") -> Chunk:
    return Chunk(
        text=f"{level} {ordinal}", file_path="f.py",
        first_character_index=ordinal * 10,
        last_character_index=ordinal * 10 + 10, chunk_type="code",
        symbols=symbols,
        id=f"00000000-0000-0000-0000-{level == PARENT:01d}{ordinal:011d}",
        domain="demo", level=level, ordinal=ordinal,
    )


def test_replace_and_load_round_trip(store: QdrantChunkStore) -> None:
    chunks = [make_chunk(CHILD, i) for i in (2, 0, 1)] + [
        make_chunk(PARENT, 0, symbols="forward")
    ]
    store.replace("demo", chunks)

    loaded = store.load("demo")

    assert [(c.level, c.ordinal) for c in loaded] == [
        (CHILD, 0), (CHILD, 1), (CHILD, 2), (PARENT, 0),
    ]
    assert loaded[3].symbols == "forward"
    assert store.count("demo") == 4


def test_replace_drops_previous_content(store: QdrantChunkStore) -> None:
    store.replace("demo", [make_chunk(CHILD, i) for i in range(5)])
    store.replace("demo", [make_chunk(CHILD, 0)])

    assert store.count("demo") == 1


def test_get_returns_requested_order(store: QdrantChunkStore) -> None:
    chunks = [make_chunk(CHILD, i) for i in range(3)]
    store.replace("demo", chunks)

    unknown = "ffffffff-0000-0000-0000-000000000000"
    got = store.get("demo", [chunks[2].id, unknown, chunks[0].id])

    assert [c.ordinal for c in got] == [2, 0]


def test_unknown_domain_is_empty(store: QdrantChunkStore) -> None:
    assert store.load("nothing") == []
    assert store.count("nothing") == 0


def test_end_to_end_index_and_search(tmp_path: Path,
                                     store: QdrantChunkStore) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "lora.py").write_text(PY_FILE, encoding="utf-8")
    (root / "serving.md").write_text(MD_FILE, encoding="utf-8")
    source = SourceConfig(
        root=str(root), include=[".py", ".md"], code_extensions=[".py"],
        chunkers={".py": "python_ast", ".md": "markdown_headers_packed"},
    )
    config = RagConfig(
        paths=PathsConfig(processed_dir=str(tmp_path / "processed")),
        chunking=ChunkingConfig(),
        sources={"demo": source},
    )

    ingester = Ingester(
        "demo", source, config.chunking,
        part_types=corpus_part_types(config.retrieval.code_aware_tokens),
    )
    ingester.build()
    ingester.save_bm25(config.paths.processed_dir)
    store.replace("demo", ingester.all_chunks())
    retriever = Retriever.from_store("demo", config=config, store=store)

    results = retriever.search_smart("How do I load a LoRA adapter "
                                     "with the server endpoint?", k=3)

    assert results
    assert all(r.file_path.endswith((".py", ".md")) for r in results)
    assert any("serving.md" in r.file_path for r in results)
    # Without its own threshold the source uses the global gate.
    assert retriever.settings.relevance_threshold == 0.0
    source.relevance_threshold = -3.5
    gated = Retriever.from_store("demo", config=config, store=store)
    assert gated.settings.relevance_threshold == -3.5
    assert config.retrieval.relevance_threshold == 0.0


def test_store_and_index_mismatch_is_detected(
        tmp_path: Path, store: QdrantChunkStore) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "lora.py").write_text(PY_FILE, encoding="utf-8")
    source = SourceConfig(root=str(root), include=[".py"],
                          code_extensions=[".py"],
                          chunkers={".py": "python_ast"})
    config = RagConfig(
        paths=PathsConfig(processed_dir=str(tmp_path / "processed")),
        sources={"demo": source},
    )
    ingester = Ingester(
        "demo", source, config.chunking,
        part_types=corpus_part_types(config.retrieval.code_aware_tokens),
    )
    ingester.build()
    ingester.save_bm25(config.paths.processed_dir)
    store.replace("demo", ingester.all_chunks()[:-1])

    with pytest.raises(RuntimeError, match="make index"):
        Retriever.from_store("demo", config=config, store=store)
