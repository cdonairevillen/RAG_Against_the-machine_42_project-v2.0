# BENCHMARK REPORT — RAG Against the Machine v2.0

> English translation of [`es/BENCHMARK_REPORT.md`](es/BENCHMARK_REPORT.md), the working version. Updated at the end of each phase.

Comparison of models and pipeline configurations, with the same rules in every measurement:

- **Official recall:** the public 42 datasets (100 docs questions + 100 code questions), `k = 10`, the original evaluator, the `search_smart` path (`search_dataset`).
- **Metric priority:** R@5 > R@10 > R@3 > R@1.
- **Complementary multilingual set:** 20 questions from the public datasets (one in ten: 10 docs and 10 code), in English (`--suite en`) and translated into Spanish (`--suite es`) with the same ground truth. Each question is worth 0.10. It measures what the 42 benchmark cannot see; **it does not replace the official recall**.
- **Hardware:** NVIDIA RTX 3080 Ti (12 GB) and a 24-core CPU. CPU times on the 42 machines will probably be worse.
- Every run is in `bench/results/` with its full configuration (chunking, retrieval, device).

---

## 1. Embeddings (Phase 2, step 3)

Common configuration:
- Tokenisation `code_aware_tokens = "code"`.
- RRF fusion of the reranker, and the `ms-marco-MiniLM-L-6-v2` reranker.
- Embeddings in both branches.
- The 37,381 child chunks are embedded (path + text); the query, unexpanded and with each model's prefix.

### 1.1 Official recall (public 42 datasets)

| Model | Parameters | Dim. | License | Docs R@1/@3/@5/@10 | Code R@1/@3/@5/@10 |
|---|---|---|---|---|---|
| No embeddings (`36`) | — | — | — | 0.72 / 0.91 / **0.93** / 0.94 | 0.49 / 0.70 / 0.75 / 0.83 |
| `intfloat/multilingual-e5-small` (`37`) | 118M | 384 | MIT | 0.70 / 0.89 / 0.92 / 0.93 | 0.48 / 0.70 / **0.79** / 0.84 |
| **`BAAI/bge-m3`** (`40`) | 568M | 1024 | MIT | **0.75 / 0.92** / 0.92 / **0.94** | 0.52 / **0.71 / 0.79 / 0.86** |
| `Qwen/Qwen3-Embedding-0.6B` (`41`) | 596M | 1024 | Apache 2.0 | 0.71 / 0.90 / 0.92 / 0.94 | **0.55** / 0.66 / **0.79** / 0.83 |

