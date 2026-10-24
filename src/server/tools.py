"""The RAG as tools: what an agent or an MCP client can call.

One implementation, used in-process by the agent (src/agent/) and
exposed over MCP by src/server/mcp_server.py. Every text that leaves through a
tool has its domain's private data masked (src/rag/domain_rules.py), the
same as the web and the CLI.
"""
import math
from typing import Any, Optional, Sequence

from src.config import RagConfig, get_config
from src.rag.domain_rules import DomainRules
from src.rag.generator import Generator
from src.rag.pipeline import RagPipeline
from src.rag.router import DomainRouter

# Characters of each source returned by search (the agent reads them).
SOURCE_PREVIEW = 1200


class RagTools:
    """list_domains / search / answer over every indexed domain.

    Usage:
        tools = RagTools.load()
        tools.list_domains()
        tools.search("¿Dónde trabaja Chrystian?", domains="cv")
        tools.answer("How do I enable LoRA in vLLM?")
    """

    def __init__(self, router: DomainRouter, config: RagConfig,
                 generator: Optional[Generator] = None) -> None:
        self.router = router
        self.config = config
        self.rules = DomainRules(config)
        self.generator = generator
        self.pipeline: Optional[RagPipeline] = None

    @classmethod
    def load(cls, config: Optional[RagConfig] = None,
             generator: Optional[Generator] = None,
             domains: Optional[str | Sequence[str]] = None) -> "RagTools":
        """Load the router (with reranker) over the given domains, or
        over every indexed domain."""
        config = config or get_config()
        return cls(DomainRouter.from_store(domains, config=config), config,
                   generator)

    def get_pipeline(self) -> RagPipeline:
        """The answer flow, loading the generator on first use."""
        if self.pipeline is None:
            if self.generator is None:
                self.generator = Generator(self.config.generation)
            self.pipeline = RagPipeline(self.router, self.generator,
                                        self.rules)
        return self.pipeline

    def list_domains(self) -> list[dict[str, Any]]:
        """Indexed domains, with what they contain.

        Returns:
            One dict per domain: name, description and indexed chunks.
        """
        return [
            {"name": domain,
             "description": self.config.sources[domain].description,
             "chunks": len(retriever.chunks)}
            for domain, retriever in self.router.retrievers.items()
        ]

    def search(self, query: str,
               domains: Optional[str | Sequence[str]] = None,
               k: int = 5) -> dict[str, Any]:
        """Search the knowledge base (the best domain for the query).

        Args:
            query: What to look for, as a complete question.
            domains: Optional filter ("cv", "vllm,xquad"...); all
                indexed domains when empty.
            k: Sources to return (the domain's answer_k may raise it).

        Returns:
            Dict with the chosen domain, its relevance score and the
            sources (domain, file_path, offsets and masked text). No
            sources when no domain is relevant enough (out-of-domain
            gate).
        """
        sources = self.router.search_for_generation(query, k, domains)
        route = self.router.last_route
        domain, score = route[0] if route else (None, float("nan"))
        parents = self.router.get_parent_chunk_map()
        results = []
        for src in sources:
            parent = parents.get((src.file_path, src.first_character_index))
            text = self.rules.redact(parent.text, parent.domain) \
                if parent else ""
            results.append({
                "domain": parent.domain if parent else domain,
                "file_path": src.file_path,
                "first_character_index": src.first_character_index,
                "last_character_index": src.last_character_index,
                "text": text[:SOURCE_PREVIEW],
            })
        # No score when a single domain was searched (nothing to route);
        # NaN is not valid JSON for MCP clients.
        return {"domain": domain,
                "score": None if math.isnan(score) else round(score, 3),
                "sources": results}

    def answer(self, question: str,
               domains: Optional[str | Sequence[str]] = None,
               k: int = 5) -> dict[str, Any]:
        """Answer a question from the knowledge base (direct flow).

        Returns:
            Dict with the answer text, whether it is "not found", the
            domain it came from and its sources.
        """
        pipeline = self.get_pipeline()
        result = pipeline.answer(question, k=k, domains=domains)
        return {
            "answer": result.text,
            "not_found": result.not_found,
            "domain": pipeline.answered_domain(),
            "sources": [s.model_dump() for s in result.sources],
        }
