from typing import Any

import pytest

from src.config import RetrievalConfig
from src.models import MinimalSource
from src.rag.router import DomainRouter, parse_domains


class FakeRetriever:
    """Returns fixed sources and a fixed relevance per domain."""

    def __init__(self, domain: str, relevance: float,
                 threshold: float = 0.0) -> None:
        self.domain = domain
        self.relevance = relevance
        self.settings = RetrievalConfig(relevance_threshold=threshold)
        self.reranker = object()
        self.chunks: list[Any] = []
        self.answer_k = None

    def source(self) -> MinimalSource:
        return MinimalSource(file_path=f"{self.domain}.md",
                             first_character_index=0,
                             last_character_index=10)

    def search_smart(self, query: str, k: int = 10) -> list[MinimalSource]:
        return [self.source()]

    def search_for_generation(self, query: str,
                              k: int = 10) -> list[MinimalSource]:
        return [self.source()] if self.relevance >= 0 else []

    def top_relevance(self, query: str, sources: list) -> float:
        return self.relevance

    def get_parent_chunk_map(self) -> dict:
        return {(f"{self.domain}.md", 0): self.domain}


def router(vllm: float, xquad: float) -> DomainRouter:
    return DomainRouter({  # type: ignore[dict-item]
        "vllm": FakeRetriever("vllm", vllm),
        "xquad": FakeRetriever("xquad", xquad),
    })


def test_parse_domains() -> None:
    assert parse_domains(None) == []
    assert parse_domains("all") == []
    assert parse_domains("vllm, xquad") == ["vllm", "xquad"]
    assert parse_domains(("xquad",)) == ["xquad"]


def test_best_domain_wins_without_filter() -> None:
    r = router(vllm=-2.0, xquad=3.0)
    assert r.search_smart("q")[0].file_path == "xquad.md"
    assert [d for d, _ in r.last_route] == ["xquad", "vllm"]


def test_filter_restricts_the_search() -> None:
    r = router(vllm=-2.0, xquad=3.0)
    assert r.search_smart("q", domains="vllm")[0].file_path == "vllm.md"
    with pytest.raises(ValueError):
        r.search_smart("q", domains="cv")


def test_gate_rejects_when_no_domain_is_relevant() -> None:
    assert router(vllm=-2.0, xquad=-1.0).search_for_generation("q") == []
    assert router(vllm=-2.0, xquad=1.0).search_for_generation("q")


def test_parent_map_merges_domains() -> None:
    assert set(router(0, 0).get_parent_chunk_map()) == {
        ("vllm.md", 0), ("xquad.md", 0),
    }


def test_gate_uses_the_winning_domain_threshold() -> None:
    r = DomainRouter({  # type: ignore[dict-item]
        "vllm": FakeRetriever("vllm", -5.0),
        "xquad": FakeRetriever("xquad", -2.0, threshold=-3.0),
    })
    assert r.search_for_generation("q")[0].file_path == "xquad.md"
    r.retrievers["xquad"].settings.relevance_threshold = -1.0
    assert r.search_for_generation("q") == []
