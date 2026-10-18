import json
import os
import shutil
from collections import Counter
from pathlib import Path
from typing import Iterator, Optional

import bm25s
from tqdm import tqdm

from src.config import ChunkingConfig, SourceConfig
from src.ingestion.chunk import CHILD, PARENT, Chunk, chunk_uuid
from src.ingestion.chunkers import get_chunker, split_by_size

INDEX_DIR = "bm25_index"
INDEX_CODE_DIR = "bm25_code_index"
INDEX_DOC_DIR = "bm25_doc_index"
MANIFEST_FILE = "manifest.json"


def walk_source(source: SourceConfig) -> Iterator[str]:
    """Yield the paths of every indexable file of a source.

    Args:
        source: Source configuration (root, extensions, excluded dirs).

    Yields:
        File paths under source.root passing the extension and
        directory filters, in a deterministic os.walk order.
    """
    include = set(source.include)
    exclude = set(source.exclude_dirs)
    for dirpath, dirnames, filenames in os.walk(source.root):
        dirnames[:] = [
            d for d in dirnames
            if d not in exclude and not d.startswith(".")
        ]
        for filename in filenames:
            _, ext = os.path.splitext(filename)
            if ext not in include:
                continue
            abs_path = os.path.join(dirpath, filename)
            rel_parts = set(
                os.path.relpath(abs_path, source.root)
                .replace("\\", "/")
                .split("/")
            )
            if not rel_parts.intersection(exclude):
                yield abs_path


def assign_ids(chunks: list[Chunk], domain: str, level: str) -> None:
    """Set domain, level, ordinal and a stable id on each chunk."""
    seen: Counter[tuple[str, int, int]] = Counter()
    for ordinal, chunk in enumerate(chunks):
        key = (
            chunk.file_path,
            chunk.first_character_index,
            chunk.last_character_index,
        )
        chunk.domain = domain
        chunk.level = level
        chunk.ordinal = ordinal
        chunk.id = chunk_uuid(domain, level, *key, seen[key])
        seen[key] += 1


def normalise_for_bm25(text: str) -> str:
    """Lowercase, turn '_' and '-' into spaces and collapse whitespace."""
    text = text.lower().replace("_", " ").replace("-", " ")
    return " ".join(text.split())


def build_bm25(chunks: list[Chunk], label: str = "corpus") -> bm25s.BM25:
    """Tokenize chunks and fit a BM25 model.

    Each chunk's text is prefixed with its normalised file path (without
    extension) so the filename contributes to ranking.

    Args:
        chunks: Chunks to index, in BM25 row order.
        label: Human-readable label for progress output.

    Returns:
        A fitted bm25s.BM25 instance.
    """
    corpus = [
        normalise_for_bm25(str(Path(c.file_path).with_suffix("")))
        + " " + c.text
        for c in chunks
    ]
    print(f"Tokenizing {label} ({len(corpus)} chunks)...")
    tokenized = bm25s.tokenize(corpus, stopwords="en", show_progress=True)
    retriever = bm25s.BM25()
    retriever.index(tokenized, show_progress=True)
    return retriever


