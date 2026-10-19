from src.generator import (
    NOT_FOUND_MESSAGE, build_messages, clean_output, is_not_found,
)
from src.language import detect_language


def test_messages_number_sources_and_set_language() -> None:
    messages = build_messages(
        "¿Qué endpoint carga un adaptador LoRA?",
        ["--- file: a.md ---\nfirst", "--- file: b.py ---\nsecond"],
        "es",
    )

    assert [m["role"] for m in messages] == ["system", "user"]
    user = messages[1]["content"]
    assert "[1] --- file: a.md ---" in user
    assert "[2] --- file: b.py ---" in user
    assert "Answer in Spanish" in user
    assert NOT_FOUND_MESSAGE in messages[0]["content"]


def test_clean_output_strips_reasoning_traces() -> None:
    assert clean_output("<think>hmm</think>\n\nIt uses X [1].") == (
        "It uses X [1]."
    )
    assert clean_output("stray reasoning\n</think>\n\nAnswer [2].") == (
        "Answer [2]."
    )


def test_not_found_is_normalised_in_both_languages() -> None:
    assert clean_output("Not found in the provided sources.") == (
        NOT_FOUND_MESSAGE
    )
    assert is_not_found("La respuesta no se encuentra en las fuentes.")
    assert is_not_found("No he encontrado información sobre eso.")
    assert not is_not_found("The endpoint is /v1/load_lora_adapter [1].")


def test_question_language_detection() -> None:
    assert detect_language("¿Cómo instalo vLLM en una GPU?") == "es"
    assert detect_language("How do I install vLLM on a GPU?") == "en"
