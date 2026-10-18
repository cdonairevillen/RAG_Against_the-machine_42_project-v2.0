import uuid
from dataclasses import asdict, dataclass, field
from typing import Any

PARENT = "parent"
CHILD = "child"

# Fixed namespace so chunk ids are stable across re-indexing runs.
CHUNK_NAMESPACE = uuid.UUID("5b3f7c1e-2a4d-4e8b-9c6f-42a6e0b1d7a3")


@dataclass
class Chunk:
    """A contiguous slice of a source file used as retrieval unit.

    Attributes:
        text: Text content of the chunk (used for BM25 indexing).
        file_path: Path relative to the project working directory.
        first_character_index: Inclusive start offset in the file.
        last_character_index: Exclusive end offset in the file.
        chunk_type: One of 'code' or 'doc'.
        symbols: Space-separated AST identifier names extracted from
            the chunk, kept out of the BM25 text.
        parent_id: Id of this chunk's parent, or '' for parents.
        id: Stable identifier (UUID string), assigned by the pipeline.
        domain: Knowledge source the chunk belongs to (e.g. 'vllm').
        level: 'parent' (returned to callers) or 'child' (indexed).
        modality: Kind of content; 'text' for now (images, audio and
            video arrive in Phase 4).
        ordinal: Position within its level. For children it is the row
            of the chunk in the BM25 index.
    """

    text: str
    file_path: str
    first_character_index: int
    last_character_index: int
    chunk_type: str
    symbols: str = field(default="")
    parent_id: str = field(default="")
    id: str = field(default="")
    domain: str = field(default="")
    level: str = field(default="")
    modality: str = field(default="text")
    ordinal: int = field(default=-1)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Chunk":
        """Deserialize from a plain dict, ignoring unknown keys."""
        known = cls.__dataclass_fields__
        return cls(**{k: v for k, v in data.items() if k in known})


def chunk_uuid(domain: str, level: str, file_path: str, first: int,
               last: int, occurrence: int = 0) -> str:
    """Build a deterministic chunk id.

    The same chunk (domain, level, file and range) always gets the same
    id, so ids survive re-indexing. `occurrence` disambiguates chunks
    that share all of those fields.

    Returns:
        UUID string usable as a Qdrant point id.
    """
    key = f"{domain}|{level}|{file_path}|{first}|{last}|{occurrence}"
    return str(uuid.uuid5(CHUNK_NAMESPACE, key))
