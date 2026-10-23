from typing import Any

import pytest

from src.rag.sources import xquad

ROWS = [
    {"id": "q1", "title": "Apollo_program", "context": "First paragraph.",
     "question": "Which?", "answer": "First", "answer_start": 0},
    {"id": "q2", "title": "Apollo_program", "context": "Second one here.",
     "question": "Where?", "answer": "here", "answer_start": 11},
    {"id": "q3", "title": "Warsaw", "context": "Capital of Poland.",
     "question": "What?", "answer": "Poland", "answer_start": 11},
]


@pytest.fixture
def built(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> Any:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(xquad, "load_rows", lambda lang: ROWS)
    return xquad.build_language("en")


def test_one_file_per_article_with_title_header(built: Any) -> None:
    assert built == (2, 3)
    with open("data/raw/xquad/en/Apollo_program.md", encoding="utf-8",
              newline="") as fh:
        assert fh.read() == (
            "# Apollo program\n\nFirst paragraph.\n\nSecond one here.\n"
        )


def test_sources_are_answer_spans_with_forward_slashes(built: Any) -> None:
    assert xquad.verify_sources("en") == 3


def test_load_rows_rebases_offsets_of_stripped_paragraphs(
        tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    pq = pytest.importorskip("pyarrow.parquet")
    import json

    import pyarrow as pa

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(xquad, "fetch", lambda url, path: None)
    (tmp_path / xquad.DOWNLOAD_DIR).mkdir(parents=True)
    # GitHub keeps the leading space; Hugging Face strips it but keeps
    # the original offset (the Apollo_program case).
    original = {"data": [{"title": "T", "paragraphs": [{
        "context": " Golovin led it.", "qas": [{"id": "q"}]}]}]}
    with open(f"{xquad.DOWNLOAD_DIR}/xquad.en.json", "w",
              encoding="utf-8") as fh:
        json.dump(original, fh)
    pq.write_table(pa.Table.from_pylist([{
        "id": "q", "context": "Golovin led it.", "question": "Who?",
        "answers": {"text": ["Golovin"], "answer_start": [1]},
    }]), f"{xquad.DOWNLOAD_DIR}/xquad.en.parquet")

    [row] = xquad.load_rows("en")
    assert row["answer_start"] == 0
    assert row["title"] == "T"
