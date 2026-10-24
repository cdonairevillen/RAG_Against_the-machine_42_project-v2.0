# CHANGELOG — Phase 2: Hybrid retrieval

> English translation of [`../es/changelog/FASE_2.md`](../es/changelog/FASE_2.md), the working version.

**Start date:** 2026-10-18
**Status:** ✅ completed (2026-10-19).
- **Step 1** (recovering code and unifying paths): commit `acab947`.
- **Step 2** (code-aware tokenizer, B8 + B14): commit `1a91f74` (§6).
- **Steps 3–5** (embeddings, rerankers, classifier) and closing: commit "Autosave" (§7–§11). Done autonomously with the author's authorisation, for his review.

> **Phase summary (official path):**
> - **Docs R@5:** 0.87 → **0.92**.
> - **Code R@5:** 0.64 → **0.80**.
> - **Code R@10:** 0.71 → **0.88**.
>
> Every model comparison is in `docs/BENCHMARK_REPORT.md`.

**Metric priority: R@5 > R@10 > R@3 > R@1.**

---

## 1. Result of step 1

The public 42 datasets, `k = 10`, the original evaluator. The runs are in `bench/results/`, and each one records its retrieval parameters and the device.

| Run | What is tested | Docs R@1/@3/@5/@10 | Code R@1/@3/@5/@10 |
|---|---|---|---|
| `20-fix-b16-b17-v2` | Baseline (end of Phase 1) | 0.67 / 0.84 / 0.87 / 0.89 | 0.43 / 0.59 / 0.64 / 0.71 |
| `21-cuda-check` | The same, with the reranker on GPU | identical | identical |
| `22-sin-gpu` | The same, with the GPU hidden (simulates 42) | identical | identical |
| `23-skip-rerank-1000` | Reranker always on, the reranker's order | 0.73 / 0.90 / 0.93 / 0.95 | 0.44 / 0.59 / 0.62 / 0.67 |
| `25-rrf-skip-1000` | Naive RRF fusion (a single list) | 0.64 / 0.79 / 0.83 / 0.90 | 0.46 / 0.64 / 0.68 / 0.72 |
| `26-rrf3-skip-1000` | **Per-list RRF** (BM25 code + BM25 docs + reranker) | 0.72 / 0.90 / 0.93 / 0.95 | 0.45 / 0.63 / 0.67 / 0.72 |
| **`29-rrf-default` smart** | **Current state (default config)** | **0.72 / 0.90 / 0.93 / 0.95** | **0.45 / 0.63 / 0.67 / 0.72** |
| **`29-rrf-default` generation** | The web's path, now unified | **0.72 / 0.90 / 0.93 / 0.95** | **0.45 / 0.63 / 0.67 / 0.71** |

**Net result on the official path against the baseline:**
- **Docs:** +0.05 / +0.06 / +0.06 / +0.06.
- **Code:** +0.02 / +0.04 / +0.03 / +0.01.

It improves **at every cut-off on both datasets**, and code also beats Phase 0 (0.45 / 0.62 / 0.64 / 0.72).

**The web's path against how it was:**
- **Docs:** 0.69 / 0.85 / 0.89 / 0.93 → 0.72 / 0.90 / 0.93 / 0.95.
- **Code:** 0.25 / 0.53 / 0.66 / 0.72 → 0.45 / 0.63 / 0.67 / 0.71. R@1 almost doubles; R@10 drops 0.01 (see §2.5).

---

## 2. What was changed and why

### 2.1 CUDA, without depending on it

- **torch with CUDA 12.6** (the `pytorch-cu126` index in `pyproject.toml`). 12.6 is chosen because it works with old drivers, which matters for the 42 machines, whose GPU is unknown.
  - The CUDA index brings **torch 2.14.1** (PyPI had 2.12.1).
  - torch is declared as a direct dependency of the project only to choose the build. `llm_sdk` is not touched.
- **`accelerate`** added: `llm_sdk` loads Qwen with `device_map="auto"` when there is a GPU, and transformers requires it. Without a GPU it is not used.
- **`[models] device = "auto"`** in `rag.toml`: CUDA if there is a GPU and CPU otherwise. Forced with `RAG_MODELS_DEVICE=cpu`.
- **Tested without a GPU:**
  - Hiding the card with `CUDA_VISIBLE_DEVICES=-1`, the benchmark comes out **identical** and `answer` works.
  - Note: on Windows, `CUDA_VISIBLE_DEVICES=""` does **not** hide the GPU, because Windows removes empty variables. The first test was not valid for that reason.
