import ast
from typing import Callable

from src.ingestion.chunk import Chunk

OVERLAP_RATIO = 0.20
DEFAULT_CODE_CHUNK_SIZE = 2000
DEFAULT_DOC_CHUNK_SIZE = 2000


def split_by_size(text: str, file_path: str, chunk_type: str,
                  max_chunk_size: int, start_offset: int = 0,
                  symbols: str = "") -> list[Chunk]:
    """Split text into overlapping chunks of at most max_chunk_size.

    Chunks end at a line break and the next one starts at a line break
    inside the last OVERLAP_RATIO * max_chunk_size characters of the
    previous chunk, so pieces never begin mid-line and every character
    is covered (the next start is derived from where the previous chunk
    actually ended). A line longer than the limit is cut by characters.

    Args:
        text: The text to split.
        file_path: Source file path for metadata.
        chunk_type: Label for the chunk type ('code' or 'doc').
        max_chunk_size: Maximum characters per chunk.
        start_offset: Character offset of text[0] in the original file.
        symbols: AST symbol names to store on each produced chunk.

    Returns:
        List of overlapping Chunk objects.
    """
    chunks: list[Chunk] = []
    overlap = int(max_chunk_size * OVERLAP_RATIO)
    pos = 0
    prev_end = 0

    while pos < len(text):
        end = min(pos + max_chunk_size, len(text))
        if end < len(text):
            # Only snap back to a line break that still ends past the
            # previous piece; otherwise a long line ahead would make the
            # loop crawl line by line producing redundant pieces.
            newline = text.rfind("\n", max(pos, prev_end), end)
            if newline > pos:
                end = newline + 1
        prev_end = end
        slice_text = text[pos:end].strip()
        if slice_text:
            chunks.append(Chunk(
                text=slice_text,
                file_path=file_path,
                first_character_index=start_offset + pos,
                last_character_index=start_offset + end,
                chunk_type=chunk_type,
                symbols=symbols,
            ))
        if end >= len(text):
            break
        next_pos = max(end - overlap, pos + 1)
        newline = text.find("\n", next_pos - 1, end - 1)
        pos = newline + 1 if newline != -1 else next_pos

    return chunks