**Variant with `bge-m3` only in the code branch** (`42-bge-m3-code-branch-only`): docs 0.72 / 0.91 / 0.93 / 0.94 (the same as without embeddings), and code the same as with embeddings in both branches. In other words, on docs the vectors trade −0.01 of R@5 for +0.03 of R@1 and +0.01 of R@3. **Decision (the author's): embeddings in both branches**, for their multilingual value (§1.2).

### 1.2 Multilingual (20 questions, English vs Spanish)

| Model | Docs EN | **Docs ES** | Code EN | Code ES |
|---|---|---|---|---|
| No embeddings | 0.80 / 0.90 / 1.00 / 1.00 | **0.30 / 0.50 / 0.50 / 0.50** | 0.50 / 0.80 / 0.90 / 0.90 | 0.60 / 0.80 / 0.80 / 0.90 |
| `e5-small` | 0.90 / 0.90 / 1.00 / 1.00 | 0.40 / 0.60 / 0.70 / 0.70 | 0.40 / 0.80 / 0.90 / 0.90 | 0.50 / 0.80 / 0.80 / 0.90 |
| `bge-m3` | 0.80 / 0.90 / 0.90 / 1.00 | 0.30 / 0.60 / 0.70 / **0.90** | 0.60 / 0.90 / 0.90 / 0.90 | 0.60 / 0.80 / 0.80 / 0.90 |
| `Qwen3-Embedding-0.6B` | 0.70 / 0.90 / 0.90 / 1.00 | 0.30 / 0.70 / 0.80 / 0.90 | 0.70 / 0.80 / 0.90 / 0.90 | 0.70 / 0.80 / 0.80 / 0.80 |

(Format R@1 / R@3 / R@5 / R@10; runs `43-ml-*`.)

- **Without embeddings, a docs question in Spanish loses half of its hits** (R@10: 1.00 → 0.50): BM25 compares words, and "adaptador" does not match "adapter".
- With `bge-m3` or Qwen3, docs in Spanish goes back to R@10 = 0.90.
- Code barely changes with the language: the questions keep their identifiers (`get_num_new_matched_tokens`…), which BM25 still finds.
- With 10 questions per set, a difference of 0.10 is **a single question**: Qwen3 and `bge-m3` are tied in Spanish.

### 1.3 Speed

| Model | Embedding the corpus on **GPU** (measured) | Embedding on **CPU** (children/s) | Corpus on CPU (estimated) | Query on CPU |
|---|---|---|---|---|
| `e5-small` | 45 s | 47.9 | ~13 min | 17 ms |
| `bge-m3` | 354 s | 5.0 | **~2 h** | 141 ms |
| `Qwen3-Embedding-0.6B` | 222 s | 0.6 | **~19 h** | 797 ms |

(CPU: a sample of 512 real children; the full corpus is extrapolated from it.)

### 1.4 Decision

**`BAAI/bge-m3` by default.**
- It is the best on the official benchmark with the project's priority: code R@5 ties with the others (0.79) and it wins on R@10 (0.86 vs 0.84 and 0.83), and docs has the best R@3.
- It is multilingual, with Spanish docs at 0.90 R@10.
- It answers quickly on a CPU (141 ms per query).
- **Its cost:** indexing without a GPU takes about 2 h. For machines without a GPU (42) there is the optional **`cpu-light`** profile (`e5-small`, ~13 min on CPU: `make index PROFILE=cpu-light`), or the index can be built on a machine with a GPU and shipped ready-made.
- **Qwen3-Embedding-0.6B discarded:** it does not beat `bge-m3` on the official benchmark, ties in Spanish, and is unworkable on a CPU (19 h of indexing and 0.8 s per query).

---

## 2. Rerankers (Phase 2, step 4)

### 2.1 Latency (34 real candidates per query)

| Reranker | Parameters | License | Multilingual | GPU | CPU |
|---|---|---|---|---|---|
| `cross-encoder/ms-marco-MiniLM-L-6-v2` (v1) | 23M | Apache 2.0 | no | 57 ms | 0.9 s |
| `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` | 118M | Apache 2.0 | yes | 97 ms | 1.8 s |
| `BAAI/bge-reranker-v2-m3` | 568M | Apache 2.0 | yes | 1.1 s | **23 s** |

- `jinaai/jina-reranker-v2-base-multilingual` is discarded for its license (**CC-BY-NC-4.0**, non-commercial).
- `Qwen3-Reranker-0.6B` is not measured: it needs its own adapter (it is used as a causal LM), is heavier on a CPU, and would only pay off with a very large gain. It stays as a possibility.

### 2.2 Official recall (with `bge-m3`, RRF fusion)

| Reranker | Also reranks the docs branch | Docs R@1/@3/@5/@10 | Code R@1/@3/@5/@10 |
|---|---|---|---|
| `ms-marco-MiniLM-L-6-v2` | no | 0.75 / **0.92 / 0.92** / 0.94 | 0.52 / 0.71 / 0.79 / 0.86 |
| `ms-marco-MiniLM-L-6-v2` | yes | 0.71 / 0.89 / 0.91 / 0.92 | 0.52 / 0.71 / 0.79 / 0.86 |
| **`mmarco-mMiniLMv2-L12`** | no | 0.75 / 0.90 / 0.91 / 0.94 | 0.51 / **0.72 / 0.80 / 0.88** |
| `mmarco-mMiniLMv2-L12` | yes | 0.70 / 0.88 / 0.90 / 0.93 | 0.51 / 0.72 / 0.80 / 0.88 |
| `bge-reranker-v2-m3` (`46`, measured later) | no | **0.78 / 0.92** / 0.92 / 0.94 | 0.52 / **0.83 / 0.86** / 0.87 |

- **Reranking the docs branch still hurts** with both rerankers (−0.01 to −0.02 on R@5), so it stays disabled (`rerank_doc_branch = false`), as in v1.
- **`bge-reranker-v2-m3`:** the first measurement stopped because the system ran out of memory (Claude Code stopped the process while the session was idle). **Relaunched at the author's request, in the foreground:**
  - **Result:** code R@5 +0.06 (0.80 → 0.86) and R@3 +0.11, with R@10 −0.01; docs R@1 +0.02 and R@3 +0.01.
  - **Cost:** 439 s for the code dataset (~4.4 s per question on GPU), against 15 s with `mmarco`; ~23 s per query on CPU.
  - **Memory:** a peak of 39.1 GB of committed memory out of 67.9 GB; it was not close to the limit. The process adds about 16 GB to the system load.
  - **Decision:** available as the optional `gpu-quality` profile (`make bench PROFILE=gpu-quality`); the base stays with `mmarco`.

### 2.3 Multilingual (20 questions, with `bge-m3`)

| Reranker | Docs ES | Code ES | Docs EN | Code EN |
|---|---|---|---|---|
| `ms-marco` (English only) | 0.30 / 0.60 / 0.70 / 0.90 | 0.60 / 0.80 / 0.80 / 0.90 | 0.80 / 0.90 / 0.90 / 1.00 | 0.60 / 0.90 / 0.90 / 0.90 |
| **`mmarco` (multilingual)** | **0.60 / 0.90 / 0.90 / 0.90** | 0.50 / 0.70 / 0.80 / 0.90 | 0.80 / 0.90 / 0.90 / 1.00 | 0.50 / 0.70 / 0.80 / 0.90 |

**Finding:** the docs branch uses no reranker, so if the reranker changes docs in Spanish, it is because **those questions were being sent to the code branch** (see §3).

### 2.4 Decision

**`cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` by default.**
- On the official benchmark it ties with `ms-marco` on R@5 (+0.01 on code, −0.01 on docs) and wins on R@10 (code +0.02). It loses 0.02 on docs R@3.
- In Spanish it improves docs a lot (R@5 0.70 → 0.90).
- It costs twice as much as `ms-marco` (97 ms vs 57 ms on GPU, 1.8 s vs 0.9 s on CPU), and is still workable on a CPU.

---

## 3. Docs/code classifier (Phase 2, step 5)

The lexical classifier picks the branch (docs or code) by comparing the BM25 scores of the two indices plus some vocabulary signals.

### 3.1 Routing errors

| Configuration | Official docs → code | Official code → docs | Docs ES → code | Code ES → docs |
|---|---|---|---|---|
| v1 (English-only signals, punctuation not stripped) | 25/100 | 1/100 | **10/10** | 0/10 |
| + punctuation stripping (incl. `¿¡`) | 23/100 | 1/100 | 10/10 | 0/10 |
| **+ Spanish signals** (default) | **23/100** | **1/100** | **8/10** | **0/10** |
| docs signals ×2 (weight 1.0) | 18/100 | 7/100 | 7/10 | 1/10 |
| docs signals ×3 (weight 1.5) | 11/100 | 17/100 | 5/10 | 1/10 |
| signals ×2 + margin 1.5 | 8/100 | 19/100 | 5/10 | 1/10 |

### 3.2 Official recall

| Configuration | Docs R@1/@3/@5/@10 | Code R@1/@3/@5/@10 |
|---|---|---|
| v1 (`47-defaults`) | 0.75 / 0.90 / 0.91 / 0.94 | 0.51 / 0.72 / 0.80 / 0.88 |
| **+ Spanish + punctuation** (`48-cls-w0.5-m0.5`) | **0.76 / 0.91 / 0.92** / 0.94 | 0.51 / 0.72 / 0.80 / 0.88 |
| signals ×2 (`48-cls-w1.0-m0.5`) | 0.76 / 0.91 / 0.92 / 0.94 | 0.47 / 0.68 / 0.76 / 0.84 |
| signals ×3 (`48-cls-w1.5-m0.5`) | 0.77 / 0.91 / 0.93 / 0.95 | 0.42 / 0.61 / 0.68 / 0.75 |
| signals ×2 + margin 1.5 (`48-cls-w1.0-m1.5`) | 0.77 / 0.91 / 0.93 / 0.95 | 0.41 / 0.59 / 0.66 / 0.73 |

### 3.3 Decision

- **Spanish signals + punctuation stripping: adopted.** They are a strict improvement on the official benchmark (docs +0.01 on R@1, R@3 and R@5; code identical).
- **Weights and margin: unchanged.** Every docs question no longer sent to code is paid for with misrouted code questions, and code collapses (R@5 down to 0.66).
- ⚠️ **On the Spanish set**, docs loses one question on R@3 and R@5 (0.90 → 0.80): the signals send two questions to the docs branch, which has no reranker, and one does worse there. The reference benchmark is the official one (D4).
- The lexical classifier is at its limit. A semantic classifier (for example, with the embeddings already computed) remains a future improvement.

---

## 4. Final state of Phase 2 (`49-fase2-final`)

| Set | Docs R@1/@3/@5/@10 | Code R@1/@3/@5/@10 |
|---|---|---|
| **Official (42), smart path** | **0.76 / 0.91 / 0.92 / 0.94** | **0.51 / 0.72 / 0.80 / 0.88** |
| Official, generation path (web) | 0.76 / 0.91 / 0.92 / 0.94 | 0.51 / 0.72 / 0.80 / 0.88 |
| English (20) | 0.80 / 0.90 / 0.90 / 1.00 | 0.50 / 0.70 / 0.80 / 0.90 |
| Spanish (20) | 0.60 / 0.80 / 0.80 / 0.90 | 0.50 / 0.70 / 0.80 / 0.90 |

**Evolution on the official path:**

| | Docs R@5 | Docs R@10 | Code R@5 | Code R@10 |
|---|---|---|---|---|
| v1 (Phase 0, baseline) | 0.85 | 0.85 | 0.64 | 0.72 |
| End of Phase 1 | 0.87 | 0.89 | 0.64 | 0.71 |
| **End of Phase 2** | **0.92** | **0.94** | **0.80** | **0.88** |

**Default configuration:** code-aware BM25 (`code`) + `bge-m3` (in both branches) + the `mmarco-mMiniLMv2-L12` reranker with RRF fusion, the reranker always on in the code branch, and a classifier with English and Spanish signals.

---

## 5. Generation: comparison of LLMs (Phase 3)

**Common conditions:**
- The default retrieval (`bge-m3` + `mmarco` + relevance gate) and the same prompt (v3a), k = 5, greedy decoding and 150 output tokens.
- **`gen-bench` with 25 questions** from each official dataset, the 20 of the Spanish set and the 40 out-of-domain ones.
- **Judge:** `openai/gpt-oss-120b` through Groq, a 0–2 score against the 42 reference answer, on **10 answers per set**. Each answer moves the set's average by 0.1–0.2: only large differences are reliable.
- Runs `10-llm-*` in `bench/results/gen/` and `bench/results/judge/`.

| Model | Judge (mean 0–2) | F1 docs / code | False "not found" on code | s/answer (docs / code, GPU) | Download | License |
|---|---|---|---|---|---|---|
| **Qwen3-0.6B** (base) | 1.25 | 0.471 / 0.450 | 0.12 | 3.9 / 2.7 | ~1.2 GB | Apache 2.0 |
| Qwen3-1.7B | 1.53 | 0.497 / 0.494 | 0.08 | 4.0 / 3.1 | ~4 GB | Apache 2.0 |
| Qwen3-4B | **1.60** | **0.575 / 0.498** | **0.04** | 5.1 / 4.8 * | ~8 GB | Apache 2.0 |
| Phi-4-mini (3.8B) | 1.45 | 0.492 / 0.426 | 0.12 | 3.8 / 2.7 | ~7.7 GB | MIT |
| SmolLM3-3B (discarded) | 1.45 | 0.368 / 0.353 | 0.24 | 5.4 / 3.0 | ~6 GB | Apache 2.0 |

\* Qwen3-4B does not fit in a 12 GB GPU together with `bge-m3` and the reranker: its profile runs retrieval on the CPU (same results, more latency).

**Judge per set (0–2):**

| Model | Docs EN | Code EN | Docs ES | Code ES |
|---|---|---|---|---|
| Qwen3-0.6B | 1.00 | 1.20 | 1.70 | 1.10 |
| Qwen3-1.7B | 1.30 | 1.30 | 1.90 | 1.60 |
| Qwen3-4B | 1.60 | 1.30 | 1.80 | 1.70 |
| Phi-4-mini | 1.40 | 1.20 | 1.80 | 1.40 |
| SmolLM3-3B | 1.10 | 1.30 | 1.60 | 1.80 |

**Other results:**
- All of them answer in the language of the question (90–100%) and reject 100% of the clearly unrelated questions (the gate runs before the LLM).
- On the "almost in-domain" questions in Spanish, Qwen3-4B (0.90) and Phi-4-mini (0.80) reject better than the base (0.70).

**Decision (the author's):**
- **The whole Qwen3 family:** 0.6B (the base, mandatory), and 1.7B and 4B as profiles.
- **Phi-4-mini** as an alternative from another family.
- **SmolLM3-3B discarded:** the lowest F1 and twice as many false rejections on code as the base.
- **Which model the web recommends:** decided in Phase 6.
- **CPU speed of the optional models: not measured.** Given their size, the 3–4B ones will be much slower without a GPU.

---

## 6. General knowledge: XQuAD en/es (Phase 4a)

The same 1,190 questions, in English and in Spanish, over a mixed domain (`xquad`: 48 Wikipedia articles × 2 languages, indexed together). The correct source is the exact answer span in the file of the question's language. `search_smart`, k = 10.

| Configuration | EN @1/@3/@5/@10 | ES @1/@3/@5/@10 | Time EN/ES (s) |
|---|---|---|---|
| BM25 only | 0.92 / 0.97 / 0.98 / 0.99 | 0.88 / 0.97 / 0.98 / 0.99 | 0 / 0 |
| **Base (BM25 + `bge-m3`)** | **0.95 / 0.99 / 0.99 / 1.00** | **0.92 / 0.99 / 0.99 / 1.00** | 42 / 49 |
| Base + reranker in the doc branch | 0.95 / 0.99 / 1.00 / 1.00 | 0.94 / 0.99 / 1.00 / 1.00 | 189 / 194 |

**Reading:**
- **A nearly saturated corpus:** from R@3 on, every configuration is above 0.97. XQuAD measures multilinguality, not which configuration to choose (MLQA would be for that).
- **A ~3-point EN–ES gap on R@1:** for 32 Spanish questions the first result is the same article in English (14 the other way round). It is a correct answer in the wrong language.
- **The reranker in the doc branch is not adopted:** +0.02 on R@1 in Spanish for 4× the time, and on vLLM it made docs worse.

### 6.1 Router without a filter (`44-router-base`)

Every question is searched in **all** the indexed domains (`vllm`, `xquad`). The winning domain is the one whose best source (among its top 5) gets the highest cross-encoder score, the same signal as the out-of-domain gate (B15).

| Set | Questions | To the right domain | Recall @1/@3/@5/@10 with the router |
|---|---|---|---|
| 42 docs | 100 | **1.000** | 0.76 / 0.91 / 0.92 / 0.94 (the same as with the domain fixed) |
| 42 code | 100 | **1.000** | 0.51 / 0.72 / 0.80 / 0.88 (the same) |
| Complementary ES docs / code | 10 / 10 | 1.000 / 1.000 | 0.60 / 0.80 / 0.80 / 0.90 · 0.50 / 0.70 / 0.80 / 0.90 |
| XQuAD EN | 1,190 | **0.982** | 0.94 / 0.97 / 0.98 / 0.98 (vs 0.95 / 0.99 / 0.99 / 1.00) |
| XQuAD ES | 1,190 | **0.978** | 0.91 / 0.97 / 0.97 / 0.98 (vs 0.92 / 0.99 / 0.99 / 1.00) |

**Reading:**
- **No 42 question goes astray.** The official benchmark still fixes `vllm`, so its numbers do not depend on the router.
- **The 2% of XQuAD that ends up in vLLM** are questions that, out of context, are ambiguous or sound technical. For example, *"In the article's title, what did the machine hope to end?"*, *"What is one way in which graphs can be encoded?"* or *"What are stators attached to?"*. That is the cost of not filtering; with the domain filter, recall goes back to that of §6.
- **Cost:** every question is searched in both domains and 10 pairs are scored with the cross-encoder.

### 6.2 Generation over XQuAD (Qwen3-0.6B, k = 5, 1,190 questions per language)

XQuAD's reference answers are short spans (for example, "308") and the model answers with full sentences, so F1 penalises every extra word. The main metric is **"contains the answer"**: whether the normalised reference appears inside the answer.

| Configuration | Contains EN / ES | "Not found" EN / ES | Dropped by the gate EN / ES | F1 EN / ES |
|---|---|---|---|---|
| Global threshold 0.0 (`20-xquad-base`) | 0.59 / 0.51 | 0.22 / 0.19 | 0.17 / 0.19 | 0.152 / 0.149 |
| **Own threshold −2.0 (`22-xquad-gate-2`)** | **0.65 / 0.57** | **0.13 / 0.08** | **0.07 / 0.07** | 0.167 / 0.169 |

- **The out-of-domain gate was calibrated for vLLM only.** With XQuAD's own threshold (calibrated with `gate_scores`; the full case is in `changelog/FASE_4.md` §1.2), 6 points are recovered without letting any unrelated question through.
- **Citations and language:** the right source is cited in 99% of the answers, and they are in the question's language in 98–99%.
- **What is missing is on the generation side:**
  - In English, 6% of refusals with the answer in the context.
  - In Spanish, the answer is picked up less well (0.62 vs 0.74 among the questions it answers).
- **Time:** 1.4–2.5 s per answer, 96% of it in generation. Iterations use a fixed subset of 300 questions per language (~20 min, ±2 points against the full set).

---

## 7. CV mode (Phase 4b)

Corpus: the CV (`.docx`, English), the LinkedIn profile (`.pdf`, Spanish) and the biography (Spanish + an English version). Own benchmark: the same 30 questions in English and Spanish, plus 10 about the author with no answer in the data (private contact, reserved topics, missing data). Qwen3-0.6B.

| Run | Change | Contains EN / ES | Cites the right one EN / ES | Missing data handled well EN / ES | Leaks |
|---|---|---|---|---|---|
| `30-cv-base` | first version | 0.50 / 0.57 | 0.57 / 0.88 | 9/10 · 7/10 | 0 |
| `31`–`31b` | CV prompt + "not found" patterns | 0.40 / 0.67 | 0.30 / 0.77 | — | 0 |
| `32-cv-k8` | 8 sources | 0.53 / 0.57 | 0.38 / 0.77 | 10/10 · 9/10 | 0 |
| `33-cv-chunks800` | chunks of 800 / 400 | 0.50 / 0.67 | 0.64 / 0.96 | 9/10 · 9/10 | 0 |
| `34` | threshold −3.0 | 0.57 / 0.70 | 0.62 / 0.92 | 9/10 · 9/10 | 0 |
| **`35-cv-bio-en`** | **English biography + contact rule** | **0.73 / 0.80** | 0.73 / 0.89 | **10/10 · 9/10** | **0** |
| `36` (discarded) | "do not answer yes/no" rule | 0.60 / 0.73 | 0.74 / 0.89 | 10/10 · 9/10 | 0 |

- **EN retrieval with the English biography:** from 0.13 / 0.43 / 0.57 / 0.70 to **0.47 / 0.80 / 0.93 / 0.97**. ES: 0.70 / 0.83 / 0.97 / 1.00.
- **Out-of-domain gate threshold:** −3.0. It lets 93% of the valid questions through (EN/ES) and no out-of-domain question.
- **Router with 3 domains** (`46-router-cv`): 100% of the 42 and CV questions reach their domain; XQuAD, 98%.
- **The biggest gains come from the data** (the English version) and from the **chunk size** (less mixing of jobs). Prompt rules fix specific cases (reserved topics, the contact), but with a 0.6B model every extra rule can cost correct answers (`36`).

---

## 8. Agent vs direct access (Phase 5)

`make agent-bench` (`src/evaluation/agent_bench.py`): every question is answered with the agent and with the direct pipeline, with the same LLM (the profile's) and `k = 5`. Sets:
- **Conversations:** 12 dialogues (12 first questions + 18 follow-ups that depend on the earlier turns).
- **CV:** 30 + 30 (EN/ES).
- **XQuAD:** 50 + 50, a fixed sample.
- **vLLM:** 25 docs + 25 code.

On vLLM the useful metric is F1 (the 42 answers are long sentences, so "contains the answer" is ~0 in both modes).

**Two rounds:**
- **`01-agent-*`:** the agent as it came out of the design (§4 of `changelog/FASE_5.md`).
- **`02-agent-nets-*`:** with the two safety nets (`decisions.md`, DEC-03):
  1. If the model's queries find nothing, the original question is searched.
  2. If the model restricted the domains and found nothing, the search is repeated within the user's filter (no filter: in all of them), never outside it.

### 8.1 Contains the answer, agent / direct

| Set | 0.6B r1 | **0.6B r2** | 1.7B r1 | 1.7B r2 | 4B r1 | 4B r2 | Phi-4-mini r1 | Phi-4-mini r2 |
|---|---|---|---|---|---|---|---|---|
| Conversations: 1st question | 1.00 / 1.00 | **1.00 / 1.00** | 0.83 / 0.92 | 0.92 / 0.92 | 0.92 / 0.92 | 0.92 / 0.92 | 0.83 / 0.92 | 0.83 / 0.92 |
| **Conversations: follow-ups** | 0.44 / 0.33 | **0.78 / 0.33** | 0.28 / 0.33 | **0.83** / 0.33 | 0.89 / 0.39 | **1.00** / 0.39 | 0.78 / 0.33 | 0.78 / 0.33 |
| CV EN | 0.70 / 0.73 | 0.70 / 0.73 | 0.80 / 0.90 | 0.90 / 0.90 | 0.80 / 0.90 | 0.87 / 0.90 | 0.83 / 0.87 | 0.83 / 0.87 |
| CV ES | 0.80 / 0.80 | 0.80 / 0.80 | 0.73 / 0.90 | 0.87 / 0.90 | 0.87 / 0.93 | 0.90 / 0.93 | 0.90 / 0.90 | 0.90 / 0.90 |
| XQuAD EN | 0.50 / 0.62 | 0.58 / 0.62 | 0.46 / 0.78 | 0.76 / 0.78 | 0.80 / 0.78 | 0.80 / 0.78 | 0.72 / 0.74 | 0.74 / 0.74 |
| XQuAD ES | 0.64 / 0.70 | **0.70 / 0.70** | 0.50 / 0.70 | 0.68 / 0.70 | 0.86 / 0.88 | 0.88 / 0.88 | 0.60 / 0.68 | 0.64 / 0.68 |
| vLLM docs (F1) | 0.52 / 0.52 | 0.52 / 0.52 | 0.51 / 0.51 | 0.51 / 0.51 | 0.58 / 0.57 | 0.58 / 0.57 | 0.43 / 0.46 | 0.45 / 0.46 |
| vLLM code (F1) | 0.43 / 0.44 | 0.43 / 0.44 | 0.51 / 0.51 | 0.51 / 0.51 | 0.50 / 0.50 | 0.50 / 0.50 | 0.45 / 0.42 | 0.45 / 0.42 |

The direct-mode values do not change between rounds (the direct pipeline was not touched), which confirms that the comparison is fair.

### 8.2 "Not found", latency and use of the nets (round 2)

| Model | "Not found" on follow-ups, agent / direct | s/answer, agent / direct (1st q. · follow-ups · XQuAD EN) | Nets used (follow-ups · XQuAD EN · CV EN) |
|---|---|---|---|
| **Qwen3-0.6B** | **0.11 / 0.50** | 3.4/1.6 · 4.3/1.0 · 3.5/1.6 | 39% · 24% · 7% |
| Qwen3-1.7B | 0.06 / 0.50 | 3.1/1.5 · 4.1/1.3 · 3.2/1.5 | 56% · 42% · 17% |
| Qwen3-4B | 0.00 / 0.44 | 6.0/3.5 · 7.2/3.6 · 6.7/4.1 | 11% · 8% · 10% |
| Phi-4-mini | 0.17 / 0.50 | 3.4/2.5 · 5.7/1.7 · 5.3/2.3 | 6% · 12% · 3% |

Times on the 3080 Ti; on the Space's CPU they will be several times longer.

⚠️ **The "tool calls" column of the console table changes meaning in round 2.** In round 1 it counted the answers with at least one valid tool call. In round 2 it counts those that did **not** end in the deterministic fallback, which is now also used when the model's searches and net 1 find nothing. That is why it drops (0.6B: from 1.00 to 0.67 on follow-ups) without the model calling the tool any worse. The metric that measures the nets is `safety_net_rate` (in the JSON files).

### 8.3 Reading

- **The agent wins where it has to win: on follow-ups.** Without memory, "And in which year?" cannot be answered (direct: 0.33, with 50% "not found"). With the agent, Qwen3-0.6B reaches **0.78** and Qwen3-4B, **1.00**.
- **The safety nets fix what the agent was losing on single questions.** In round 1, the 0.6B and the 1.7B lost on XQuAD (up to −0.32 with the 1.7B), because their keyword-style rewrites did not pass the relevance gate or because they restricted the domain wrongly. In round 2 the agent is **on a par with direct mode (±0.04)** on every set of single questions with all four models. With the 1.7B, follow-ups go from 0.28 to 0.83.
- **The user's filter is always respected** (test `test_user_filter_is_never_exceeded`): net 2's retries never go beyond it.
- **vLLM:** the agent neither adds nor takes away (same F1); these are self-contained questions.
- **Cost:** the agent adds 1–3 s per answer with the small models (one planning call and another to say DONE) and ~3 s with the 4B.
- **Which model to deploy** (proposal, to be decided with the author):
  - **Qwen3-0.6B**, the base (`PLANING.md`): with the nets, the agent no longer loses against direct mode, it improves follow-ups a lot, and it is the lightest for the Space's free CPU.
  - **Qwen3-1.7B** is the clear candidate if the CPU can take it: the same latency on GPU and better on the CV (0.90 / 0.87 vs 0.70 / 0.80) and XQuAD EN (0.76 vs 0.58). Its latency on the Space's CPU **has not been measured**.
  - **Qwen3-4B** is the best agent (1.00 on follow-ups), but takes ~2× on GPU. On a CPU it would foreseeably be too slow for a website (not measured).
  - **Phi-4-mini** is not worth it: less reliable tool calls (44% on XQuAD ES) and a worse F1 on vLLM docs.

### 8.4 Latency on the deployment CPU (Phase 6)

The Space image run locally with the free tier's limits simulated (`docker run --cpus=2 --memory=16g`), Qwen3-0.6B and 4 questions (CV, a follow-up, vLLM and XQuAD). Details in `changelog/FASE_6.md` §6.

| Mode | First token | Full answer |
|---|---|---|
| Direct | 9.6–17.5 s | 14.3–24.0 s |
| Agent | 18.2–27.5 s | 22.0–31.7 s |

- **With torch's threads left unadjusted** (12 threads on 2 vCPUs), everything was ~3.5× slower: 48–88 s direct and 84–123 s with the agent. They are adjusted in `entrypoint.sh` (DEC-17).
- **On a CPU, the agent costs ~8 s more per answer.** On the 3080 Ti it was ~2 s.
