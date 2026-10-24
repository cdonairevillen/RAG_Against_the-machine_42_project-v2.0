# CHANGELOG — Phase 3: Improving answer generation

> English translation of [`../es/changelog/FASE_3.md`](../es/changelog/FASE_3.md), the working version.

**Start date:** 2026-10-19
**Status:** ✅ completed (2026-10-19). Generation benchmark, a new prompt, an out-of-domain guardrail (B15), a unified answer pipeline, streaming, optional LLMs with a comparison and a judge, a dead-code review, and the evaluators grouped in `src/evaluation/`.

---

## 1. Result so far

The generation benchmark (`make gen-bench`): 50 questions from each official dataset, the 20 of the Spanish set and 40 out of domain. Qwen3-0.6B, k = 5, greedy decoding, 150 output tokens.

| Set | Metric | v1 (`00`) | **Current (`06`/`07`)** |
|---|---|---|---|
| Official docs | F1 against the 42 answer | 0.480 | **0.497** |
| | False "not found" | 0.02 | **0.00** |
| | Cites some source / cites the right one | 0.82 / 0.75 | **0.90 / 0.80** |
| Official code | F1 | 0.426 | **0.437** |
| | False "not found" (with the answer in the context) | 0.12 (—) | 0.12 (**0.04**) |
| | Cites some source / cites the right one | 0.86 / 0.82 | **1.00 / 0.84** |
| Spanish docs | Answers in Spanish | 0.62 | **0.90** |
| | False "not found" | 0.20 | **0.00** |
| Spanish code | Answers in Spanish | 0.70 | **1.00** |
| Out of domain | Right rejection: unrelated EN / ES | 0.80 / 0.90 | **1.00 / 1.00** (`07`, corrected set) |
| | Right rejection: almost in-domain EN / ES | 1.00 / 0.70 | 0.90 / 0.70 |

**Reading notes:**
- **The F1 of the Spanish sets is not reliable:** it compares with the 42 reference answer, which is in English, so a correct answer in Spanish scores low. In Spanish, what counts is the language, the citations and the rejections.
- **"With the answer in the context"** separates the generator's failures from retrieval's: if the right source did not reach the context, saying "not found" is the honest answer.
- Token F1 is an approximate measure (free and reproducible); the LLM judge is a complement.

---

## 2. What was changed and why

### 2.1 Generation benchmark (new)

- **`src/gen_bench.py`** + `make gen-bench` (`--limit`, `--k`). For each question it saves the answer, the sources and the metrics in `data/output/gen_bench/<label>/answers.json`; the summary goes to `bench/results/gen/`.
- **Metrics:**
  - SQuAD-style token F1.
  - Whether the answer cites a source (by file name or `[n]`) and whether it is the ground-truth one.
  - The answer's language.
  - False "not found", separating whether the answer was in the context (the same overlap criterion as the 42 evaluator).
  - Right out-of-domain rejection.
  - Latency.
- **Out-of-domain set** (`bench/datasets/ood/questions.json`): 40 questions, 20 in English and 20 in Spanish. Half are "unrelated" (geography, cooking, sport…) and the other half "almost in-domain" (nginx, PyTorch Lightning, Keras, Kubernetes…).
  - **Correction (`07`):** *"What is the capital of France?"* **is in the corpus**. The vLLM documentation uses it, with its answer, as an API example (`openai_compatible_server.md`; it appears in 79 files), so answering "Paris" while citing it is correct. It was replaced by the Everest one. Every term in the set was checked against the indexed part of the corpus (`benchmarks/` included).
  - This **qualifies B15**: the star "hallucination" case since Phase 0 was actually in the documentation.

### 2.2 New prompt (`src/generator.py`)

Measured step by step: `01` prompt v2, `04` a softened "not found" rule (discarded), `05` only the code rule (adopted).

