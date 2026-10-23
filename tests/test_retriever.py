from src.config import RetrievalConfig
from src.rag.ingestion.chunk import Chunk
from src.rag.retriever import Retriever, expand_query


def make_retriever(chunks: list[Chunk],
                   parents: list[Chunk]) -> Retriever:
    retriever = Retriever(chunks=chunks, bm25=None)  # type: ignore[arg-type]
    retriever.set_parents(parents)
    return retriever


def test_expand_query_adds_snake_case_variant_of_camel_case() -> None:
    expanded = expand_query("How does PagedAttention work?")
    assert expanded.split()[-1] == "paged_attention"


def test_expand_query_does_not_split_snake_case_yet() -> None:
    query = "What is max_model_len_limit for?"
    assert expand_query(query) == query


def test_expand_query_leaves_plain_text_untouched() -> None:
    query = "How do I install vLLM with pip?"
    assert expand_query(query) == query


def test_classifier_counts_identifiers_as_code_signals() -> None:
    retriever = make_retriever([], [])
    code, doc = retriever.classify_query(
        "What does RMSNorm do in the forward method?"
    )
    assert code > 0.0


def test_classifier_ignores_product_name_and_first_word() -> None:
    retriever = make_retriever([], [])
    code, doc = retriever.classify_query(
        "How do I install vLLM's CUDA wheels?"
    )
    assert code == 0.0
    assert doc > 0.0


def test_classifier_counts_spanish_doc_markers() -> None:
    retriever = make_retriever([], [])
    code, doc = retriever.classify_query("¿Cómo instalo vLLM en una GPU?")
    assert doc > 0.0

    retriever.settings = RetrievalConfig(doc_signal_languages=["en"])
    code, doc_en_only = retriever.classify_query(
        "¿Cómo instalo vLLM en una GPU?"
    )
    # "gpu" is an English marker too; Spanish ones add on top of it.
    assert doc > doc_en_only


def test_child_maps_to_parent_source() -> None:
    parent = Chunk("parent text", "f.py", 10, 90, "code", id="p1")
    child = Chunk("child", "f.py", 20, 40, "code", parent_id="p1")
    retriever = make_retriever([child], [parent])

    source = retriever.child_to_parent_source(child)

    assert (source.first_character_index,
            source.last_character_index) == (10, 90)


class FakeReranker:
    """Scores each (query, text) pair with a fixed table."""

    def __init__(self, scores: dict[str, float]) -> None:
        self.scores = scores

    def predict(self, pairs: list[tuple[str, str]]) -> "FakeScores":
        return FakeScores([self.scores[text] for _, text in pairs])


class FakeScores(list):  # type: ignore[type-arg]
    def tolist(self) -> list[float]:
        return list(self)


def fused_retriever(fusion: str) -> Retriever:
    parents = [
        Chunk(name, f"{name}.py", 0, 10, "code", id=name)
        for name in ("A", "B", "C", "D")
    ]
    retriever = make_retriever([], parents)
    retriever.settings = RetrievalConfig(rerank_fusion=fusion)
    # The reranker strongly prefers C, then D; BM25 had A, B first.
    retriever.reranker = FakeReranker(  # type: ignore[assignment]
        {"A": 0.1, "B": 0.0, "C": 9.0, "D": 5.0}
    )
    return retriever


def sources_of(retriever: Retriever) -> list:
    return [retriever.chunk_to_source(p) for p in retriever.parent_chunks]


def test_replace_fusion_follows_the_reranker() -> None:
    retriever = fused_retriever("replace")

    ranked = retriever.rerank_parents("q", sources_of(retriever), k=4)

    assert [s.file_path for s in ranked] == ["C.py", "D.py", "A.py", "B.py"]


def test_rrf_fusion_balances_bm25_and_reranker() -> None:
    retriever = fused_retriever("rrf")

    ranked = retriever.rerank_parents("q", sources_of(retriever), k=4)

    # BM25 order A, B, C, D; reranker order C, D, A, B. C rises from 3rd
    # to 2nd but A, BM25's best, is not buried (it ties with C at
    # 1/60 + 1/62 and keeps its place; B and D tie the same way).
    assert [s.file_path for s in ranked] == ["A.py", "C.py", "B.py", "D.py"]


def test_rrf_uses_per_list_ranks() -> None:
    """D leads its own (doc) list: with per-list ranks it beats B, the
    second of the code list, even if both are tied by the reranker."""
    retriever = fused_retriever("rrf")
    retriever.reranker = FakeReranker(  # type: ignore[assignment]
        {"A": 1.0, "B": 0.5, "C": 0.0, "D": 0.5}
    )
    sources = sources_of(retriever)

    ranked = retriever.rerank_parents(
        "q", sources, k=4, input_ranks=[0, 1, 2, 0]
    )

    order = [s.file_path for s in ranked]
    assert order.index("D.py") < order.index("B.py")


def test_orphan_child_maps_to_itself() -> None:
    child = Chunk("child", "f.py", 20, 40, "code", parent_id="")
    retriever = make_retriever([child], [])

    source = retriever.child_to_parent_source(child)

    assert (source.first_character_index,
            source.last_character_index) == (20, 40)
