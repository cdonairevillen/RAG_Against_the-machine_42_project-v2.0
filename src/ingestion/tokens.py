import re
from typing import Any

import bm25s

# How identifiers are handled for BM25:
#   "none"  - text is tokenized as is (`max_model_len` is one token).
#   "query" - identifier parts are added to the query only.
#   "both"  - identifier parts are added to the corpus and the query.
#   "code"  - like "both", but only for code: parts are added to code
#             chunks, and to queries run against the code/general index;
#             doc chunks and doc-index queries stay as they are.
#   "doc"   - the mirror of "code": parts only for doc chunks and for
#             queries run against the doc index.
# The valid values are enforced by RetrievalConfig.code_aware_tokens.


def corpus_part_types(mode: str) -> list[str]:
    """Return the chunk types whose text gets identifier parts."""
    return {
        "both": ["code", "doc"], "code": ["code"], "doc": ["doc"],
    }.get(mode, [])


def query_uses_parts(mode: str, index: str) -> bool:
    """Whether a query against `index` ('all', 'code' or 'doc') gets
    identifier parts under `mode`."""
    if mode in ("query", "both"):
        return True
    if mode == "code":
        return index in ("all", "code")
    return mode == "doc" and index == "doc"


IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
IDENTIFIER_PART = re.compile(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|\d+")
CAMEL_BOUNDARY = re.compile(r"[a-z0-9][A-Z]|[A-Z]{2}[a-z]")
# Mixed-case names that are words, not compound identifiers: splitting
# `vLLM` would add "llm" to nearly every chunk of the corpus.
NOT_COMPOUND = {"vllm"}


def split_identifier(token: str) -> list[str]:
    """Split a snake_case or CamelCase identifier into lowercase parts.

    `max_model_len` -> ['max', 'model', 'len'];
    `PagedAttention` -> ['paged', 'attention'];
    `RMSNorm` -> ['rms', 'norm']. Plain words return [] (nothing to add).

    Args:
        token: A single identifier-like token.

    Returns:
        Lowercase parts of two or more characters, or [] when the token
        is not a compound identifier.
    """
    core = token.strip("_")
    if core.lower() in NOT_COMPOUND:
        return []
    if "_" not in core and not CAMEL_BOUNDARY.search(core):
        return []
    parts = [
        p.lower()
        for piece in core.split("_")
        for p in IDENTIFIER_PART.findall(piece)
    ]
    return [p for p in parts if len(p) > 1]


def with_identifier_parts(text: str) -> str:
    """Append the parts of every compound identifier found in text.

    The original identifiers are kept, so exact matches still count;
    the parts let natural-language words ("max model length") match
    code spellings (`max_model_len`).

    Args:
        text: Chunk text or query.

    Returns:
        text, followed by the identifier parts (if any).
    """
    extras = [
        part
        for match in IDENTIFIER.finditer(text)
        for part in split_identifier(match.group())
    ]
    if not extras:
        return text
    return text + " " + " ".join(extras)


def tokenize(texts: list[str], code_aware: bool,
             show_progress: bool = False) -> Any:
    """Tokenize texts for BM25, optionally adding identifier parts.

    Single entry point for both indexing and querying, so the corpus
    and the queries are always processed the same way.

    Args:
        texts: Texts to tokenize.
        code_aware: Whether to add identifier parts first.
        show_progress: Show bm25s' progress bar.

    Returns:
        bm25s tokenized output.
    """
    if code_aware:
        texts = [with_identifier_parts(t) for t in texts]
    return bm25s.tokenize(texts, stopwords="en", show_progress=show_progress)
