import re
from typing import Any, Optional
import bm25s
import numpy as np
from src.config import (
    EmbeddingsConfig, ModelsConfig, RagConfig, RetrievalConfig, get_config,
)
from src.rag.ingestion.chunk import CHILD, PARENT, Chunk
from src.rag.ingestion.pipeline import load_bm25
from src.rag.ingestion.tokens import (
    corpus_part_types, query_uses_parts, tokenize,
)
from src.rag.language import detect_language
from src.models import MinimalSource
from src.rag.storage.base import ChunkStore

IDENTIFIER_PATTERN = re.compile(r"_|[a-z0-9][A-Z]|[A-Z]{2,}[a-z]{2,}")
TOKEN_PUNCTUATION = ".,;:?!¿¡()[]{}'\"`"
NON_IDENTIFIER_TERMS = {"vllm"}

CODE_SIGNAL_TERMS = {
    "def", "return", "attribute", "instance",
    "import", "module", "init", "self",
}

DOC_SIGNAL_TERMS = {
    "how", "what", "when", "where", "why", "configure",
    "install", "setup", "guide", "documentation", "example",
    "tutorial", "start", "run", "serve", "deploy", "support",
    "compatible", "hardware", "version", "requirement",
    "platform", "gpu", "rocm", "amd", "cli", "command",
    "api", "endpoint", "port", "package",
    "capability", "compute", "status", "feature",
}

# Spanish doc-question markers (the web is multilingual, D6). Without
# them every Spanish doc question was routed to the code branch.
DOC_SIGNAL_TERMS_ES = {
    "cómo", "como", "qué", "que", "cuál", "cuáles", "cuándo", "dónde",
    "configurar", "configuro", "instalar", "instalo", "guía", "ejemplo",
    "documentación", "tutorial", "ejecutar", "servir", "desplegar",
    "soporta", "soportan", "compatible", "versión", "requisito",
    "plataforma", "comando", "puerto", "paquete", "característica",
    "encontrar", "información", "recomienda", "recomendado",
}
DOC_SIGNAL_TERMS_BY_LANGUAGE = {
    "en": DOC_SIGNAL_TERMS, "es": DOC_SIGNAL_TERMS_ES,
}


def expand_query(query: str) -> str:
    """Expand a query with snake_case variants of CamelCase names.

    `PagedAttention` adds `paged_attention`, so BM25 can match code
    that uses the snake_case spelling of the same concept.

    Splitting identifiers into their parts (`Paged`, `Attention`,
    `max`, `model`...) is deliberately not done yet: it inflates BM25
    scores past the hand-tuned skip_rerank_score and was measured to
    lower Recall@3. It is revisited together with the code-aware
    tokenizer in Phase 2 (see docs/changelog/FASE_0.md, B14).

    Args:
        query: The original natural-language search string.

    Returns:
        Expanded query string with the snake_case variants appended.
    """
    camel_pattern = re.compile(
        r"\b([A-Z][a-zA-Z0-9]*(?:[A-Z][a-z0-9]+)+)\b"
    )
    extras: list[str] = []
    for match in camel_pattern.finditer(query):
        parts = re.sub(r"([A-Z])", r" \1", match.group(1)).split()
        if len(parts) > 1:
            extras.append("_".join(p.lower() for p in parts))

    query_tokens = set(re.findall(r"\w+", query.lower()))
    unique_extras = list(dict.fromkeys(
        e for e in extras if e not in query_tokens
    ))
    if not unique_extras:
        return query
    return query + " " + " ".join(unique_extras)


def rrf_merge(lists: list[list[MinimalSource]],
              rrf_k: int = 60) -> list[MinimalSource]:
    """Fuse several rankings of sources with Reciprocal Rank Fusion.

    Args:
        lists: Rankings to fuse, best first. A source may appear in
            several of them (matched by file and start offset).
        rrf_k: RRF constant.

    Returns:
        One ranking with every distinct source, best fused score first
        (ties keep the order of first appearance).
    """
    scores: dict[tuple[str, int], float] = {}
    first: dict[tuple[str, int], MinimalSource] = {}
    for ranking in lists:
        for rank, source in enumerate(ranking):
            key = (source.file_path, source.first_character_index)
            scores[key] = scores.get(key, 0.0) + 1 / (rrf_k + rank)
            first.setdefault(key, source)
    order = sorted(first, key=lambda key: -scores[key])
    return [first[key] for key in order]