- **Qwen3's official chat template** with `enable_thinking=False`, instead of the hand-written prompt with `/no_think`. In v1, reasoning leftovers (`</think>`) slipped through.
- **Numbered sources** `[1]…[n]` and `[n]` citations. v1's example (*"Source: \<filename\>"*) made the model copy `<filename>` literally.
- **Explicit language:** the question's language is detected (`src/language.py`) and *"Answer in Spanish/English"* is requested.
- **A rule for reading code:** *"Sources may be code: read default values, conditions and return values directly from it."* It lowered the code rejections with the answer in the context from 0.12 to 0.04.
- **A strict "not found" rule (v2's):** the softened version (`04`) improved code but made docs worse (2 false "not found" and fewer citations). Separating the two changes (`05`) showed that the improvement came from the code rule.
- **A context budget in tokens (B9):** the sources are trimmed so that the prompt fits in 3072 tokens; **the question is never truncated**. v1 truncated by characters and then, when tokenising, from the right, which is where the question was.
- **Output clean-up** (`clean_output`): reasoning leftovers and "not found" sentences in English and Spanish.
- `max_new_tokens` stays at 150 to compare without mixing effects (the reference answers have a median of 31 words).

### 2.3 Out-of-domain guardrail (B15)

- **The reranker's score** instead of the BM25 threshold: the generation path returns "not found" if the best retrieved fragment has a reranker logit below `relevance_threshold = 0.0` (a 0.5 probability of "relevant").
- **Measured** on 220 legitimate questions and 40 out of domain:

| Threshold | Legitimate rejected | Out of domain rejected |
|---|---|---|
| −3 | 0.0% | 60.0% |
| **0** | **0.9%** | **82.5%** |
| 2 | 5.0% | 87.5% |

- **Why 0:** it is the model's natural boundary (logit 0 = 50%), not a value hand-tuned to our 40 questions.
- **Why it was needed:** with the new prompt, Qwen was keener to answer out of domain (`01`: rejection of 0.50–0.80). A 0.6B model is not a good guardrail; the gate goes **before** the LLM.
- **Cost:** 2 legitimate code questions are wrongly rejected (about `OvisConfig` and Triton attention). On the web's path, code R@5 goes from 0.80 to 0.78. **The official benchmark does not change** (`search_dataset` does not use the gate).
- The BM25 threshold (`bm25_score_floor`) stays only as a fallback if no reranker is loaded.

### 2.4 A single answer pipeline (the author's proposal)

- **`src/rag.py` (new): `RagPipeline.answer()`**, which does retrieval (`search_for_generation`: `search_smart` + gate) → context blocks → generation, with optional streaming (`on_piece`). It returns a `RagAnswer` (text, sources in `[n]` order, `not_found` and timings).
- **Everything uses it:** the CLI's `answer` and `answer_dataset`, the web and the generation benchmark. There used to be four copies of the same sequence.
- **One measurement point per thing:** `make bench` measures recall (the official benchmark) and `make gen-bench` the whole answer pipeline, gate included. `bench`'s `generation` mode and `make bench-gen` are **removed**.
- **Checked:** the 160 benchmark answers are identical before and after unifying (`05` = `06`).

### 2.5 Streaming

- `Generator.stream_answer()` uses transformers' `TextIteratorStreamer`, with generation in another thread; the same prompt and the same decoding as `answer_with_text()`.
- **CLI:** `answer` shows the answer as it is generated (`--stream False` to turn it off).
- **Web:** the answer is drawn as it is generated, and then the `[1]…[n]` source cards appear.

### 2.6 Web

- Uses `RagPipeline` with streaming.
- **B6 solved:** the answer is escaped before rendering it as HTML; code quoted with `<…>` no longer breaks the page.
- **Really tested** with `streamlit.testing.AppTest` (it runs the page without a browser, types a question and presses the button): the question in Spanish is answered in Spanish with its `[1]` citation and 5 source cards.
- ⚠️ **On the author's machine, Windows Application Control blocks `streamlit.exe`** (pip's launcher, as happened with `pyarrow`). It works with `python -m streamlit run src/web.py`, and **`make web` now launches it that way**.
- **B5 still pending:** the model is loaded per browser session; solved in the web rewrite (Phase 6).

### 2.7 Dead-code review (at the author's request)

After the restructurings (ingestion into `src/ingestion/`, a single pipeline in `src/rag.py`, the end of the `generation` mode) the code was reviewed with **`vulture`** (static analysis, run once with `uvx`, without adding it to the project), and each finding was checked by hand.

**Removed:**

| What | Why |
|---|---|
| `Embedder.dimension` | Never used (the dimension is read from the vector itself) |
| `Generator.MODEL_NAME` | The model now comes from `[generation]` in `rag.toml` |
| `Generator(repo_root=…)` | Kept "for compatibility", but nobody passed it any more |
| `Retriever.search_no_rerank()` | It was an alias of `search()`; only `search()` remains |
| `bench --mode` and `MODES` | Since the paths were unified only `smart` remained. `"mode": "smart"` is kept in the results so as not to break the comparison with the 90 already saved |
| Copies of `build_context_blocks` / `is_not_found` in the CLI and the web | Replaced by the single pipeline (`src/rag.py`) |

**Turned into something useful:** `TOKEN_MODES` described the valid modes of `code_aware_tokens`, but nothing checked them. Now the configuration type is `Literal[...]`, so a misspelt value (`"cod"`) gives a clear error instead of silently behaving like `"none"`.

**Kept, although `vulture` flags it:**
- The CLI commands (`search_dataset`, `evaluate`, `bench`…): Fire calls them by name.
- `max_context_length` in `evaluate`: compatibility with the 42 moulinette's call.
- `question_str`: the 42 JSON format.
- `Chunk.modality`: stored in Qdrant and the basis for Phase 4b.
- `available_profiles`: the list for the web's picker (Phase 6), with a test.

**Outdated documentation fixed:** the `Retriever` docstring described `search_for_generation` as "BM25 + reranker over the unified index", which was the old path.

**Checked:** recall identical to `49-fase2-final` (`52-deadcode-check`), 58 tests, lint clean, and `search` and `answer` tested from the CLI.

### 2.8 Optional LLMs and the judge

