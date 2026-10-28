import os
import sys
from functools import lru_cache
from typing import Any, Literal, Optional

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
    reranker_model: str = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"
    # "replace": reranker order wins; "rrf": fuse it with the BM25 order.
    rerank_fusion: str = "rrf"
    rrf_k: int = 60
    # Languages whose doc-question markers the classifier counts.
    doc_signal_languages: list[str] = Field(
        default_factory=lambda: ["en", "es"]
    )
    # Out-of-domain gate before generation: minimum cross-encoder logit
    # of the best source (0 = 50% relevance). None disables it and falls
    # back to bm25_score_floor.
    relevance_threshold: Optional[float] = 0.0
    # Rerank the doc branch too (v1 removed it: ms-marco hurt docs).
    rerank_doc_branch: bool = False
    # Identifier splitting for BM25: "none", "query", "both" or "code".
    # Changing it needs a re-index (see src/rag/ingestion/tokens.py).
    code_aware_tokens: Literal["none", "query", "both", "code", "doc"] = (
        "code"
    )


class EmbeddingsConfig(BaseModel):
    """Dense retrieval: child chunks and queries embedded with one model.

    Vectors live in Qdrant as a named vector on the child points, fused
    with BM25 through RRF. Changing the model needs `make index`. Off by
    default in code (tests, light setups); rag.toml turns it on.
    """

    enabled: bool = False
    model: str = "BAAI/bge-m3"
    batch_size: int = 64
    # Dense candidates fetched per list (code / doc), before fusion.
    dense_k: int = 50
    # Also fuse dense candidates in the doc branch of search_smart (the
    # code branch, including its doc safety net, always uses them).
    dense_in_doc_branch: bool = True


class GenerationConfig(BaseModel):
    """The LLM that writes the answers.

    Qwen/Qwen3-0.6B is the base (comparable with other 42 RAGs); other
    models are optional profiles. All load through llm_sdk.
    """

    model: str = "Qwen/Qwen3-0.6B"
    max_new_tokens: int = 150
    max_input_tokens: int = 3072
    # llm_sdk default. False uses the transformers implementation instead
    # of the model repo's own code (needed when that code is outdated).
    trust_remote_code: bool = True
    # Replaces rule 6 of the system prompt (answer length and form) for
    # this model; empty keeps the default "Be direct and concise" rule.
    # Per model, so each one gets the form it handles (Phase 8, FASE_8.md
    # 8g).
    style_rule: str = ""


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
    # What the domain contains, for the agent and MCP clients choosing
    # where to search (list_domains).
    description: str = ""
    # Names skipped anywhere in a path (a directory or a file name).
    exclude_dirs: list[str] = Field(default_factory=list)
    # Paths relative to root (a directory or a file) skipped entirely,
    # for one folder whose name exists elsewhere too (deploy/stage but
    # not src/deploy).
    exclude_paths: list[str] = Field(default_factory=list)
    # Blank the regions of Markdown files between the about:skip markers
    # (HTML comments, see ingestion/pipeline.py) before chunking, keeping
    # the offsets: parts of a document this source must not index (Phase
    # 7a: test transcripts quoting CV answers inside the changelogs).
    skip_marked: bool = False
    code_extensions: list[str] = Field(default_factory=list)
    chunkers: dict[str, str] = Field(default_factory=dict)
    default_chunker: str = "size"
    # Out-of-domain gate for this source (cross-encoder logit). None uses
    # retrieval.relevance_threshold. Calibrated with `gate_scores`: the
    # reranker scores each corpus on its own scale (see FASE_4.md).
    relevance_threshold: Optional[float] = None
    # Regular expressions (case-insensitive) that name this domain in a
    # question ("this project"). The router lets a matching domain win
    # when it also passes its own relevance_threshold; otherwise routing
    # is unchanged (see DomainRouter.route).
    route_hints: list[str] = Field(default_factory=list)
    # Files that exist in two languages, as [English, Spanish] path
    # prefixes (a file or a folder, relative to root). For a question in
    # one language, the other language's copy of a translated file is
    # left out of the results, so both copies never fill the context.
    translations: list[tuple[str, str]] = Field(default_factory=list)
    # Question languages the translations filter applies to. "about"
    # keeps English copies for Spanish questions: a section of the
    # English file can hold the answer when the Spanish file's retrieved
    # section does not (measured, FASE_7.md 7b.4).
    translation_languages: list[str] = Field(
        default_factory=lambda: ["en", "es"])
    # The web always searches this domain: it joins every domain filter
    # and its chip cannot be turned off (Phase 7a: "about").
    pinned: bool = False
    # Data hidden at answer time ("phone", "email"): masked in the
    # context given to the LLM, in the answer and in the sources shown.
    # The indexed material is not modified. public_emails stay visible.
    private_data: list[Literal["phone", "email"]] = Field(
        default_factory=list
    )
    public_emails: list[str] = Field(default_factory=list)
    private_replacement: str = "[private]"
    # "Not found" answer of this domain, per language ("es", "en"...);
    # empty uses the generic message.
    not_found_message: dict[str, str] = Field(default_factory=dict)
    # Extra rules appended to the system prompt when answering from this
    # domain (e.g. the CV mode's persona and secrecy rules).
    prompt_rules: str = ""
    # Rules for one model only (its Hugging Face id), after prompt_rules:
    # a reminder one model needs and the others do not (Phase 8, Granite
    # and the CV's private data). The other models' prompts stay as is.
    model_rules: dict[str, str] = Field(default_factory=dict)
    # Rule 6 (answer length and form) for this domain, over the model's
    # style_rule: a domain whose answers must stay short (the CV, where
    # longer answers made up facts; FASE_8.md 8g). None: the model's.
    style_rule: Optional[str] = None
    # Sources given to the LLM when answering from this domain (None:
    # the caller's k). Retrieval benchmarks are not affected.
    answer_k: Optional[int] = None
    # Parent/child chunk sizes for this source (None: [chunking]).
    # Changing them needs `make index SOURCE=<name>`.
    chunk_size: Optional[int] = None
    child_size: Optional[int] = None

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
    embeddings: EmbeddingsConfig = Field(default_factory=EmbeddingsConfig)
    generation: GenerationConfig = Field(default_factory=GenerationConfig)
    sources: dict[str, SourceConfig] = Field(default_factory=dict)
    # Active profile ("default" = the stable base configuration) and the
    # profiles rag.toml offers, e.g. for a model selector in the web.
    profile: str = "default"
    available_profiles: list[str] = Field(default_factory=list)

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
        "embeddings": EmbeddingsConfig,
        "generation": GenerationConfig,
    }
    for section, model in sections.items():
        for key in model.model_fields:
            value = environ.get(f"{ENV_PREFIX}{section}_{key}".upper())
            if value is not None:
                merged.setdefault(section, {})[key] = value
    return merged


