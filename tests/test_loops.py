from src.rag.generator import clean_output
from src.rag.loops import cut_loop, find_loop

GOOD = "To serve a model with vLLM:\n\n1. Install vLLM. [1]\n" \
    "2. Start the server with `vllm serve`. [2]\n3. Send a request. [2]\n"
ORDINALS = ["seventh", "eighth", "ninth", "tenth", "eleventh", "twelfth",
            "thirteenth", "fourteenth", "fifteenth", "sixteenth"]


def test_a_repeated_list_item_is_cut_where_it_starts() -> None:
    item = "For more information, refer to the features section. [1]"
    text = GOOD + "".join(f"{n}. {item}\n" for n in range(4, 14))
    assert cut_loop(text) == (GOOD + f"4. {item}").rstrip()


def test_two_alternating_lines_are_a_loop() -> None:
    a = "`--help=serve=ApiServerCount`: shows the API server group. [1]"
    b = "`--help=serve=Headless`: shows the headless mode group. [1]"
    text = GOOD + "".join(f"{n}. {a if n % 2 else b}\n"
                          for n in range(4, 16))
    assert find_loop(text) is not None
    assert cut_loop(text).startswith(GOOD.rstrip())


def test_sentences_with_one_word_changed_are_a_loop() -> None:
    # Phi-4-mini's prose loop: no line breaks, a new ordinal each time.
    text = "vLLM serves models in stages. " + " ".join(
        f"In the {n} stage, the answer is compared with the domain "
        f"threshold, and if it does not pass, plan B is used [1]."
        for n in ORDINALS)
    at = find_loop(text)
    assert at is not None and text[:at].count("stage,") >= 1


def test_the_same_word_over_and_over_is_a_loop() -> None:
    text = GOOD + "step " * 20
    assert cut_loop(text) == GOOD.rstrip()


def test_good_answers_tables_and_code_are_not_loops() -> None:
    table = "| Model | Size |\n|---|---|\n" + "".join(
        f"| Llama-3.1-{n}B | {n}B |\n" for n in range(1, 15))
    code = "```python\n" + "".join(
        f'parser.add_argument("--opt{n}", type=int, default={n})\n'
        for n in range(15)) + "```\n"
    for text in (GOOD, table, code, GOOD + table + code):
        assert find_loop(text) is None and cut_loop(text) == text


def test_clean_output_cuts_a_loop() -> None:
    assert clean_output(GOOD + "step " * 20) == GOOD.rstrip()