- **Speed:** code takes 3 s with the reranker on GPU, against 36–40 s on CPU. Identical results on both.

### 2.2 Retrieval parameters in the configuration

- `classifier_margin`, `code_signal_weight`, `doc_signal_weight`, `skip_rerank_score`, `bm25_score_floor`, `reranker_model`, `rerank_fusion` and `rrf_k` move from constants in the code to the `[retrieval]` section of `rag.toml`.
- They can be swept with environment variables (`RAG_RETRIEVAL_SKIP_RERANK_SCORE=12 make bench`).
- Checked that, with the old values, the output is identical to `20`.

### 2.3 The threshold to skip the reranker mainly affected docs

- The `skip_rerank_score` sweep (0, 6, 9, 12, 15, no limit) showed that **docs gains 6 points** if it always reranks:
  - Many docs questions are classified as code and go down the code branch.
  - There, the reranker is what brings the 4 backup documents to the top.
- But on code, the reranker's order (`ms-marco`, trained on web text) is **worse than BM25's** (R@10 0.71 → 0.67).

### 2.4 Per-list RRF fusion (the solution)

- **`rerank_fusion = "rrf"`:** instead of replacing BM25's order with the reranker's, both are fused with *Reciprocal Rank Fusion*. A candidate that BM25 puts at the top does not sink if the reranker hesitates, and one the reranker raises can get in.
- **Per list:** the code candidates and the backup documents come from **two different BM25 rankings**, and each keeps its own position in the fusion.
  - The naive version (`25`), with a single list, put the documents in positions 31–34 and **sank docs** (R@5 0.83).
- **`skip_rerank_score = inf`:** with the fusion, always reranking is best.
- **Question by question, against `20`:**
  - **Docs:** 8 improve and 1 gets worse (from 1st to 2nd).
  - **Code:** 17 improve and 10 get worse, almost all by one or two positions; one that was 9th is lost.
- **Tests:** three new ones with a fake reranker (order by replacement, RRF balance with the exact expected order, and use of per-list positions).

### 2.5 Unified paths (pending since Phase 1)

- **`search_for_generation`** (the one for the web and `answer`) becomes: **relevance gate + `search_smart`**. Before, it had its own logic (forcing 2 documents to the top and reranking everything together), which gave code R@1 0.25.
- With RRF fusion, the old logic also sank code R@1 to 0.13 (`27-gen-rrf3`), which confirmed it was worth unifying.
- **The only difference between the two paths:** the relevance gate (`bm25_score_floor = 5.5`), which drops **2 legitimate code questions**. That is why the web's path has code R@10 0.71 against 0.72.

### 2.6 The BM25 relevance gate does not work (left for Phase 3)

| Question | Max BM25 score | Passes the 5.5 threshold? |
|---|---|---|
| "…what endpoint … LoRA adapter in vLLM?" (legitimate) | 13.56 | yes ✅ |
| "**What is the capital of France?**" (out of domain) | **12.28** | **yes ❌** |
| "Who won the 2018 football World Cup?" (out of domain) | 7.93 | yes ❌ |
| "…min_dynamic_patch … NemotronVL…" (legitimate) | 5.40 | **no ❌** |
| "…max_position_embeddings … ChameleonSwinDecoderLayer?" (legitimate) | 4.96 | **no ❌** |
| "How do I bake a chocolate cake?" (out of domain) | 4.22 | no ✅ |

- It fails in both directions.
- **Not changed yet:** removing it would let questions like the cake one reach Qwen, which today answers from its own knowledge (B15).
- It is replaced in **Phase 3** by a better signal, such as the reranker's score or a guardrail in generation. It only affects the web's path, not the official benchmark.

---

## 3. List of files (step 1)

| File | Change |
|---|---|
| `pyproject.toml`, `uv.lock` | torch with CUDA 12.6 (the `pytorch-cu126` index), `accelerate` |
| `rag.toml` | `[models]` and `[retrieval]` sections; RRF and the reranker always on by default |
| `src/config.py` | `RetrievalConfig`, `ModelsConfig` (`device = auto`) and their environment overrides |
| `src/retriever.py` | Parameters from the config; reranker on the configured device; per-list RRF fusion; `search_for_generation` unified with `search_smart` |
| `src/bench.py` | Records each run's retrieval parameters and device |
| `tests/test_retriever.py` | Fusion tests with a fake reranker |
| `bench/results/*.json` | Runs 21–29 |
| `llm_sdk/**` | **Untouched** |