class Retriever:
    """Searches the indexed knowledge base using dual BM25 indices.

    Search modes:
        search()                — fast BM25-only over the unified index,
                                   mapped to parents (CLI `search`).
        search_smart()          — classifier-guided hybrid retrieval
                                   (BM25 + dense + reranker fused with
                                   RRF). The benchmarked 42 path.
        search_for_generation() — search_smart() + relevance gate; the
                                   retrieval step of RagPipeline.

    Attributes:
        chunks: All indexed child Chunk objects.
        parent_chunks: All parent Chunk objects.
        bm25: Fitted unified BM25 instance over all child chunks.
        bm25_code: Fitted BM25 instance over code child chunks only.
        bm25_doc: Fitted BM25 instance over doc child chunks only.
        code_chunk_indices: Indices into chunks[] for code chunks.
        doc_chunk_indices: Indices into chunks[] for doc chunks.
        reranker: Loaded CrossEncoder, or None until load_reranker().
    """

    def __init__(self, chunks: list[Chunk],
                 bm25: bm25s.BM25,
                 settings: Optional[RetrievalConfig] = None,
                 models: Optional[ModelsConfig] = None) -> None:
        """Initialise with pre-loaded components.

        Prefer Retriever.from_store() for normal usage.

        Args:
            chunks: All child Chunk objects in corpus order.
            bm25: Fitted unified BM25 instance.
            settings: Retrieval knobs (defaults to the v1 values).
            models: Device settings for the neural models.
        """
        self.chunks = chunks
        self.bm25 = bm25
        self.settings = settings or RetrievalConfig()
        self.models = models or ModelsConfig()
        self.reranker = None

        # Dense retrieval (set by from_store when embeddings are on).
        self.store: Optional[ChunkStore] = None
        self.domain = ""
        self.embeddings = EmbeddingsConfig()
        self.embedder: Optional[Any] = None
        self.dense_name = ""
        self._query_cache: tuple[str, list[float]] = ("", [])
        # Sources for the LLM when answering from this domain (rag.toml
        # answer_k); None keeps the caller's k.
        self.answer_k: Optional[int] = None
        # Patterns that name this domain in a question (rag.toml
        # route_hints), used by the DomainRouter.
        self.route_hints: list[re.Pattern[str]] = []
        # Patterns that name it beyond doubt (rag.toml route_names).
        self.route_names: list[re.Pattern[str]] = []
        # [English, Spanish] path prefixes of translated files (rag.toml
        # translations), longest first, and the question languages the
        # filter applies to (translation_languages).
        self.translations: list[tuple[str, str]] = []
        self.translation_languages: list[str] = ["en", "es"]

        self.chunk_map: dict = {}
        self.parent_chunk_map: dict = {}
        self.parent_chunks: list[Chunk] = []
        self.parent_by_id: dict[str, Chunk] = {}

        self.bm25_code: Optional[bm25s.BM25] = None
        self.bm25_doc: Optional[bm25s.BM25] = None
        self.code_chunk_indices: list[int] = []
        self.doc_chunk_indices: list[int] = []

    def get_chunk_map(self) -> dict:
        """Return cached child chunk map keyed by (file_path, first_char)."""
        if not self.chunk_map:
            self.chunk_map = {
                (c.file_path, c.first_character_index): c
                for c in self.chunks
            }
        return self.chunk_map

    def get_parent_chunk_map(self) -> dict:
        """Return cached parent chunk map keyed by (file_path, first_char)."""
        if not self.parent_chunk_map:
            self.parent_chunk_map = {
                (c.file_path, c.first_character_index): c
                for c in self.parent_chunks
            }
        return self.parent_chunk_map

    def load_reranker(self) -> None:
        """Load the cross-encoder reranker model.

        Call this explicitly before search_smart() or
        search_for_generation() when precision matters. Falls back
        gracefully if the model cannot be loaded.
        """
        try:
            from sentence_transformers import CrossEncoder
            self.reranker = CrossEncoder(
                self.settings.reranker_model,
                device=self.models.resolved_device(),
            )
            print("Reranker loaded — precision reranking active.")
        except Exception as exc:
            print(f"Warning: reranker unavailable ({exc}).")
            self.reranker = None

    def tokenize(self, query: str, index: str = "all") -> Any:
        """Tokenize a query the way a BM25 index expects it.

        Args:
            query: Query text.
            index: 'all' (general), 'code' or 'doc' index.
        """
        mode = self.settings.code_aware_tokens
        return tokenize([query], code_aware=query_uses_parts(mode, index))

    def set_parents(self, parents: list[Chunk]) -> None:
        """Set the parent chunks and reset the lookups built on them."""
        self.parent_chunks = parents
        self.parent_by_id = {p.id: p for p in parents}
        self.parent_chunk_map = {}

    def set_children(self, children: list[Chunk]) -> None:
        """Set the child chunks (in BM25 row order) and derive the
        per-type row mappings used by the code and doc indices."""
        self.chunks = children
        self.chunk_map = {}
        self.code_chunk_indices = [
            i for i, c in enumerate(children) if c.chunk_type == "code"
        ]
        self.doc_chunk_indices = [
            i for i, c in enumerate(children) if c.chunk_type == "doc"
        ]

    def load_embedder(self, indexed_model: Optional[str],
                      embedder: Optional[Any] = None) -> None:
        """Load the query embedder, checking it matches the index.

        Args:
            indexed_model: Embedding model recorded in the manifest.
            embedder: An already loaded Embedder of the same model to
                reuse (several domains share one model in memory).

        Raises:
            RuntimeError: If the index was built with another model (or
                without embeddings).
        """
        from src.rag.embeddings import Embedder, vector_name

        model = self.embeddings.model
        if indexed_model != model:
            raise RuntimeError(
                f"Embeddings are enabled with '{model}' but the index of "
                f"'{self.domain}' was built with {indexed_model!r}. "
                f"Run 'make index' again."
            )
        self.embedder = embedder or Embedder(
            model, device=self.models.resolved_device()
        )
        self.dense_name = vector_name(model)

    @classmethod
    def from_store(cls, domain: str = "vllm",
                   config: Optional[RagConfig] = None,
                   store: Optional[ChunkStore] = None,
                   embedder: Optional[Any] = None) -> "Retriever":
        """Load a Retriever for one domain.

        Chunk records come from the ChunkStore (Qdrant) and the BM25
        indices from disk; the manifest written at indexing time
        guarantees both belong to the same ingestion run.

        Args:
            domain: Knowledge source to load (a key of rag.toml sources).
            config: Pipeline configuration (defaults to rag.toml).
            store: ChunkStore to read from (defaults to Qdrant from the
                configuration).
            embedder: Query Embedder to reuse instead of loading one.

        Returns:
            A ready-to-use Retriever instance.

        Raises:
            RuntimeError: If the store and the BM25 indices disagree,
                which means the domain must be re-indexed.
        """
        config = config or get_config()
        if store is None:
            from src.rag.storage.qdrant_store import QdrantChunkStore
            store = QdrantChunkStore.from_config(config.qdrant)

        bm25, bm25_code, bm25_doc, manifest = load_bm25(
            config.paths.processed_dir, domain
        )
        mode = config.retrieval.code_aware_tokens
        indexed = manifest.get("identifier_parts", [])
        if indexed != corpus_part_types(mode):
            raise RuntimeError(
                f"The BM25 index of '{domain}' has identifier parts for "
                f"{indexed or 'no'} chunks, but code_aware_tokens='{mode}' "
                f"expects {corpus_part_types(mode) or 'none'}. "
                f"Run 'make index' again."
            )
        chunks = store.load(domain)
        parents = [c for c in chunks if c.level == PARENT]
        children = [c for c in chunks if c.level == CHILD]
        if (len(parents), len(children)) != (
                manifest["parents"], manifest["children"]):
            raise RuntimeError(
                f"Store has {len(parents)} parents / {len(children)} "
                f"children for '{domain}' but the BM25 index expects "
                f"{manifest['parents']} / {manifest['children']}. "
                f"Run 'make index' again."
            )

        settings = config.retrieval
        source = config.sources.get(domain)
        if source is not None and source.relevance_threshold is not None:
            settings = settings.model_copy(update={
                "relevance_threshold": source.relevance_threshold,
            })
        retriever = cls(chunks=children, bm25=bm25,
                        settings=settings, models=config.models)
        retriever.set_children(children)
        retriever.set_parents(parents)
        retriever.bm25_code = bm25_code
        retriever.bm25_doc = bm25_doc
        retriever.store = store
        retriever.domain = domain
        retriever.answer_k = source.answer_k if source else None
        retriever.route_hints = [
            re.compile(hint, re.IGNORECASE)
            for hint in (source.route_hints if source else [])
        ]
        retriever.route_names = [
            re.compile(name, re.IGNORECASE)
            for name in (source.route_names if source else [])
        ]
        retriever.translations = sorted(
            ((english, spanish) for english, spanish in
             (source.translations if source else [])),
            key=lambda pair: -max(len(pair[0]), len(pair[1])))
        if source is not None:
            retriever.translation_languages = source.translation_languages
        retriever.embeddings = config.embeddings
        if config.embeddings.enabled:
            retriever.load_embedder(manifest.get("embedding_model"),
                                    embedder)
        print(
            f"Loaded {len(children)} chunks for '{domain}' "
            f"({len(retriever.doc_chunk_indices)} doc, "
            f"{len(retriever.code_chunk_indices)} code), "
            f"{len(parents)} parents"
        )
        return retriever

    def search(self, query: str, k: int = 10) -> list[MinimalSource]:
        """BM25 retrieval over the unified index, mapped to parents.

        Args:
            query: Natural-language search string.
            k: Number of results to return.

        Returns:
            Ranked list of parent MinimalSource objects.
        """
        if not query or not query.strip() or k <= 0:
            return []

        expanded = expand_query(query)
        fetch_k = min(k * 5, len(self.chunks))
        child_candidates = self.search_bm25(
            expanded, fetch_k, min_score=0.0
        )

        parent_map = self.get_chunk_map()
        seen: set = set()
        parent_sources: list[MinimalSource] = []

        for source in child_candidates:
            child = parent_map.get(
                (source.file_path, source.first_character_index)
            )
            if child is None:
                continue
            parent_source = self.child_to_parent_source(child)
            key = (
                parent_source.file_path,
                parent_source.first_character_index,
            )
            if key not in seen:
                seen.add(key)
                parent_sources.append(parent_source)
            if len(parent_sources) >= k:
                break

        return parent_sources

    def classify_query(self, query: str) -> tuple[float, float]:
        """Score a query's affinity for the doc vs. code index.

        Combines the mean top-3 BM25 score from each per-type index
        with lexical signal counts (identifier-like tokens favour
        code, natural-language tokens favour docs).

        Args:
            query: The expanded search string.

        Returns:
            Tuple of (combined_code_score, combined_doc_score).
        """
        doc_top_score = 0.0
        code_top_score = 0.0
        try:
            # Always the plain query, whatever code_aware_tokens says:
            # identifier parts inflate the scores of whichever index has
            # them and would bias the routing towards it.
            plain = tokenize([query], code_aware=False)
            if self.bm25_doc is not None:
                _, ds = self.bm25_doc.retrieve(
                    plain, k=3, show_progress=False
                )
                doc_top_score = float(np.mean(ds[0]))
            if self.bm25_code is not None:
                _, cs = self.bm25_code.retrieve(
                    plain, k=3, show_progress=False
                )
                code_top_score = float(np.mean(cs[0]))
        except Exception:
            pass

        query_terms = {
            t.strip(TOKEN_PUNCTUATION).lower() for t in query.split()
        }
        raw_terms = {
            t.strip(TOKEN_PUNCTUATION).removesuffix("'s")
            for t in query.split()
        }
        code_signals = sum(
            1 for t in raw_terms
            if t.lower() not in NON_IDENTIFIER_TERMS
            and (
                IDENTIFIER_PATTERN.search(t)
                or t.lower() in CODE_SIGNAL_TERMS
            )
        )
        doc_terms = set().union(*(
            DOC_SIGNAL_TERMS_BY_LANGUAGE[lang]
            for lang in self.settings.doc_signal_languages
        ))
        doc_signals = sum(1 for t in query_terms if t in doc_terms)

        w = self.settings
        combined_code = code_top_score + code_signals * w.code_signal_weight
        combined_doc = doc_top_score + doc_signals * w.doc_signal_weight
        return combined_code, combined_doc

    def search_smart(self, query: str, k: int = 10) -> list[MinimalSource]:
        """search_smart_all() without the other language's copies of
        translated files (rag.toml translations), when the question's
        language is clear and listed in translation_languages. Otherwise
        it is exactly search_smart_all().
        """
        language = detect_language(query) if self.translations else "?"
        if language not in ("en", "es") \
                or language not in self.translation_languages:
            return self.search_smart_all(query, k)
        files = {c.file_path for c in self.parent_chunks}
        kept = [s for s in self.search_smart_all(query, k * 2)
                if not self.translated_copy(s.file_path, language, files)]
        return kept[:k]

    def translated_copy(self, file_path: str, language: str,
                        files: set[str]) -> bool:
        """Whether a file is the other-language copy of an indexed
        file, for a question in `language`."""
        for english, spanish in self.translations:
            if file_path.startswith(spanish):
                return (language == "en"
                        and english + file_path[len(spanish):] in files)
        for english, spanish in self.translations:
            if file_path.startswith(english):
                return (language == "es"
                        and spanish + file_path[len(english):] in files)
        return False

    def search_smart_all(self, query: str,
                         k: int = 10) -> list[MinimalSource]:
        """Classifier-guided retrieval: doc index for docs, reranker
        for code.

        Routes each query to whichever per-type index it best
        matches. Doc queries are served by the doc index without the
        reranker (it hurts doc ranking on this corpus). Code queries are
        served by the unified index filtered to code chunks, plus a few
        doc results as a safety net for borderline queries, fused with
        the cross-encoder through RRF. When embeddings are enabled, each
        list (code, doc) first fuses its BM25 and dense candidates.

        Args:
            query: Natural-language search string.
            k: Number of results to return.

        Returns:
            Ranked list of parent MinimalSource objects.
        """
        if not query or not query.strip() or k <= 0:
            return []

        expanded = expand_query(query)
        combined_code, combined_doc = self.classify_query(expanded)

        if combined_code > combined_doc + self.settings.classifier_margin:
            return self._search_smart_code(
                query, expanded, k, combined_code
            )
        return self._search_smart_docs(query, expanded, k)

    def _search_smart_code(self, query: str, expanded: str, k: int,
                           code_top_score: float) -> list[MinimalSource]:
        """Code-mode branch of search_smart(). See that method."""
        fetch_k = min(k * 10, len(self.chunks))
        candidates = self.search_bm25(expanded, fetch_k, min_score=0.0)
        chunk_map = self.get_chunk_map()

        code_sources: list[MinimalSource] = []
        seen: set = set()
        for source in candidates:
            child = chunk_map.get(
                (source.file_path, source.first_character_index)
            )
            if child is None or child.chunk_type != "code":
                continue
            parent_source = self.child_to_parent_source(child)
            key = (
                parent_source.file_path,
                parent_source.first_character_index,
            )
            if key not in seen:
                seen.add(key)
                code_sources.append(parent_source)
            if len(code_sources) >= k * 3:
                break
        dense_code = self.dense_parents(query, "code")
        if dense_code:
            code_sources = rrf_merge(
                [code_sources, dense_code], self.settings.rrf_k
            )[:k * 3]
            seen = {(s.file_path, s.first_character_index)
                    for s in code_sources}

        doc_backup: list[MinimalSource] = []
        if self.bm25_doc is not None and self.doc_chunk_indices:
            try:
                tokenized = self.tokenize(expanded, "doc")
                results, _ = self.bm25_doc.retrieve(
                    tokenized, k=10, show_progress=False
                )
                seen_doc: set = set()
                for idx in results[0].tolist():
                    chunk = self.chunks[self.doc_chunk_indices[int(idx)]]
                    ps = self.child_to_parent_source(chunk)
                    key = (ps.file_path, ps.first_character_index)
                    if key not in seen_doc and key not in seen:
                        seen_doc.add(key)
                        doc_backup.append(ps)
                    if len(doc_backup) >= 4:
                        break
            except Exception:
                pass
        dense_doc = [
            s for s in self.dense_parents(query, "doc")
            if (s.file_path, s.first_character_index) not in seen
        ]
        if dense_doc:
            doc_backup = rrf_merge(
                [doc_backup, dense_doc], self.settings.rrf_k
            )[:4]

        if code_top_score > self.settings.skip_rerank_score:
            return code_sources[:k]
        # Code and doc candidates come from two separate BM25 rankings:
        # each keeps its own rank for the fusion with the reranker.
        input_ranks = list(range(len(code_sources))) + list(
            range(len(doc_backup))
        )
        return self.rerank_parents(
            expanded, code_sources + doc_backup, k, input_ranks
        )

    def _search_smart_docs(self, query: str, expanded: str,
                           k: int) -> list[MinimalSource]:
        """Doc-mode branch of search_smart(). See that method."""
        fetch_k = min(k * 5, len(self.doc_chunk_indices))
        doc_sources: list[MinimalSource] = []

        if self.bm25_doc is not None and self.doc_chunk_indices:
            try:
                tokenized = self.tokenize(expanded, "doc")
                results, _ = self.bm25_doc.retrieve(
                    tokenized, k=fetch_k, show_progress=False
                )
                seen: set = set()
                for idx in results[0].tolist():
                    chunk = self.chunks[self.doc_chunk_indices[int(idx)]]
                    ps = self.child_to_parent_source(chunk)
                    key = (ps.file_path, ps.first_character_index)
                    if key not in seen:
                        seen.add(key)
                        doc_sources.append(ps)
            except Exception:
                pass
        dense_doc = (
            self.dense_parents(query, "doc")
            if self.embeddings.dense_in_doc_branch else []
        )
        if dense_doc:
            doc_sources = rrf_merge(
                [doc_sources, dense_doc], self.settings.rrf_k
            )

        if len(doc_sources) < k:
            unified = self.search(expanded, k * 2)
            seen_unified = {
                (s.file_path, s.first_character_index)
                for s in doc_sources
            }
            for src in unified:
                if len(doc_sources) >= k * 2:
                    break
                key = (src.file_path, src.first_character_index)
                if key not in seen_unified:
                    seen_unified.add(key)
                    doc_sources.append(src)

        if self.settings.rerank_doc_branch and self.reranker is not None:
            pool = doc_sources[:k * 3]
            return self.rerank_parents(expanded, pool, k)
        return doc_sources[:k]

    def query_vector(self, query: str) -> list[float]:
        """Embed a query, reusing the last result for repeated calls."""
        if self.embedder is None:
            return []
        if self._query_cache[0] != query:
            self._query_cache = (query, self.embedder.encode_query(query))
        return self._query_cache[1]

    def dense_parents(self, query: str,
                      chunk_type: str) -> list[MinimalSource]:
        """Parents of the nearest children to the query (dense search).

        Args:
            query: Original (non-expanded) query.
            chunk_type: 'code' or 'doc'.

        Returns:
            Distinct parent sources, best first; [] when embeddings are
            disabled.
        """
        if self.embedder is None or self.store is None:
            return []
        ordinals = self.store.search_dense(
            self.domain, self.dense_name, self.query_vector(query),
            self.embeddings.dense_k, chunk_type,
        )
        parents: list[MinimalSource] = []
        seen: set = set()
        for ordinal in ordinals:
            source = self.child_to_parent_source(self.chunks[ordinal])
            key = (source.file_path, source.first_character_index)
            if key not in seen:
                seen.add(key)
                parents.append(source)
        return parents

    def get_top_bm25_score(self, query: str) -> float:
        """Return the highest BM25 score for a query over the corpus.

        Args:
            query: Search string.

        Returns:
            Highest score, or 0.0 on error.
        """
        try:
            tokenized = self.tokenize(query)
            _, scores = self.bm25.retrieve(
                tokenized, k=1, show_progress=False
            )
            return float(scores[0][0])
        except Exception:
            return 0.0

    def rerank_parents(self, query: str,
                       sources: list[MinimalSource],
                       k: int,
                       input_ranks: Optional[list[int]] = None
                       ) -> list[MinimalSource]:
        """Rerank parent sources using parent chunk text.

        With `rerank_fusion = "replace"` the cross-encoder order replaces
        the incoming (BM25) order. With "rrf" both orders are fused with
        Reciprocal Rank Fusion, so a source either ranking puts high
        stays competitive.

        Args:
            query: The original search string.
            sources: Parent MinimalSource objects to rerank, in their
                incoming (BM25) order.
            k: Number of top results to return.
            input_ranks: Rank of each source in the list it came from,
                for RRF when sources merge several rankings (defaults to
                its position in `sources`).

        Returns:
            Reranked and truncated MinimalSource list.
        """
        if self.reranker is None or not sources:
            return sources[:k]

        parent_map = self.get_parent_chunk_map()
        pairs: list[tuple[str, str]] = []
        for source in sources:
            parent = parent_map.get(
                (source.file_path, source.first_character_index)
            )
            text = parent.text if parent else source.file_path
            pairs.append((query, text))

        try:
            scores: list[float] = self.reranker.predict(pairs).tolist()
        except Exception:
            return sources[:k]

        if self.settings.rerank_fusion == "rrf":
            rrf_k = self.settings.rrf_k
            by_score = sorted(range(len(sources)),
                              key=lambda i: scores[i], reverse=True)
            ranks = input_ranks or list(range(len(sources)))
            fused = [0.0] * len(sources)
            for rank, i in enumerate(by_score):
                fused[i] = 1 / (rrf_k + rank) + 1 / (rrf_k + ranks[i])
            scores = fused

        ranked = sorted(
            zip(scores, sources), key=lambda x: x[0], reverse=True
        )
        return [source for _, source in ranked[:k]]

    def search_for_generation(self, query: str,
                              k: int = 10) -> list[MinimalSource]:
        """Retrieval for LLM generation: search_smart() + relevance gate.

        Same ranking as the benchmarked path (search_smart), plus an
        out-of-domain gate: when the best source is not relevant enough
        nothing is returned, so the LLM answers "not found" instead of
        guessing. The gate uses the cross-encoder score of the best
        source (relevance_threshold); without a reranker it falls back
        to the BM25 floor, a much weaker signal.

        Args:
            query: Natural-language search string.
            k: Number of results to return.

        Returns:
            Ranked list of parent MinimalSource objects, or [] when the
            query is out of domain.
        """
        if not query or not query.strip() or k <= 0:
            return []

        k = self.answer_k or k
        threshold = self.settings.relevance_threshold
        if self.reranker is None or threshold is None:
            if self.get_top_bm25_score(query) < self.settings.bm25_score_floor:
                return []
            return self.search_smart(query, k)

        results = self.search_smart(query, k)
        if results and self.top_relevance(query, results) < threshold:
            return []
        return results

    def top_relevance(self, query: str,
                      sources: list[MinimalSource]) -> float:
        """Best cross-encoder score of the query against the sources.

        Args:
            query: The user's question.
            sources: Retrieved parent sources.

        Returns:
            The highest reranker logit (0 = 50% relevance), or -inf if
            no source text is available.
        """
        if self.reranker is None:
            return float("-inf")
        parent_map = self.get_parent_chunk_map()
        pairs = [
            (query, parent_map[(s.file_path, s.first_character_index)].text)
            for s in sources
            if (s.file_path, s.first_character_index) in parent_map
        ]
        if not pairs:
            return float("-inf")
        return float(max(self.reranker.predict(pairs)))

    def search_bm25(self, query: str, k: int,
                    min_score: float = 0.0) -> list[MinimalSource]:
        """BM25-only retrieval over the unified index.

        Args:
            query: Search string (already expanded).
            k: Number of results.
            min_score: Minimum BM25 score to include a result.

        Returns:
            Ranked MinimalSource list.
        """
        try:
            tokenized = self.tokenize(query)
            effective_k = min(k, len(self.chunks))
            results, scores = self.bm25.retrieve(
                tokenized, k=effective_k, show_progress=False
            )
            indices: list[int] = results[0].tolist()
            result_scores: list[float] = scores[0].tolist()
        except Exception:
            return []

        return [
            self.chunk_to_source(self.chunks[int(idx)])
            for idx, score in zip(indices, result_scores)
            if score >= min_score
        ]

    def chunk_to_source(self, chunk: Chunk) -> MinimalSource:
        """Convert a Chunk to the MinimalSource model the CLI expects.

        Args:
            chunk: Internal Chunk dataclass.

        Returns:
            MinimalSource Pydantic model.
        """
        return MinimalSource(
            file_path=chunk.file_path,
            first_character_index=chunk.first_character_index,
            last_character_index=chunk.last_character_index,
        )

    def child_to_parent_source(self, child: Chunk) -> MinimalSource:
        """Map a child chunk to its parent's MinimalSource.

        Args:
            child: Child Chunk with parent_id set.

        Returns:
            MinimalSource of the parent chunk, or the child's own
            source if it has no parent.
        """
        parent = self.parent_by_id.get(child.parent_id)
        if parent is not None:
            return MinimalSource(
                file_path=parent.file_path,
                first_character_index=parent.first_character_index,
                last_character_index=parent.last_character_index,
            )
        return self.chunk_to_source(child)
