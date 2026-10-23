from src.config import RagConfig, SourceConfig
from src.domain_rules import DomainRules, redact

CV = SourceConfig(
    root="data/raw/cv", include=[".md"],
    private_data=["phone", "email"],
    public_emails=["public@example.com"],
    private_replacement="[private]",
    not_found_message={"es": "No lo sé.", "en": "I don't know."},
)


def test_phones_in_every_format_are_masked() -> None:
    for text in ("(+34) 654705242 (Mobile)", "+34 654 70 52 42 |",
                 "Tel: 654-70-52-42", "654705242"):
        assert "654" not in redact(text, CV), text


def test_years_and_other_numbers_are_kept() -> None:
    text = "2016–2017, 25 piezas, 3326 chars, 20 de enero de 1996, 60 %"
    assert redact(text, CV) == text


def test_only_private_emails_are_masked() -> None:
    text = "old@hotmail.es and [public@example.com](mailto:public@example.com)"
    assert redact(text, CV) == (
        "[private] and [public@example.com](mailto:public@example.com)"
    )


def test_rules_per_domain_and_not_found_message() -> None:
    rules = DomainRules(RagConfig(sources={
        "cv": CV, "vllm": SourceConfig(root="r", include=[".md"]),
    }))
    assert rules.redact("call 654705242", "vllm") == "call 654705242"
    assert rules.redact("call 654705242", "cv") == "call [private]"
    assert rules.redact_all("call 654705242") == "call [private]"
    assert rules.not_found_message("cv", "¿Qué coche tiene?") == "No lo sé."
    assert rules.not_found_message("cv", "What car does he drive?") == (
        "I don't know."
    )
    assert rules.not_found_message("vllm", "anything") is None