**Tests:** 38. Lint clean.

---

## 4. What to know about the architecture

- **A single ranking** for the benchmark, the CLI and the web (`search_smart`); the web only adds the relevance gate.
- **The code of the old generation path has been removed** (it is still in git and in `v1.0-42`).
- **CPU vs GPU reproducibility:** with the current reranker, the outputs are identical. With bigger models there could be tiny differences on ties; `bench` records the device used.

---

## 5. The phase's plan after step 1 (all resolved)

1. ~~Code-aware tokenizer (B8 + B14)~~ → §6 and §7.
2. ~~Multilingual embeddings in Qdrant, measured on CPU and GPU~~ → §8 (`bge-m3`).
3. ~~Rerankers~~ → §9 (`mmarco`; `Qwen3-Reranker` discarded and `bge-reranker-v2-m3` pending a recall measurement).
4. ~~Doc/code classifier~~ → §10.
5. ~~`docs/BENCHMARK_REPORT.md`~~ → created.

---

## 6. Step 2: code-aware tokenizer (B8 + B14)

### Result

| Run | Mode | Docs R@1/@3/@5/@10 | Code R@1/@3/@5/@10 |
|---|---|---|---|
| `29-rrf-default` | no decomposition (before) | 0.72 / 0.90 / 0.93 / 0.95 | 0.45 / 0.63 / 0.67 / 0.72 |
| `30-tokens-none` | `none` (refactor, **identical** to `29`) | 0.72 / 0.90 / 0.93 / 0.95 | 0.45 / 0.63 / 0.67 / 0.72 |
| `31-tokens-query` | `query`: the query only (the original B14) | 0.71 / 0.89 / 0.93 / 0.96 | 0.45 / 0.62 / 0.67 / 0.75 |
| `33-tokens-both` | `both`: corpus and query (B8 + B14) | 0.74 / 0.89 / 0.92 / 0.93 | 0.48 / 0.69 / 0.74 / 0.81 |
| `33-tokens-code` | `code`: code chunks and indices only | 0.72 / 0.90 / 0.92 / 0.94 | 0.50 / 0.71 / 0.76 / 0.84 |
| **`35-tokens-code-default`** | **`code` + the classifier without decomposition** (default) | **0.72 / 0.91 / 0.93 / 0.94** | **0.49 / 0.70 / 0.75 / 0.83** |

**Net result against `29`:**
- **Docs:** R@5 the same, R@3 +0.01, R@10 −0.01 (one question).
- **Code:** **+0.04 / +0.07 / +0.08 / +0.11**.
- **The web's path now gives exactly the same as the official one:** the two legitimate questions the relevance gate blocked (§2.6) now pass it, because with the identifier parts they score higher.

### What was changed

- **`src/ingestion/tokens.py` (new):** a single tokenisation point for the corpus and the query, so they cannot get out of sync.
  - `split_identifier()`: `max_model_len` → max, model, len; `PagedAttention` → paged, attention; `RMSNorm` → rms, norm.
  - The **original identifiers are kept**, so exact matches still count.
  - `vLLM` is excluded: splitting it added "llm" to almost the whole corpus. It is the same trap seen in Phase 0 with the classifier.
- **`code_aware_tokens`** in `[retrieval]`, with four measured modes (`none`, `query`, `both`, `code`). By default, **`code`**:
  - The parts are added **only to code chunks**; in the documentation they were mostly noise (`both` lowered docs R@10 by 0.02).
  - The query is decomposed when searching the code index and the general one, **never the docs one**.
- **The doc/code classifier uses the undecomposed query** on both indices. With the parts, the code index scored higher in general and sent docs questions down the code branch (`33-tokens-code`: docs R@5 0.92). With the undecomposed query, docs R@5 goes back to 0.93.
- **Safety:** the manifest records which chunks got parts added (`identifier_parts`), and the retriever **refuses to start** if it does not match `code_aware_tokens` ("Run 'make index' again"). The integration test caught it when the default changed, which is exactly what it is for.

### Question by question (`29` → `35`)

