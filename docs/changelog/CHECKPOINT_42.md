# CHECKPOINT — 42 tests (after Phase 3)

> English translation of [`../es/changelog/CHECKPOINT_42.md`](../es/changelog/CHECKPOINT_42.md), the working version.

**Date:** 2026-10-19
**Result:** ✅ passed. The measured core (retrieval + generation) beats v1 on the official benchmark and is still compatible with the 42 moulinette.
**Tag:** `v2.0-core`, a marker on the checkpoint commit, like `v1.0-42`. It is not a branch: the project stays on `main`. It is there to compare (`git diff v2.0-core`) or to go back to this point.

Starting point: the v1 delivered to 42 (`v1.0-42`), measured with its own code on the same data (run `00-baseline`).

---

## 1. Compatibility with 42

Every command, run with **the exact syntax of the v1 Makefile**:

| Command (v1) | Result | Time (GPU) |
|---|---|---|
| `index --max_chunk_size 2000` | ✅ 16,716 parents and 37,381 children, embedded with `bge-m3` | 414 s |
| `search "How to configure OpenAI server?" --k 10` | ✅ 10 sources | 21 s* |
| `search_dataset --dataset_path … --save_directory …` (docs, code) | ✅ | 30 s / 40 s* |
| `evaluate --student_answer_path … --dataset_path … --k 10 --max_context_length 2000` | ✅ the same recall as `make bench` | 11 s |
| `answer_dataset … --skip_generation True` (docs, code) | ✅ | 33 s / 42 s* |
| `answer_dataset … --skip_generation False` (docs, 100 questions) | ✅ | 310 s |
| `answer "How to configure OpenAI server?" --k 10` | ✅ (a poor answer, see §6) | 30 s* |

\* Includes loading the models on each invocation.