def deep_merge(base: dict[str, Any],
               override: dict[str, Any]) -> dict[str, Any]:
    """Return base with override applied recursively (dicts merged,
    everything else replaced)."""
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_config(path: str = CONFIG_FILE,
                environ: dict[str, str] | None = None,
                profile: str | None = None) -> RagConfig:
    """Load and validate the configuration file.

    Precedence: environment variables > selected profile > rag.toml base
    > code defaults. Without a profile the stable base configuration is
    used, so results do not depend on the machine.

    Args:
        path: TOML file to read. A missing file yields the defaults.
        environ: Environment used for overrides (defaults to os.environ).
        profile: Profile from `[profiles.<name>]` to apply on top of the
            base (defaults to RAG_PROFILE, then "default").

    Returns:
        The validated RagConfig.

    Raises:
        KeyError: If the requested profile does not exist.
    """
    data: dict[str, Any] = {}
    if os.path.isfile(path):
        with open(path, "rb") as fh:
            data = tomllib.load(fh)
    env = dict(os.environ) if environ is None else environ

    profiles: dict[str, Any] = data.pop("profiles", {})
    name = profile or env.get(f"{ENV_PREFIX}PROFILE") or "default"
    if name != "default":
        if name not in profiles:
            known = ", ".join(sorted(profiles)) or "none"
            raise KeyError(f"Unknown profile '{name}' (available: {known})")
        data = deep_merge(data, profiles[name])
    data["profile"] = name
    data["available_profiles"] = ["default", *sorted(profiles)]
    return RagConfig.model_validate(apply_env_overrides(data, env))


@lru_cache(maxsize=1)
def get_config() -> RagConfig:
    """Return the process-wide configuration (loaded once)."""
    return load_config()
