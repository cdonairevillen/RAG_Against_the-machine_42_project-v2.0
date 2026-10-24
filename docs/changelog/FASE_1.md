# CHANGELOG — Phase 1: Changing the ingestion

> English translation of [`../es/changelog/FASE_1.md`](../es/changelog/FASE_1.md), the working version.

**Date:** 2026-10-18
**Status:** completed. Commits `17ec310` and `a823a23`; the closing with B16 and B17 was pending commit.

---

## 1. The result in one table

The public 42 datasets, `k = 10`, the original evaluator. Every run is in `bench/results/`.

**Agreed metric priority: R@5 > R@10 > R@3 > R@1.**

### Smart path (`search_dataset`, the official benchmark)

| Run | What is tested | Docs R@1/@3/@5/@10 | Code R@1/@3/@5/@10 | Decision |
|---|---|---|---|---|
| `04-fase0-final` | Phase 0 baseline | 0.64 / 0.83 / 0.85 / 0.85 | 0.45 / 0.62 / 0.64 / 0.72 | — |
| `10-fase1-qdrant` | New architecture (Qdrant + config) | = Phase 0, **identical question by question** | = Phase 0 | ✅ |
| `11-fix-b7` | Offsets fix (B7) | 0.64 / 0.83 / 0.85 / 0.85 | 0.44 / 0.63 / 0.64 / 0.72 | ✅ (see §2) |
| `12-langchain-md` | LangChain docs chunker | 0.72 / 0.84 / 0.87 / 0.87 | 0.44 / 0.63 / 0.64 / 0.72 | ❌ Discarded (the author's decision) |
| `14-packed` | The author's packed chunker, overlap by sections | 0.68 / 0.84 / 0.86 / 0.88 | 0.43 / 0.63 / 0.64 / 0.72 | ✅ Default |
| `16-packed-lines` | The same, overlap by lines | 0.68 / 0.82 / 0.85 / 0.87 | 0.44 / 0.63 / 0.64 / 0.72 | ❌ Worsens R@5/@10/@3 |
| `17-fase1-final` | Initial closing (= `14-packed`, identical output) | 0.68 / 0.84 / 0.86 / 0.88 | 0.43 / 0.63 / 0.64 / 0.72 | Superseded by `20` |
| `19-fix-b16-b17` | `split_by_size`: first version of the fix | 0.67 / 0.84 / 0.88 / 0.89 | 0.43 / 0.59 / 0.64 / 0.72 | ❌ Faulty (it produced redundant pieces, see §2) |
| **`20-fix-b16-b17-v2`** | **`split_by_size` fixed (B16 + B17)** | **0.67 / 0.84 / 0.87 / 0.89** | **0.43 / 0.59 / 0.64 / 0.71** | **✅ Official baseline** (the author's decision) |

> `13-fase1-final` is the run with LangChain (when it was still the candidate), and `17-fase1-final` the closing before B16/B17. They are kept as history; the good one is `20-fix-b16-b17-v2`.

### Generation path (the web and `answer`)

| Run | Docs R@1/@3/@5/@10 | Code R@1/@3/@5/@10 |
|---|---|---|
| `04-fase0-final` | 0.70 / 0.82 / 0.89 / 0.89 | 0.23 / 0.55 / 0.62 / 0.70 |
| `13-fase1-final` (LangChain) | 0.69 / 0.81 / 0.85 / 0.90 | 0.24 / 0.55 / 0.62 / 0.70 |
| `14-packed` (= `17-fase1-final`) | 0.68 / 0.83 / 0.88 / 0.92 | 0.25 / 0.55 / 0.62 / 0.69 |
| `16-packed-lines` | 0.70 / 0.80 / 0.85 / 0.90 | 0.24 / 0.56 / 0.64 / 0.70 |
| `19-fix-b16-b17` (faulty) | 0.68 / 0.83 / 0.87 / 0.92 | 0.24 / 0.53 / 0.65 / 0.70 |
| **`20-fix-b16-b17-v2` (= final state)** | **0.69 / 0.85 / 0.89 / 0.93** | **0.25 / 0.53 / 0.66 / 0.72** |

### Net result vs Phase 0 (final state, `20`)

- **Official path:**
  - Docs improves at every cut-off: **+0.02 on R@5, +0.04 on R@10, +0.01 on R@3** and +0.03 on R@1.
  - **⚠️ Code:** R@5 the same, but **R@10 −0.01, R@3 −0.03** and R@1 −0.02. Almost all of it comes from B16/B17 (see §2); it is tackled in Phase 2.
- **Generation path (the web and `answer`):**
  - Docs: **R@10 +0.04, R@3 +0.03**, R@5 the same and R@1 −0.01.
  - Code: **R@5 +0.04, R@10 +0.02**, R@1 +0.02 and R@3 −0.02.

---

## 2. What was changed and why

### Database: Qdrant as a server (the author's decision after the comparison)

- **Comparison measured on the author's machine** with ~59,000 chunks:

  | Option | Write | With 384d vectors | Filtered query |
  |---|---|---|---|
  | Qdrant local mode | ~9 min | — | — |
  | **Qdrant server** | **1.9 s** | **8.8 s** | **18 ms** |
  | Postgres + pgvector | 0.4 s | 1.1 s + 24 s for the index | 13 ms |
  | SQLite | 0.4 s | no vectors | — |
  | LanceDB | blocked by Windows Application Control (the `pyarrow` DLL) | | |

- **`docker-compose.yml`:** Qdrant **v1.19.1**, the same as the `qdrant-client==1.19.1` client, with a named Docker volume (`rag_2_qdrant_storage`). It uses a named volume because Qdrant needs a POSIX file system and Windows bind mounts are not.
- **One collection per domain** (`rag_vllm`), with no vectors in this phase. Qdrant is the source of truth for the chunks and their metadata; the *dense* and *sparse* vectors are added to the same points in Phase 2.
- **BM25 stays on disk** (`data/processed/<domain>/`) with a `manifest.json`. On load, the retriever checks that Qdrant and BM25 come from the same ingestion: if the counts do not match, it fails with "Run 'make index' again" instead of returning inconsistent results.

### The chunk's data model

- **Stable IDs:** a UUID5 of (domain, level, file, range, occurrence). The same chunk gets the same ID on every reindex.
- **New fields:** `domain`, `level` (`parent` or `child`), `modality` (`text`; prepared for Phase 4b) and `ordinal` (the row in the BM25 index).
- **`parent_id`** changes from an integer index to the parent's ID.

### Configuration (`rag.toml` + `src/config.py`)

- Qdrant, paths, chunk sizes and **sources**. Each source declares its root, its extensions, the excluded directories and **which chunker each extension uses**.
- **Override through environment variables** `RAG_<SECTION>_<KEY>` (for example `RAG_QDRANT_URL`), validated with pydantic.
- It is the basis of modularisation: the chunker is changed in the config, not in the code.
- The CLI accepts `--config other.toml` and `--domain`. Every comparison was done this way, without touching `rag.toml`.

### Multi-domain ingestion

- `index --source <name>`; `vllm` by default.
- **Bug found by the tests:** a source **without code or without documentation** (the case of the future CV mode) made `bm25s` fail when creating an empty index. Now the per-type indices are only created if there are chunks of that type.

### B7: offsets of enriched chunks

- **Problem:** when splitting an enriched method (class signature + method) or a table with a title, the text was split *with* the prefix, so the offsets were shifted by the prefix length. Also, **only the first piece carried the context**.
- **Fix:** `split_with_header()` splits the original text (real offsets) and adds the header to **every** piece.
- **Effect on code:** −0.01 on R@1 and +0.01 on R@3, one question each way. In the one that drops, the old 1st result was a **shifted** piece that hit by chance; now the **right** piece appears, which contains the whole answer, but the reranker puts it 2nd.
- **Decision:** adopted for correctness, justified according to the rule.
- The test that was an `xfail` in Phase 0 now passes. Another one was added for tables, and it was checked that **both fail with the previous code**.

### Documentation chunker

- **Why recall changed so much:**
  - The ground-truth answers have a median length of **1,154 characters**.
  - The original chunker cuts at every header and separates tables from text, so it produces chunks with a median of **633 characters**, and only 63% of the answers fall whole inside one chunk.
- **`markdown_headers_packed` (new, default):** the author's header logic with three changes:
  1. It **packs** consecutive sections up to the maximum size.
  2. It **overlaps by whole sections** (up to 20% of the size), so that every chunk starts at a header.
  3. It **does not separate tables** from their section's text.
  - **It also ignores the `#` inside code blocks.** The original took them for headers: a bash `# comment` split the section.
  - Sections over the maximum are split, and each piece keeps the title.
- **LangChain** (`RecursiveCharacterTextSplitter` for Markdown): better R@1 on the official path, but worse on R@10 and on the web's path. **Discarded for this version** by the author's decision, with its code and dependency removed. Noted in *Possibilities* (`PLANING.md`), to be measured again after Phase 2.
- **Overlap by lines** (tuned to try to raise R@1): it does not improve R@1 on the official path and worsens R@5, R@10 and R@3 on both paths. **Discarded**, and its code removed.
- **`markdown_headers` (the original) removed from the code** by the author's decision. Its version remains in the `v1.0-42` tag, and its results in `bench/results/` (runs `00`–`11`). After removing it, the benchmark comes out identical (`18-sin-markdown-headers` = `17-fase1-final`).

### B16 + B17: `split_by_size()` (closing the phase, before Phase 2)

- **B16, starts in the middle of a line:** the function adjusted the **end** of each piece to a line break, but **not the start**. Measured on the vLLM files, **93% of the pieces** started in the middle of a line (for example `'value 17 |'`).
- **B17, lost text** (found while reviewing B16): the next piece started at `pos + fixed step` after the previous one, regardless of where it had really ended. When the end was trimmed back to a line break, the text between that end and the next start **fell into no piece**: **28,388 characters (0.14%)**, text the RAG could never find.
- **Duplicates in the original:** with fixed steps, the loop went on after reaching the end of the text. With parents of ~2,000 characters, it almost always produced a last child contained in the previous one (for example `[1920, 2000]` inside `[1440, 2000]`). They were **0.9%** of the 600-character pieces and many code children.
- **Fix:**
  1. The next piece starts at the first line break of the overlap window **before the real end** of the previous one.
  2. The loop stops when it reaches the end of the text.
  3. A piece only trims its end to a line break if it then ends **beyond** the previous one. Otherwise it cuts by characters.
- **Faulty first version (`19`):** without point 3, a line longer than the maximum made the loop advance line by line, producing redundant pieces (3.1%). It was detected while trying to confirm a hypothesis that turned out to be false; fixed in `20`.
- **Measured result:**
  - **0 characters lost.**
  - **0 redundant pieces.**
  - Only 1% of starts in the middle of a line, all due to lines longer than the maximum, which have to be cut by characters.
  - Code children drop from 39,065 to 34,917: those were the duplicates.
- **Effect on recall:**
  - It improves the generation path almost everywhere.
  - On the official path, docs raises R@5 and R@10 (+0.01).
  - **Code drops on R@3 (−0.04) and R@10 (−0.01)**: 13 questions change, almost all by one position, and one (Molmo, `multimodal_embeddings`) goes from 1st to not found.
  - Interpretation: the duplicated children gave **double BM25 weight to the end of each function**, an accidental effect of the bug that favoured some code questions.
- **Decision: adopted (the author's).** It is a technical fix, and the loss on code is tackled in Phase 2 by recalibrating thresholds and introducing hybrid search.
- **Tests:** four new ones (start at a line break, full coverage, advancing beyond the previous piece, lines longer than the maximum). It was checked that the first two **fail with the previous code**.

| Docs chunker | Parent chunks | Median size | GT answer whole in one chunk |
|---|---|---|---|
| `markdown_headers` (original, removed) | 1,275 | 633 | 63% |
| LangChain (discarded) | 797 | 1,419 | 81% |
| **`markdown_headers_packed`** | 768 | 1,583 | 72% |

---

## 3. List of files

| File | Change |
|---|---|
| `docker-compose.yml` | **New**: Qdrant v1.19.1 |
| `rag.toml` | **New**: pipeline configuration |
| `src/config.py` | **New**: config loading and validation, environment overrides |
| `src/ingestion/chunk.py` | **New**: `Chunk` with a stable ID, domain, level, modality and ordinal |
| `src/ingestion/chunkers.py` | **New**: chunkers moved from `ingester.py` + a registry + `split_with_header` (B7) + `markdown_headers_packed`, which replaces `markdown_headers` |
| `src/ingestion/pipeline.py` | **New**: walking the sources, parents and children, BM25 and the manifest |
| `src/storage/base.py` | **New**: the `ChunkStore` interface |
| `src/storage/qdrant_store.py` | **New**: the Qdrant implementation |
| `src/ingester.py` | **Deleted** (split into `ingestion/` and `storage/`) |
| `src/retriever.py` | `from_store()` instead of `from_disk()`; parents by ID |
| `src/cli.py` | `--domain`, `--config`; `index` writes to Qdrant; the same interface for the 42 commands |
| `src/bench.py` | Loads from the store; records each run's domain, chunking and chunkers |
| `src/web.py` | Loads from the store |
| `Makefile` | `db-up`, `db-down`, `db-reset`; `index`, `search-*`, `bench*` and `web` start Qdrant if needed |
| `pyproject.toml`, `uv.lock` | `qdrant-client==1.19.1`, `tomli` (Python 3.10 only) and a filter for an in-memory Qdrant warning |
| `tests/test_config.py`, `tests/test_storage.py` | **New** |
| `tests/test_ingester.py`, `tests/test_retriever.py` | Adapted, plus tests for B7 and the packed chunker |
| `docs/PLANING.md` | LangChain added to *Possibilities* |
| `bench/results/*.json` | Measurements 10–17 |
| `llm_sdk/**` | **Untouched** |

**Tests:** 35 (previously 13 + 1 xfail). The storage and integration ones use **in-memory Qdrant**, so `make test` does not need Docker.

---

## 4. What to know about the architecture

```
rag.toml ──► config ──► Ingester(domain) ──► chunkers (per extension)
                              │
              ┌───────────────┴───────────────┐
              ▼                               ▼
   Qdrant: collection rag_<domain>     data/processed/<domain>/
   (parents + children, payload)       bm25_*  + manifest.json
              └───────────────┬───────────────┘
                              ▼
                 Retriever.from_store(domain)
          (validates the manifest; child.ordinal = BM25 row)
```

- **Workflow:** `make db-up` (or any target that needs it) → `make index` → `make bench`. Qdrant stays running (`restart: unless-stopped`). `make db-down` stops it, and `make db-reset` **also deletes the data**.
- **Retriever startup:** 2.5 s (it reads the 58,731 chunks from Qdrant and loads BM25). Qdrant uses ~390 MB of RAM, and the volume takes ~650 MB.
- **The retriever still loads every chunk into memory**, as before. It was the way to guarantee identical results in the refactor. In Phase 2, vector search will go directly against Qdrant.
- **Reindexing recreates the domain's collection**: the other domains are not touched.
- **Docker at 42:** Docker images and volumes go to Docker's storage, not to `/goinfre`. If the home quota on the 42 machines is small, Docker's `data-root` will have to be moved. It is **to be checked** there.
- **For deployment (Phase 6):** the HF Space is a single container. A choice will be needed between Qdrant inside the container and a free cloud plan (limits **to be checked**).

---

## 5. How to check it

```bash
make db-up                 # Qdrant v1.19.1 in Docker
make index                 # ~25 s
make bench LABEL=check     # must reproduce 20-fix-b16-b17-v2 / smart
make test                  # 35 passed (no Docker)
make lint                  # flake8 + mypy clean
make search-docs && make eval-docs   # 42 commands: 0.67 / 0.84 / 0.87 / 0.89
```
