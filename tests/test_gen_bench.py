from src.gen_bench import cited_files, detect_language, token_f1
from src.models import MinimalSource


def test_token_f1_squad_style() -> None:
    assert token_f1("The /v1/load_lora_adapter endpoint",
                    "the /v1/load_lora_adapter endpoint") == 1.0
    assert token_f1("completely different", "nothing shared") == 0.0
    partial = token_f1("uses the PagedAttention kernel",
                       "PagedAttention kernel")
    assert 0.0 < partial < 1.0


def test_detect_language() -> None:
    assert detect_language("The endpoint is used to load the adapter.") == "en"
    assert detect_language(
        "El endpoint se usa para cargar el adaptador de la red."
    ) == "es"
    assert detect_language("/v1/load_lora_adapter") == "?"


def test_cited_files_by_name_and_index() -> None:
    sources = [
        MinimalSource(file_path="data/raw/vllm/docs/lora.md",
                      first_character_index=0, last_character_index=1),
        MinimalSource(file_path="data/raw/vllm/vllm/x.py",
                      first_character_index=0, last_character_index=1),
    ]

    assert cited_files("Source: vllm-0.10.1/docs/lora.md.", sources) == {
        "lora.md"
    }
    assert cited_files("It does X [2].", sources) == {"x.py"}
    assert cited_files("No citation here [9].", sources) == set()
