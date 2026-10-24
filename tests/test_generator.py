from src.rag.generator import (
    NOT_FOUND_MESSAGE, build_messages, clean_output, is_not_found,
)
from src.rag.language import detect_language


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


def test_domain_rules_extend_the_system_prompt() -> None:
    plain = build_messages("q", ["--- file: a.md ---\nx"], "en")
    ruled = build_messages("q", ["--- file: a.md ---\nx"], "en",
                           "7. Answer in the third person.")
    assert ruled[0]["content"].startswith(plain[0]["content"])
    assert ruled[0]["content"].endswith("7. Answer in the third person.")
    assert build_messages("q", [], "en", "  ")[0] == plain[0]


def test_not_found_message_follows_the_question_language() -> None:
    from src.rag.generator import NOT_FOUND_MESSAGE, not_found_for

    assert not_found_for("How do I enable LoRA?") == NOT_FOUND_MESSAGE
    spanish = not_found_for("Háblame de su trabajo actual")
    assert spanish.startswith("No se encuentra") and is_not_found(spanish)


def test_spanish_not_available_refusal_is_detected() -> None:
    assert is_not_found("La información sobre donde trabaja ahora no está "
                        "disponible en los fuentes proporcionadas.")


def test_short_keyword_questions_get_a_language() -> None:
    # Seen in the web: "Experiencia laboral de Chrystian" had no marker,
    # so no answer language was requested and Qwen3-1.7B wrote English.
    for question in ("Experiencia laboral de Chrystian", "Aficiones y gustos",
                     "Proyectos en 42 Madrid", "Música favorita"):
        assert detect_language(question) == "es", question
    for question in ("Work experience of Chrystian", "LoRA adapters in vLLM",
                     "Who is Chrystian?"):
        assert detect_language(question) == "en", question
