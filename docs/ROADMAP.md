# ROADMAP — RAG Against the Machine v2.0

> English translation of [`es/ROADMAP.md`](es/ROADMAP.md), the working version. Updated at the end of each phase.

The roadmap of the project's improvement. Everything discussed and agreed from here on is updated here, where it belongs.

**Related documents** (the Spanish working versions are in `docs/es/`):
- `PLANING.md` (Spanish only): goals, proposals, constraints and rules.
- `RESPUESTA.md` (Spanish only): technical analysis, bugs found (B1–B13) and options considered. B14 and B15 are in `changelog/FASE_0.md`.
- `ROADMAP.md` (this one): **the current document**. If something contradicts `RESPUESTA.md`, this one prevails.
- `changelog/FASE_N.md`: one changelog per phase, following the rules in `PLANING.md`.
- `BENCHMARK_REPORT.md`: comparison of models and configurations (created in Phase 2).
- `decisions.md`: decisions taken out of necessity, with their options.
- `es/README.md`: Spanish translation of the project's README.
- `es/RESPUESTAS_ARCHIVADAS.md` (Spanish only): the test questions and the wrong answers verbatim, outside the "about" index (DEC-39). The other documents name them by their id (`A-NN`, `about-NN`, `L-N`).

**Languages:** the work is done in Spanish (`docs/es/`), and these English versions are updated **at the end of each phase**. `PLANING.md`, `RESPUESTA.md` and `Elements_frontend.md` are not translated (the initial plan and working notes).

---

# Answers #

The author's answers to the questions in `RESPUESTA.md` §7, and what each one means for the roadmap.

| Question | Answer | Consequence for the roadmap |
|---|---|---|
| **D1** Private datasets | They belonged to the grading. The public ones are enough to get an idea of the performance. | The Makefile's `test-*` targets are removed in Phase 0. The baseline is measured **only** with the public datasets. |
| **D2** Makefile URLs | They changed at some point. Updated here; they will be changed in the real repo later. | The Makefile change goes into the first commit of Phase 0. |
| **D3** Hardware | An NVIDIA RTX 3080 Ti locally. The idea is that it runs on the 42 machines (they have a GPU, not a powerful one, model unknown). | **Light defaults** (they must run at 42 and on a CPU). The big models are optional and tested on the 3080 Ti. The 42 GPU is still to be found out.<br>**Updated 2026-10-23:** the 42 GPUs do not accept CUDA (indexing vLLM there takes ~10 h), so **indexing at 42 is ruled out**. All ingestion is done on the 3080 Ti and the project is served **online**. In company presentations at 42, the deployed web is shown or the link is given. The defaults stay light because the free deployment runs on a CPU. |
| **D4** Evaluation | Recall is measured **only** on the 42 datasets. Any extra test is welcome. A free key can be used for answer tests. | The 42 evaluator is the reference and is not touched. Extra metrics (MRR, nDCG, a manual set, an LLM judge through a free API) are complementary. |
| **D5** Frontend | FastAPI + React, but **the look must stay the same as the current one**. | Phase 6: React reproduces the design of `src/web.py` (colours, typefaces, cards). |
| **D6** Language and domains | Multilingual. Also, more datasets, not just vLLM. This repo is mainly about having clear recall figures. | **Multilingual** embeddings and reranker from Phase 2. Multi-domain ingestion is prepared in Phase 1 and used in Phase 4. vLLM stays as the **benchmark**. |
| **D7** Agent | A dichotomy: its own agent as an intermediary, but also direct access to the RAG. **To be discussed.** | The architecture supports **both** paths by design. Which one is the default is decided before Phase 5.<br>**Decided (2026-10-23): the agent by default**, as in a real RAG, with session memory. Direct access stays available as an option.<br>**Changed in the web (2026-10-24):** direct by default, the agent marked as a work in progress (Phase 7). |
| **D8** Permission for Phase 0 | Yes, permission to fix the code. Curious to see how recall evolves. | Each fix is measured before and after, and documented in `changelog/FASE_0.md`. |
| **D9** Multimedia | It should accept as much as possible. Video and audio above all. The idea is that it works like something meant for high-end production. | Phase 4b **is no longer optional**, with priority for **video and audio**:<br>• Transcription with timestamps.<br>• Images with OCR + captions.<br>• Image search by text (CLIP/SigLIP, level B).<br>The generative VLM (level C) only locally.<br>⚠️ "High-end production" clashes with a free CPU deployment: ingestion is done offline on the 3080 Ti, and production only serves what is already indexed. |

**Note:** a comparison of how the proposed models work is needed, to see which ones suit the project best, like AgentSmith's `BENCHMARK_REPORT.md`. Only that way can we check what suits us best.

→ `docs/BENCHMARK_REPORT.md` is created in Phase 2 (embeddings and rerankers) and extended in Phase 3 (LLMs) and Phase 5 (agent vs direct access).

---

# Clarifications #

Since a real frontend is being built, the **modularisation** of the project could be considered: choosing which model to use at each moment, whether or not to use the intermediary… by changing the navigation in the website. **To be discussed.**

**How it is prepared without closing the discussion:**
- Every pipeline piece (chunker, embeddings, reranker, LLM, agent yes/no) is chosen by **configuration**, not by code. A config file plus a per-request override in the API.
- The same options are available in the CLI, the API and the web. The web only shows what the API allows.
- Which options are exposed to the web user, and how to navigate between them, is decided in Phase 6.

---

# ROADMAP #

**Rule common to all phases:**
- At the end of each phase, `make bench` is run on the public 42 datasets.
- **Recall cannot get worse** than the previous best. If it does, it is justified in the changelog or reverted.
- **Metric priority: R@5 > R@10 > R@3 > R@1.** A change that raises R@1 at the expense of the others is not adopted.
- Each phase closes with its `changelog/FASE_N.md`: what was changed, the list of files, why, what it affects, and what to know about the architecture.

```
Phase 0 ─► Phase 1 ─► Phase 2 ─► Phase 3 ─► [42 tests] ─► Phase 4 ─► Phase 5 ─► Phase 6 ─► Phase 7 ─► Phase 8
clean-up   ingestion  hybrid     generation  checkpoint    modes      agent +    web +      optional   Granite,
                                                                      MCP        deploy     & polish   deployment
```

## Phase 0 — Clean-up and professionalisation of the repository

**Goal:** leave a clean base and a **measured, reproducible baseline**.

- **Repository**
  - `.gitignore`.
  - Take `__pycache__/*.pyc` out of version control.
  - Commit the new Makefile URLs (D2).
- **Portable Makefile**
  - The cache path becomes a variable: `/goinfre` by default at 42, a local path elsewhere.
  - Remove the `test-*` targets (D1) and fix `.PHONY`.
  - Drop `index-embed` until Phase 2 (it does nothing today).
- **"Before" baseline**
  - Measure public recall with the code as it is, **before** touching anything.
  - It is measured with `search_smart` (the mode evaluated at 42), not with `answer_dataset`.
- **Bugs** (permission D8; each one measured separately):
  - **B1**: fix the classifier's CamelCase signal.
  - **B2**: remove the symbol expansion that does nothing and also walks the whole corpus on every query.
  - **B3**: a single evaluation path. `search-docs` and `search-code` now use `search_dataset`.
  - **B10**: centralise the "not found" messages.
  - **B13**: clean up unused imports and constants.
