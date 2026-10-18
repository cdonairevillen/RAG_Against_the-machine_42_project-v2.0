import os
import sys
from functools import lru_cache
from typing import Any

from pydantic import BaseModel, Field

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - exercised only on Python 3.10
    import tomli as tomllib

CONFIG_FILE = "rag.toml"
ENV_PREFIX = "RAG_"


class QdrantConfig(BaseModel):
    """Connection settings for the Qdrant server."""

    url: str = "http://localhost:6333"
    collection_prefix: str = "rag_"
    batch_size: int = 512

    def collection(self, domain: str) -> str:
        """Return the collection name holding a domain's chunks."""
        return f"{self.collection_prefix}{domain}"


class PathsConfig(BaseModel):
    """Local directories used by the pipeline."""

    processed_dir: str = "data/processed"


class ChunkingConfig(BaseModel):
    """Parent and child chunk sizes, in characters."""

    code_chunk_size: int = 2000
    doc_chunk_size: int = 2000
    code_child_size: int = 600
    doc_child_size: int = 600


class RetrievalConfig(BaseModel):
    """Retrieval knobs, tuned with `make bench`."""

    classifier_margin: float = 0.5
    code_signal_weight: float = 0.5
    doc_signal_weight: float = 0.5
    skip_rerank_score: float = float("inf")
    bm25_score_floor: float = 5.5
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    # "replace": reranker order wins; "rrf": fuse it with the BM25 order.
    rerank_fusion: str = "rrf"
    rrf_k: int = 60


class ModelsConfig(BaseModel):
    """Where neural models run.

    `device = "auto"` uses CUDA when a GPU is available and the CPU
    otherwise, so the same configuration works on machines without GPU.
    """

    device: str = "auto"

    def resolved_device(self) -> str:
        """Return the concrete torch device for `device`."""
        if self.device != "auto":
            return self.device
        import torch

        return "cuda" if torch.cuda.is_available() else "cpu"


class SourceConfig(BaseModel):
    """A knowledge source (domain) and how its files are chunked."""

    root: str
    include: list[str]
    exclude_dirs: list[str] = Field(default_factory=list)
    code_extensions: list[str] = Field(default_factory=list)
    chunkers: dict[str, str] = Field(default_factory=dict)
    default_chunker: str = "size"

    def chunker_for(self, extension: str) -> str:
        """Return the chunker name configured for a file extension."""
        return self.chunkers.get(extension, self.default_chunker)

    def chunk_type_for(self, extension: str) -> str:
        """Return 'code' or 'doc' for a file extension."""
        return "code" if extension in self.code_extensions else "doc"


class RagConfig(BaseModel):
    """Root configuration, loaded from rag.toml."""

    qdrant: QdrantConfig = Field(default_factory=QdrantConfig)
    paths: PathsConfig = Field(default_factory=PathsConfig)
    chunking: ChunkingConfig = Field(default_factory=ChunkingConfig)
    retrieval: RetrievalConfig = Field(default_factory=RetrievalConfig)
    models: ModelsConfig = Field(default_factory=ModelsConfig)
    sources: dict[str, SourceConfig] = Field(default_factory=dict)

    def source(self, domain: str) -> SourceConfig:
        """Return a source by name.

        Raises:
            KeyError: If the domain is not configured.
        """
        if domain not in self.sources:
            known = ", ".join(sorted(self.sources)) or "none"
            raise KeyError(f"Unknown source '{domain}' (configured: {known})")
        return self.sources[domain]


def apply_env_overrides(data: dict[str, Any],
                        environ: dict[str, str]) -> dict[str, Any]:
    """Override scalar settings with RAG_<SECTION>_<KEY> variables.

    Only top-level sections with scalar values are overridable, which
    covers connection details and paths (the values that change between
    machines). Sources are configured in the file only.

    Args:
        data: Raw configuration dict.
        environ: Environment mapping (usually os.environ).

    Returns:
        A copy of data with the overrides applied.
    """
    merged = {k: dict(v) if isinstance(v, dict) else v
              for k, v in data.items()}
    sections: dict[str, type[BaseModel]] = {
        "qdrant": QdrantConfig,
        "paths": PathsConfig,
        "chunking": ChunkingConfig,
        "retrieval": RetrievalConfig,
        "models": ModelsConfig,
    }
    for section, model in sections.items():
        for key in model.model_fields:
            value = environ.get(f"{ENV_PREFIX}{section}_{key}".upper())
            if value is not None:
                merged.setdefault(section, {})[key] = value
    return merged


def load_config(path: str = CONFIG_FILE,
                environ: dict[str, str] | None = None) -> RagConfig:
    """Load and validate the configuration file.

    Args:
        path: TOML file to read. A missing file yields the defaults.
        environ: Environment used for overrides (defaults to os.environ).

    Returns:
        The validated RagConfig.
    """
    data: dict[str, Any] = {}
    if os.path.isfile(path):
        with open(path, "rb") as fh:
            data = tomllib.load(fh)
    env = dict(os.environ) if environ is None else environ
    return RagConfig.model_validate(apply_env_overrides(data, env))


@lru_cache(maxsize=1)
def get_config() -> RagConfig:
    """Return the process-wide configuration (loaded once)."""
    return load_config()
