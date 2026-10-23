"""Text of a source file, as the ingester and the datasets see it.

Plain-text files are read as they are. Word and PDF files are converted
to Markdown with Docling, so their chunks get headers and the same
chunkers apply; offsets refer to that Markdown text. The conversion is
deterministic for a pinned Docling version (see uv.lock).
"""
import os
from functools import lru_cache
from typing import Any

CONVERTED_EXTENSIONS = (".docx", ".pdf")


@lru_cache(maxsize=1)
def converter() -> Any:
    """Docling converter, loaded once (its PDF layout model is heavy).

    PDFs use the pypdfium2 backend: docling-parse ships a native library
    that Windows Application Control blocks on some machines.
    """
    # Windows without developer mode cannot create the symlinks of the
    # Hugging Face cache; Docling downloads its layout model through it.
    os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS", "1")
    from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
    from docling.datamodel.base_models import InputFormat
    from docling.document_converter import (
        DocumentConverter, PdfFormatOption,
    )

    return DocumentConverter(format_options={
        InputFormat.PDF: PdfFormatOption(backend=PyPdfiumDocumentBackend),
    })


def read_text(path: str) -> str:
    """Return the indexable text of a file.

    Args:
        path: File to read.

    Returns:
        The file contents, or Docling's Markdown for .docx/.pdf.

    Raises:
        OSError: If the file cannot be read or converted.
    """
    if path.lower().endswith(CONVERTED_EXTENSIONS):
        try:
            document = converter().convert(path).document
        except Exception as exc:
            raise OSError(f"Docling could not convert {path}: {exc}") \
                from exc
        return str(document.export_to_markdown())
    with open(path, "r", encoding="utf-8", errors="ignore") as fh:
        return fh.read()