- **`make bench`**
  - Runs search and evaluation for docs and code.
  - Saves the config and the metrics in `bench/results/<date>_<label>.json`.
  - Prints a comparison table with the previous runs.
- **Minimal tests** (`pytest`): evaluator, chunk offsets and child→parent deduplication. They do not aim for full coverage, but to act as a safety net for the next phases.
- **Lint**: flake8 + mypy are kept (the 42 ones).

**Closing:** a "before / after each fix" table in `changelog/FASE_0.md`. The official v2.0 baseline is the "after".

> ✅ **Completed (2026-10-18).** Official v2.0 baseline (`search_smart`, public datasets):
> - **Docs:** 0.64 / 0.83 / 0.85 / 0.85.
> - **Code:** 0.45 / 0.62 / 0.64 / 0.72 (code R@10 up from 0.68).
>
> Details in `changelog/FASE_0.md`.

## Phase 1 — Changing the ingestion

**Goal:** move from loose JSON files to a **database** with a data model that can take everything that comes: multi-domain, multilingual, modes and multimedia.

- **`Chunker` interface**, with implementations swappable by config:
  - **Code**: the project's own AST chunker, with the offsets fixed (B7).
  - **Docs**: `langchain-text-splitters` (`MarkdownHeaderTextSplitter` + `RecursiveCharacterTextSplitter`), compared with the current chunker.
  - **PDF/DOCX**: Docling, integrated when the CV arrives (Phase 4).
- **Qdrant in local mode**:
  - Stable IDs.
  - Payload with `domain` (vllm, cv, …), `chunk_type`, `modality` (text for now), `lang`, `file_path`, ranges and `parent_id`.
- **BM25 (`bm25s`) is kept** as the sparse index, linked by the same ID.
- **Multi-domain ingestion** (D6): `index --source vllm` (and others in the future). Each source declares its chunker and its collection or domain.
- **Configuration system** (the basis of modularisation): a config file + environment variables, validated with pydantic.

**Closing:** it is a refactor, so **recall must be the same** as in Phase 0, except for the change from the offsets fix (B7), which is documented.

> ✅ **Completed (2026-10-18).** Details in `changelog/FASE_1.md`. Changes from the plan:
> - **Qdrant as a server (Docker)**, not in local mode: local mode took ~9 min to write the chunks.
> - **Docs chunker:** the author's packed version (`markdown_headers_packed`), not LangChain.
> - **`split_by_size()` fixed (B16 + B17):** no lost text, no duplicated pieces, and starting at a line break.
>
> Official baseline (`search_smart`, run `20-fix-b16-b17-v2`):
> - **Docs:** 0.67 / 0.84 / 0.87 / 0.89.
> - **Code:** 0.43 / 0.59 / 0.64 / 0.71. ⚠️ R@3 and R@10 fall below Phase 0 (0.62 / 0.72); recovered in Phase 2.

## Phase 2 — Hybrid retrieval

**Goal:** show with numbers whether hybrid search improves things, now that embeddings are implemented properly (see `RESPUESTA.md` §3).

- ✅ **Code-aware tokenizer** (B8 + B14): `code` mode (identifier parts only in code chunks and indices). Code 0.49 / 0.70 / 0.75 / 0.83; docs 0.72 / 0.91 / 0.93 / 0.94.
- **Chunk and query embeddings** with the same model and the right instruction prefix.
  - **Multilingual** candidates (D6): `multilingual-e5-small`, `bge-m3`, `Qwen3-Embedding-0.6B`.
  - Reference: `bge-small-en-v1.5`.
  - Heavy ingestion is done on the 3080 Ti. The defaults must be able to run at 42 (D3).
  - ✅ torch with CUDA 12.6 set up; `device = "auto"` falls back to CPU without a GPU (tested).
- ✅ **Unified paths**: `search_for_generation` = relevance gate + `search_smart`.
- ✅ **Code recovered** with per-list RRF fusion and the reranker always on: code 0.45 / 0.63 / 0.67 / 0.72 (beats Phase 0) and docs 0.72 / 0.90 / 0.93 / 0.95.
- **Vector search against Qdrant** (named vectors in the same points of `rag_<domain>`). Today the retriever loads every chunk into memory.
- **Measure the LangChain chunker again** after hybrid search (it is in the *Possibilities* of `PLANING.md`), in case R@1 needs raising.
- **RRF fusion**, with separate ablations on docs and code (BM25 / dense / hybrid).
- **Rerankers**:
  - `ms-marco-MiniLM` (current reference).
  - `bge-reranker-v2-m3` (multilingual).
  - `Qwen3-Reranker-0.6B`.
- **Hand-made rules**: ✅ `skip_rerank_score` (now `inf`) and ✅ the 2-doc minimum (removed when unifying). The 5.5 threshold is measured as a bad signal; it moves to Phase 3 (B15). Pending: review the doc/code classifier.
- **Complementary metrics**: MRR and nDCG@10. The 42 evaluator stays untouched.

**Deliverable:** `docs/BENCHMARK_REPORT.md`, *Retrieval* section (table of configurations × docs/code recall × latency).

> ✅ **Completed (2026-10-19).** Details in `changelog/FASE_2.md` and `BENCHMARK_REPORT.md`.
> - **Official baseline:** docs **0.76 / 0.91 / 0.92 / 0.94**, code **0.51 / 0.72 / 0.80 / 0.88**. Both paths are identical.
> - **Configuration:** code-aware BM25 + `bge-m3` embeddings (in both branches) + the `mmarco-mMiniLMv2-L12` reranker with RRF + a classifier with English and Spanish signals.
> - **Done:** CUDA with CPU fallback, unified paths, code-aware tokenizer, embeddings, rerankers and classifier.
> - **Not done, moved to pending:**
>   - MRR/nDCG metrics.
>   - Measuring LangChain again.
>   - A semantic classifier.

## Phase 3 — Improving answer generation

**Goal:** more natural answers, with structured sources and swappable models.

- **LLM backend** (`src/llm/`):
  - Qwen3-0.6B through `llm_sdk` as the **base and default**. `llm_sdk` is not touched.
  - A generic HF backend for the optional models.
- **Prompt**:
  - The official chat template with `enable_thinking=False`.
  - A context budget in tokens (B9).
  - `[n]` citations linked to the structured sources.
  - Prompts per mode.
  - **Answer in the language of the question** (today Qwen answers Spanish questions in English, although retrieval is already multilingual).
  - **B15**: out-of-domain guardrails. Today *"What is the capital of France?"* answers "Paris", although it is literally the prompt's rejection example.
- **Token streaming**, which prepares the Phase 6 API.
- **Comparison of LLMs** on the 3080 Ti: Qwen3-0.6B vs Qwen3-1.7B / Qwen3-4B, SmolLM3-3B and Phi-4-mini.
  - A manual question set + an LLM judge with a free key (D4).
  - Quality and latency are measured.

**Deliverable:** `BENCHMARK_REPORT.md`, *Generation* section.

> ✅ **Completed (2026-10-19).** Details in `changelog/FASE_3.md` and `BENCHMARK_REPORT.md` §5.
> - **Generation benchmark** (`make gen-bench`) and **judge** (`make judge`, Groq `gpt-oss-120b`, with a cache).
> - **New prompt:** official chat template, `[n]` citations, the question's language (ES: 90–100%) and a token budget (B9).
> - **B15 solved:** a gate with the reranker; it rejects 100% of what is clearly unrelated.
> - **A single pipeline** (`src/rag.py`) for the CLI, the web and the benchmark, with streaming.
> - **LLM:** Qwen3-0.6B as the base; Qwen3-1.7B, Qwen3-4B and Phi-4-mini as profiles (SmolLM3 discarded). Phi-4-mini was dropped in Phase 7 (DEC-32).
> - Evaluators grouped in `src/evaluation/`.

