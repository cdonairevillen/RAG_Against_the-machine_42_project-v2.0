from src.config import ChunkingConfig, SourceConfig
from src.ingestion.chunk import PARENT, chunk_uuid
from src.ingestion.chunkers import (
    chunk_markdown_packed, chunk_python_file,
    markdown_sections, split_by_size,
)
from src.ingestion.pipeline import Ingester, assign_ids

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
    chunks = chunk_markdown_packed("f.md", DOC_SOURCE, max_chunk_size=2000)

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
    source = SourceConfig(root="", include=[".py"], code_extensions=[".py"])
    chunking = ChunkingConfig(code_child_size=50, doc_child_size=50)
    ingester = Ingester("test", source, chunking)
    ingester.parent_chunks = chunk_python_file("f.py", PYTHON_SOURCE)
    assign_ids(ingester.parent_chunks, "test", PARENT)
    parents = {p.id: p for p in ingester.parent_chunks}

    children = ingester.collect_child_chunks()

    assert len(children) >= len(ingester.parent_chunks)
    for child in children:
        parent = parents[child.parent_id]
        assert child.file_path == parent.file_path
        assert (parent.first_character_index
                <= child.first_character_index
                < parent.last_character_index)


def test_split_enriched_method_offsets_match_file() -> None:
    """B7: every piece of a split method keeps the class header in its
    text and points at its real position in the file."""
    body = "".join(f"        x{i} = {i}\n" for i in range(120))
    source = (
        "class Big:\n"
        + "".join(f"    attr{i} = {i}\n" for i in range(60))
        + "\n    def method(self):\n" + body
    )
    header = "class Big:\n    ...\n"
    chunks = chunk_python_file("f.py", source, max_chunk_size=600)
    method_parts = [c for c in chunks if c.symbols.startswith("method")]

    assert len(method_parts) > 1
    for chunk in method_parts:
        assert chunk.text.startswith(header)
        assert len(chunk.text) <= 600
        file_slice = source[
            chunk.first_character_index:chunk.last_character_index
        ]
        assert chunk.text[len(header):] in file_slice


def test_split_table_offsets_match_file() -> None:
    """B7: every piece of a split table keeps its section title and
    points at its real position in the file."""
    rows = "".join(f"| row {i} | value {i} |\n" for i in range(80))
    source = (
        "# Intro\n\n" + "Text. " * 40 + "\n\n## Table\n\n"
        + "| name | value |\n|---|---|\n" + rows
    )
    title = "## Table\n"
    chunks = chunk_markdown_packed("f.md", source, max_chunk_size=500)
    table_parts = [c for c in chunks if c.text.startswith(title)]

    assert len(table_parts) > 1
    assert table_parts[0].text.startswith(title + "| name | value |")
    for chunk in table_parts:
        file_slice = source[
            chunk.first_character_index:chunk.last_character_index
        ]
        assert chunk.text[len(title):] in file_slice


def test_packed_markdown_packs_sections_with_exact_offsets() -> None:
    source = "".join(
        f"## Section {i}\n\n" + f"Body of section {i}. " * 8 + "\n\n"
        for i in range(12)
    )
    chunks = chunk_markdown_packed("f.md", source, max_chunk_size=600)

    assert 1 < len(chunks) < 12
    for chunk in chunks:
        assert len(chunk.text) <= 600
        assert chunk.text.startswith("## Section")
        assert source[
            chunk.first_character_index:chunk.last_character_index
        ].strip() == chunk.text


def test_packed_markdown_overlaps_consecutive_chunks() -> None:
    # ~45-char sections: several fit in the 100-char overlap budget, so
    # consecutive chunks must repeat whole sections.
    source = "".join(
        f"## Section {i}\n\nLine {i} of the body.\n\n" for i in range(30)
    )
    chunks = chunk_markdown_packed("f.md", source, 500)

    assert len(chunks) > 1
    for prev, nxt in zip(chunks, chunks[1:]):
        assert nxt.first_character_index < prev.last_character_index
        assert nxt.text.startswith("## Section")
        assert len(nxt.text) <= 500
        assert source[
            nxt.first_character_index:nxt.last_character_index
        ].strip() == nxt.text


def test_packed_markdown_ignores_headers_inside_code_fences() -> None:
    source = (
        "## Install\n\n```bash\n# install the package\npip install vllm\n"
        "```\n\nDone.\n"
    )
    sections = markdown_sections(source)

    assert [title for _, _, title in sections] == ["## Install"]


def test_packed_markdown_splits_oversized_section_keeping_title() -> None:
    source = "## Huge\n\n" + "".join(
        f"Sentence number {i} of a very long section.\n" for i in range(80)
    )
    chunks = chunk_markdown_packed("f.md", source, max_chunk_size=500)

    assert len(chunks) > 1
    for chunk in chunks:
        assert chunk.text.startswith("## Huge\n")
        assert len(chunk.text) <= 500
        assert chunk.text[len("## Huge\n"):] in source[
            chunk.first_character_index:chunk.last_character_index
        ]


def test_chunk_ids_are_stable_and_disambiguated() -> None:
    first = chunk_python_file("f.py", PYTHON_SOURCE)
    again = chunk_python_file("f.py", PYTHON_SOURCE)
    assign_ids(first, "vllm", PARENT)
    assign_ids(again, "vllm", PARENT)

    assert [c.id for c in first] == [c.id for c in again]
    assert len({c.id for c in first}) == len(first)
    assert chunk_uuid("vllm", PARENT, "f.py", 0, 10, 0) != chunk_uuid(
        "vllm", PARENT, "f.py", 0, 10, 1
    )
