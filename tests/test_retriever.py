from src.ingestion.chunk import Chunk
from src.retriever import Retriever, expand_query


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


def test_child_maps_to_parent_source() -> None:
    parent = Chunk("parent text", "f.py", 10, 90, "code", id="p1")
    child = Chunk("child", "f.py", 20, 40, "code", parent_id="p1")
    retriever = make_retriever([child], [parent])

    source = retriever.child_to_parent_source(child)

    assert (source.first_character_index,
            source.last_character_index) == (10, 90)


def test_orphan_child_maps_to_itself() -> None:
    child = Chunk("child", "f.py", 20, 40, "code", parent_id="")
    retriever = make_retriever([child], [])

    source = retriever.child_to_parent_source(child)

    assert (source.first_character_index,
            source.last_character_index) == (20, 40)