- **Code:** 24 improve and 16 get worse. 4 that were between 3rd and 10th are lost; the rest move a few positions.
- **Docs:** 3 change. The one lost (*"Where can I find information about using generative models in vLLM?"*, previously 6th) is a **classifier failure**, not a tokenisation one: it is sent down the code branch (code 7.41 vs doc 6.09), where only 4 backup documents get in. It is reviewed in step 4 (the classifier).
- **Decision:** adopted, justified according to the rule (R@5 does not get worse on any dataset). It is reverted with `code_aware_tokens = "none"` and `make index`.

### Files

| File | Change |
|---|---|
| `src/ingestion/tokens.py` | **New**: identifier decomposition and shared tokenisation |
| `src/ingestion/pipeline.py` | The BM25 corpus adds parts according to the chunk type; manifest with `identifier_parts` |
| `src/retriever.py` | Tokenisation per index; classifier with the undecomposed query; manifest check |
| `src/cli.py` | `index` applies the configured mode |
| `src/config.py`, `rag.toml` | `code_aware_tokens = "code"` |
| `tests/test_tokens.py` | **New** (4 tests) |
| `tests/test_storage.py` | The integration test indexes according to the configuration |

**Tests:** 42. Lint clean.

---

## 7. Step 2 (review): tokenisation modes with a neutral classifier

Following the author's question ("why is there no docs-only mode?"):

- **A mistake fixed:** the classifier used the "docs" tokenisation assuming it would always be the undecomposed query, which is only true in `code` mode. Now it **always** uses the undecomposed query, whatever the mode. In `code` mode (the default), the result is identical (`39-tokens-code-plain-classifier` = `36`).
- **`doc` mode added** (identifier parts only in docs chunks and the docs index) and measured. A fair comparison, without embeddings:

| Mode | Docs R@1/@3/@5/@10 | Code R@1/@3/@5/@10 |
|---|---|---|
| **`code`** (default) | 0.72 / **0.91 / 0.93** / 0.94 | 0.49 / 0.70 / 0.75 / **0.83** |
| `both` | **0.73** / 0.88 / 0.92 / 0.94 | 0.49 / 0.70 / 0.75 / 0.82 |
| `doc` | 0.72 / 0.87 / 0.92 / 0.94 | 0.42 / 0.61 / 0.65 / 0.69 |

- **Conclusion:** adding identifier parts to the documentation makes docs worse (R@3 −0.03/−0.04, R@5 −0.01). `code` is kept.

---

## 8. Step 3: embeddings (hybrid search)

### What was implemented

- **`src/embeddings.py` (new):** an `Embedder` with the right prompts for each family, checked on Hugging Face:
  - E5: `query: ` and `passage: `.
  - Qwen3: the `query` prompt declared by the model.
  - bge-m3: no instructions.
  - The same model and the same normalisation for documents and queries, which is what failed in v1 (there, indices of two different lists were crossed).
- **What is embedded:** the **child chunks** (the same unit as BM25), as "path + text". The query is embedded **unexpanded**.
- **Qdrant:** the vectors go as a **named vector** in the same points of `rag_vllm` (one name per model, cosine distance). Search filtered by level (`child`) and type (`code`/`doc`).
- **Fusion:** inside each list (code candidates and backup documents, or the docs list), BM25 and vectors are fused with **RRF** (`rrf_merge`) before the reranker.
- **Safety:** the manifest records `embedding_model`, and the retriever refuses to start if the configuration uses another model.
- **`[embeddings]`** in `rag.toml`: `enabled`, `model`, `batch_size`, `dense_k` and `dense_in_doc_branch`. In the code it is **off by default**, so that tests and light environments do not download 2 GB; `rag.toml` turns it on.

### Results and decision

