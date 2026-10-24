# CHANGELOG — Phase 0: Clean-up and professionalisation

> English translation of [`../es/changelog/FASE_0.md`](../es/changelog/FASE_0.md), the working version.

**Date:** 2026-10-18
**Status:** completed. Pending the author's review and commit (no commit was made).

---

## 1. The result in one table

The public 42 datasets (100 docs questions + 100 code questions), `k = 10`, the original evaluator. Every run is in `bench/results/`.

| Run | Path | Docs R@1/@3/@5/@10 | Code R@1/@3/@5/@10 | Decision |
|---|---|---|---|---|
| `00-baseline` | smart | 0.64 / 0.83 / 0.85 / 0.85 | 0.44 / 0.61 / 0.63 / 0.68 | "Before" baseline |
| `00-baseline` | generation | 0.70 / 0.82 / 0.89 / 0.89 | 0.23 / 0.55 / 0.62 / 0.70 | The `make search-*` path (B3) |
| `01-fix-b2` | smart | = baseline (identical output, byte for byte) | = baseline | ✅ Adopted |
| `02-fix-b1` | smart | 0.66 / 0.82 / 0.84 / 0.84 | 0.46 / 0.63 / 0.65 / 0.71 | ❌ Breaks 1 docs question |
| `02b-fix-b1-refined` | smart | 0.64 / 0.83 / 0.85 / 0.85 | 0.45 / 0.62 / 0.64 / **0.72** | ✅ Adopted |
| `03-fix-b14` | smart | 0.65 / 0.82 / 0.84 / 0.85 | 0.43 / 0.58 / 0.63 / 0.75 | ❌ Worsens R@3; moved to Phase 2 |
| **`04-fase0-final`** | **smart** | **0.64 / 0.83 / 0.85 / 0.85** | **0.45 / 0.62 / 0.64 / 0.72** | **Official v2.0 baseline** |
| `04-fase0-final` | generation | 0.70 / 0.82 / 0.89 / 0.89 | 0.23 / 0.55 / 0.62 / 0.70 | Unchanged (B1 does not affect it) |

**Net result:**
- Docs stays the same, with zero questions changed.
- Code improves at every cut-off, with no per-question regressions: +0.01 on R@1, R@3 and R@5, and +0.04 on R@10.
  - 4 questions that used to fail now succeed.
  - 1 question moves up in the ranking.

