import pytest

from src.ingester import (
    Ingester, chunk_doc_file, chunk_python_file, split_by_size,
)

PYTHON_SOURCE = '''import os

CONSTANT = 1


def small_function(a, b):
    return a + b


class Small:
    value = 3

    def method(self):
        return self.value
'''

DOC_SOURCE = (
    "# Title\n\n" + "Intro paragraph. " * 20 + "\n\n"
    "## Section\n\n" + "Section body text. " * 20 + "\n"
)


def test_unsplit_python_chunks_match_file_offsets() -> None:
    chunks = chunk_python_file("f.py", PYTHON_SOURCE, max_chunk_size=2000)
    units = [c for c in chunks if c.symbols]

    assert {c.symbols.split()[0] for c in units} == {
        "small_function", "Small",
    }
    for chunk in units:
        file_slice = PYTHON_SOURCE[
            chunk.first_character_index:chunk.last_character_index
        ]
        assert file_slice.strip() == chunk.text


def test_doc_chunks_point_inside_their_section() -> None:
    chunks = chunk_doc_file("f.md", DOC_SOURCE, max_chunk_size=2000)

    assert chunks
    for chunk in chunks:
        file_slice = DOC_SOURCE[
            chunk.first_character_index:chunk.last_character_index
        ]
        assert chunk.text in file_slice


def test_split_by_size_respects_limit_and_overlaps() -> None:
    text = "".join(f"line {i:04d}\n" for i in range(300))
    chunks = split_by_size(text, "f.txt", "doc", max_chunk_size=200)

    assert len(chunks) > 1
    assert all(len(c.text) <= 200 for c in chunks)
    for prev, nxt in zip(chunks, chunks[1:]):
        assert nxt.first_character_index < prev.last_character_index


def test_children_reference_valid_parents() -> None:
    ingester = Ingester(repo_root="", code_child_size=50, doc_child_size=50)
    ingester.parent_chunks = chunk_python_file("f.py", PYTHON_SOURCE)

    children = ingester.collect_child_chunks()

    assert len(children) >= len(ingester.parent_chunks)
    for child in children:
        parent = ingester.parent_chunks[child.parent_id]
        assert child.file_path == parent.file_path
        assert (parent.first_character_index
                <= child.first_character_index
                < parent.last_character_index)


@pytest.mark.xfail(
    reason="B7: los chunks enriquecidos (firma de clase + metodo) "
           "desplazan los offsets al subdividirse. Se arregla en Fase 1.",
    strict=True,
)
def test_split_enriched_method_offsets_match_file() -> None:
    body = "".join(f"        x{i} = {i}\n" for i in range(120))
    source = (
        "class Big:\n"
        + "".join(f"    attr{i} = {i}\n" for i in range(60))
        + "\n    def method(self):\n" + body
    )
    chunks = chunk_python_file("f.py", source, max_chunk_size=600)
    method_parts = [c for c in chunks if c.symbols.startswith("method")]

    assert len(method_parts) > 1
    for chunk in method_parts[1:]:
        file_slice = source[
            chunk.first_character_index:chunk.last_character_index
        ]
        assert chunk.text in file_slice
