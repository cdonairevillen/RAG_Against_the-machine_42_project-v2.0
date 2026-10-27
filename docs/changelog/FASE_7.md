# CHANGELOG — Phase 7: Optional work and polish

> English translation of [`../es/changelog/FASE_7.md`](../es/changelog/FASE_7.md), the working version. Updated at the end of each phase.

Phase opened on 2026-10-24, after commit `3378494` (Phase 6). **Closed on 2026-10-27** (what is pending moves to Phase 8, see `ROADMAP.md`). The plan is in `ROADMAP.md` (Phase 7). This file records what is changed, why and what it affects, following the rules in `PLANING.md`.

## Status

| Block | Status |
|---|---|
| 7a — The "about" domain (README, `docs/`, code) | ✅ Done: README, source, bilingual benchmark, separation from the CV (§7a.6), threshold and lexical rule (§7a.7), and web and bundle (§7a.8). 6 questions still go to vLLM, with no words that tell them apart |
| 7b — Answer quality (Markdown, the agent's fallback, formatting, CV judge) | Agent off by default in the web, token cap per model (§7b.1), loop detector (§7b.2), echo cleanup (§7b.3), language filter (§7b.4, turned on in §7b.8), answer form (§7b.7) **Qwen only, no tricks** (§7b.8: Phi-4-mini, its retry and `route_names` removed, "about" re-indexed) and quotes of test questions and wrong answers removed (§7b.9); the rest planned (P11 resolved: Groq) |
| Deployment | Platform changed to Oracle Cloud Always Free (DEC-19); guide in `deploy/README.md` |
| 7c — Visual (flipping cards, scroll) | Planned |
| 7d — Optional (Gulliver, MLQA) | Parked; `repetition_penalty` dropped (§7b.1). An optional model from another family to replace Phi, not tested (DEC-32) |

## 7a.1 — README rewritten (draft for the author's review)

`README.md` was as delivered to 42: vLLM only, BM25, the MiniLM reranker and the v1 figures (which, besides, were labelled as the private datasets although they came from the public ones). It is rewritten in English:
- **What it is:** three domains with their size, Qwen3-0.6B as the base and the optional profiles.
- **Results:**
  - Official 42 recall, from v1 to v2.0 (docs R@5 +0.07, code R@5 +0.17).
  - XQuAD and CV (recall and generation).
  - Router.
  - Agent vs direct.
- **How it works:** ingestion, retrieval (including the detail that the reranker is only always on in the code branch), generation, agent and MCP.
- **The rest:** the web and its API, how to run and measure it, deployment (with the simulated latencies), the folder layout, the links to `docs/`, the credits (vLLM Apache-2.0, XQuAD CC-BY-SA 4.0, models and tools) and AI usage.

Every figure comes from `BENCHMARK_REPORT.md`, `CHECKPOINT_42.md` and the changelogs; none is new. No personal data, except the author's name and public email.

**After the author's review:**
- **First line:** *"Started as part of the 42 curriculum by cdonaire…"*, approved.
- **AI usage:** *"updated together with Claude (Anthropic), and reviewed and designed by hand by Chrystian"*.
- **MIT license** (`LICENSE`, DEC-14 resolved), with a README section that leaves third-party content out (XQuAD CC-BY-SA, the 42 datasets, `llm_sdk`). Also in the Space card and in `make space-stage`.
- **Demo:** *"Live demo: coming soon"*, at the top and in *Deployment*, with a `TODO` for the Space link.
- **A table of contents** at the top.

## 7a.2 — The "about" source indexed, and a first benchmark

**File selection without copies:** the source reads the repo live (`root = "."`). After editing the documents, `make index SOURCE=about` has to be run again.
- **`exclude_paths`, a new `SourceConfig` field:** relative paths skipped entirely. It was needed because `exclude_dirs` compares names, and excluding `deploy` also removed `src/deploy/`. It is additive: the other sources are indexed the same way. Test `test_exclude_paths_skips_one_folder_not_its_namesakes`.
- **53 files go in:** the README, `deploy/README.md`, the Space card, 12 documents from `docs/` and 38 code files.
- **Out:** `data/`, `bench/`, `web/`, `tests/`, `llm_sdk/`, `deploy/stage`, `deploy/bundle`, `PLANING.md`, `RESPUESTA.md`, `Elements_frontend.md` and `CLAUDE.md`.
- **Indexed** (`make index SOURCE=about`): 537 parents and 1,369 children (635 documentation and 734 code), in 14 s. The other domains are not touched.

**Benchmark** (`bench/datasets/about/questions.json`, a draft for the author's review): 18 questions in EN and ES with their exact evidence: 15 in the README, 1 in the ROADMAP and 2 in the code. Built with `python -m src build_about_bench` (the same method as the CV) and measured with `make bench SUITE=about`.

| Run | EN @1/@3/@5/@10 | ES @1/@3/@5/@10 |
|---|---|---|
| `70-about-base` | 0.50 / 0.50 / 0.78 / 0.78 | 0.11 / 0.22 / 0.22 / 0.33 |

**Why Spanish is so low:** the Spanish questions retrieve the Spanish documents (changelogs, `decisions.md`, `ROADMAP.md`), which say the same as the README. Since each question only accepts one source, valid answers count as misses (license → DEC-14; deployment → the ROADMAP's Phase 6; Stop button → `FASE_6.md` §6g). The English questions retrieve the README.

## 7b.0 — Agent off by default in the web (the author's decision, 2026-10-24)

**Reason:** with the small models, the agent's memory mixes in earlier topics or gives answers that are too basic (measured in `FASE_6.md`: the 0.6B does not rewrite follow-ups, and the fallback answers two questions at once).
- **API:** `agent` is `False` by default in `/chat`, and `/config` returns `agent_default: false` (`AGENT_DEFAULT` in `src/api/app.py`).
- **Web:** the switch starts on "Direct RAG". When it is turned on, a note floats under the switch (without moving the page): *"Work in progress: the agent's conversation memory is still being improved, and it may mix in earlier topics."*.
- **CLI:** unchanged (`answer` and `chat` still use the agent by default, D7).
- **D7 changes only in the web**, until the fallback improvement (7b) is measured and works.

## 7a.3 — "about" kept out of the web until it is calibrated

With the API restarted after indexing "about", that domain entered the router **uncalibrated**. The author's example with the 1.7B: <!-- about:skip -->to "Chrystian Donaire Villén Que me estas contando" it answered with the author's date of birth and<!-- /about:skip --> added a sentence of internal jargon about the default agent (verbatim in `docs/es/RESPUESTAS_ARCHIVADAS.md`). The changelogs contain test transcripts (for example, `FASE_6.md` §5 quotes CV answers) and internal jargon, and the router picked them.
- **`RAG_API_DOMAINS`:** the list of domains the web serves (empty: every indexed one). `make api` uses `API_DOMAINS ?= vllm,xquad,cv` until steps 4–5 of 7a are done. `RagTools.load` accepts the domain list (optional; without it, as before).
- **Pending for step 4:** decide whether the changelogs' test transcripts stay in the "about" index or are excluded, because they put CV answers inside "about".

## 7a.4 — Documentation in two languages (the author's decision, 2026-10-24)

The documents exist in both languages, so that "about" answers well in both and recruiters can follow the workflow in English.
- **`docs/es/`:** the Spanish originals, moved with `git mv` (with `git mv`; Git only records it as a rename for `PLANING.md`, `RESPUESTA.md` and `Elements_frontend.md`. For the others, the translation reuses the old path, so their Spanish history is found with `git log docs/<file>`, not with `--follow` on `docs/es/`). They remain **the working version**. Also `PLANING.md`, `RESPUESTA.md` and `Elements_frontend.md`, which are not translated.
- **`docs/`:** the English translation of `ROADMAP.md`, `BENCHMARK_REPORT.md`, `decisions.md` and the changelogs. Updated **at the end of each phase**. Where the original speaks to the author as "you", the translation says "the author".
- **`docs/es/README.md`:** the Spanish translation of the README, with its links adjusted to its folder.
- **`CLAUDE.md`** loads the rules and the roadmap from `docs/es/`.
- **The paths** cited by the code and the config (`docs/changelog/FASE_4.md`…) remain valid: they now point to the English version.

## 7a.5 — The "about" benchmark with the bilingual documentation

**Correction of a wrong statement:** it was stated that the 42 evaluator accepts *any* ground-truth source. It does not: it computes the **fraction** of sources found (`found / len(gt_sources)` in `src/evaluation/evaluator.py`). With two sources per question (the English evidence and the Spanish one), finding only one scores 0.5. It was checked when recall went down (`71-about-bilingual`).

**What was applied:** the ground truth in the question's language, as in the CV. `questions.json` carries `file`/`evidence` (English) and `file_es`/`evidence_es` (Spanish, in `docs/es/`); the code, untranslated, serves both. The "about" source reindexed with both languages: 67 files, 721 parents and 2,039 children.

| Run | Ground truth | EN @1/@3/@5/@10 | ES @1/@3/@5/@10 |
|---|---|---|---|
| `70-about-base` | only the English README (docs only in Spanish) | 0.50 / 0.50 / 0.78 / 0.78 | 0.11 / 0.22 / 0.22 / 0.33 |
| `71-about-bilingual` | both versions at once (wrongly set up, see above) | 0.14 / 0.31 / 0.31 / 0.42 | 0.25 / 0.31 / 0.39 / 0.47 |
| `72-about-gt-per-language` | the one in the question's language | 0.28 / 0.50 / 0.50 / 0.72 | 0.44 / 0.50 / 0.67 / 0.72 |

**Why English drops in `72`:** the English questions now also find the English translation of the changelogs and the ROADMAP, which say the same as the README, and the README falls behind. A "single valid source" metric does not reflect well a corpus where several documents say the same thing.

**Complementary metric (the same as for the CV, Phase 4b):** does any of the top k sources contain the answer? It does not touch the 42 evaluator.

| | @1 | @3 | @5 |
|---|---|---|---|
| EN | 0.67 | 0.78 | **0.89** |
| ES | 0.78 | 0.83 | **0.89** |

**Reading:** "about" retrieval works in both languages: for 89% of the questions the answer is in the top 5 sources. What is left of 7a is calibrating the threshold, running `route-bench` (the risk of stealing questions from vLLM and the CV) and the web.

## 7a.6 — "about" stops competing with the CV

**Problem (`73-router-about`, the first route-bench with "about"):** "about" took 5 of the 60 CV questions, and 8 of the 36 questions about the project went to vLLM. The documentation talked about the content of the CV mode: transcripts of the tests, "an autobiography with tastes, hobbies and travels", "Where was he born…?". With questions where the CV scored low, a document that talked about the topic without holding the answer won: the router compares raw scores (−9.2, −1.2 and −4.2 for the three English CV questions).

**What was applied:**
1. **`skip_marked`** (new in `SourceConfig`, on for "about"): in `.md` files, the regions between `<!-- about:skip -->` and `<!-- /about:skip -->` are replaced by spaces before chunking. The length and the line breaks do not change, so the offsets of the rest stay exact. A section left blank produces no chunks, and an unclosed marker is an error. The markers are HTML comments, so GitHub does not show them and the document reads whole.
2. **Simpler documentation** (the author's decision: redirect, do not repeat):
   - **`ROADMAP.md` 4b:** one line with the link to `FASE_4.md` §4b and `BENCHMARK_REPORT.md` §7.
   - **Biography notes:** out of the ROADMAP.
   - **The "own texts" idea:** moves to 7d.
3. **Marked with `about:skip`** (in both languages):
   - `FASE_4.md` §4b and `BENCHMARK_REPORT.md` §7, entirely.
   - The CV test rows in `FASE_6.md` (§5 and §6).
   - The examples with personal questions in `FASE_5.md` and `FASE_7.md`.
   - **Kept:** the README says that the `cv` domain exists and who the author is. "About" must be able to answer that.
4. **Checked:** every marker is paired, and after blanking, no personal vocabulary is left in "about", except the author's name in the README and in the AI-usage credit.

"about" re-indexed: 718 parents and 2,008 children (1,258 documentation and 750 code).

**Route-bench** (`74-about-cv-skip` vs `73-router-about`):

| Set | Routing 73 → 74 | Taken by "about" | R@1/@3/@5/@10 in 74 |
|---|---|---|---|
| 42 docs / code | 0.99 → 0.99 | 1 / 1 | 0.76 / 0.91 / 0.92 / 0.94 · 0.51 / 0.72 / 0.80 / 0.88 (same) |
| XQuAD EN / ES | 0.981 / 0.975 → same | 2 / 5 | same |
| **CV EN** | **0.90 → 0.967** | 3 → 1 | R@5 0.87 → **0.90**, R@10 0.90 → **0.93** |
| **CV ES** | **0.933 → 0.967** | 2 → 1 | R@3 0.77 → **0.80**, R@5 0.90 → **0.93**, R@10 0.93 → **0.97** |
| About EN | 0.667 → 0.722 | — (to vLLM: 5 → 4) | 0.17 / 0.33 / 0.33 / 0.56 |
| About ES | 0.778 → 0.833 | — (to vLLM: 3 → 2) | 0.28 / 0.33 / 0.44 / 0.50 |

**Reading:**
- Without touching the router, the CV gets back 3 of its 5 questions and no set gets worse. The 42 benchmark does not change.
- The "about" recall in this table is the 42 evaluator's with a single valid source (see §7a.5), so it comes out low even when the answer is there.
- **Still pending:** the project questions that go to vLLM (4 + 2), the "about" threshold and the web.

## 7a.7 — The "about" threshold and the project's lexical rule

**Threshold** (`gate_scores`, `75-about-cv-skip`, with the §7a.6 index). Share that passes the "about" gate:

| Threshold | About EN / ES | Far / near out-of-domain (EN) | CV without an answer EN / ES |
|---|---|---|---|
| 0.0 (global, the previous one) | 0.67 / 0.67 | 0 / 0 | 0.10 / 0.10 |
| **−1.0** ✅ | **0.83 / 0.78** | 0 / 0.10 | 0.20 / 0.30 |
| −1.5 | 0.83 / 0.89 | 0.10 / 0.10 | 0.20 / 0.30 |
| −2.0 | 0.83 / 0.89 | 0.20 / 0.10 | 0.20 / 0.50 |

- **Why −1.0:** it recovers most valid questions without opening the door to unrelated ones. Below it, the gate starts accepting far questions.
- **Caveat:** only 18 questions per language, so each question is worth 0.06.
- **The 42 questions do not matter here:** they score high against "about" because the documentation talks about vLLM, but the router sends them to vLLM (99%), and the "about" threshold only acts when "about" wins.

**Why they went to another domain** (question by question, with the §7a.6 index; the ids are those of `bench/datasets/about/questions.json`):

| Question | Winner | "About" score | Hint? |
|---|---|---|---|
| about-01 (EN / ES) | **cv** (8.3 / 8.0): the author's CV mentions the project | 6.7 / 6.4 | the name |
| about-02 (EN) | vllm (−2.06) | −2.25 | "the project" |
| about-11 (EN) | vllm (−0.24) | −2.91 | "the project" |
| about-03 and about-09 (EN and ES) | vllm | lower | none: vLLM also answers that |

**The rule (`route_hints`, new in `SourceConfig`):** regular expressions that name a domain.
- **When it acts:** if the question matches **and** that domain passes its own threshold, it goes first. If it does not pass the threshold, routing stays as before.
- **Why it requires the threshold:** "the project" also appears in one XQuAD question per language ("…undertake the project from design to construction"), and a hint alone would have sent it to "about".
- **In "about":** `\b(this|the|your) project\b`, `\b(este|el|tu) proyecto\b` and `rag against the machine`. The other domains have no hints, so they do not change.
- **Code:** `DomainRouter.hinted` (`src/rag/router.py`), and `Retriever.route_hints` compiles the patterns.

**Route-bench** (`76-about-hints` vs `74-about-cv-skip`):

| Set | Routing | R@1/@3/@5/@10 |
|---|---|---|
| 42, XQuAD and CV | same | same |
| About EN | 0.722 → **0.778** (to vLLM: 4) | 0.17 / 0.33 / 0.33 / 0.56 → 0.22 / 0.39 / 0.39 / 0.61 |
| About ES | 0.833 → **0.889** (to vLLM: 2) | 0.28 / 0.33 / 0.44 / 0.50 → 0.33 / 0.39 / 0.50 / 0.56 |

- **What it fixes:** about-01 in both languages.
- **What it does not fix:** about-02 and about-11 (EN) do have the hint, but "about" does not pass its threshold (−2.25 and −2.91 vs −1.0). The rule does not force them, which is the intent.
- **The rest** (embeddings, Python code) are questions that the vLLM documentation also answers, with no word that tells them apart.

**Tests:** `test_a_hinted_domain_wins_when_it_passes_its_threshold` and `test_a_hint_alone_does_not_route` in `tests/test_router.py`. 109 tests; flake8 and mypy clean.

## 7a.8 — "about" in the web and in the bundle (step 5)

**Pinned domain (`pinned`, new in `SourceConfig`, on for "about"):**
- **API:** a pinned domain joins any domain filter (`ChatService.domains_for`). Without a filter (`domains: null`), every domain is searched, as before. `/config` marks each domain with `pinned`.
- **Web:** the "about" chip is always on, with a dot in front (`● about`), no hand cursor and "(always on)" in its title. Clicking it does nothing.
- **`make api`:** `API_DOMAINS` becomes empty, so the web serves every indexed domain. The deployment server already served everything in the bundle.
- **Web texts:** the introduction and the question field mention the project ("…and the project explaining itself").

**Example questions** (`web/src/examples.ts`). All checked against the real index, searching every domain. Questions about the project are named by their open-bank id (`A-NN`, listed in `docs/es/RESPUESTAS_ARCHIVADAS.md`):

| Example | Reaches | Passes the gate? |
|---|---|---|
| vLLM, XQuAD (2), CV (2) and three about the project (A-04, A-12, A-14) | its domain | yes |
| ~~"Which instrument does he play?"~~ | vllm (−3.77) | no. **It already failed without "about"**: on its own, the question does not say who "he" is |
| → "Which instrument does Chrystian play?" | cv (3.52) | yes |
| ~~An example on the project's models~~ (verbatim in `docs/es/RESPUESTAS_ARCHIVADAS.md`) | vllm (−0.83) | no |
| → A-13 | about (1.09) | yes |

**Recall cards: "about" is not shown.** Its recall with the 42 evaluator is low (R@5 0.39 / 0.50), although the answer is in the top 5 sources for 89% of the questions (§7a.5). The card would give the wrong idea.

**Bundle regenerated** (`make bundle`): vllm, xquad, cv and about, 405 MB and 58 files with SHA256.

**Tests:** `test_a_pinned_domain_joins_every_filter` and `test_config_marks_pinned_domains` in `tests/test_api.py`. 111 tests; flake8 and mypy clean; the web builds. Screenshot with headless Chrome: the pinned chip and the four domains in the system panel.

## 7b.1 — Token cap per model, and Phi-4-mini's loops

**Cap per model in the web.** It used to be 1024 for all (`FASE_6.md` §6g). Now each model has its own, fitted to what was measured: the longest valid answer was 464 tokens with Phi-4-mini (10 sources) and 321 with Qwen3-1.7B. Anything beyond that was Phi's loop, which is now cut earlier.
- **`RAG_API_MAX_TOKENS`** (new, in `ModelPool`): one number for every model, or a value per model (`default=512,llm-phi4-mini=640`). Unknown ids are ignored, and models not listed keep their `max_new_tokens`. It replaces `RAG_GENERATION_MAX_NEW_TOKENS` in `make api`.
- **`make api`:** 512 for the 0.6B and the 1.7B, and 640 for Phi-4-mini (the author's decision: it stays at 640).
- **Space:** `RAG_API_MAX_TOKENS=512` (only the small models are served there).
- **Unchanged:** `rag.toml` keeps 150 for the benchmarks; a capped answer is trimmed at its last sentence and the Stop button works as before.

**Phi-4-mini's template and end of generation (checked at the author's request).** A typical cause of loops is not using the official template or not stopping at the end-of-turn token. That is not the case here:
- The prompt comes from `apply_chat_template`: `<|system|>…<|end|><|user|>…<|end|><|assistant|>`, the official format, with no duplicated start tokens.
- `generate()` stops at the two tokens the model declares, `<|end|>` (200020) and `<|endoftext|>` (199999) (`Generator.stop_token_ids`).

The loop is the degeneration of *greedy* generation in long answers: the model never gets to want to close the turn.

**`repetition_penalty`: dropped (the author's decision).** In its loops, Phi changes words on each turn, so penalising repetition does not cut them, and it had already been seen not to work. How to give the LLM complete freedom of length stays open (ROADMAP 7b).

**Tests:** `test_max_tokens_per_model` and `test_the_pool_applies_the_caps` in `tests/test_api.py`.

## 7b.2 — Phi-4-mini's loops: detector integrated (approved by the author)

**Reproduction** (Phi-4-mini, 10 sources, 1,500-token cap, 6 "step by step" and list questions): 3 of the 6 use up the cap. The other three end by themselves in 133–493 tokens.

| Question (text and output verbatim in `docs/es/RESPUESTAS_ARCHIVADAS.md`) | How it degenerates |
|---|---|
| L-1, a vLLM step-by-step guide (EN) | From step 26 on, the same line again and again |
| L-2, the command-line options (EN) | Two alternating lines from option 29 on |
| L-3, a short step-by-step (ES) | In prose, with no line breaks, the same sentence with the ordinal changed. **It changes words on each turn**, as the author had seen: that is why penalising repetition does not work |
| All three | End with the same word repeated up to the cap |

**Microsoft** recommends on the model card what we already do: *greedy* (`do_sample=False`) and a maximum of 500 tokens. The card itself warns that Phi-4 "may generate repetitive responses".

**Idea: a loop detector by sentence similarity.** Instead of comparing exact n-grams (dropped in `FASE_6.md` §6g: it fired on 32 of 3,933 good answers), it compares **whole sentences and lines** with an approximate similarity:
- **Unit:** each line and each sentence, normalised (without list numbering or `[n]` citations).
- **Window:** among the last 8 units, if 5 or more are near-copies (similarity ≥ 0.95, `difflib`) of an earlier one in the window, it is a loop. *(Window 12 since DEC-28, §7b.7.)*
- **Left out of the comparison:** tables, HTML, logs, code and indented blocks, which repeat their shape by nature.
- **Also:** the same word 12 times in a row.
- **When detected:** generation stops and the answer is cut where the repetition starts, keeping the good part.

**Measured** (prototype in `data/output/loop_detector/`, outside git):

| | Result |
|---|---|
| Reproduced loops | **3 of 3** detected. Keeps 1,828–2,328 good characters of each |
| False positives on long documents (202 `.md` from vLLM, `docs/`, README and XQuAD) | **0** |
| False positives on stored answers (11,550, every `gen-bench` and `agent-bench`) | **0** |
| More aggressive variant (4 repeats) | 1 document and 4 answers: dropped |

**What it allows:** removing the web's fixed token cap (or raising it a lot) and letting the LLM write what it needs, stopping only when it degenerates. It answers the "freedom of length" item of 7b.

**Integrated** (with the author's approval, 2026-10-24):
- **`src/rag/loops.py`** (new): `find_loop` (the rule above) and `cut_loop`.
- **`Generator.stopping_criteria`:** a `Looping` criterion that only decodes and checks the text when the last token closes a line or a sentence, and stops generation on a loop. It works in the web, the CLI, the benchmarks and the agent.
- **`clean_output`:** cuts the loop where it starts, with or without streaming. The web replaces the streamed text with the final answer, so the repeated part disappears at the end.
- **A fix on the way:** a list number ("5. ") no longer counts as the end of a sentence. A test found it: the cut left a dangling "5.".
- **No switch:** with 0 measured false positives, there is no need to turn it off. Answers without a loop do not change.

**End-to-end test** (Phi-4-mini on GPU, the 6 questions, 1,500-token cap; `data/output/loop_detector/repro_guard.json`):

| Question | Before | With the detector |
|---|---|---|
| L-3 | 1,500 tokens, 67 s | **419 tokens, 34 s** |
| L-1 | 1,500 tokens, 69 s | **661 tokens, 47 s** |
| L-2 | 1,500 tokens, 73 s | **499 tokens, 35 s** |
| The other 3 | 133 / 248 / 493 tokens | **identical, character by character** |

The cut answers end on a complete line. The prose one keeps a few already repetitive sentences, which are the ones the detector uses as reference before confirming the loop.

**Benchmarks:** unchanged. With 150 tokens there are no loops (0 of 11,550 answers flagged).

**Web cap: 1,024 tokens for every model** (the author's decision, 2026-10-24), in `make api` and in the server image. It used to be 512, and 640 for Phi-4-mini (§7b.1). It is no longer the defence against loops, only a safety net. ⚠️ On CPU (the free server) the 0.6B writes at ~1–1.5 tokens/s: a very long answer may take several minutes, although streaming shows it as it comes and the Stop button cuts it.

**Tests:** `tests/test_loops.py` (6 tests: a repeated line, two alternating lines, sentences with one word changed, a repeated word, and tables, code and good answers with no false positive).

**A case seen on the way:** L-3 (short and ambiguous) goes to "about" (3.13 vs 2.09 for vLLM), because the documentation talks about the RAG's "step by step". Phrased completely ("Explícame paso a paso cómo usar vLLM"), it goes to vLLM (3.0 vs 1.2). The router is not touched for an edge case.

## 7b.3 — Answers that copy the prompt (echo)

**Autonomous session on the night of the 24th to the 25th** (decisions DEC-20 to DEC-26 in `decisions.md`). Rule: no case may get worse. Baseline `80-*`, taken at the start with the code of commit `02ff464`:
- **0.6B:** vllm (50 questions per set), xquad (300 per language), cv and about.
- **1.7B, Phi-4-mini and 4B:** vllm (25 per set), cv and about.

**What the author saw:**
- With Phi and A-04, the "answer" was the 5 sources copied with their headers, and the real answer (after `ANSWER:`) came at the end, cut by the token cap (verbatim in `docs/es/RESPUESTAS_ARCHIVADAS.md`).
- The wrong label of source [4] was a wrong copy by Phi; the index was right (checked).
- The 0.6B does the same on a small scale: it ends by repeating our closing instruction from the prompt.

**Measuring it (DEC-20):** an `about` suite in `gen-bench` and two new metrics, `echo` and `bad_citation` (`src/evaluation/gen_bench.py`). Echo in the baseline:

| | vllm docs | vllm code | xquad EN / ES | cv EN | about EN |
|---|---|---|---|---|---|
| Qwen3-0.6B | 0.00 | 0.02 | 0.03 / 0.01 | 0.10 | 0.06 |
| Phi-4-mini | 0.16 | 0.04 | — | 0.00 | 0.17 |
| Qwen3-1.7B and 4B | 0.00 | 0.00 | — | 0.00 | 0.00 |

**Prompts tested (DEC-21), with the full matrix:**

| Style | What changes | Drops vs `80` | Reading |
|---|---|---|---|
| `v4` (`81-*`) | Language and anti-copy rule in the system message; the user message ends with the question | **112** | They stop citing: 0.6B "cites" on vLLM docs 0.90 → 0.16, Phi 0.92 → 0.40. The language goes down. Phi's echo on about/en does fall (0.17 → 0) |
| `v6` (`82-*`) | `v3` plus only the anti-copy rule | **75** | Small changes in every direction; the echo does not fall |
| `v5` | `v4` plus "ignore the sources that do not answer" | not tested | Inherits what `v4` breaks |

**Conclusion:** the closing instruction is what makes them cite and answer in the requested language. The prompt stays at `v3`, and the code of the styles was removed.

**Cleaning (DEC-22), `strip_echo` in `clean_output`** (`src/rag/generator.py`):
1. After a copy of the sources, keep what follows the last `ANSWER:`.
2. Drop the repeated instruction.
3. If the answer opens by copying a source, keep the text without the header and cite it `[n]`.
4. Other headers become `[n] (path)`.

Since generation does not change, it was measured on the stored answers:

| Matrix | Answers | Changed | Echo before → after | Losing the reference answer | F1 |
|---|---|---|---|---|---|
| `80` (`v3`) | 1,554 | 25 | 25 → 0 | **0** | +0.86 (sum) |
| `82` (`v6`) | 1,554 | 35 | 35 → 0 | 0 | +1.04 |
| `81` (`v4`) | 1,554 | 78 | 78 → 0 | 0 | +2.70 |

The author's case with Phi becomes *"RAG against the Machine is a multi-domain Retrieval-Augmented Generation system with an agent, an MCP server, and a web interface. …"*.

**Tests:** `test_strip_echo_keeps_only_the_answer` and `test_strip_echo_handles_copied_source_headers` (`tests/test_generator.py`).

## 7b.4 — "About" sources in a single language (implemented, disabled)

For an English question, "about" returned Spanish copies of the same document (`docs/es/…`), which took up places in the context.

**Implemented** (`Retriever.search_smart`, `src/rag/retriever.py`): with `translations` (pairs of [English, Spanish] prefixes) in a source, twice as many candidates are requested, the other-language copy of translated files is removed, and the list is cut to `k`. `translation_languages` says which question language it applies to. Without `translations`, `search_smart` is exactly the previous one (`search_smart_all`), so vLLM, XQuAD and CV do not change.

**Measured with the same index** (`79-about-c-*` and `data/output/night/about_contains.py`):

| Filter | 42 recall EN @1/@3/@5/@10 | ES | Contains the answer EN @1/@3/@5 | ES | Sources in the other language (top 5, EN / ES) |
|---|---|---|---|---|---|
| No filter | 0.28 / 0.44 / 0.50 / 0.72 | 0.33 / 0.44 / 0.61 / 0.67 | 0.67 / 0.72 / 0.83 | 0.72 / 0.89 / 0.94 | 16 / 5 of 90 |
| Both languages | 0.28 / 0.50 / 0.56 / 0.72 | 0.33 / 0.44 / 0.61 / 0.72 | 0.67 / 0.78 / 0.83 | 0.72 / **0.83 / 0.83** | 3 / 0 |
| **English only** | 0.28 / 0.50 / 0.56 / 0.72 | identical | 0.67 / 0.78 / 0.83 | identical | 3 / 5 |

- **Why "both languages" loses in Spanish:** the retrieved English section sometimes holds the answer and the retrieved Spanish section is another one. For example, for about-01 in Spanish, the fragment of the English `README.md` containing "Retrieval-Augmented Generation" was removed.

**Generation** ("English only" filter `83-*` vs no filter `84-*`, same index):

| Model | about/en | about/es |
|---|---|---|
| Qwen3-0.6B | contains 0.44 → **0.61**, cites 0.23 → 0.29, language 0.93 → 1.00 | = |
| Qwen3-1.7B | correct citations 0.43 → 0.33, cites 0.93 → 0.80 | = |
| Phi-4-mini | correct citations 0.33 → 0.17, "not found" 0.17 → 0.28; language 0.80 → 0.92 | = |
| Qwen3-4B | contains 0.61 → 0.67; "not found" 0.22 → 0.28 | = |

**Decision (DEC-23):** it stays **disabled** in `rag.toml` (commented out), because it worsens metrics of the optional models. It is very good for the 0.6B, the one to be deployed: turning it on is uncommenting two lines, without re-indexing. *(Turned on in §7b.8, DEC-34.)*

**Tests:** `test_translated_copies_are_recognised` (`tests/test_retriever.py`).

## 7b.5 — Questions that name the project or the author

*(Removed in §7b.8, DEC-33.)*

**A-02** (asking about the RAG without naming it) went to vLLM (1.04 vs −1.85 for "about"), and even if it had gone to "about", its gate (−1.0) would have rejected it.

**`route_names`** (new in `SourceConfig`; `DomainRouter.named` in `src/rag/router.py`): expressions that name the domain unambiguously. If they match, that domain wins **and its gate does not apply**, in routing and also when it is the only domain in the filter.
- **In "about":** "rag against the machine", "este/esta/tu/vuestro + rag/proyecto/sistema/chatbot/asistente/web/aplicación" and "this/your + rag/project/system/chatbot/assistant/website/app".
- **"The project" and "el proyecto"** stay as a weak hint (`route_hints`): they must pass the threshold, because of the XQuAD question that says "the project".
- **Checked:** no pattern matches questions of the other benchmarks (vLLM, XQuAD, CV, out of domain, conversations).

**8 questions that name the project** (`named.py`; open-bank ids), before (the commit) and after:

| Question | Before | After |
|---|---|---|
| A-02 | vLLM, not found | about |
| A-03 | vLLM (3.91) | about |
| A-06 | XQuAD | about |
| A-07 | CV | about |
| A-08 | about, not found | about |
| A-09 | about, not found | about |
| A-10 | XQuAD | about |
| A-11 | about, not found | about |

**The author, for the CV** (weak hint `\b(chrystian|donaire)\b` in `[sources.cv]`): with a bigger "about" index, a CV question about the contact e-mail ended in "about" (0.17), which answered it with code. With the hint, if the question names the author and the CV passes its threshold (−3.0), the CV wins. Only CV questions match.

**Route-bench** (`85-night-final` vs `76-about-hints`, the state of the commit): the same routing on every set. With the new "about" index (before restoring it, `79-cv-name-hint`), the CV hint brought the CV back to 0.967 / 0.967 from 0.933 / 0.933.

**Tests:** `test_a_named_domain_wins_and_skips_its_gate` and `test_a_named_single_domain_skips_its_gate` (`tests/test_router.py`).

## 7b.6 — The "about" index, and the final check

**The "about" index grows and gets worse.** Re-indexed that night (753 parents, +35, because of the documentation of the 24th), "about" generation falls compared with the baseline **without any code change** (`84-*` vs `80-*`; for example, the 1.7B in ES "contains" 0.67 → 0.56), and one Spanish "about" question moves to vLLM.
- **Decision (DEC-25):** the **baseline index is restored** from `deploy/bundle` (718 parents, SHA256 checked). The new documentation stays out of "about" until it is re-indexed, and what parts it sees (`about:skip`) has to be decided before deployment. *(Re-indexed in §7b.8, DEC-37.)*
- **Prepared, with no effect until re-indexing:** `deploy/space/README.md` (the old Space card) leaves "about".

**Final check** (the state it was left in: prompt `v3`, `strip_echo`, `route_names`, the CV hint, the language filter disabled and the baseline index):

| Check | Result |
|---|---|
| 42 `make bench` (`85-night-final`) | **Identical:** docs 0.76 / 0.91 / 0.92 / 0.94, code 0.51 / 0.72 / 0.80 / 0.88 |
| Route-bench (`85-night-final`) | Same routing as the commit. XQuAD/ES R@1 0.9059 → 0.9050 (one question, because of the approximate vector search after restoring the bundle) |
| `gen-bench` of about (`85-*`, four models) | Identical to `80`, with the echo at 0. Phi about/en: language 1.00 → 0.93, because of an answer left as code after the cleaning (same content) |
| `gen-bench` of vllm, xquad and cv | No generation changes (same prompt and indices); the cleaning only acts on answers with an echo (§7b.3) |
| 8 questions that name the project | 8 of 8 in "about" (before, 0) |

**Tests:** 122 tests; flake8 and mypy clean.

## 7b.7 — Answer form: open questions, Phi's echo and loops (session of the 25th to the 26th)

**What the author saw in the web after the previous night:**
- **Phi-4-mini:** still copies sources with A-01 and with A-04, and the second answer comes out cut.
- **0.6B:** A-01 gives no answer at all.
- **1.7B:** answers well.

The session's rule: no case may get worse. Decisions DEC-27 to DEC-31 in `decisions.md`.

**Why it did not work:**
- **0.6B, empty answer:** the cleaning of the repeated instruction (`INSTRUCTION_ECHO`, §7b.3) went from "citing the sources by number" to the last full stop, crossing the colon, so when the 0.6B repeated the instruction followed by a colon and the answer, it swallowed the whole answer.
  - **Fix:** the pattern does not cross the colon, and if the cleaning leaves the answer empty, the original is returned.
  - **Checked:** 0 changes in the 4,662 stored answers of `80`/`81`/`82`.
- **Phi:** in the web there are two failures that `strip_echo` cannot fix.
  - **(a)** It copies the sources and the question, and stops without answering.
  - **(b)** It copies the five sources and runs out of tokens before writing the answer.

  In both cases the answer opens with `[1] --- file:`.

**Measuring it as in the web (DEC-27):**
- **`gen-bench`:** `cut` (an answer that stops mid-sentence or at 95% of the cap), `tokens` (mean) and `tokens_max` metrics.
- **A bank of 34 open questions** (`data/output/night2/open_bench.py`): about, CV, vLLM, XQuAD and out of domain, including the author's cases and the web examples.
  - It goes the same way as the web (`RagService.chat`, every domain, 1,024 tokens and trimming).
  - It measures cut answers, echo, loops, repeated sentences, empty answers and language.
- **Baseline `90-*`:** the `gen-bench` matrix at 1,024 tokens plus the open bank, with the previous night's code plus the 0.6B fix.

**Changes:**
1. **Loop detector, window 8 → 12** (DEC-28). A Phi loop of 4 sentences was not detected, because a window of 8 never holds 5 copies. With 12, cycles of up to 7 sentences are detected.
   - 4 of 7 reproduced loops, vs 3 of 7 with window 8.
   - 0 false positives over 14,261 answers and 299 documents.
2. **Retry when Phi copies the sources** (DEC-29, `EchoStart` in `src/rag/generator.py`). *(Removed in §7b.8, DEC-32.)*
   - **When:** the answer opens with a source header or a label (`[n] ---`, `SOURCES:`, `QUESTION:`) and goes on to copy a second one.
   - **What it does:** it stops and generates again, without letting the answer open with `[` and without letting it write headers or labels.
   - **In the web:** the opening of the answer is held back until it is clearly not an echo, so the copy never reaches the screen.
   - **Cost:** twice the time, but only in these cases.
   - **Why a second copy is required:** the version that retried at the first header (`91-*`) improved the form of ~11 answers of the 0.6B, but lost one (an XQuAD/ES question that switched to a wrong date; verbatim in `docs/es/RESPUESTAS_ARCHIVADAS.md`).
3. **Repeated blocks** (DEC-30, `repeated_block` in `src/rag/loops.py`): 6 or more sentences in a row that repeat those a little earlier, with a cycle of up to 40 sentences.
   - It detects Phi's long cycles (14 sentences on the hybrid search, up to 1,016 tokens) and the answer written twice, with the instruction repeated in between.
   - With blocks of 4 it gave false positives in 4 vLLM documents; with 5 or more, none. 6 is used for margin.
   - Over 15,793 answers and 299 documents, only the Phi answers that repeated change.

**Result (`92-*` vs `90-*`):**

| | `gen-bench` (every suite of the matrix) | Open questions (34) |
|---|---|---|
| Qwen3-0.6B | Identical (0 changes in vllm, xquad, cv and about) | Identical |
| Qwen3-1.7B | Identical | Identical |
| Qwen3-4B | Identical | Not measured in `92` (see below) |
| Phi-4-mini | 3 changes, all three for the better (below) | 5 changes: cut 2 → 0, echo 1 → 0, maximum 1,016 → 606 tokens, mean 239 → 203 |

**Phi's changes:**
- **The Triton commit (vLLM):** from copying 1,461 characters of the documentation to *"…is `e5be006` [1]"*.
- **A-04:** from 49 tokens cut mid-sentence to a complete answer.
- **A-05:** no longer writes the answer twice (773 → 375 tokens).
  - That is why two of Phi's about/ES metrics go down: "cites" 0.93 → 0.86 and "citation ok" 0.38 → 0.33.
  - The citations of that answer (`[1][2][3][4][5]`) were only at the end of the copy.
- **A-15:** 1,016 → 307 tokens, without the cycle.
- **A-09:** from a copied piece of changelog to a written answer.
- **A-01:** from copying 873 tokens of sources to "not found".

**What remains:**
- **A-01:** the 0.6B gives an answer no longer empty but poor (it repeats the instruction and cites the question itself; verbatim in `docs/es/RESPUESTAS_ARCHIVADAS.md`), and Phi says it cannot find it.
  - With that question, the sources that arrive are poor: loose sections of the ROADMAP and the changelogs.
  - Searching with the project's name instead of the way A-01 names it improves the sources for general questions, but worsens them for specific ones (reranker, agent, web). Not applied.
- **Phi in "about" is still verbose:** it summarises each source one after another.
  - It repeats false facts from `deploy/space/README.md` (the old Space card: the deployment and the default agent), still in the restored index (DEC-25).
  - Fixed by re-indexing "about" (already excluded in `rag.toml`); the author's pending decision.
- **The 4B's open bank in `92`:** the 4B does not load in the open-bank process (llm_sdk offloads part of it to the CPU with 12 GB; in `90` it did load).
  - Its answers cannot change: in `90` it has no echo and no repeated blocks, and its `gen-bench` is identical.
  - Inferred from the data, not measured.
- **Incident:** a Phi test that was meant to run on CPU used the GPU and blocked the baseline from 00:45 to 14:05. It affects no result (deterministic generation), only the timings of `90-q06-xquad`.

**Tests:** 129 tests (new: the retry and the repeated blocks); flake8 and mypy clean. 42 `make bench` (`93-session-final`) **identical**: docs 0.76 / 0.91 / 0.92 / 0.94, code 0.51 / 0.72 / 0.80 / 0.88.

## 7b.8 — Qwen only, no tricks (session of the 26th to the 27th)

**Starting point:** commit `644c455` (the §7b.7 checkpoint) and the author's decisions that afternoon:
- **Phi-4-mini out** ("Phi's problem is beyond saving"): the Qwen3 family stays.
- **A cleanup on top of the current commit**, not going back to an earlier version: what works is kept (metrics, open bank and loop detector).
- **Remove the tricks**, even if less focused questions get worse.
- **The language filter stays**, and if the LLM can be given a hint about the language, all the better.
- **All the documentation up to date**, without contradictions.

Decisions DEC-32 to DEC-38 in `decisions.md`.

### What changed

| File | Change | Why |
|---|---|---|
| `src/rag/generator.py` | Back to the `02ff464` version (without Phi's echo retry: `EchoStart`, the `ECHO_*` constants, held-back streaming) plus `strip_echo` with the 0.6B fix | DEC-32, DEC-35 |
| `src/rag/router.py`, `src/config.py`, `src/rag/retriever.py` | `route_names` removed (`DomainRouter.named`, the `SourceConfig` field and its compilation) | DEC-33 |
| `rag.toml` | The `llm-phi4-mini` profile, `route_names` and the CV hint removed; the "about" hints back to those of `8ff05d0`; `translations` and `translation_languages = ["en"]` on | DEC-32, DEC-33, DEC-34 |
| `Makefile` | `API_MODELS ?= default,llm-qwen3-1.7b` | DEC-32 |
| `web/src/App.tsx` | Phi's note in the picker removed (web rebuilt) | DEC-32 |
| `tests/test_generator.py`, `tests/test_router.py` | The tests of the retry and of `route_names` removed | — |
| `src/agent/toolcalls.py`, `src/api/app.py`, `src/rag/loops.py` | Only comments and docstrings (Phi as an option until Phase 7; section references) | So that the code does not contradict the documents |
| `bench/datasets/about/` | Ground truth rebuilt with `build_about_bench`; about-11 now answers "Oracle" (it said "Hugging Face") and about-17 points to the current signature of `stopping_criteria` | DEC-37 |
| `README.md`, `docs/es/README.md` | Four domains (with "about"), Qwen models only, a "Models" section with Phi's withdrawal, deployment on Oracle (no longer Hugging Face), agent off in the web, the "about" chip always on | Contradictions found in the diagnosis (below) |
| `deploy/README.md`, `deploy/space/README.md` | Domains and models up to date; the Space card warns that the real deployment is on Oracle | Same |
| `docs/es/DETECTOR_BUCLES.md` | Window 12, repeated blocks and a §8 with the update | It still described window 8 |
| `docs/es/ROADMAP.md`, `docs/ROADMAP.md`, `BENCHMARK_REPORT.md`, `decisions.md`, this changelog (ES and EN) | The state of the session; the English version synced with everything missing since `8ff05d0` (§7a.6–7b.8, DEC-19 to DEC-38) | The author's brief |

### Prior diagnosis: do vague questions or duplicated data break "about"?

The author asked both things before deciding. Measured with retrieval only (API, the restored index of DEC-25):
- **Specific questions fail on their own**, not because of the vague ones: with the web's filter, 6 of 36 go to vLLM or XQuAD; with "about" only, its threshold (−1.0) rejects 7 of 36 (for example, about-02 in English, −2.07).
- **The EN/ES copies do take up room:** in 5 of 18 English questions, the Spanish copy of a document takes slots in the top 5 (1 of 18 in Spanish). That is what the language filter fixes (DEC-34).
- **There were real contradictions in the index:**
  - The README said "Hugging Face Space" and "agent by default" (true in the CLI, not in the web).
  - "Oracle" only appeared in `docs/es`.
  - A ghost file, `docs/nextstep.md` (19 chunks), was in the index although it no longer exists on disk and was never in git.
  - The old Space card (`deploy/space/README.md`) was still inside the restored index.
- **The history weighs a lot:** the README is 44 of the 1,613 Markdown points of the index (counting parents and children; 2,726 points in total). In the new index, the history (changelogs, `decisions.md`, `DETECTOR_BUCLES.md`) is 1,121 of the 1,623 documentation chunks.

### Measurements

Same matrix as §7b.7 (`gen-bench` at 1,024 tokens; open bank of 34 questions; `route-bench`), one change at a time. Up to `96`, with the same index:

| Run | Change | `gen-bench` vs the previous one | Open bank | Route-bench |
|---|---|---|---|---|
| `94` | Cleanup (no Phi, no retry, no `route_names` or CV hint), filter off | **Identical to `92`** in the 10 runs of the Qwen models | 9 answers change per model (0.6B and 1.7B), all questions that named the project (DEC-33) | **Identical** to `76` and `85` |
| `95` | + language filter | Only about/EN changes (DEC-34) | 2 changes per model, for the better or equal | about/EN R@5 0.39 → 0.44, R@10 0.61 → 0.56 |
| `96` | + language hint (option A of DEC-36) | 22 metrics drop; 158 answers change in the 0.6B's XQuAD/ES; the 0.6B's about/ES language 1.00 → 0.86 | — | — |
| `97` | `95` (without the hint) + "about" re-indexed | vLLM, XQuAD and CV identical to `95`; "about" changes (see `98`) | 12 of 34 change per model (DEC-37) | Same except CV and "about" (see `98`) |
| `98` | `97` with the "about" ground truth regenerated | about/ES improves (contains 0.61–0.78), about/EN drops one question per model | — | about R@5 EN 0.33, ES 0.67; CV routed 0.933 / 0.900 |
| `99` | Experiment: "about" without the history (reverted) | Contains EN rises with all three models (0.44–0.67 → 0.61–0.72); ES drops (0.61–0.78 → 0.50–0.67) | 0.6B: about 7 of 12 for the better, no echo or wrong language; 1.7B: answers 3 Spanish questions in English | about R@5 EN 0.50, ES 0.78; 42's es/docs routed 0.9 → 1.0; XQuAD/ES −2 questions |
| `100` | Final state, after writing the documentation | Contains EN / ES: 0.6B 0.44 / 0.50, 1.7B 0.56 / 0.72, 4B 0.72 / 0.83; false "not found" on ES at 0 | 12 of 34 change vs `97` per model; **7 of the 12 questions about the project are answered by quoting notes from the changelogs and `decisions.md`**, including this session's | about routed EN 0.889 · ES 0.944, R@5 EN 0.33 · ES 0.61; XQuAD/EN, one more question to "about"; the rest as in `98` |

**`96`, the language hint:** not adopted (DEC-36). It worsens exactly what it meant to improve: the 0.6B's language on about/ES (to about-01 it answers with a single citation and no text) and, as a side effect, XQuAD/ES and the CV message on private questions (no leaks). Another way of giving the hint remains open (option C).

**`97`–`98`, the re-index:** details in DEC-37. Three things to know:
- **The "about" ground truth stores character offsets.** Editing the README moved 16 of the 18 passages; `97` gave a false recall (EN R@5 0.28). Regenerated with `python -m src build_about_bench` (`98`). It must be repeated every time the documentation is edited.
- **Spanish improves and English drops a little.** But the answers that switch language halfway double (10 → 20 in the whole matrix, all the new ones on about/ES and in the open bank), and the CV loses 1–2 routing questions to "about".
- **The documentation quotes itself:** the changelogs copied the test questions, and the search returned the quote instead of the answer (verbatim examples in `docs/es/RESPUESTAS_ARCHIVADAS.md`). Measured without the history in `99`; fixed in §7b.9.

**`99`, "about" without the history:** the changelogs, `decisions.md` and `DETECTOR_BUCLES.md` are 1,121 of the 1,623 documentation chunks. Without them, the "about" recall rises a lot and self-quoting almost disappears, but Spanish loses material in its language ("contains" and the language drop). No clear winner: it is reverted and left as the author's call (full table and options in DEC-37).

**`100`, the final state:** "about" re-indexed with all this documentation (2,616 chunks, 892 parents). The Spanish `gen-bench` rises with the 1.7B and the 4B (0.72 and 0.83), but the open bank gets worse: documenting the self-quoting makes it worse, because §7b.8 and DEC-37 quote the questions again. Both models answer A-09 with the text of DEC-37. It is the strongest argument for option B (DEC-37). *(In the end another route was chosen: §7b.9.)*

**The 4B in the open bank:** as in `92`, it does not load in that process (llm_sdk sends part of the model to the CPU). Its `gen-bench` is measured.

**Tests:** 123 tests (the 6 of the retry and of `route_names` removed), flake8 and mypy clean. 42 (`97-final`) identical: docs 0.76 / 0.91 / 0.92 / 0.94, code 0.51 / 0.72 / 0.80 / 0.88.

**Pending the author's call:** ~~the history inside "about" (DEC-37)~~ → resolved in §7b.9 without taking it out of the index; another model from a different family (DEC-32), option C of the language hint (DEC-36) and rebuilding the bundle before deploying (DEC-38).

## 7b.9 — Quotes of test questions and wrong answers removed (2026-10-27, the author's decision)

**What the author saw in the web with the §7b.8 state:** to A-04 the 1.7B answered by explaining `clean_output` and `strip_echo` with the text of `decisions.md`, and to A-13 the 0.6B said "not found". It is the self-quoting of DEC-37, the same I had measured in the open bank of `100` and did not translate into "this shows in the web".

**The author's decision:** remove every quote of a wrong answer and keep them, if worth keeping, in a file outside the index. Details and options in DEC-39.

### What changed

| File | Change |
|---|---|
| `docs/es/RESPUESTAS_ARCHIVADAS.md` | **New, outside the index.** The test questions and the wrong answers verbatim, with the section each comes from, and the id lists: `A-01`…`A-16` (open bank), `about-01`…`about-18` ("about" benchmark) and `L-1`…`L-3` (Phi's loops). In Spanish only, like `DETECTOR_BUCLES.md` |
| `rag.toml` | `docs/es/RESPUESTAS_ARCHIVADAS.md` in `exclude_paths` of `[sources.about]` |
| `changelog/FASE_7.md`, `decisions.md` (both languages) | Questions about the project are named by their id, and the bad answers are described without copying them (about 35 replacements per file) |
| `docs/es/DETECTOR_BUCLES.md` | The example loops are described; the verbatim output moves to the archive |
| `ROADMAP.md`, `FASE_6.md` (both languages) | The loose mentions (the pending open question, the `route_names` phrases, the loop from the web review) |
| `bench/datasets/about/` | Ground truth regenerated (`build_about_bench`), since the ROADMAP offsets change |

**What was removed and what was not:** every copied wrong answer, and the text of every test question about the project (also the well-answered ones), because the question is what attracts the search. Kept: vLLM, XQuAD and CV questions quoted without a bad answer, correct answers, interface and prompt texts, and "capital of France" → "Paris", which is not wrong (B15). The CV transcripts were already out with `about:skip`. The code is untouched. Full list in §8 of the archive.

**Checked:** a script goes through everything "about" indexes and finds none of the 36 benchmark questions, the 16 open-bank ones or their short forms. "About" re-indexed: 894 parents and 2,630 children (1,846 of documentation and 784 of code).

### Measurements (`101` vs `100`)

| | `100` | `101` |
|---|---|---|
| Open bank 0.6B: answers quoting the history | 7 of the 12 project questions | **0** |
| Open bank 0.6B: answered · echo · wrong language | 30 · 2 · 1 | 29 · **0 · 0** |
| Open bank 1.7B: answered · echo · wrong language · repeated sentences | 31 · 1 · 2 · 1 | 29 · **0 · 0 · 0** |
| Language switch halfway (about + open bank) | 4 of 165 | **1 of 150** |
| `gen-bench` about, contains EN / ES: 0.6B | 0.44 / 0.50 | 0.44 / 0.50 |
| 1.7B | 0.56 / 0.72 | 0.56 / **0.61** |
| 4B | 0.72 / 0.83 | **0.67 / 0.72** |
| False "not found" EN / ES (0.6B · 1.7B · 4B) | 0.11 / 0 · 0.06 / 0 · 0.06 / 0 | 0.17 / 0.11 · 0.17 / 0.11 · 0.22 / 0.11 |
| Route-bench about/EN, routed · R@1/@3/@5/@10 | 0.889 · 0.11 / 0.28 / 0.33 / 0.67 | **0.778** · 0.17 / 0.28 / 0.28 / 0.56 |
| Route-bench about/ES | 0.944 · 0.39 / 0.50 / 0.61 / 0.67 | 0.944 · **0.44** / 0.50 / **0.67** / 0.67 |
| Route-bench CV EN / ES, routed | 0.933 / 0.900 | **0.967** / 0.900 |
| Route-bench 42, es/docs, es/code, XQuAD | — | Same (XQuAD/EN, one question fewer to "about") |

**`102`, with the final index** (re-indexed after writing this section and DEC-39, 913 parents and 2,700 children; only the 0.6B and the `route-bench`): "about" `gen-bench` EN / ES 0.50 / 0.50; open bank, 3 answers change vs `101` (the agent, the model and the recall), all on topic and none quoting the history; `route-bench` as `101` except about/ES R@5 0.67 → 0.61. After writing this line, "about" is re-indexed once more, without measuring again.

**In the open bank, the web's answers:**
- **0.6B:** A-04 and A-13 are answered well again (the project and Qwen3-0.6B). A-07, A-14 and A-15 explain the project instead of copying notes from the history or `FASE_0.md`. A-09 and A-02 become "not found", which beats answering with DEC-37.
- **1.7B:** the same: A-05, A-07, A-13 and A-15 are answered on topic, without repeating the question or copying notes; A-09 and A-02 become "not found".
- **Still wrong, without self-quoting:** A-01 talks about the RAG technique in general (vLLM sources) and A-06 answers with XQuAD's construction contract. It is the retrieval of questions that do not name the project (DEC-33).
- **The 4B** does not load in the open-bank process, as since `92`.

**Why the "about" `gen-bench` drops:** the questions that lose are about-02 (language model), about-04 (reranker) and about-11 (deployment). They now give "not found": their best source no longer passes the "about" gate (−1.0). Before, they passed it thanks to the history note that copied the question, and several "correct" answers were that same quote (for example, the Spanish answer to about-02 began by repeating the question). It is the threshold problem noted in DEC-38, hidden by the self-quoting. For the same reason, about-02 and about-04 in English go to vLLM in the `route-bench`.

**Tests:** 123 tests, flake8 clean. Only documents and `rag.toml` (one excluded path) change.

**Pending:** recalibrating the "about" threshold with `gate_scores` now that the documentation does not quote the questions (DEC-39). Not done: it changes the routing of every domain and the `route-bench` has to be passed again.

## Decisions (the author's, 2026-10-24)

- **README in English.**
- **P11, the CV judge: Groq**, until the free tokens run out. It is an explicit exception to the Phase 4b rule ("the external judge is not used with personal data unless the author decides so"): the CV sources and answers are sent to Groq, with private contact data masked. If needed, it is repeated with Qwen3-4B as a local judge.