> **About the README figures** (corrected after the author's clarification):
> - The README figures (docs 0.89, code 0.75 on R@10) **come from the public datasets**, although its table says *"private evaluation datasets"*: the README is mislabelled.
> - They came from earlier configurations. The author reached 0.93 on R@10, but at the cost of sinking other cut-offs.
> - **They cannot be reproduced with the `v1.0-42` code**: measured here, it gives docs 0.85 / code 0.68 on R@10 (smart path).
> - **Decision:** accepted. The official baseline is the `04-fase0-final / smart` row, which is reproducible with `make bench`. The wrong README label is fixed in the final rewrite.

---

## 2. What was changed and why

### Bugs

- **B1 — Doc/code classifier** (`src/retriever.py`, `classify_query`):
  - **Problem:** the CamelCase signal was dead, because uppercase letters were searched for after calling `.lower()`.
  - **Fix:** identifier detection now uses the original tokens, with a pattern (`IDENTIFIER_PATTERN`) that recognises snake_case, inner CamelCase (`PagedAttention`) and attached acronyms (`RMSNorm`).
  - **What had to be fine-tuned:** the first version counted **`vLLM` as an identifier** (`v→L`), and vLLM appears in almost every question, so it broke a docs question. Now the product name is excluded (`NON_IDENTIFIER_TERMS`), the possessive `'s` is removed, and plural acronyms (`LLMs`) do not count.
- **B2 — Symbol expansion** (`expand_query`):
  - **Problem:** it never added anything (whatever it added, the final filter removed) and it walked the 41,608 chunks on every query.
  - **Fix:** removed, and `expand_query` no longer receives `chunks`. Identical output and somewhat faster.
- **B3 — A single evaluation path** (`Makefile`): `search-docs` and `search-code` now use `search_dataset` (→ `search_smart`), which is the mode evaluated at 42, instead of `answer_dataset --skip_generation` (→ `search_for_generation`). The *generation* path is still available in `make bench-gen`.
- **B10 — Centralised "not found"** (`src/generator.py`): a single `is_not_found()` function with `NOT_FOUND_PATTERNS`, used by the `Generator`, the CLI and the web. There used to be three different lists.
- **B13 — Clean-up:**
  - Removed the unused `RRF_K`.
  - Standard import `from llm_sdk import Small_LLM_Model` (see §4).
  - The files in `src/` end with a newline (flake8 W292).

### New bugs found during the phase

- **B14 — The identifier decomposition in `expand_query` was dead code.**
  - **Problem:** the final filter dropped every variant that was a *substring* of the query, and the parts of an identifier always are. Only the snake_case variant of CamelCase names survived (`PagedAttention` → `paged_attention`).
  - **Measurement:** with the decomposition on (`03-fix-b14`), code R@10 goes up to 0.75, but R@1 and R@3 go down. The reason is that inflating the query inflates the BM25 score, which exceeds the manual `SKIP_RERANK_SCORE = 9.0` threshold more often, so the reranker is skipped more often (code time goes from 40 s to 19 s).
  - **Decision:** not adopted in Phase 0 (the no-regression rule). `expand_query` keeps its effective behaviour, now written explicitly and documented. **It moves to Phase 2**, together with the code-aware tokenizer (B8) and the review of thresholds.
- **B15 — Qwen answers out of domain.**
  - **Symptom:** `answer "What is the capital of France?"` returns *"The capital of France is Paris"*. The curious thing is that it is literally the rejection example of the prompt itself.
  - **Check:** verified with the original `generator.py`: it is **pre-existing behaviour**, not introduced in this phase.
  - **Cause:** the 5.5 BM25 threshold does not filter this question, and the 0.6B model ignores the instruction.
  - **Moved to Phase 3** (prompt, official chat template and guardrails).

### Repository and tools

- **A new `.gitignore`.** `data/*` is ignored **except `data/datasets/`**, plus `data/output/`.
- **`__pycache__` out of git** (`git rm --cached`; the files stay on disk).
- **Public datasets versioned** in `data/datasets/` (172 KB). Recovered from the history (commit `d4e13a6`).
  - **Reason:** the 42 CDN returns **403** without a session, so the benchmark was not reproducible.
- **vLLM 0.10.1 from GitHub** (the official `v0.10.1` tag). Checked: the 200 ground-truth sources exist and the text at their offsets matches the answers. It is equivalent to the 42 attachment.
- **`Makefile` rewritten:**
  - `install` → `data` + venv + `uv sync`. **It no longer runs `rm -rf data/`**.
  - `data`: downloads vLLM from GitHub if it is missing.
  - `data-42`: the original intranet download, for when there is access.
  - Caches in `/goinfre` **only if it exists**. Outside 42 the normal caches are used and the models are not downloaded again.
    - The detection is done by the shell (`sh -c 'test -d /goinfre'`), not `$(wildcard)`, and it can be forced with `ON_42=yes|no`.
    - **Reason:** on the author's Windows machine there is an empty `C:\goinfre\`, left over from an old `make install`. Native `make` saw it, but the shell translated `/goinfre` to the Git folder, and `uv` failed with "Access denied". The original Makefile had the same bug. The folder was not deleted; it can be removed.
  - `PY := python`. On Windows, `python3` points to the Microsoft Store stub.
  - New: `bench`, `bench-gen`, `test`. Removed: `test-*` (D1) and `index-embed` (it did nothing; it comes back in Phase 2).
  - `clean` no longer deletes `data/datasets/`.
  - The Makefile keeps LF endings on purpose (`make` on Linux).
- **`make bench`** (`src/bench.py` + the CLI's `bench` command):
  - Loads the retriever once, runs docs and code and evaluates with the 42 evaluator.
  - Saves the config, the commit and the metrics in `bench/results/<date>_<label>_<mode>.json`.
  - Prints the comparison table with the whole history.
  - Usage: `make bench LABEL=my-change`.
- **Tests** (`tests/`, `make test`): 13 tests plus 1 strict `xfail`.
  - They cover the evaluator (overlap and partial credit), `expand_query`, the classifier, the child→parent mapping and the chunk offsets.
  - **The `xfail` documents B7** (shifted offsets in enriched chunks). When it is fixed in Phase 1, the test will start to pass and force the mark to be removed.
- **`pytest`** added as a development dependency (`[dependency-groups] dev`).

---

## 3. List of files

| File | Change |
|---|---|
| `src/retriever.py` | B1, B2, B13, `expand_query` documented (B14) |
| `src/generator.py` | B10 (`is_not_found`), standard `llm_sdk` import, typing of `generate()` |
| `src/cli.py` | `bench` command; `is_not_found` delegates to the generator |
| `src/web.py` | `is_not_found` delegates to the generator |
| `src/ingester.py` | Only the final newline |
| `src/bench.py` | **New**: benchmark harness |
| `tests/test_evaluator.py`, `tests/test_retriever.py`, `tests/test_ingester.py` | **New** |
| `Makefile` | Rewritten (see above) |
| `pyproject.toml` | `pytest` (dev), `[tool.pytest.ini_options]`, `mypy_path = "llm_sdk"` |
| `uv.lock` | `pytest` and its dependencies |
| `.gitignore` | **New** |
| `data/datasets/**` | **New** (versioned public datasets) |
| `bench/results/*.json` | **New**: this phase's measurement history |
| `src/__pycache__/*`, `llm_sdk/llm_sdk/__pycache__/*` | Out of version control |
| `llm_sdk/**` | **Untouched** |

---

## 4. What to know about the architecture

- **`llm_sdk` and mypy:**
  - The package is installed through `pyproject.toml` (`[tool.uv.sources]`, editable) and imported the standard way.
  - The old `from llm_sdk.__init__ import ...` was a workaround for mypy: with `mypy_path = "."`, mypy mistook the outer `./llm_sdk/` folder (without `__init__.py`) for the package. That import also ran `__init__.py` twice.
  - Now `mypy_path = "llm_sdk"` points to the real package.
  - **Side effect:** mypy now type-checks the interaction with the SDK. That is why `generate()` carries an explicit, commented `Any`: the transformers annotations do not expose it on `PreTrainedModel`.
- **`search_smart` is the official benchmark path**, because it is the one `search_dataset` (the moulinette) uses. `search_for_generation` is the one the web and `answer` use: it gives more recall on docs but much less on code R@1, and takes 5 times longer (a reranker over 50 candidates). **Unifying or choosing a path is a decision for Phase 2.**
- **The no-regression rule applies per question, not only to the mean.** `src/bench.py` saves the outputs in `data/output/bench/<label>_<mode>/`, which allow per-question diffs (that is how the `vLLM` false positive in B1 was found).
- **Line endings:** ✅ **resolved when closing the phase (P7).**
  - **`.gitattributes`:** `* text=auto eol=lf` across the repo, and `llm_sdk/** -text` so that the SDK is not touched, not even its line endings.
  - **Commit `5a1cc4b`:** normalisation only. With `git diff --ignore-cr-at-eol` the only change is `.gitattributes` itself.
  - **`.git-blame-ignore-revs`:** makes `git blame` and GitHub skip that commit. Locally it is enabled with `git config blame.ignoreRevsFile .git-blame-ignore-revs`.
  - **Control measurement** (`05-eol-lf`): identical to `04-fase0-final`.
- **Torch on CPU:** `uv sync` installs `torch 2.12.1+cpu` (on Windows, PyPI has no CUDA). It is enough for retrieval and for Qwen3-0.6B. To use the 3080 Ti in Phases 2 and 3, the PyTorch index with CUDA will have to be set up in `pyproject.toml`; to be decided then.

---

## 5. How to check it

```bash
make data              # vLLM from GitHub (if missing)
make index             # ~15 s
make bench LABEL=check # must reproduce 04-fase0-final / smart
make test              # 13 passed, 1 xfailed
make lint              # flake8 + mypy clean
```