## 42 tests — Checkpoint

The results obtained during the evaluation must not get worse.

- A full `make bench` on the public datasets and a comparison against the Phase 0 baseline.
- Check that the output format is still compatible with the moulinette (`search_dataset`, `answer_dataset`, `evaluate`).
- Tag `v2.0-core` if it passes. From here on, features are **added**; the measured core is not touched without passing this checkpoint again.

> ✅ **Passed (2026-10-19).** Details in `changelog/CHECKPOINT_42.md`.
> - **Recall vs v1:** docs R@5 +0.07 (0.92) and code R@5 +0.17 (0.80).
> - **42 commands:** compatible.
> - **Without a GPU:** the same metrics.
> - The "where" rule is added to the prompt.

## Phase 4 — Adding modes

**Goal:** the RAG stops being "vLLM only": multilingual general knowledge, the author's CV and multimedia, each as its own domain and with its own way of being measured.

**Agreed order:** 4a general knowledge → 4b CV mode → 4c multimedia. The **router** is built in 4a, as soon as there is a second domain, and grows with each one.

### 4a — General knowledge: XQuAD (then MLQA)

- **Dataset:** XQuAD (Google, CC-BY-SA 4.0). The **same** questions, over the same Wikipedia paragraphs, professionally translated into 12 languages, **English and Spanish** among them.
  - According to its card, ~1,190 questions over ~240 paragraphs; **to be checked** when downloading it.
- **Why:** it measures multilinguality exactly: *recall in English vs Spanish with the same questions and the same sources*. It is the scaled-up version of the 20-question complementary set.
- **A benchmark like 42's:** it is converted to the `RagDataset` format (question, answer and source passage with offsets), so `make bench` and `make gen-bench` work the same way. The 42 evaluator is not touched.
- **Ingestion:** the `xquad` domain, with its own Qdrant collection (`rag_xquad`) and a chunker suited to Wikipedia paragraphs.
- **Router:** decides between `vllm` and `xquad` (and later the others) from the question or the chosen mode.
- **License:** CC-BY-SA requires **citing the source** visibly in the web and publishing derived works under the same license.
- **Later:** MLQA (Meta, CC-BY-SA 3.0, thousands of questions per language) as a bigger, harder corpus.

> ✅ **Completed (2026-10-23).** Details in `changelog/FASE_4.md` and `BENCHMARK_REPORT.md` §6.
> - **Done:** data (HF + GitHub titles, with SHA256), one file per article, ground truth with the answer span, a mixed `xquad` domain and `bench --suite xquad`.
> - **Done:** `make index` indexes every source, the router without a filter or with `--domains`, and CC-BY-SA attribution in the web.
> - **Recall:** EN 0.95 / 0.99 / 0.99 / 1.00, ES 0.92 / 0.99 / 0.99 / 1.00. vLLM unchanged.
> - **Router:** 100% of the 42 questions and ~98% of the XQuAD ones reach their domain.
> - **Generation:** contains the right answer in 65% (EN) and 57% (ES); cites the right source in 99%.
> - **Out-of-domain gate threshold per domain:** XQuAD uses −2.0, calibrated with `gate_scores`; vLLM keeps 0.0. Without it, 18% of the valid questions were dropped.
> - **XQuAD `gen-bench`:** a fixed subset of 300 questions per language; `FULL=1` for full runs.
> - **Pending for later:** MLQA.

### 4b — CV mode

> ✅ **Completed (2026-10-23).** The `cv` domain: the author presented through their own documents, with private contact data protected. Details in `changelog/FASE_4.md` (4b) and `BENCHMARK_REPORT.md` §7.

### 4c — Multimedia: *Gulliver's Travels* (1939) vs Swift's novel (1726)

