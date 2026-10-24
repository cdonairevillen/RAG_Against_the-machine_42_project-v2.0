# CHANGELOG — Phase 7: Optional work and polish

> English translation of [`../es/changelog/FASE_7.md`](../es/changelog/FASE_7.md), the working version. Updated at the end of each phase.

Phase opened on 2026-10-24, after commit `3378494` (Phase 6). The plan is in `ROADMAP.md` (Phase 7). This file records what is changed, why and what it affects, following the rules in `PLANING.md`.

## Status

| Block | Status |
|---|---|
| 7a — The "about" domain (README, `docs/`, code) | In progress: README, source and benchmark done; multiple sources, threshold, router and web still to do |
| 7b — Answer quality (Markdown, the agent's fallback, formatting, CV judge) | Agent off by default in the web; the rest planned (P11 resolved: Groq) |
| 7c — Visual (flipping cards, scroll) | Planned |
| 7d — Optional (Gulliver, MLQA, `repetition_penalty`) | Parked |

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

With the API restarted after indexing "about", that domain entered the router **uncalibrated**. The author's example with the 1.7B: <!-- about:skip -->to "Chrystian Donaire Villén Que me estas contando" it answered with his date of birth and<!-- /about:skip --> added *"the answer is given with the agent by default (D7)"*. The changelogs contain test transcripts (for example, `FASE_6.md` §5 quotes CV answers) and internal jargon, and the router picked them.
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

## Decisions (the author's, 2026-10-24)

- **README in English.**
- **P11, the CV judge: Groq**, until the free tokens run out. It is an explicit exception to the Phase 4b rule ("the external judge is not used with personal data unless the author decides so"): the CV sources and answers are sent to Groq, with private contact data masked. If needed, it is repeated with Qwen3-4B as a local judge.