def split_with_header(text: str, header: str, file_path: str,
                      chunk_type: str, max_chunk_size: int,
                      start_offset: int, symbols: str = "") -> list[Chunk]:
    """Split text and prepend a context header to every piece.

    The text is split on its own, so each piece's offsets point at its
    real position in the file; the header (a class signature, a table's
    section title) is then added to the piece's text only. Splitting the
    header together with the text would shift every offset by the
    header's length and leave the context on the first piece alone.

    Args:
        text: Raw file text to split (as it appears in the file).
        header: Context prepended to each piece's text.
        file_path: Source file path for metadata.
        chunk_type: Label for the chunk type ('code' or 'doc').
        max_chunk_size: Maximum characters per piece, header included.
        start_offset: Character offset of text[0] in the original file.
        symbols: AST symbol names to store on each piece.

    Returns:
        List of overlapping Chunk objects, each starting with header.
    """
    body_size = max(max_chunk_size - len(header), max_chunk_size // 2)
    pieces = split_by_size(
        text, file_path, chunk_type, body_size, start_offset, symbols
    )
    for piece in pieces:
        piece.text = header + piece.text
    return pieces


def extract_symbols(node: ast.AST) -> str:
    """Extract identifier names from an AST node.

    Collects class names, method names and attribute names defined
    within the node. These are stored in Chunk.symbols separately
    from the BM25 corpus text so they do not inflate chunk length.

    Args:
        node: Top-level AST node (FunctionDef, AsyncFunctionDef,
            ClassDef).

    Returns:
        Space-separated symbol names, or empty string if none found.
    """
    names: list[str] = []

    if isinstance(node, ast.ClassDef):
        names.append(node.name)
        for child in ast.walk(node):
            if isinstance(
                child, (ast.FunctionDef, ast.AsyncFunctionDef)
            ):
                names.append(child.name)
            if isinstance(child, ast.Assign):
                for target in child.targets:
                    if isinstance(target, ast.Name):
                        names.append(target.id)
            if isinstance(child, ast.AnnAssign):
                if isinstance(child.target, ast.Name):
                    names.append(child.target.id)

    elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        names.append(node.name)
        for arg in node.args.args:
            names.append(arg.arg)

    if not names:
        return ""

    return " ".join(dict.fromkeys(names))


def chunk_python_file(file_path: str, content: str,
                      max_chunk_size: int = DEFAULT_CODE_CHUNK_SIZE
                      ) -> list[Chunk]:
    """Chunk a Python file using the AST to keep logical units intact.

    AST symbol names are stored in Chunk.symbols, not Chunk.text, so
    they do not affect BM25 length normalization. The Retriever uses
    them for query expansion at search time.

    Args:
        file_path: Relative path used for chunk metadata.
        content: Full text content of the Python file.
        max_chunk_size: Maximum characters per chunk.

    Returns:
        List of Chunk objects with symbols metadata.
    """
    chunks: list[Chunk] = []

    try:
        tree = ast.parse(content)
    except SyntaxError:
        return split_by_size(content, file_path, "code", max_chunk_size)

    lines = content.splitlines(keepends=True)
    line_offsets: list[int] = []
    offset = 0
    for line in lines:
        line_offsets.append(offset)
        offset += len(line)
    line_offsets.append(offset)

    def node_char_range(node: ast.AST) -> tuple[int, int]:
        start_line = getattr(node, "lineno", 1) - 1
        end_line = getattr(node, "end_lineno", start_line)
        first = line_offsets[start_line]
        last = (
            line_offsets[end_line + 1]
            if end_line + 1 < len(line_offsets)
            else len(content)
        )
        return first, last

    covered: list[tuple[int, int]] = []

    for node in ast.iter_child_nodes(tree):
        if not isinstance(
            node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        ):
            continue

        first, last = node_char_range(node)
        node_text = content[first:last]
        symbols = extract_symbols(node)
        covered.append((first, last))

        if len(node_text) <= max_chunk_size:
            chunks.append(Chunk(
                text=node_text.strip(),
                file_path=file_path,
                first_character_index=first,
                last_character_index=last,
                chunk_type="code",
                symbols=symbols,
            ))
        elif isinstance(node, ast.ClassDef):
            class_sig = node_text.split("\n")[0]
            method_covered: list[tuple[int, int]] = []

            for child in ast.iter_child_nodes(node):
                if not isinstance(
                    child, (ast.FunctionDef, ast.AsyncFunctionDef)
                ):
                    continue
                c_first, c_last = node_char_range(child)
                method_text = content[c_first:c_last]
                method_symbols = extract_symbols(child)
                method_covered.append((c_first, c_last))
                enriched = (
                    class_sig + "\n    ...\n" + method_text.strip()
                )

                if len(enriched) <= max_chunk_size:
                    chunks.append(Chunk(
                        text=enriched,
                        file_path=file_path,
                        first_character_index=c_first,
                        last_character_index=c_last,
                        chunk_type="code",
                        symbols=method_symbols,
                    ))
                else:
                    chunks.extend(split_with_header(
                        method_text, class_sig + "\n    ...\n",
                        file_path, "code", max_chunk_size, c_first,
                        method_symbols,
                    ))

            if not method_covered:
                chunks.extend(split_by_size(
                    node_text, file_path, "code",
                    max_chunk_size, first, symbols,
                ))
        else:
            chunks.extend(
                split_by_size(
                    node_text, file_path, "code",
                    max_chunk_size, first, symbols,
                )
            )

    covered_sorted = sorted(covered)
    preamble_parts: list[str] = []
    preamble_start = 0

    for seg_start, seg_end in covered_sorted:
        gap = content[preamble_start:seg_start].strip()
        if gap:
            preamble_parts.append(gap)
        preamble_start = seg_end

    tail = content[preamble_start:].strip()
    if tail:
        preamble_parts.append(tail)

    preamble = "\n\n".join(preamble_parts).strip()
    if preamble:
        chunks.extend(
            split_by_size(preamble, file_path, "code", max_chunk_size)
        )

    return chunks


def chunk_text_file(file_path: str, content: str,
                    max_chunk_size: int = DEFAULT_DOC_CHUNK_SIZE
                    ) -> list[Chunk]:
    """Fallback chunker for plain text and unrecognised file types.

    Args:
        file_path: Relative path used for chunk metadata.
        content: Full text content of the file.
        max_chunk_size: Maximum characters per chunk.

    Returns:
        List of Chunk objects with overlap.
    """
    return split_by_size(content, file_path, "doc", max_chunk_size)


def markdown_sections(content: str) -> list[tuple[int, int, str]]:
    """Split Markdown into header-delimited sections.

    A section starts at a header line ('#...') and runs until the next
    one. Lines inside fenced code blocks (``` or ~~~) are never headers,
    so shell comments in examples do not split a section.

    Args:
        content: Full text of the file.

    Returns:
        (start, end, title) per section, covering the whole file. The
        title is the header line, or '' for text before the first one.
    """
    sections: list[tuple[int, int, str]] = []
    start, title, offset = 0, "", 0
    fence = ""
    for line in content.splitlines(keepends=True):
        stripped = line.lstrip()
        marker = stripped[:3]
        if marker in ("```", "~~~"):
            fence = "" if fence == marker else (fence or marker)
        elif not fence and line.startswith("#") and offset > start:
            sections.append((start, offset, title))
            start, title = offset, line.strip()
        elif not fence and line.startswith("#"):
            title = line.strip()
        offset += len(line)
    if offset > start:
        sections.append((start, offset, title))
    return sections


def chunk_markdown_packed(file_path: str, content: str,
                          max_chunk_size: int = DEFAULT_DOC_CHUNK_SIZE
                          ) -> list[Chunk]:
    """Chunk Markdown by headers, packing consecutive sections.

    Sections start at header lines (see markdown_sections()) and are
    accumulated until the next one would exceed max_chunk_size, so a
    chunk holds as much related context as fits. Consecutive chunks
    overlap by whole sections: a new chunk repeats the trailing sections
    of the previous one that fit in OVERLAP_RATIO of the size, so an
    answer near a boundary is not cut in two and every chunk starts at a
    header. Tables stay with the text of their section. A section larger
    than the limit is split on its own, every piece keeping the section
    title as a header.

    Args:
        file_path: Relative path used for chunk metadata.
        content: Full text content of the file.
        max_chunk_size: Maximum characters per chunk.

    Returns:
        List of Chunk objects with exact file offsets.
    """
    chunks: list[Chunk] = []
    pack: list[tuple[int, int]] = []
    overlap_budget = int(max_chunk_size * OVERLAP_RATIO)

    def flush() -> None:
        start, end = pack[0][0], pack[-1][1]
        text = content[start:end]
        if text.strip():
            lead = len(text) - len(text.lstrip())
            chunks.append(Chunk(
                text=text.strip(),
                file_path=file_path,
                first_character_index=start + lead,
                last_character_index=end,
                chunk_type="doc",
            ))

    def overlap_tail() -> list[tuple[int, int]]:
        tail: list[tuple[int, int]] = []
        for section in reversed(pack[1:]):
            if pack[-1][1] - section[0] > overlap_budget:
                break
            tail.insert(0, section)
        return tail

    for start, end, title in markdown_sections(content):
        if end - start > max_chunk_size:
            if pack:
                flush()
                pack = []
            body_start = start
            if title:
                body_start += len(content[start:end].split("\n", 1)[0])
            chunks.extend(split_with_header(
                content[body_start:end],
                title + "\n" if title else "",
                file_path, "doc", max_chunk_size, body_start,
            ))
            continue
        if pack and end - pack[0][0] > max_chunk_size:
            flush()
            pack = overlap_tail()
            while pack and end - pack[0][0] > max_chunk_size:
                pack.pop(0)
        pack.append((start, end))

    if pack:
        flush()
    return chunks


ChunkerFn = Callable[[str, str, int], list[Chunk]]

# Chunkers selectable from rag.toml, by name. Every chunker receives
# (file_path, content, max_chunk_size) and returns parent chunks.
CHUNKERS: dict[str, ChunkerFn] = {
    "python_ast": chunk_python_file,
    "markdown_headers_packed": chunk_markdown_packed,
    "size": chunk_text_file,
}


def get_chunker(name: str) -> ChunkerFn:
    """Return a registered chunker by name.

    Raises:
        KeyError: If no chunker is registered under that name.
    """
    if name not in CHUNKERS:
        known = ", ".join(sorted(CHUNKERS))
        raise KeyError(f"Unknown chunker '{name}' (available: {known})")
    return CHUNKERS[name]