> ⏸️ **Postponed (2026-10-23, the author's decision):** it remains a possible phase at the end of the project. The plan below is kept as it is. The book and the film are already downloaded in `data/raw/gulliver/`, with URL and SHA256 in the checklist. Proposal pending approval when it is resumed: a Markdown transcription with one header per time window (`## 00:12:30`) instead of the offset-to-seconds map.

- **Goal:** ingest the same story in two formats, novel and film, and compare what is retrieved from each. A recruiter must be able to see the code and every file used in the ingestion.
- **Requirements:**
  - The film must have **sound**, so that the Whisper transcription contributes real text.
  - The book and the film must be downloadable and publishable without rights issues.
  - Everything **reproducible**: whoever clones the repo gets the same data.
- **Why Gulliver:** Fleischer's film, animated, in colour, with dialogue and songs, which **only adapts the Lilliput part**. Three kinds of questions can therefore be tested:
  - **Book only:** Brobdingnag, Laputa, the Houyhnhnms. They check that the RAG does not make the answer up from the video.
  - **Film only:** what the film adds, such as Princess Glory's wedding to Prince David, or the character of Gabby.
  - **Both:** Lilliput, Blefuscu, the war.
- **Discarded:**
  - *The Lord of the Rings*: books and films under copyright.
  - *Dracula* vs *Nosferatu* (1922): both are in the public domain, but *Nosferatu* is **silent**. Whisper would get nothing, and the intertitles would need OCR.
  - Universal's *Dracula* (1931): it has sound, but it is not in the public domain.
- **Backups** (if Gulliver fails because of the copy or the audio quality):
  - *The Little Princess* (1939) + Burnett, Gutenberg #146.
  - *Scrooge* (1935) + Dickens, *A Christmas Carol*. The archive.org copy and the Gutenberg number are still to be checked.
- **Material:**
  - Novel: Gutenberg **#829**, Plain Text UTF-8, removing the license header and footer before chunking.
  - Film: Internet Archive. The lightest copy with good audio is chosen, and its URL and SHA256 are recorded.
- **Multimedia ingestion (level A of the analysis), offline on the 3080 Ti:**
  - **Whisper transcription** (`faster-whisper` with a VAD filter) with timestamps. The film has many songs, and Whisper tends to make text up during music; this is checked with a 5-minute test.
  - **Scene descriptions:** keyframes (PySceneDetect) + captions from a small vision model. The keyframe rate and the model are decided in the test.
  - Each chunk keeps its **modality** (book, transcription, caption) and its **position** (chapter or timestamp). The sources link to the exact minute of the film.
  - **Proposal to validate:** the transcription is stored as derived text plus an offsets → seconds map. That way `Chunk` and the evaluator keep working with character offsets, and the web turns the offset into the minute.
  - Image search by text with CLIP/SigLIP (level B) as an option.
- **Evaluation:** the 42 benchmark does not cover multimedia. A set of 10–15 questions is needed: book only, film only and both. Questions in Spanish about the English audio measure multilinguality.
- **Publication:**
  - **Code** on GitHub: the pipeline, `scripts/fetch_data.py` (fixed URLs + SHA256) and a GIF or keyframes of the result in the README.
  - **Data** in a **Hugging Face Dataset**: the video, the book's `.txt` and the derived artefacts (transcription, captions, chunks in JSONL). A dataset card with the source and license of every file. GitHub does not accept files over 100 MB without LFS, and the video is bigger.
  - **Demo:** the Phase 6 web (FastAPI + React), not a separate Gradio or Streamlit app.
- **Legal note:** the candidate films are in the public domain in the **US**, not necessarily in Spain, where a film is protected for 70–80 years after the death of the director, the writer and the composer. Publishing them on US platforms (Hugging Face, Internet Archive) is common practice in portfolio projects, but **it is not a legal guarantee**. The three novels are in the public domain worldwide.
- **Plan B**, with no legal doubt in any country: Blender's open films with dialogue and a CC-BY license (*Sprite Fright*, *Tears of Steel*) or LibriVox audiobooks with the Gutenberg text. The book-vs-film comparison of the same story is lost in exchange.
- **Checklist:**
  - [x] Find the copy on archive.org and record its URL and SHA256 (2026-10-23, in `data/raw/gulliver/`, ignored by git):
    - **Film:** `GulliversTravels720p_652` (CC0 according to its page), `https://archive.org/download/GulliversTravels720p_652/GulliversTravels.mp4`. 720p h.264, 76:22, 475,808,316 bytes. SHA256 `a5c8ba9f5d6e57b307ea5398c5c4fefa8424da42fb6ea1d455fad0fc59dfdccd`; the SHA1 matches the one archive.org publishes. The most downloaded copy (`gullivers_travels1939`) was discarded because it lasts 72:39 and is missing ~4 min.
    - **Novel:** `https://www.gutenberg.org/ebooks/829.txt.utf-8`, 613,946 bytes. SHA256 `fca36de3de0d8b831b7588cf1df84639ccf4c503172d6444ee61d1c1b2036edd`. The `*** START/END OF THE PROJECT GUTENBERG EBOOK ***` marks are on lines 27 and 9573. **Note:** Gutenberg may revise the file and change the hash, so the fixed copy for reproducibility will be the one in the HF Dataset.
    - archive.org also has an automatic transcription (`GulliversTravels.asr.srt`) that can serve as a reference to compare with Whisper.
  - [ ] Check what has to be added to the loader for the `.txt` and the video.
  - [ ] Test Whisper on 5 minutes: transcription quality and time on the 3080 Ti.
  - [ ] Decide the keyframe rate and the captioning model.
  - [ ] Define each chunk's metadata: source, chapter or timestamp, modality.
  - [ ] Write the 10–15 evaluation questions.
  - [ ] Create the dataset on Hugging Face with its dataset card.

## Phase 5 — Agents and the RAG as an MCP server

**Goal:** get closer to how companies do it, without losing direct access (D7).

- **MCP server** (FastMCP, as in AgentSmith) with the tools `search(domain, query)`, `answer(...)` and `list_domains`.
- **The project's own intermediary agent**:
  - Router, query rewriting and tool calls, with a deterministic *fallback*.
  - A multi-step loop only with the big optional models.
  - **Memory** (the author's request): conversation history plus retrievable semantic memory. It could be stored in Qdrant (a `memory_*` collection with vectors) or, if something relational were needed, justify the move to Postgres left open in Phase 1.
- **Direct access to the RAG** always available: chosen with a config or request flag.
- **Agent vs direct access benchmark** (recall, quality, latency) in `BENCHMARK_REPORT.md`.
- ✅ **D7 decided (2026-10-23):**
  - **The agent by default**, with direct access as an option.
  - **Every model can be an agent**, Qwen3-0.6B included, without restrictions. The benchmarks will say which one is deployed.
  - **Session-only memory.**
- **Design:**
  - `src/server/tools.py` (the RAG's tools).
  - An MCP server (`src/server/mcp_server.py`; FastMCP is called `MCPServer` in `mcp` 2.x) on top of those tools. ✅ Done: `make mcp`.
  - The agent in `src/agent/`: it rewrites the question with the history, decides the searches with the model's native tool-call format (at most 3 steps) and gives the final answer with the generator and the current domain rules. If it fails, it uses the direct pipeline. ✅ Done: `answer` (agent by default), `chat` (with `/agent` to toggle) and `make agent-bench`.

> ✅ **Completed (2026-10-24).** Details in `changelog/FASE_5.md` and `BENCHMARK_REPORT.md` §8.
> - **Safety nets** (DEC-03 in `decisions.md`): if the rewrite finds nothing, the original question is searched; if the domain the model chose has nothing, the search is repeated within the user's filter, **never outside it**.
> - **Agent vs direct** (Qwen3-0.6B): follow-ups **0.78 vs 0.33**; on single questions it stays within ±0.04 of direct mode with all four models. Qwen3-4B reaches 1.00 on follow-ups.
> - **42 recall:** unchanged. The 42 datasets move to `bench/datasets/public/` and recall comes out identical (`61-datasets-moved`).
> - **Pending decision:** which LLM is deployed (proposal: Qwen3-0.6B; Qwen3-1.7B if the Space's CPU can take it).
> - **Not done, on purpose:** semantic memory in Qdrant (D7: session only).

## Phase 6 — Web deploy

**Goal:** a public website for LinkedIn with the **CV** and **Demo** modes.

- **FastAPI backend**: `/chat` (SSE streaming), `/search`, `/sources/{id}`, `/metrics` and `/config` (available models and options).
- **React frontend** (Vite) with **the same look as the current web** (D5):
  - `#0a0a0a` background and `#ff3b3b` accent.
  - JetBrains Mono + Inter typefaces.
  - Source cards and recall bars.
- **Navigation and pickers** (model, agent yes/no), depending on what is decided about modularisation.
  - **"With agent / Without agent" switch** (the author's request, 2026-10-23): a switch in the chat interface that toggles between the agent (session memory, rewriting and tools) and the direct conversation with the RAG (the current pipeline, question by question). The API takes it as a request parameter (`agent: true|false`); Phase 5 leaves both paths ready behind that same parameter.
  - **Groundwork already done (Phase 2):** the `rag.toml` profiles (`available_profiles`) are the options an ingestion, reranker or embeddings picker could offer. The stable base is still the benchmark one. *To be raised in this phase.*
- **Zero-cost deployment**:
  - ~~Backend in a Hugging Face Space (Docker, free CPU).~~ → **Oracle Cloud Always Free** (DEC-19, 2026-10-24): since July 2026, Docker Spaces are paid.
  - **Updated (Phase 8, current):** for now the web is served from the author's computer (the 3080 Ti) through a Tailscale Funnel tunnel, as a stopgap. Oracle is left for later.
  - Static frontend on GitHub Pages.
  - **Google Cloud is not touched.**
  - The free deployment can probably hold only one loaded model; the rest, locally.
  - **Prebuilt index:** since indexing happens neither at 42 nor in the Space, the index (Qdrant snapshot + BM25 files) is built on the 3080 Ti and the deployment only loads it.
  - **Presentations at 42:** this deployed website is shown, or the link is given to the recruiters. Nothing is installed on the 42 machines.
  - **Data on Hugging Face (to explore, P10):** use Hugging Face datasets as an ingestion source (for example, XQuAD) and, if possible, host ours there: the 42 ones, the Gulliver derivatives and maybe the prebuilt index.
- **Final README**: rewritten when the whole improvement of the project is finished.

> 🟡 **Ready up to the point of deployment (2026-10-24).** Details in `changelog/FASE_6.md`, guide in `deploy/README.md` and decisions in `decisions.md` (DEC-04 to DEC-16).
> - **FastAPI API** (`src/api`): `/chat` (SSE, with `agent`, `domains`, `model` and `depth`), `/search`, `/sources/{id}`, `/metrics`, `/config` and `/health`. Tested with the real index: 0 leaks.
> - **React web** (`web/`), reviewed with the author over several rounds (`FASE_6.md` §6b–6g):
>   - Full-screen chat and domain filters (no Demo/CV modes).
>   - Agent switch, model and depth pickers (5 by default).
>   - Stop button and example questions.
>   - Retrievals of the answering domain in a carousel with dotted corners, and recall cards per domain.
>   - The API serves the web at `/`. Commit `3378494`.
> - **Deployment (the Phase 6 plan, no longer current):** an HF Space (Docker, CPU) with Qdrant inside; the index in a bundle (`make bundle`, SHA256) in a **private dataset**; Pages with a manual workflow. It then moved to Oracle (DEC-19) and, in Phase 8, the web is served from the author's computer through a Tailscale Funnel tunnel.
> - **Left to the author:** creating the dataset and the Space, setting the secrets, and deciding the Space's LLM, the privacy strategy (DEC-09) and whether Streamlit is deleted (DEC-13).
> - **P4 (modularisation):** the web exposes the domain filters, agent yes/no, the model (the `llm-*` profiles, one loaded at a time) and the depth.

## Phase 7 — Optional work and polish

**Goal:** polish what came up while using the web, and pick up the parked optional items. Phase opened on 2026-10-24, after commit `3378494`. Changelog in `changelog/FASE_7.md`.

> ✅ **Closed (2026-10-27, the author's decision).** Done: all of 7a and 7b up to §7b.9 (loop detector, echo cleanup, "about" language filter, Qwen only and no tricks, and documentation without test-question quotes). 42 identical (docs 0.76 / 0.91 / 0.92 / 0.94, code 0.51 / 0.72 / 0.80 / 0.88; `97-final` and `route-bench` `102`). **Moves to Phase 8:** Granite as a model from another family (DEC-32), the Oracle deployment (rebuild the bundle first, DEC-38), the "about" threshold (DEC-39), language hint option C (DEC-36) and the extra tests. Parked: 7c (visual), the agent's fallback, the formatting rule, the CV judge and 7d.

### 7a — The "about" domain: the project talks about itself (first)
1. **Rewrite `README.md`** (pending since Phase 0), aimed at GitHub and recruiters. It will be the domain's main source. Reviewed with the author before indexing it.
2. **An `about` source in `rag.toml`:**
   - **In:** the README, `ROADMAP.md`, `BENCHMARK_REPORT.md`, `decisions.md`, the changelogs and the code in `src/` (AST code chunker).
   - **Out:** `PLANING.md`, `RESPUESTA.md` (the initial plan, now superseded) and `Elements_frontend.md`.
   - **To check:** whether the current loader accepts that selection of files or needs its own one, like the CV.
3. **A set of 15–20 questions** in English and Spanish about the project, to measure recall and generation.
4. **Its own threshold**, calibrated with `gate_scores`, and **`route-bench`**: 42 → vLLM at 100%, XQuAD ~98%, CV 100%. `docs/` talks a lot about vLLM and the CV, so the risk of stealing their questions is real.
5. **API and web:** an "about" chip **always on** (it cannot be turned off), its suggested questions in the examples drop-down, and the domain inside the deployment bundle.

**Progress (2026-10-24):**
- ✅ **1.** README rewritten in English and approved, with an MIT license and a Spanish copy (`docs/es/README.md`).
- ✅ **2.** The `about` source indexed. A new field, `exclude_paths`, was needed to exclude `deploy/stage` without losing `src/deploy`.
- 🟡 **3.** 18 EN/ES questions (`bench/datasets/about/`). First measurement: EN R@5 0.78, ES 0.22. Spanish collapses because each question only accepted one source (the README's), and the Spanish questions find the same thing in the Spanish documents.
- **The author's decision:** documentation in two languages (`docs/` in English and `docs/es/` in Spanish), and several valid sources per question.
- ✅ **3 (cont.).** Ground truth in the question's language; with the "contains the answer" metric, the answer is in the top 5 sources in 89% of cases (EN and ES).
- ✅ **4.** The CV's personal content out of "about" (`about:skip` markers, the author's decision: redirect, don't repeat). Threshold −1.0 and a lexical rule for the project (`route_hints`). Route-bench `76`: CV 0.97 / 0.97, about 0.78 / 0.89, and 42 and XQuAD unchanged.
- ✅ **5.** The "about" chip pinned (`pinned`), the examples checked one by one, and the bundle with the four domains. Details in `FASE_7.md` §7a.6–7a.8.

### 7b — Answer quality
- **Markdown in the web** (lists, bold, code). No risk: no answer changes.
- **The agent's fallback:** it searches with the previous query + the new one, but it must **answer the original question**. With the 0.6B, answering the mix gives wrong answers on follow-ups (measured, `FASE_6.md`). Measured with `agent-bench` before adopting it.
- **A formatting rule** (lists and bold) only in the web, tested per model: with the 0.6B, every extra rule in the prompt can cost correct answers.
- **A judge for the answers, especially the CV ones:** to find where they fail, not to show it in the web. **Decided (P11): Groq**, until the free tokens run out; if needed, it is repeated with Qwen3-4B as a local judge.
- 🟡 **Freedom of length** (the author's request, 2026-10-24): let the LLM write what it needs without getting stuck in a loop. ✅ **Loop detector integrated** (`src/rag/loops.py`, `FASE_7.md` §7b.2): it stops generation when the model starts repeating near-identical lines or sentences. 0 false positives in 11,550 answers, and Phi's loops go from 1,500 tokens to 419–661. The web cap raised to 1,024 tokens for every model (the author's decision), now only a safety net.
- **Agent off by default in the web** (the author's decision, 2026-10-24), marked as a work in progress until the fallback is improved.
- ✅ **Answers that copy the prompt** (night of the 24th to the 25th, `FASE_7.md` §7b.3, DEC-21/22). The new prompts worsened citations and language, so the prompt does not change. The answers are cleaned instead: echo at 0 in the 4,662 measured answers, without losing any.
- ✅ **"About" sources in one language** (§7b.4, DEC-23): implemented and off on the night of the 24th to the 25th; **turned on** on 2026-10-27 (§7b.8, DEC-34, the author's decision).
- ~~**Questions that name the project**~~ (§7b.5, DEC-24): fixed phrases that name the project went to "about" without passing its gate, and the author's name sent questions to the CV. **Removed** on 2026-10-27 (§7b.8, DEC-33, the author's decision: they were tricks), even though less focused questions get worse.
- ✅ **Which documentation "about" sees** (§7b.6, DEC-25): as the documentation grew, "about" generation dropped, and the previous index was restored. On 2026-10-27 it is **re-indexed** with the synced documentation and without the old Space card (§7b.8, DEC-37). Marking the history with `about:skip` remains the author's option.
- ✅ **Answer form** (§7b.7, DEC-27 to DEC-31, session of the 25th to the 26th): a bank of open questions as in the web, the loop detector with a window of 12 and repeated blocks, and a retry when Phi copies the sources. The 0.6B, 1.7B and 4B stay identical; Phi goes from 2 cut answers and 1 with echo to none. Open question A-01, which asks about the RAG without naming it, remains (the sources that arrive are poor), and so does the "about" index (DEC-25). Pros and cons of going back to an earlier version, at the end of `decisions.md`. The retry was removed along with Phi (DEC-32).
- ✅ **Qwen only, no tricks** (§7b.8, DEC-32 to DEC-38, session of the 26th to the 27th, the author's decisions): Phi-4-mini and its retry removed, `route_names` and the author's-name hint removed, the "about" language filter on, `strip_echo` kept (it also acts with the Qwen models) and the language hint in the prompt **not** adopted (it worsened the 0.6B's language). Documentation synced in both languages and "about" re-indexed. 42 identical. The history inside "about" is resolved in §7b.9.
- ✅ **Quotes of test questions and wrong answers removed** (§7b.9, DEC-39, 2026-10-27, the author's decision): indexed documents name the questions by their id (`A-NN`, `about-NN`, `L-N`), and the verbatim text moves to `es/RESPUESTAS_ARCHIVADAS.md`, outside the index. The open bank stops quoting the history (before, 7 of 12 project questions). The "about" `gen-bench` and `route-bench` drop on three questions that only passed the gate thanks to their own quote. **Proposed for Phase 8:** recalibrating the "about" threshold.

### 7c — Visual
- Floating recall cards that flip when moving from one to the next.
- The final style of the scroll bar.

### 7d — Parked optional items
- **4c, Gulliver** (multimedia). The plan is in Phase 4.
- **MLQA.**
- **A module of the author's own texts:** the author's stories, as part of the CV mode or as a separate domain.
- ~~**`repetition_penalty`**~~ → **dropped** (2026-10-24, the author's decision): in its loops, Phi-4-mini changes words on every turn, so penalising repetition does not stop them. The official template and the stop tokens were checked and are correct (`FASE_7.md` §7b.1).

**Note on deployment:** on the server (Oracle, 2 CPUs and 12 GB), the realistic options are the 0.6B and maybe the 1.7B (P12). Phi-4-mini is no longer an option: it was dropped on 2026-10-27 (DEC-32). It did not fit on a CPU anyway (~15 GB in float32).

---

## Phase 8 — Granite, deployment and extra tests

**Goal:** an optional model from another family (Granite), the web deployed (for now from the author's computer with a tunnel; Oracle later) and the tests that were parked. Phase opened on 2026-10-27, after commit `477bff9` (the end of Phase 7). Changelog in `changelog/FASE_8.md`.

**The author's decisions (2026-10-27):**
- **The base is still Qwen3-0.6B:** benchmarks, CLI and comparisons with 42.
- **In the web, the default model becomes Qwen3-1.7B**, to show the RAG at its best.
- **Qwen3-4B came back to the web's list, only with the agent off**; later in the phase, **IBM Granite 4.0 Micro replaced it** (8a.2): today the 4B is not in the web.
- **Granite's limits are found by measuring**, without ruling it out beforehand.
- **The decisions are the author's:** the assistant proposes, measures and documents.
- **The agent's fallback is part of Phase 8** (8f).
- **The 4B's memory in the web: option A**: when the 4B is chosen, the search moves to the CPU, as outside the web; the 4B still generates on the GPU.
- **Granite: Granite 4.0 Micro** (`ibm-granite/granite-4.0-micro`, the dense 3B one; the hybrid one is `granite-4.0-h-micro`), tested with the same matrix as the Qwen models.
- **Deployment: from the author's computer, as a stopgap.** The web is served locally through a tunnel; Oracle and Hugging Face PRO stay as likely options for the future (table below).

**Solved in 8w (option A), and then the 4B left the web (8a.2):** the 4B did not load in the web's direct mode either: with the retrieval (`bge-m3` and the reranker) on the GPU it does not fit in 12 GB. With option A, choosing the 4B moves the retrieval to the CPU. Today the web offers Qwen3-1.7B (default), Qwen3-0.6B and Granite 4.0 Micro, all with and without the agent. On Oracle (CPU, 12 GB) the 4B is not measured.

| Block | What | Status |
|---|---|---|
| 8w — Web | The web's default model: the 1.7B. Qwen3-4B in the picker, disabled with the agent on. Solve the 4B's memory | ✅ Implemented (`FASE_8.md` §8w): with the 4B, first token ~3.8 s and total 4.7–8.9 s, with the search on the CPU |
| 8a — Granite | Optional `llm-granite-*` profile (Apache 2.0, Spanish among its languages). Check the template, stop tokens, default system message and tool format (`<tool_call>`); then the Qwen matrix (`gen-bench`, open bank, `agent-bench`, echo, loops, language, latency) | ✅ Granite 4.0 Micro measured (`FASE_8.md` §8a, matrix `110`): quality at the 4B's level, a good agent, and it fits on the GPU with the agent; worse with the CV's private questions (no leaks). **It replaces the 4B in the web** (the author's decision), with a rule of its own for the CV's private data (§8a.2) |
| 8b — "about" threshold | Recalibrate with `gate_scores` on the clean index, to recover about-02, 04 and 11 (DEC-39), and repeat the `route-bench` | ✅ −1.25 (`FASE_8.md` §8b): recovers two project questions; −1.5 let an out-of-domain question through. The official `route-bench` is still to run |
| 8c — Language hint | Option C of DEC-36 (the language in the system message). Only if nothing drops | Proposed, low priority |
| 8d — Deployment | From the author's computer with a tunnel (the author's decision); Oracle later: CPU latency and memory (P12), `make bundle` with the clean index (DEC-38), `deploy/stage`, machine, `scp`, `.env` and Pages | 🟡 Local ready (`FASE_8.md` §8d): `make api-public` (a queue of 4 questions, restrictable origin) and the guide in `deploy/local/README.md`. Tunnel: Tailscale Funnel; Cloudflare's quick tunnel does not support the chat's streaming, and its fixed URL needs a paid domain (§8d.2). Security measures in `make api-public` and in the guide. The Tailscale account is still to be created |
| 8g — More elaborate answers | Prompt rule 6 per model (`style_rule`) and per domain. The author's request of 2026-10-27 | ✅ Measured (`FASE_8.md` §8g): no rule is adopted (the best one, S5 on the 1.7B, makes code worse). S5 is left commented out in `rag.toml`; the CV always keeps the short rule |
| 8f — Agent fallback | When the model makes no valid call, the agent searches with the previous query plus the new one (Phase 5); today it also passes that mix to the model, and the 0.6B answers both questions together (`FASE_6.md`). Improvement: search with the mix and answer only the original question. Measured with `agent-bench` (0.6B and 1.7B) before adopting it; if it works, turning the agent back on in the web is considered | In (the author's decision) |
| 8e — Extra tests | Candidates: MRR and nDCG@10, Groq judge on the CV (P11), a server load test, measuring the LangChain chunker again | Which ones, to be decided |

**Deployment: three options** (the second one chosen as a stopgap; checked on 2026-10-27):

| Option | For | Against / to confirm |
|---|---|---|
| Oracle Cloud Always Free (DEC-19) | Free; 2 ARM CPUs and 12 GB; already prepared (`deploy/`) | CPU only (0.6B and maybe 1.7B; the 4B and Granite 3B not measured and hard in 12 GB). Creating the machine can fail for lack of capacity (`deploy/README.md`) |
| Serving from the author's computer (the 3080 Ti) with a tunnel (Tailscale Funnel or Cloudflare Tunnel, §8d) | Free; GPU, so every web model (1.7B by default, 0.6B, Granite); no router ports opened | The web only works with the computer on; the home connection limits the traffic; Cloudflare's quick tunnels change URL on every start (a fixed URL needs a paid domain) and do not support the chat's streaming; exposing the machine requires reviewing the API's security |
| Hugging Face PRO | A platform recruiters know | **Paid** (about $9/month according to several 2026 sources, not confirmed on the official page), which clashes with "I do not want to spend money" in `PLANING.md`. What PRO gives is mostly ZeroGPU quota; **still to confirm** whether ZeroGPU works for a Docker Space like ours |

The usual rule: every step is measured separately, 42 cannot get worse and test questions are cited by id (DEC-39).

---

# Pending decisions #

| # | Topic | When it must be decided |
|---|---|---|
| P1 | ~~D7: agent vs direct access~~ → resolved: agent by default, every model, session memory | Done |
| P2 | ~~Multimedia material~~ → resolved: *Gulliver's Travels* (1939) vs Swift's novel (Gutenberg #829), with *The Little Princess* and *Scrooge* as backups. It replaces *Nosferatu*/*Dracula*, which was silent. Copies downloaded on 2026-10-23 (URL and SHA256 in the 4c checklist) | Done |
| P7 | ~~`.gitattributes` to normalise line endings~~ → resolved: all LF and `llm_sdk/` untouched (commit `5a1cc4b`) | Done |
| P8 | ~~`bge-m3` by default even though indexing on a CPU takes ~2 h?~~ → resolved: `bge-m3` in the base and a `cpu-light` profile (`e5-small`) | Done |
| P9 | ~~`bge-reranker-v2-m3`~~ → resolved: the optional `gpu-quality` profile | Done |
| P3 | ~~New domains~~ → resolved: XQuAD (general knowledge, en/es) and then MLQA | Done |
| P4 | ~~Modularisation: which options the web exposes~~ → resolved in the Phase 6 review: domain filters, agent yes/no, model and depth | Done |
| P11 | ~~Judge for the CV answers (Phase 7b)~~ → resolved (2026-10-24, the author's decision): **Groq**, also with the CV questions, until the free tokens run out. If needed, it is repeated with Qwen3-4B as a local judge | Done |
| P12 | The server's LLM: the 0.6B (the base) or the 1.7B (a better agent; its CPU latency is not measured). On Oracle, the 1.7B would fit in memory (estimated ~9.5 GB of 12). **Progress (2026-10-27, the author's decisions):** in the web, the 1.7B by default; the 4B came back only without the agent and was then replaced by Granite 4.0 Micro (Phase 8). For now the web is served from the author's computer with a tunnel; the latency and memory on Oracle's CPU are still to be measured | Phase 8 (8d) |
| P5 | ~~The GPU of the 42 machines~~ → resolved: they do not accept CUDA (vLLM takes ~10 h to index). Indexing at 42 is ruled out and the project is served online | Done |
| P10 | Hugging Face Datasets: use them as an ingestion source and host ours there (the 42 ones, the multimedia derivatives and maybe the index). Whether the 42 datasets' license allows publishing them is still to be checked. **Progress (2026-10-24):** with Oracle, the prebuilt index goes to the machine by `scp` (DEC-19); the **private** HF dataset (DEC-09) stays as an alternative. Publishing the 42 datasets has not been done: the license has not been checked | To develop; before Phase 6 (deployment) or 4c if it is resumed |
| P6 | Provider of the free key for the LLM judge | Before Phase 3 |

---

# Roadmap log #

(Clarifications and decisions made during the work.)

- **2026-10-18**: the v2.0 repo is created (`RAG_Against_the-machine_42_project-v2.0`) with the whole history. The state delivered to 42 is tagged `v1.0-42`. Remotes: `origin` points to v2.0 and `v1` to the original repo, which is frozen.
- **2026-10-18**: the working documentation moves to `docs/`. `README.md` stays at the root and will be rewritten at the end of the project. A minimal `CLAUDE.md` stays at the root, importing the planning and the roadmap, so that Claude Code keeps loading the rules automatically.
- **2026-10-18**: the 42 CDN returns 403 without a session. The public datasets are versioned in `data/datasets/` (recovered from the history) and vLLM 0.10.1 is downloaded from the official GitHub tag. Checked: the 200 ground-truth sources match in path and offsets.
- **2026-10-18**: `llm_sdk` is imported the standard way (`from llm_sdk import ...`). The fix is in the mypy config (`mypy_path = "llm_sdk"`), without touching the SDK folder.
- **2026-10-18**: Phase 0 completed. See `changelog/FASE_0.md`.
- **2026-10-18**: **database: Qdrant as a server (Docker)**, decided after measuring local Qdrant, Qdrant server, Postgres + pgvector, SQLite and LanceDB (the last one blocked by Windows). Postgres remains an option if a relational database is needed later (for example, the agent's memory).
- **2026-10-18**: metric priority: R@5 > R@10 > R@3 > R@1.
- **2026-10-18**: LangChain discarded as a chunker in this version (noted in *Possibilities*); the default docs chunker is the project's own packed one.
- **2026-10-18**: the payload's `lang` field, planned in Phase 1, has not been added yet: vLLM is English only. It comes with the multilingual CV mode (Phase 4).
- **2026-10-18**: Phase 1 completed. See `changelog/FASE_1.md`.
- **2026-10-18**: Phase 2 started: CUDA 12.6 (with CPU fallback), RRF fusion for the reranker and unified paths. See `changelog/FASE_2.md`.
- **2026-10-19**: `bge-m3` embeddings by default (with `e5-small` as the no-GPU alternative); the `mmarco-mMiniLMv2-L12` reranker (multilingual); `Qwen3-Embedding` and `Qwen3-Reranker` discarded for their cost; Jina discarded for its non-commercial license. A complementary set in English and Spanish (20 questions) in `bench/datasets/`.
- **2026-10-19**: Phase 2 completed (steps 3–5 done autonomously with the author's authorisation, for review). See `changelog/FASE_2.md`.
- **2026-10-19**: profiles: a stable base (`bge-m3` + `mmarco` + Qwen3-0.6B) and extra models as explicit options (`gpu-quality`, `cpu-light`, `llm-*`). The basis for the web's pickers (Phase 6).
- **2026-10-19**: B15's star case ("capital of France") was in the vLLM documentation as an API example; it was not a hallucination.
- **2026-10-19**: Phase 3 completed. See `changelog/FASE_3.md`.
- **2026-10-19**: the "42 tests" checkpoint passed; tag `v2.0-core` (a marker, not a branch: the project stays on `main`). See `changelog/CHECKPOINT_42.md`.
- **2026-10-19**: Phase 4 planned: 4a general knowledge (XQuAD; then MLQA), 4b CV mode and 4c multimedia (*Nosferatu*/*Dracula*). *The Lord of the Rings* discarded because of copyright. Innovatiana reviewed: a catalogue aimed at training vision models, with no datasets useful to evaluate the RAG.
- **2026-10-19**: the CV folder moved from the root to `data/raw/cv/` (ignored by git), and `cv/` was added to `.gitignore`, so that personal data is never uploaded.
- **2026-10-18**: the README figures (docs 0.89 / code 0.75 on R@10) came from the **public** datasets, although they were labelled as private, and from earlier configurations that `v1.0-42` does not reproduce. `04-fase0-final / smart` is accepted as the official baseline. The README label is fixed in the final rewrite.
- **2026-10-18**: line endings normalised to LF with `.gitattributes`, with `llm_sdk/` excluded (P7).
- **2026-10-23**: **indexing on the 42 cluster is ruled out**: its GPUs do not accept CUDA and vLLM takes ~10 h. All ingestion is done on the 3080 Ti and the project is hosted online. In company presentations, the deployed web is shown or the link is given (P5).
- **2026-10-23**: 4c changes from *Nosferatu*/*Dracula* to *Gulliver's Travels* (1939) vs Swift's novel. Having sound, Whisper can be used, and since it only adapts Lilliput it allows questions only the book can answer. Content taken from the document "RAG 2 — Selección de fuentes multimedia", deleted after merging it here. The demo follows the roadmap (FastAPI + React), not Gradio or Streamlit.
- **2026-10-23**: Hugging Face Datasets exploration opened, as an ingestion source and to host ours (P10).
- **2026-10-23**: Phase 4a started. XQuAD with one file per article, a mixed en+es domain, ground truth with the exact answer span, and HF data with the GitHub titles (the author's decisions). See `changelog/FASE_4.md`.
- **2026-10-23**: router decided: without a filter it searches every domain and answers from the best one; with a filter, only in the chosen ones. `make index` now indexes every source (`SOURCE=` for one). The 42 commands and benchmark stay fixed to `vllm`.
- **2026-10-23**: out-of-domain gate threshold **per domain** (`relevance_threshold` in each source). The reranker scores each corpus on its own scale, so each new domain is calibrated with `gate_scores` before setting its threshold.
- **2026-10-23**: the XQuAD `gen-bench` uses a fixed subset of 300 questions per language; the full run (`FULL=1`) is kept for complete tests. Phase 4a completed.
- **2026-10-23**: unified download: `make data` = vLLM (from the GitHub repo) + XQuAD. `data-42` is removed as redundant (the same vLLM, datasets already versioned, 403 outside 42). See `changelog/FASE_5.md` §5.
- **2026-10-23**: `src/` reorganised into `rag/` (the RAG), `server/` (tools and MCP) and `agent/` (the agent), with no logic changes. See `changelog/FASE_5.md`.
- **2026-10-23**: **D7 decided** and Phase 5 started: the agent by default (like a real RAG), every model can be an agent, session-only memory, and direct access as an option. The `lang` field leaves the plan: answers already follow the question's language (90–100%).
- **2026-10-23**: **4c (multimedia, Gulliver) postponed** as a possible final phase. Phase 4 closes with 4a and 4b. MLQA, also optional, is left for the end.
- **2026-10-23**: the 42 datasets moved from `data/datasets/` to `bench/datasets/public/`: `bench/` is for what is versioned and `data/` for what is local (DEC-01). The 42 evaluator is kept as the reference metric.
- **2026-10-24**: the agent's safety nets (DEC-03) and the agent vs direct benchmark with four models (`BENCHMARK_REPORT.md` §8). Phase 5 completed.
- **2026-10-24**: Phase 6 prepared up to the point of deployment (API, React web, index bundle, Space image, Pages workflow), with no commits or publication. Decisions taken out of necessity in `decisions.md`.
- **2026-10-24**: review of the web with the author (`FASE_6.md` §6b–6g). Commit `3378494` ("Phase 6: Frontend and deployment"). Deployment on Hugging Face is pending the author's accounts.
- **2026-10-24**: **agent off by default in the web** (the author's decision): with small models, its memory mixes topics or gives answers that are too basic. When turned on, a "work in progress" note. The CLI keeps D7. Reviewed after the fallback improvement (7b). The "about" domain stays out of the web (`API_DOMAINS`) until it is calibrated. See `changelog/FASE_7.md`.
- **2026-10-24**: **documentation in two languages** (the author's decision). The Spanish originals move to `docs/es/` (with `git mv`; Git only records it as a rename for `PLANING.md`, `RESPUESTA.md` and `Elements_frontend.md`. For the others, the translation reuses the old path, so their Spanish history is found with `git log docs/<file>`, not with `--follow` on `docs/es/`) and remain the working version. `docs/` holds the English translation, updated at the end of each phase. The README has its Spanish copy in `docs/es/README.md`. `CLAUDE.md` loads the rules from `docs/es/`. Both languages are indexed in the "about" domain.
- **2026-10-24**: **Phase 7 (optional work and polish)** opened. It starts with the "about" domain (the project talking about itself, with the rewritten README, `docs/` and the code). The judge for the CV answers is decided: Groq (P11).
- **2026-10-24**: "about" domain finished and in the web (pinned chip). The CV's personal information is no longer repeated in the documentation: it redirects to `FASE_4.md` §4b and is left out of the "about" index.
- **2026-10-24**: **deployment on Oracle Cloud Always Free** instead of Hugging Face, which has charged for Docker Spaces since July 2026. Kept apart from Google Cloud (the author's decision). Measured: 5.0 GB peak RAM with 2 CPUs and 12 GB (DEC-19, `deploy/README.md`).
- **2026-10-25**: autonomous overnight session (decisions DEC-20 to DEC-26). Echo cleanup, questions that name the project and a language filter (off). Everything measured against a baseline of the four models; 42 identical. No commits. See `changelog/FASE_7.md` §7b.3–7b.6.
- **2026-10-26**: second autonomous session (DEC-27 to DEC-31): answer form (cut answers, Phi's echo, long loops). Measured against the `90` baseline: the Qwen models identical and Phi better in all its cases; 42 identical. Checkpoint at the author's request, with the pros and cons of going back in `decisions.md` for discussion. See `changelog/FASE_7.md` §7b.7.
- **2026-10-27**: third autonomous session (DEC-32 to DEC-38), on top of commit `644c455`: a cleanup instead of going back (the author's decision). Phi-4-mini dropped, routing tricks removed, the "about" language filter on, and all the documentation synced (including the English translation, which had stopped at `8ff05d0`). The Qwen models identical on vLLM, XQuAD and CV; 42 identical (`97-final`). No commits. See `changelog/FASE_7.md` §7b.8.
- **2026-10-27**: **Phase 7 closed** (the author's decision). What is pending moves to Phase 8: Granite, deployment and extra tests.
- **2026-10-27**: quotes of test questions and wrong answers removed from the indexed documentation (the author's decision, DEC-39): the search returned those notes instead of the answer. The verbatim text is kept in `es/RESPUESTAS_ARCHIVADAS.md`, excluded from "about". See `changelog/FASE_7.md` §7b.9.
- **2026-10-27**: **Phase 8 opened** after commit `477bff9`. The author's decisions: the base stays the 0.6B; in the web, the 1.7B by default and the 4B back, only with the agent off. Plan in Phase 8.
- **2026-10-27**: **Granite 4.0 Micro replaces the 4B in the web** (the author's decision), with and without the agent, and with a rule of its own so that it never presents the public Gmail address as another address (`changelog/FASE_8.md` §8a.2). Local deployment prepared (`make api-public`, `deploy/local/README.md`, §8d).
- **2026-10-28**: overnight session on the length of the answers (`changelog/FASE_8.md` §8g). A `style_rule` mechanism per model and per domain; 6 rules measured on the 1.7B and one on Granite and the 0.6B. None is adopted, because all of them make something worse; S5 is left ready to switch on in the 1.7B profile. No commits.
