from src.evaluation.gen_bench import cited_files, detect_language, token_f1
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


def test_contains_answer_matches_normalised_spans() -> None:
    from src.evaluation.gen_bench import contains_answer

    assert contains_answer("The Panthers defense gave up 308 points [1].",
                           "308")
    assert contains_answer("Fue en el año 1961, según [2].", "1961")
    assert contains_answer("It was Nicholas E. Golovin.",
                           "Nicholas E. Golovin")
    assert not contains_answer("They allowed 300 points.", "308")
    assert not contains_answer("Anything.", "")


def test_even_sample_is_deterministic_and_spread() -> None:
    from src.evaluation.gen_bench import even_sample

    items = list(range(1190))
    sample = even_sample(items, 300)
    assert len(sample) == 300
    assert sample == even_sample(items, 300)
    assert sample[0] == 0 and sample[-1] >= 1180
    assert even_sample(items, None) == items
    assert even_sample([1, 2], 300) == [1, 2]
