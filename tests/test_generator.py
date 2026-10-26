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


def test_strip_echo_keeps_only_the_answer() -> None:
    from src.rag.generator import strip_echo

    copied = ("[1] --- file: README.md ---\nA RAG system.\n\n"
              "ANSWER: It is a multi-domain RAG [1].")
    assert strip_echo(copied) == "It is a multi-domain RAG [1]."
    assert strip_echo("It uses Qwen [1]. The answer is in English, "
                      "citing the sources by number.") == "It uses Qwen [1]."
    assert strip_echo("A normal answer [2].") == "A normal answer [2]."
    # The instruction inside a sentence that goes on is not removed: the
    # answer would be lost with it (an empty answer in the web).
    framed = ("The answer in Spanish, citing the sources by number, is: "
              "[1] RAG.")
    assert strip_echo(framed) == framed


def test_strip_echo_handles_copied_source_headers() -> None:
    from src.rag.generator import strip_echo

    # An answer that opens with a copied source keeps its text, cited.
    opened = ("[2] --- file: data/raw/xquad/en/Kenya.md ---\n"
              "The Ministry of Gender was created in 2008.")
    assert strip_echo(opened) == \
        "The Ministry of Gender was created in 2008. [2]"
    # Headers used as citations become "[n] (path)".
    listed = "See the sources:\n\n[1] --- file: docs/a.md ---"
    assert strip_echo(listed) == "See the sources:\n\n[1] (docs/a.md)"


class CharTokenizer:
    """One token per character, enough for the echo criterion."""

    def decode(self, ids, skip_special_tokens: bool = False) -> str:
        return "".join(chr(int(i)) for i in ids)


def run_echo_start(text: str) -> tuple[bool, bool]:
    """Feed `text` to EchoStart one character at a time: (stopped, hit)."""
    import torch

    from src.rag.generator import EchoStart

    criterion = EchoStart(CharTokenizer(), prompt_length=2)
    ids = [ord("p"), ord("p")]
    for char in text:
        ids.append(ord(char))
        if bool(criterion(torch.tensor([ids]), None)[0]):
            return True, criterion.hit
    return False, criterion.hit


def test_echo_start_stops_when_a_second_source_is_copied() -> None:
    # Phi-4-mini: copies one source after another.
    assert run_echo_start("[1] --- file: README.md ---\nA RAG.\n"
                          "[2] --- file: docs/ROADMAP.md ---\n") == \
        (True, True)
    assert run_echo_start("[1] --- file: a.md ---\nText. QUESTION: what?") \
        == (True, True)


def test_echo_start_leaves_a_single_copied_header() -> None:
    # The 0.6B copies one header and answers: strip_echo recovers it.
    assert run_echo_start("[1] --- file: README.md ---\nA RAG.") == \
        (False, False)


def test_echo_start_lets_answers_through() -> None:
    # A citation first, or an echo-like text after the opening, is fine.
    assert run_echo_start("[1] says the default is 8.") == (False, False)
    assert run_echo_start("The answer is long enough to pass the check, "
                          "then [1] --- file: x [2] --- file: y") == \
        (False, False)


def test_echo_started_reads_the_criterion() -> None:
    from src.rag.generator import EchoStart, echo_started

    criterion = EchoStart(CharTokenizer(), prompt_length=0)
    kwargs = {"stopping_criteria": [criterion]}
    assert not echo_started(kwargs)
    assert not echo_started(kwargs, hit=False)
    criterion.started = True
    assert echo_started(kwargs, hit=False) and not echo_started(kwargs)
    criterion.hit = True
    assert echo_started(kwargs)
    assert not echo_started({})
