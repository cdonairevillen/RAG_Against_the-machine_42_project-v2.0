# Hugging Face Space (Docker, free CPU tier): the RAG API + the web.
#
# Build from the repository root (the web must be built first):
#   make web-build && make space-build
# The index is NOT in the image: the entrypoint restores the private
# bundle (Qdrant snapshots + BM25) at startup. See deploy/space/README.md.

# Same Qdrant as docker-compose.yml, run inside the Space container.
FROM qdrant/qdrant:v1.19.1 AS qdrant

FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl libunwind8 \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir uv==0.11.6

COPY --from=qdrant /qdrant/qdrant /usr/local/bin/qdrant
# Qdrant reads ./config/ from its working directory.
COPY --from=qdrant /qdrant/config /opt/qdrant/config

# Spaces run as uid 1000.
RUN useradd -m -u 1000 user
USER user
RUN mkdir -p /home/user/app
ENV HOME=/home/user \
    HF_HOME=/home/user/.cache/huggingface \
    UV_PROJECT_ENVIRONMENT=/home/user/venv \
    RAG_MODELS_DEVICE=cpu \
    PYTHONUNBUFFERED=1
WORKDIR /home/user/app

# Dependencies first (cached layer). The lock pins the CUDA build of torch
# (rag's default); it falls back to CPU, at the cost of a bigger image.
COPY --chown=user pyproject.toml uv.lock ./
COPY --chown=user llm_sdk ./llm_sdk
RUN uv sync --frozen --no-dev --no-install-project

COPY --chown=user src ./src
COPY --chown=user rag.toml ./
COPY --chown=user bench/results ./bench/results
COPY --chown=user web/dist ./web/dist
RUN uv sync --frozen --no-dev

# Models baked into the image, so a cold start does not download them.
RUN uv run --no-sync python -c "\
from sentence_transformers import SentenceTransformer, CrossEncoder; \
from transformers import AutoModelForCausalLM, AutoTokenizer; \
from src.config import get_config; c = get_config(); \
SentenceTransformer(c.embeddings.model); \
CrossEncoder(c.retrieval.reranker_model); \
AutoTokenizer.from_pretrained(c.generation.model); \
AutoModelForCausalLM.from_pretrained(c.generation.model)"

# Last, so editing it does not invalidate the model layer above.
COPY --chown=user deploy/space/entrypoint.sh ./entrypoint.sh

EXPOSE 7860
CMD ["sh", "./entrypoint.sh"]
