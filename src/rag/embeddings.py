import re
from dataclasses import dataclass
from typing import Any, Optional

import numpy as np


@dataclass(frozen=True)
class EmbeddingPreset:
    """How a model family expects queries and documents to be written.

    Attributes:
        query_prefix: Text prepended to queries.
        doc_prefix: Text prepended to documents.
        query_prompt_name: sentence-transformers prompt name used for
            queries (for models that declare their prompts).
    """

    query_prefix: str = ""
    doc_prefix: str = ""
    query_prompt_name: Optional[str] = None


# Taken from each model card (verified on Hugging Face):
#   E5:     every input starts with "query: " or "passage: ".
#   Qwen3:  config declares a "query" prompt and no document prompt.
#   bge-m3: dense retrieval without instructions.
PRESETS: dict[str, EmbeddingPreset] = {
    "intfloat/multilingual-e5-small": EmbeddingPreset("query: ", "passage: "),
    "intfloat/multilingual-e5-base": EmbeddingPreset("query: ", "passage: "),
    "BAAI/bge-m3": EmbeddingPreset(),
    "Qwen/Qwen3-Embedding-0.6B": EmbeddingPreset(query_prompt_name="query"),
}


def vector_name(model: str) -> str:
    """Return the Qdrant named-vector key for a model id."""
    return re.sub(r"[^a-z0-9]+", "_", model.lower()).strip("_")


def document_text(file_path: str, text: str) -> str:
    """Text embedded for a chunk: its file path, then its content."""
    return f"{file_path}\n{text}"


class Embedder:
    """Dense embeddings for documents and queries, with the right prompts.

    The same model and normalisation are used for both sides, which is
    what v1 got wrong: its document and query vectors were matched by
    index position across two different lists.
    """

    def __init__(self, model: str, device: str = "cpu",
                 batch_size: int = 64,
                 preset: Optional[EmbeddingPreset] = None) -> None:
        from sentence_transformers import SentenceTransformer

        self.model_name = model
        self.preset = preset or PRESETS.get(model, EmbeddingPreset())
        self.batch_size = batch_size
        self.model = SentenceTransformer(model, device=device)

    def encode_documents(self, texts: list[str],
                         show_progress: bool = True) -> np.ndarray:
        """Embed documents (L2-normalised float32 matrix)."""
        prefixed = [self.preset.doc_prefix + t for t in texts]
        vectors: Any = self.model.encode(
            prefixed, batch_size=self.batch_size,
            normalize_embeddings=True, convert_to_numpy=True,
            show_progress_bar=show_progress,
        )
        return np.asarray(vectors, dtype=np.float32)

    def encode_query(self, query: str) -> list[float]:
        """Embed one query (L2-normalised)."""
        kwargs: dict[str, Any] = {}
        if self.preset.query_prompt_name:
            kwargs["prompt_name"] = self.preset.query_prompt_name
        vector: Any = self.model.encode(
            [self.preset.query_prefix + query],
            normalize_embeddings=True, convert_to_numpy=True,
            show_progress_bar=False, **kwargs,
        )
        return [float(x) for x in vector[0]]
