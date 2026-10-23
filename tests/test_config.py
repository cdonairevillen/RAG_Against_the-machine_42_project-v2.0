from pathlib import Path

import pytest

from src.config import load_config

CONFIG = """
[qdrant]
url = "http://qdrant:6333"

[chunking]
code_chunk_size = 1500

[sources.demo]
root = "data/raw/demo"
include = [".py", ".md"]
code_extensions = [".py"]
default_chunker = "size"

[sources.demo.chunkers]
".py" = "python_ast"
"""


def write_config(tmp_path: Path) -> str:
    path = tmp_path / "rag.toml"
    path.write_text(CONFIG, encoding="utf-8")
    return str(path)


def test_loads_file_and_keeps_defaults(tmp_path: Path) -> None:
    config = load_config(write_config(tmp_path), environ={})

    assert config.qdrant.url == "http://qdrant:6333"
    assert config.qdrant.collection("demo") == "rag_demo"
    assert config.chunking.code_chunk_size == 1500
    assert config.chunking.doc_chunk_size == 2000


def test_source_maps_extensions(tmp_path: Path) -> None:
    source = load_config(write_config(tmp_path), environ={}).source("demo")

    assert source.chunker_for(".py") == "python_ast"
    assert source.chunker_for(".md") == "size"
    assert source.chunk_type_for(".py") == "code"
    assert source.chunk_type_for(".md") == "doc"


def test_environment_overrides_scalars(tmp_path: Path) -> None:
    config = load_config(write_config(tmp_path), environ={
        "RAG_QDRANT_URL": "http://elsewhere:6333",
        "RAG_CHUNKING_DOC_CHILD_SIZE": "300",
    })

    assert config.qdrant.url == "http://elsewhere:6333"
    assert config.chunking.doc_child_size == 300


def test_unknown_source_is_reported(tmp_path: Path) -> None:
    config = load_config(write_config(tmp_path), environ={})

    with pytest.raises(KeyError, match="demo"):
        config.source("missing")


PROFILES = CONFIG + """
[profiles.big.retrieval]
reranker_model = "big-reranker"

[profiles.light.embeddings]
model = "small-embedder"
"""


def write_profiles(tmp_path: Path) -> str:
    path = tmp_path / "rag.toml"
    path.write_text(PROFILES, encoding="utf-8")
    return str(path)


def test_without_profile_the_base_is_used(tmp_path: Path) -> None:
    config = load_config(write_profiles(tmp_path), environ={})

    assert config.profile == "default"
    assert config.available_profiles == ["default", "big", "light"]
    assert config.retrieval.reranker_model != "big-reranker"


def test_profile_overrides_only_what_it_declares(tmp_path: Path) -> None:
    config = load_config(write_profiles(tmp_path), environ={},
                         profile="big")

    assert config.profile == "big"
    assert config.retrieval.reranker_model == "big-reranker"
    assert config.qdrant.url == "http://qdrant:6333"
    assert config.chunking.code_chunk_size == 1500


def test_profile_from_environment_and_env_wins(tmp_path: Path) -> None:
    config = load_config(write_profiles(tmp_path), environ={
        "RAG_PROFILE": "light",
        "RAG_EMBEDDINGS_MODEL": "from-env",
    })

    assert config.profile == "light"
    assert config.embeddings.model == "from-env"


def test_unknown_profile_is_reported(tmp_path: Path) -> None:
    with pytest.raises(KeyError, match="big"):
        load_config(write_profiles(tmp_path), environ={}, profile="nope")


def test_missing_file_gives_defaults(tmp_path: Path) -> None:
    config = load_config(str(tmp_path / "nope.toml"), environ={})

    assert config.qdrant.url == "http://localhost:6333"
    assert config.sources == {}


def test_source_gate_threshold_defaults_to_global(tmp_path: Path) -> None:
    config = load_config(write_config(tmp_path), environ={})
    assert config.source("demo").relevance_threshold is None

    path = tmp_path / "rag.toml"
    path.write_text(CONFIG.replace(
        'default_chunker = "size"',
        'default_chunker = "size"\nrelevance_threshold = -3.5',
    ), encoding="utf-8")
    assert load_config(str(path), environ={}).source(
        "demo").relevance_threshold == -3.5