class Ingester:
    """Chunks a knowledge source and builds its BM25 indices.

    Parents (returned to callers) and children (indexed by BM25) are
    produced here. Persistence is split in two: chunk records go to the
    ChunkStore (Qdrant) and the BM25 indices to disk, linked by the
    children's ordinal (= BM25 row).

    Usage:
        ingester = Ingester("vllm", config.source("vllm"), config.chunking)
        ingester.build()
        ingester.save_bm25("data/processed")
        store.replace("vllm", ingester.all_chunks())
    """

    def __init__(self, domain: str, source: SourceConfig,
                 chunking: ChunkingConfig) -> None:
        self.domain = domain
        self.source = source
        self.chunking = chunking

        self.parent_chunks: list[Chunk] = []
        self.chunks: list[Chunk] = []

        self.bm25: Optional[bm25s.BM25] = None
        self.bm25_code: Optional[bm25s.BM25] = None
        self.bm25_doc: Optional[bm25s.BM25] = None

    def build(self) -> None:
        """Chunk every file of the source and fit the BM25 indices."""
        self.parent_chunks = self.collect_chunks()
        assign_ids(self.parent_chunks, self.domain, PARENT)
        self.chunks = self.collect_child_chunks()
        assign_ids(self.chunks, self.domain, CHILD)

        self.bm25 = build_bm25(self.chunks)
        code = [c for c in self.chunks if c.chunk_type == "code"]
        doc = [c for c in self.chunks if c.chunk_type == "doc"]
        # A source may have no code (e.g. a CV) or no docs: skip the
        # per-type index instead of fitting BM25 on an empty corpus.
        self.bm25_code = build_bm25(code, "code corpus") if code else None
        self.bm25_doc = build_bm25(doc, "doc corpus") if doc else None

    def all_chunks(self) -> list[Chunk]:
        """Return parents followed by children, ready for the store."""
        return self.parent_chunks + self.chunks

    def collect_chunks(self) -> list[Chunk]:
        """Walk the source and produce all parent chunks."""
        all_chunks: list[Chunk] = []
        files = list(walk_source(self.source))

        for abs_path in tqdm(files, desc=f"Chunking {self.domain}"):
            rel_path = os.path.relpath(abs_path).replace("\\", "/")
            try:
                with open(
                    abs_path, "r", encoding="utf-8", errors="ignore"
                ) as fh:
                    content = fh.read()
            except OSError:
                continue

            if not content.strip():
                continue

            _, ext = os.path.splitext(abs_path)
            chunk_type = self.source.chunk_type_for(ext)
            max_size = (
                self.chunking.code_chunk_size if chunk_type == "code"
                else self.chunking.doc_chunk_size
            )
            chunker = get_chunker(self.source.chunker_for(ext))
            file_chunks = chunker(rel_path, content, max_size)
            for chunk in file_chunks:
                chunk.chunk_type = chunk_type
            all_chunks.extend(file_chunks)

        return all_chunks

    def collect_child_chunks(self) -> list[Chunk]:
        """Generate child chunks from parent chunks.

        Parents under the child size threshold become single-child
        chunks. Larger parents are split with split_by_size(), and
        table continuation chunks get the table header re-attached
        for BM25 context.

        Returns:
            List of child Chunk objects with parent_id set.
        """
        children: list[Chunk] = []

        for parent in self.parent_chunks:
            child_size = (
                self.chunking.code_child_size
                if parent.chunk_type == "code"
                else self.chunking.doc_child_size
            )

            if len(parent.text) <= child_size:
                children.append(Chunk(
                    text=parent.text,
                    file_path=parent.file_path,
                    first_character_index=parent.first_character_index,
                    last_character_index=parent.last_character_index,
                    chunk_type=parent.chunk_type,
                    symbols=parent.symbols,
                    parent_id=parent.id,
                ))
                continue

            first_line = (
                parent.text.split("\n")[0] if parent.text else ""
            )
            is_table = first_line.strip().startswith("|")

            table_header = ""
            if is_table:
                table_lines = parent.text.split("\n")
                header_lines = [
                    line for line in table_lines[:3]
                    if line.strip().startswith("|")
                ]
                table_header = (
                    "\n".join(header_lines) + "\n" if header_lines else ""
                )

            sub_chunks = split_by_size(
                parent.text,
                parent.file_path,
                parent.chunk_type,
                child_size,
                parent.first_character_index,
                parent.symbols,
            )
            for i, sub in enumerate(sub_chunks):
                if is_table and i > 0 and table_header:
                    sub.text = table_header + sub.text
                sub.parent_id = parent.id
                children.append(sub)

        return children

    def save_bm25(self, processed_dir: str) -> str:
        """Persist the BM25 indices and a manifest for this domain.

        Args:
            processed_dir: Root directory for processed artefacts.

        Returns:
            The domain directory that was written.

        Raises:
            RuntimeError: If build() has not been called.
        """
        if self.bm25 is None:
            raise RuntimeError("Call build() before save_bm25().")

        domain_dir = os.path.join(processed_dir, self.domain)
        if os.path.isdir(domain_dir):
            shutil.rmtree(domain_dir)
        for name, index in ((INDEX_DIR, self.bm25),
                            (INDEX_CODE_DIR, self.bm25_code),
                            (INDEX_DOC_DIR, self.bm25_doc)):
            if index is None:
                continue
            path = os.path.join(domain_dir, name)
            os.makedirs(path, exist_ok=True)
            index.save(path)

        manifest = {
            "domain": self.domain,
            "parents": len(self.parent_chunks),
            "children": len(self.chunks),
        }
        with open(os.path.join(domain_dir, MANIFEST_FILE), "w",
                  encoding="utf-8", newline="\n") as fh:
            json.dump(manifest, fh, indent=2)
        return domain_dir


def load_bm25(processed_dir: str, domain: str
              ) -> tuple[bm25s.BM25, Optional[bm25s.BM25],
                         Optional[bm25s.BM25], dict]:
    """Load a domain's BM25 indices and manifest from disk.

    Returns:
        (general, code, doc, manifest). The code or doc index is None
        when the source had no chunks of that type.

    Raises:
        FileNotFoundError: If the domain has not been indexed.
    """
    domain_dir = os.path.join(processed_dir, domain)
    manifest_path = os.path.join(domain_dir, MANIFEST_FILE)
    if not os.path.isfile(manifest_path):
        raise FileNotFoundError(
            f"No BM25 index for '{domain}' in {processed_dir}. "
            f"Run 'make index' first."
        )
    with open(manifest_path, "r", encoding="utf-8") as fh:
        manifest = json.load(fh)
    general, code, doc = (
        bm25s.BM25.load(os.path.join(domain_dir, name), load_corpus=False)
        if os.path.isdir(os.path.join(domain_dir, name)) else None
        for name in (INDEX_DIR, INDEX_CODE_DIR, INDEX_DOC_DIR)
    )
    if general is None:
        raise FileNotFoundError(f"Missing {INDEX_DIR} for '{domain}'.")
    return general, code, doc, manifest