All the tables are in `docs/BENCHMARK_REPORT.md` §1. In short:
- **`bge-m3`** is the best on the official benchmark: code R@10 0.86, against 0.84 for e5-small and 0.83 for Qwen3, with R@5 tied at 0.79.
- **Docs in Spanish without embeddings drops to R@10 0.50**; with `bge-m3`, 0.90.
- **Speed on CPU:** `bge-m3` takes about 2 h to index the corpus (estimated) and 141 ms per query. `Qwen3-Embedding` is unworkable without a GPU (~19 h of indexing and 0.8 s per query). `e5-small` is the **alternative for machines without a GPU** (~13 min).
- **Embeddings in both branches** (the author's decision): on docs they trade −0.01 of R@5 for +0.03 of R@1 and +0.01 of R@3, and they bring multilingual ability.

### Complementary multilingual set (new)

- **`bench/datasets/es/`:** 20 questions from the public datasets (one in ten: 10 docs and 10 code), translated into Spanish with the **same ground truth** and the same `question_id`. Code names are left as they are.
- **`bench/datasets/en/`:** the same 20 in English, to compare over the same subset.
- `make bench` accepts `--suite public|en|es`, and each run records its `suite`.
- **Each question is worth 0.10**: differences of 0.10 are a single question. It is a complementary set (D4); the official recall is still only the 42 one.

---

## 9. Step 4: rerankers

All the tables are in `docs/BENCHMARK_REPORT.md` §2.

- **Measured:** `ms-marco-MiniLM-L-6-v2` (v1, English only), `mmarco-mMiniLMv2-L12-H384-v1` (multilingual, 118M) and the latency of `bge-reranker-v2-m3` (multilingual, 568M).
- **Discarded without measuring recall:**
  - `jina-reranker-v2-base-multilingual`, for its **CC-BY-NC-4.0** license (non-commercial).
  - `Qwen3-Reranker-0.6B`, following the author's criterion: it needs its own adapter and is heavy; it would only pay off with a very large gain. It stays in *Possibilities*.
- **`bge-reranker-v2-m3`:** the first run stopped because the system ran out of memory. **Relaunched later (`46`), in the foreground:**
  - **Result:** code **0.52 / 0.83 / 0.86 / 0.87** (R@5 +0.06 and R@3 +0.11 against `mmarco`; R@10 −0.01); docs 0.78 / 0.92 / 0.92 / 0.94.
  - **Cost:** 439 s for the code dataset (~4.4 s per question on GPU) and ~23 s per query on CPU.
  - **Memory:** a peak of 39.1 GB of committed memory out of 67.9 GB; the cause of the first stop could not be determined.
  - **Decision (the author's):** the optional `gpu-quality` profile; `mmarco` stays in the base (§12).
- **Reranking the docs branch** (`rerank_doc_branch`): it still hurts with both rerankers measured; it stays off.
- **Decision: `mmarco-mMiniLMv2-L12` by default.** On the official benchmark it ties on R@5 and wins on code R@10 (+0.02); in Spanish, docs R@5 goes from 0.70 to 0.90. It costs twice as much as `ms-marco`, but is still workable on CPU (1.8 s per query).

---

## 10. Step 5: doc/code classifier

Tables in `docs/BENCHMARK_REPORT.md` §3.

- **Measured diagnosis:** the classifier sent **25 of 100** official docs questions and **10 of 10** Spanish docs questions down the code branch. The "documentation question" signals were English only and were compared without stripping punctuation (`¿cómo` never matched).
- **Changes:**
  - Spanish signals (`DOC_SIGNAL_TERMS_ES`), selectable with `doc_signal_languages = ["en", "es"]`.
  - Punctuation stripping, `¿` and `¡` included.
- **Result:** official docs **+0.01 on R@1, R@3 and R@5, with code identical** (a strict improvement). Routing: official docs 23/100 and Spanish docs 8/10 misrouted.
- **Weights and margin unchanged:** every docs question no longer sent to code is paid for with misrouted code questions (code R@5 down to 0.66).
- ⚠️ **On the Spanish set**, docs loses one question on R@3 and R@5 (0.90 → 0.80): two questions move to the docs branch, which has no reranker, and one does worse. Accepted because the reference benchmark is the official one.
- **Limit:** the lexical classifier cannot do more. A semantic classifier, using the embeddings, remains a future improvement.

---

## 11. Closing the phase

### Final result (`49-fase2-final`)

| Set | Docs R@1/@3/@5/@10 | Code R@1/@3/@5/@10 |
|---|---|---|
| **Official (42)** (smart and generation, identical) | **0.76 / 0.91 / 0.92 / 0.94** | **0.51 / 0.72 / 0.80 / 0.88** |
| Spanish (20) | 0.60 / 0.80 / 0.80 / 0.90 | 0.50 / 0.70 / 0.80 / 0.90 |

### Files (steps 3–5)

| File | Change |
|---|---|
| `src/embeddings.py` | **New**: `Embedder`, per-model prompts, vector name |
| `src/storage/base.py`, `src/storage/qdrant_store.py` | Named vectors and filtered `search_dense` |
| `src/retriever.py` | `rrf_merge`, dense search in both branches, `load_embedder` (checks the manifest), optional reranking in the docs branch, a classifier that is always neutral and has English and Spanish signals |
| `src/ingestion/pipeline.py` | Manifest with `embedding_model` |
| `src/ingestion/tokens.py` | `doc` mode |
| `src/cli.py` | `index` embeds the children if embeddings are on; `bench --suite` |
| `src/bench.py` | `public` / `en` / `es` sets |
| `src/config.py`, `rag.toml` | `[embeddings]`; the `mmarco` reranker; `rerank_doc_branch`; `doc_signal_languages` |
| `bench/datasets/en/`, `bench/datasets/es/` | **New**: the 20-question complementary set |
| `tests/test_dense.py` | **New**: `rrf_merge`, prompts and dense search with in-memory Qdrant |
| `tests/test_retriever.py`, `tests/test_tokens.py` | Classifier in Spanish; `doc` mode |
| `docs/BENCHMARK_REPORT.md` | **New** |
| `bench/results/*.json` | Runs 36–49 |
| `llm_sdk/**` | **Untouched** |

**Tests:** 47. Lint clean.

### What to know about the architecture

- **Indexing now embeds 37,381 children with `bge-m3`:** ~6 min on the 3080 Ti and **~2 h on CPU** (estimated). On machines without a GPU, the alternative is `RAG_EMBEDDINGS_MODEL=intfloat/multilingual-e5-small make index` (~13 min).
- **Changing the embeddings model forces a reindex**; the retriever enforces it through the manifest.
- **RAM:** with `bge-m3` and the reranker loaded, the process uses several GB. A heavy measurement (`bge-reranker-v2-m3`) stopped because the system ran out of memory.
- **What the phase did not solve:**
  - The classifier still sends 23 of 100 docs questions to code (the lexical approach is at its limit).
  - The BM25 relevance gate (B15) moves to Phase 3.
- **End-to-end test:** `answer "¿Qué endpoint HTTP se usa para cargar dinámicamente un adaptador LoRA en vLLM?"` finds `lora.md` and answers correctly, **but in English**: the prompt does not ask to answer in the question's language. Moved to Phase 3.

### Pending review with the author

1. ~~`bge-reranker-v2-m3`~~ → resolved: the optional `gpu-quality` profile, with `mmarco` in the base (§12).
2. ~~`bge-m3` even though indexing on CPU takes ~2 h?~~ → resolved: `bge-m3` in the base (stable results) and a `cpu-light` profile with `e5-small` (§12). The prebuilt index stays in *Possibilities*.
3. **The Spanish docs question** that gets worse with the new classifier (§10).

---

## 12. Profiles: a stable base and extra models as options

**The author's criterion:** the system must behave the same on any computer; extra models are options, and the web could offer them with pickers (ingestion, reranker, embeddings). That will be raised in its phase.

- **Stable base:** what is in `rag.toml` outside `[profiles.*]` (`bge-m3` + `mmarco`). It is what the official benchmark uses and **it does not change with the machine** (there is no automatic selection by GPU), so the numbers are reproducible and comparable with other 42 RAGs.
- **Profiles** (`[profiles.<name>]` in `rag.toml`): they only override what they declare.
  - **How to choose one:** `--profile <name>`, `RAG_PROFILE=<name>` or `make <target> PROFILE=<name>`.
  - **Precedence:** environment variables > profile > the `rag.toml` base > the code defaults.
  - **`gpu-quality`:** the `bge-reranker-v2-m3` reranker (code R@5 0.86 vs 0.80, but ~4.4 s per question on GPU and ~23 s on CPU).
  - **`cpu-light`:** `e5-small` embeddings, to index without a GPU in ~13 min instead of ~2 h. It needs `make index PROFILE=cpu-light`; the manifest prevents mixing indices.
- **`bench` records each run's profile**, and the configuration exposes `available_profiles`, which is what a picker in the web would need (Phase 6).
- **Check:** the base gives results identical to `49-fase2-final` (`50-base-check`). Tests: 51 (+4 for profiles).
- **Files:** `src/config.py` (`deep_merge`, profiles in `load_config`), `src/cli.py` (`--profile`), `src/bench.py`, `Makefile` (`PROFILE=`), `rag.toml`, `tests/test_config.py`.