- **`[generation]` in `rag.toml`:** model, `max_new_tokens`, `max_input_tokens` and `trust_remote_code`. The base is `Qwen/Qwen3-0.6B`. **Every model is loaded through `llm_sdk`** (which accepts `model_name`), without touching the SDK folder.
- **The generator no longer assumes the model is Qwen:** the end-of-answer tokens are taken from each model's configuration (before, `<|im_end|>` was hard-coded).
- **Profiles** (the author's decision after the comparison): `llm-qwen3-1.7b`, `llm-qwen3-4b` and `llm-phi4-mini`. **SmolLM3-3B, measured and discarded.** Results in `docs/BENCHMARK_REPORT.md` §5.
- **Two problems solved while measuring:**
  - **Phi-4-mini:** its repository code imports names that no longer exist in transformers 5 (`LossKwargs`). With `trust_remote_code = false`, transformers' native implementation (the `phi3` architecture) is used.
  - **Qwen3-4B:** it does not fit in 12 GB together with `bge-m3` and the reranker (accelerate tries to move part of the model to the CPU, and the SDK does not allow it). Its profile puts retrieval on the CPU, which was already shown to give the same results.
- **Judge (`src/judge.py`, `make judge LABEL=…`):**
  - An LLM as a judge over an OpenAI-compatible API (Groq, `openai/gpt-oss-120b`), with a 0–2 score against the 42 reference answer.
  - **It only runs on request**, over the answers already saved by `gen-bench`; the normal program never uses it.
  - **Saving quota:** a disk cache (`data/output/judge_cache.json`), "not found" answers are not sent, a pause between requests and retries on 429. In total, about 190 calls to compare the five models.
  - It reads `JUDGE_BASE_URL`, `JUDGE_MODEL` and `GROQ_API_KEY` from `.env` (ignored by git); the key is never printed. No new dependencies (`urllib`).
  - **It solves the Spanish F1 problem:** the judge evaluates the meaning, not the language.

### 2.8 bis The "where" rule (added at the checkpoint)

**Prompt rule 5:** *"If the question asks where to find something, give the file path shown in that source's header."* The reason and the measurement are in `CHECKPOINT_42.md` §3: the docs EN judge score goes from 1.00 to 1.30.

### 2.9 Evaluators grouped in `src/evaluation/`

- `evaluator.py` (42 recall), `bench.py`, `gen_bench.py` and `judge.py` move from `src/` to **`src/evaluation/`**: it shows at a glance what is the RAG and what are the tools to measure it. Moved with `git mv` to keep the history; `judge.py` was new and was moved normally.
- **No behaviour changes:** the commands (`make bench`, `make gen-bench`, `make judge`, the 42 `evaluate`/`search_dataset`) are the same. Checked with recall identical to `49` (`53-evaluation-package`), the 42 commands, the judge (with 0 API calls thanks to the cache), 61 tests and lint clean.

---

## 3. Files

| File | Change |
|---|---|
| `src/rag.py` | **New**: `RagPipeline`, `RagAnswer`, `build_context_blocks` |
| `src/evaluation/gen_bench.py` | **New**: generation benchmark |
| `src/evaluation/judge.py` | **New**: LLM judge (Groq), with a cache |
| `src/evaluation/` | `evaluator.py` and `bench.py` moved here (§2.9) |
| `src/language.py` | **New**: language detection (es/en) |
| `src/generator.py` | Official chat template, `[n]` sources, language, token budget, `clean_output`, `stream_answer` |
| `src/retriever.py` | Relevance gate with the reranker (`top_relevance`) |
| `src/config.py`, `rag.toml` | `relevance_threshold = 0.0`; `[generation]`; the `llm-qwen3-1.7b`, `llm-qwen3-4b` and `llm-phi4-mini` profiles; `code_aware_tokens` validated |
| `src/cli.py` | `answer`/`answer_dataset` through `RagPipeline`, streaming, `gen_bench` |
| `src/bench.py`, `Makefile` | The `generation` mode and `bench-gen` removed; `gen-bench` added; `make web` with `python -m streamlit` |
| `src/web.py` | `RagPipeline` + streaming; escaped answer (B6) |
| `bench/datasets/ood/questions.json` | **New**: out-of-domain set |
| `tests/test_generator.py`, `tests/test_gen_bench.py`, `tests/test_judge.py` | **New** |
| `llm_sdk/**` | **Untouched** |

**Tests:** 61. Lint clean.

---

## 4. Pending in Phase 3

1. ~~`make web` with `python -m streamlit`~~ → done.
2. ~~The LLM layer and optional profiles~~ → done (§2.8).
3. ~~Comparison of LLMs with a judge~~ → done (§2.8 and `BENCHMARK_REPORT.md` §5).
4. ~~Closing: `BENCHMARK_REPORT.md` and the roadmap~~ → done.

**To review with the author:**
- **The model recommended in the web:** decided in Phase 6.
- **CPU speed of the optional LLMs:** not measured. The author finds it acceptable that it goes up.
- **The 2 legitimate code questions the gate rejects** (§2.3): if they are to be recovered, the threshold is configurable (`relevance_threshold`).