**Output format:** the 5 JSON files produced validate against `StudentSearchResults` / `StudentSearchResultsAndAnswer`.
- 100 questions each, `k=10`, no path with `\`.
- Keys `question_id`, `question_str`, `retrieved_sources` (and `answer` in the answers file).
- **`src/models.py` is identical to the one in `v1.0-42`** (the only difference is line endings). The change from `"question"` to `"question_str"` seen in old outputs in the history was made by the author in v1 itself (commit "Final finalisimo", 18 June), before the delivery.

**Behaviour difference:** `answer_dataset --skip_generation True` leaves **2 code questions without sources**, the 2 legitimate ones that the relevance gate rejects (Phase 3, §2.3). That command uses the generation path, as in v1 (which had the BM25 gate). `search_dataset`, the one behind the official recall, returns sources for all of them.

---

## 2. Official recall (public 42 datasets, `k = 10`)

| | Docs R@1/@3/@5/@10 | Code R@1/@3/@5/@10 |
|---|---|---|
| Original v1 (`00-baseline`) | 0.64 / 0.83 / 0.85 / 0.85 | 0.44 / 0.61 / 0.63 / 0.68 |
| End of Phase 0 (`04`) | 0.64 / 0.83 / 0.85 / 0.85 | 0.45 / 0.62 / 0.64 / 0.72 |
| End of Phase 1 (`20`) | 0.67 / 0.84 / 0.87 / 0.89 | 0.43 / 0.59 / 0.64 / 0.71 |
| **Checkpoint (`53`)** | **0.76 / 0.91 / 0.92 / 0.94** | **0.51 / 0.72 / 0.80 / 0.88** |
| **Difference from v1** | +0.12 / +0.08 / **+0.07** / **+0.09** | +0.07 / +0.11 / **+0.17** / **+0.20** |

**Multilingual** (the 20-question complementary set): docs in Spanish goes from R@10 0.50 (BM25 only) to **0.90**.

---

## 3. Generation (Qwen3-0.6B; 160 questions: 50 + 50 official, 20 in Spanish and 40 out of domain)

| | v1 prompt (`00-gen-baseline`) | **Checkpoint (`08-where-rule`)** |
|---|---|---|
| F1 against the 42 answer (docs / code) | 0.480 / 0.426 | **0.511 / 0.430** |
| Cites the right source (docs / code) | 0.75 / 0.82 | **0.87 / 0.86** |
| False "not found" (docs / code) | 0.02 / 0.12 | **0.00** / 0.12 (0.04 with the answer in the context) |
| Answers in Spanish (docs / code) | 0.62 / 0.70 | **0.90 / 1.00** |
| False "not found" in Spanish (docs) | 0.20 | **0.00** |
| Out-of-domain rejection: unrelated EN / ES | 0.80 / 0.90 † | **1.00 / 1.00** |
| Out-of-domain rejection: almost in-domain EN / ES | 1.00 / 0.70 | 0.80 / 0.70 |
| **Judge** `gpt-oss-120b` (mean 0–2, 10 per set) | 1.20 | **1.30** |
| Judge: docs EN / code EN / docs ES / code ES | **1.40** / 0.90 / 1.30 / 1.20 | 1.30 / **1.10** / **1.60** / 1.20 |

† `00` used the old out-of-domain set, which included "capital of France" (which is in the corpus). That row's comparison is only indicative.

### New rule adopted at the checkpoint: "where" questions

- **Problem found when comparing with v1:** on docs EN the judge scored the new prompt lower (1.40 → 1.00). The cause was the *"Where do I find…?"* questions, whose reference is a **file path**. v1 wrote the path in the text ("Source: docs/…"); with `[n]` citations, the path only appeared on the source card, and the answer read on its own (as in the `answer_dataset` JSON) was incomplete.
- **Rule added to the prompt:** *"If the question asks where to find something, give the file path shown in that source's header."*
- **Effect (`07` → `08`):**
  - Judge docs EN from 1.00 to 1.30, and the mean from 1.25 to 1.30.
  - F1 docs from 0.497 to 0.511.
  - Right citation on docs from 0.80 to 0.87.
  - **Cost:** one more "almost in-domain" English question gets through (0.90 → 0.80).
- **Decision: adopted (the author's).** Docs EN stays a tenth below v1 on the judge, which is 1 answer out of 10, within the noise of the sample.

---

## 4. Without a GPU (42 conditions)

- **Full recall benchmark** with the GPU hidden (`CUDA_VISIBLE_DEVICES=-1`): **exactly the same metrics**.
- **Time:** 273 s in total (docs 55 s, code 194 s), against ~25 s with a GPU.
- **Source order:** it changes on 12 of 200 questions (2 on docs and 10 on code; half of them reorder the same sources) because of the numerical difference between CPU and GPU in the `bge-m3` computations. **Recall does not change.** In Phase 2, without embeddings, the outputs were identical byte for byte.

---

## 5. Costs vs v1

| | v1 | Checkpoint |
|---|---|---|
| Indexing | 13 s (BM25 only) | **414 s with a GPU; ~2 h estimated without one** (`bge-m3`). The `cpu-light` profile (`e5-small`): ~13 min on CPU |
| Recall benchmark (docs / code) | 8 s / 44 s (CPU) | 7 s / 16 s (GPU) · 55 s / 194 s (CPU) |
| Answering one question (CLI, GPU) | ~2–3 s | ~2.5–3 s (with streaming) |
| Infrastructure | JSON files | Qdrant in Docker (~400 MB of RAM) |

---

## 6. Known weak points

- **Very generic questions:** v1's example *"How to configure OpenAI server?"* retrieves profiling documentation and the answer is poor. Retrieval is optimised for specific questions (like the dataset's).
- **2 legitimate code questions rejected** by the relevance gate (configurable threshold).
- **The doc/code classifier** still sends 23 of 100 docs questions to the code branch (the lexical approach is at its limit; Phase 2 §10).
- **"Almost in-domain" questions in Spanish** get through 30% of the time.

---

## 7. How to reproduce it

```bash
make db-up && make index          # ~7 min with a GPU
make bench LABEL=check            # official recall (must give the "Checkpoint" row)
make gen-bench LABEL=check        # generation
make judge LABEL=check            # judge (needs .env; cached)
CUDA_VISIBLE_DEVICES=-1 make bench LABEL=check-cpu   # no-GPU conditions
```
