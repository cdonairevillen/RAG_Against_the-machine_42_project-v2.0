import os
from typing import Any, Optional, Sequence

from src.config import RagConfig, get_config
from src.rag.ingestion.chunk import Chunk
from src.rag.ingestion.pipeline import MANIFEST_FILE
from src.models import MinimalSource
from src.rag.retriever import Retriever

# Sources of each domain scored with the cross-encoder to route a query
# (its best one decides). The same signal as the out-of-domain gate.
ROUTE_TOP = 5


def indexed_domains(config: RagConfig) -> list[str]:
    """Configured sources that have been indexed, in rag.toml order."""
    return [
        domain for domain in config.sources
        if os.path.isfile(os.path.join(
            config.paths.processed_dir, domain, MANIFEST_FILE
        ))
    ]


def parse_domains(domains: Optional[str | Sequence[str]]) -> list[str]:
    """Normalise a domain filter ('vllm,xquad', a list, or None/'all').

    Returns:
        The requested domains, or [] for "every indexed domain".
    """
    if domains is None:
        return []
    if isinstance(domains, str):
        domains = domains.split(",")
    names = [d.strip() for d in domains if d and d.strip()]
    return [] if names == ["all"] else names


class DomainRouter:
    """Searches several domains and answers from the best one.

    Each domain keeps its own Retriever (and benchmarked search_smart);
    the embedder and the reranker are loaded once and shared. A query is
    searched in every selected domain, the best ROUTE_TOP sources of each
    are scored with the cross-encoder, and the domain with the highest
    score wins. Without a filter every domain takes part.

    It exposes the Retriever methods the answer flow and the web use
    (search_smart, search_for_generation, get_parent_chunk_map, reranker,
    chunks), so RagPipeline works with either.

    Usage:
        router = DomainRouter.from_store()          # every indexed domain
        router.search_for_generation("¿Quién ganó la Super Bowl 50?")
        router.search_smart(query, domains=["vllm"])
    """

    def __init__(self, retrievers: dict[str, Retriever]) -> None:
        if not retrievers:
            raise ValueError("DomainRouter needs at least one domain.")
        self.retrievers = retrievers
        self.last_route: list[tuple[str, float]] = []
        # The last search's (domain, score, sources) of every selected
        # domain, best first: the web shows each domain's results, not
        # only the winner's. Bookkeeping only; routing is unchanged.
        self.last_ranked: list[tuple[str, float, list[MinimalSource]]] = []
        self.parent_map: dict = {}

    @classmethod
    def from_store(cls, domains: Optional[str | Sequence[str]] = None,
                   config: Optional[RagConfig] = None,
                   with_reranker: bool = True) -> "DomainRouter":
        """Load a Retriever per domain, sharing the neural models.

        Args:
            domains: Domains to load (default: every indexed source).
            config: Pipeline configuration (defaults to rag.toml).
            with_reranker: Load the cross-encoder (needed to route).

        Raises:
            ValueError: If no requested domain is indexed.
        """
        config = config or get_config()
        available = indexed_domains(config)
        wanted = parse_domains(domains) or available
        missing = [d for d in wanted if d not in available]
        if missing:
            raise ValueError(
                f"Not indexed: {', '.join(missing)} (indexed: "
                f"{', '.join(available) or 'none'}). Run 'make index'."
            )
        retrievers: dict[str, Retriever] = {}
        shared: Optional[Retriever] = None
        for domain in wanted:
            retriever = Retriever.from_store(
                domain, config=config,
                embedder=shared.embedder if shared else None,
            )
            if with_reranker:
                if shared is None:
                    retriever.load_reranker()
                else:
                    retriever.reranker = shared.reranker
            shared = shared or retriever
            retrievers[domain] = retriever
        return cls(retrievers)

    @property
    def domains(self) -> list[str]:
        """Loaded domains."""
        return list(self.retrievers)

    @property
    def reranker(self) -> Any:
        """The shared cross-encoder (None if not loaded)."""
        return next(iter(self.retrievers.values())).reranker

    @property
    def chunks(self) -> list[Chunk]:
        """Child chunks of every loaded domain."""
        return [c for r in self.retrievers.values() for c in r.chunks]

    def get_parent_chunk_map(self) -> dict:
        """(file_path, first_char) -> parent Chunk across domains.

        File paths are unique per domain (each source has its own root),
        so the per-domain maps never collide.
        """
        if not self.parent_map:
            for retriever in self.retrievers.values():
                self.parent_map.update(retriever.get_parent_chunk_map())
        return self.parent_map

    def selected(self, domains: Optional[str | Sequence[str]]
                 ) -> list[str]:
        """Loaded domains matching a filter (all when there is none).

        Raises:
            ValueError: If the filter names a domain that is not loaded.
        """
        wanted = parse_domains(domains)
        unknown = [d for d in wanted if d not in self.retrievers]
        if unknown:
            raise ValueError(f"Unknown domain(s): {', '.join(unknown)} "
                             f"(loaded: {', '.join(self.domains)})")
        return wanted or self.domains

    def route(self, query: str, k: int = 10,
              domains: Optional[str | Sequence[str]] = None,
              for_answer: bool = False
              ) -> list[tuple[str, float, list[MinimalSource]]]:
        """Search every selected domain and rank the domains.

        Args:
            query: The user's question.
            k: Sources retrieved per domain.
            domains: Optional filter (see parse_domains).
            for_answer: Use each domain's answer_k instead of k (the
                sources then go to the LLM).

        Returns:
            (domain, score, sources) per domain, best score first. The
            score is the best cross-encoder logit of the domain's top
            ROUTE_TOP sources; -inf without a reranker or results. A
            domain the question names (route_hints) goes first when it
            passes its own threshold.
        """
        ranked = []
        for domain in self.selected(domains):
            retriever = self.retrievers[domain]
            domain_k = (retriever.answer_k or k) if for_answer else k
            sources = retriever.search_smart(query, domain_k)
            score = retriever.top_relevance(query, sources[:ROUTE_TOP]) \
                if sources else float("-inf")
            ranked.append((domain, score, sources))
        # Stable sort: ties keep rag.toml order.
        ranked.sort(key=lambda item: -item[1])
        hinted = self.hinted(query, ranked)
        if hinted is not None:
            ranked.insert(0, ranked.pop(hinted))
        self.last_route = [(domain, score) for domain, score, _ in ranked]
        self.last_ranked = ranked
        return ranked

    def hinted(self, query: str,
               ranked: list[tuple[str, float, list[MinimalSource]]]
               ) -> Optional[int]:
        """Position of the best domain the question names (route_hints)
        that also passes its own threshold, or None.

        A hint alone never decides: a question that mentions "the
        project" but is not about this one keeps the normal routing.
        """
        for pos, (domain, score, _) in enumerate(ranked):
            retriever = self.retrievers[domain]
            if not any(h.search(query) for h in retriever.route_hints):
                continue
            threshold = retriever.settings.relevance_threshold
            if threshold is None or score >= threshold:
                return pos
        return None

    def search_smart(self, query: str, k: int = 10,
                     domains: Optional[str | Sequence[str]] = None
                     ) -> list[MinimalSource]:
        """Sources of the best domain for the query (no relevance gate).

        With a single domain this is exactly its search_smart().
        """
        if not query or not query.strip() or k <= 0:
            return []
        selected = self.selected(domains)
        if len(selected) == 1:
            self.last_route = [(selected[0], float("nan"))]
            sources = self.retrievers[selected[0]].search_smart(query, k)
            self.last_ranked = [(selected[0], float("nan"), sources)]
            return sources
        ranked = self.route(query, k, selected)
        return ranked[0][2]

    def search_for_generation(self, query: str, k: int = 10,
                              domains: Optional[str | Sequence[str]] = None
                              ) -> list[MinimalSource]:
        """search_smart() across domains plus the out-of-domain gate.

        The winning domain's own threshold applies (each source can set
        one in rag.toml; see SourceConfig.relevance_threshold).

        Returns:
            The best domain's sources, or [] when not even the best
            domain is relevant enough (the question belongs to none).
        """
        if not query or not query.strip() or k <= 0:
            return []
        selected = self.selected(domains)
        if len(selected) == 1:
            self.last_route = [(selected[0], float("nan"))]
            sources = self.retrievers[selected[0]].search_for_generation(
                query, k
            )
            self.last_ranked = [(selected[0], float("nan"), sources)]
            return sources
        domain, score, sources = self.route(query, k, selected,
                                            for_answer=True)[0]
        threshold = self.retrievers[domain].settings.relevance_threshold
        if self.reranker is None or threshold is None:
            return sources
        return sources if score >= threshold else []
