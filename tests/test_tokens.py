from src.ingestion.tokens import (
    corpus_part_types, query_uses_parts, split_identifier,
    with_identifier_parts,
)


def test_split_snake_and_camel_case() -> None:
    assert split_identifier("max_model_len") == ["max", "model", "len"]
    assert split_identifier("PagedAttention") == ["paged", "attention"]
    assert split_identifier("RMSNorm") == ["rms", "norm"]
    assert split_identifier("_call_hf_processor") == [
        "call", "hf", "processor",
    ]
    assert split_identifier("JSONTree") == ["json", "tree"]


def test_plain_words_and_product_name_are_not_split() -> None:
    assert split_identifier("plain") == []
    assert split_identifier("__init__") == []
    assert split_identifier("vLLM") == []


def test_identifier_parts_are_appended_keeping_originals() -> None:
    text = "What does max_model_len do in PagedAttention?"

    result = with_identifier_parts(text)

    assert result.startswith(text)
    assert result.endswith("max model len paged attention")
    assert with_identifier_parts("How do I install it?") == (
        "How do I install it?"
    )


def test_modes_decide_corpus_and_query_handling() -> None:
    assert corpus_part_types("none") == []
    assert corpus_part_types("query") == []
    assert corpus_part_types("both") == ["code", "doc"]
    assert corpus_part_types("code") == ["code"]

    assert not query_uses_parts("none", "all")
    assert query_uses_parts("query", "doc")
    assert query_uses_parts("both", "doc")
    assert query_uses_parts("code", "code")
    assert query_uses_parts("code", "all")
    assert not query_uses_parts("code", "doc")
