# CHANGELOG — Phase 4: Adding modes

> English translation of [`../es/changelog/FASE_4.md`](../es/changelog/FASE_4.md), the working version.

**Start date:** 2026-10-23
**Status:** ✅ completed (2026-10-23) with 4a and 4b. **4c (multimedia, Gulliver) is postponed** as a possible final phase, by the author's decision; MLQA too.

**4a (XQuAD) completed (2026-10-23):**
- Data, ingestion and retrieval benchmark.
- `make index` for every source.
- Router with a filter, and attribution in the web.
- Generation benchmark, with a fixed subset and the full option.
- Out-of-domain gate threshold per domain.

**4b (CV mode) completed (2026-10-23):** the CV, LinkedIn and the biography (ES + EN) indexed as they are, without contact data leaks, with the author's message when a piece of data is missing. It contains the right answer in 73% (EN) and 80% (ES) of the cases.

Postponed: 4c (Gulliver).

---

<!-- about:skip -->
## 4b — CV mode

### Decisions (the author's)
- **Everything is indexed as it is:** the CV (`.docx`, in English), the LinkedIn profile (`.pdf`, in Spanish) and the biography (`.md`, in Spanish). Each file stays in its language, without translating or cleaning it.
- **Private contact data** stays in the files, but **is never shown**: there are guardrails at answer time.
- **Without the data**, the CV mode answers: *"I don't have that information, but you can ask him yourself! cdonairevillen@gmail.com"* (and its Spanish version).
- **The evaluation questions go to git.**

### Changes
- **Docling** (`src/ingestion/loaders.py`): it converts the `.docx` and the `.pdf` to Markdown when indexing, and the offsets refer to that Markdown. Three fixes for Windows:
  - The `pypdfium2` PDF backend: Application Control blocks `docling-parse`'s native library.
  - `HF_HUB_DISABLE_SYMLINKS`: without developer mode, Windows does not create the Hugging Face cache symlinks.
  - `torchvision` from the cu126 index: the PyPI wheel broke `torchvision::nms` with our CUDA torch.
- **pytest without `faulthandler`** (`pyproject.toml`): with Docling's optional dependencies, importing `transformers` pulls in `sklearn → pandas → pyarrow`, and loading `pyarrow` with `faulthandler` on kills Python on Windows. Normal execution does not use `faulthandler`.
- **Per-domain rules** (`src/domain_rules.py`, new fields in `[sources.<x>]`):
  - `private_data` (`phone`, `email`), `public_emails` and `private_replacement`: they are masked in the context the LLM reads, in the final answer and in the sources shown (CLI and web). **The indexed material is not touched.**
  - `not_found_message` per language: the "not found" of the domain that answered, or of the closest one if the gate rejected the question.
- **The `cv` source** in `rag.toml`: 15 parents and 56 children (biography 8, LinkedIn 4, CV 3).
- **Benchmark** (`bench/datasets/cv/`, in git):
  - 30 hand-written questions, the same in English and in Spanish. The right source is the exact biography fragment that answers, and `make`/`build_cv_bench` checks that it is still there.
  - 10 questions about the author with no answer in the data (`ood`): private contact, reserved topics, and missing data.
- **`.gitignore`:** the `cv/` rule becomes `/cv/`, which is the root folder. Before, it ignored any folder named `cv`, including the benchmark's. `data/` stays fully ignored.

### Results (first measurement)

**Retrieval** (`50-cv-base`):

| | @1 | @3 | @5 | @10 |
|---|---|---|---|---|
| EN, evaluator (only the biography counts) | 0.20 | 0.60 | 0.73 | 1.00 |
| ES, evaluator | 0.80 | 0.90 | 0.97 | 1.00 |
| EN, the answer is in the retrieved text | 0.47 | 0.77 | 0.87 | — |
| ES, the answer is in the retrieved text | 0.87 | 0.93 | 1.00 | — |

- **The evaluator exaggerates the drop in English:** with questions in English, the first result is the **English CV** in 18 of 30 cases, and the ground truth only accepts the biography. Even so, there is a real drop, because the CV does not have the data that is only in the biography (birth, hobbies, travels…).

**Out-of-domain gate** (`gate_scores --domain cv`): with 0.0, **40%** of the valid English questions were rejected. With **−2.0**, 90% pass (EN/ES) and no *far*/*near* out-of-domain question gets in. Of the questions about the author with no data, half pass, but they end in his message anyway.

**Generation** (`30-cv-base`, Qwen3-0.6B, k = 5):

| | EN | ES |
|---|---|---|
| Contains the right answer | 0.50 | 0.57 |
| "Not found" (with the answer in the context) | 0.23 (0.13) | 0.13 (0.03) |
| Cites the right source | 0.57 | 0.88 |
| **Private data leaks** | **0** | **0** |
| Missing data → the author's message (missing data / private contact) | 1.00 / 1.00 | 0.86 / 0.50 |
| Reserved topic → the author's message | **0 / 1** | **0 / 1** |

**Problems observed** (reviewed by hand in `data/output/gen_bench/30-cv-base/answers.json`):
1. **Mixing facts:** "he did his Erasmus at De La Luna Luna Studio", "he works at Lion's Roar Games at De La Luna Luna", "props for Secret 6 (a German company)". The chunks put several consecutive jobs together and the 0.6B model crosses the data.
2. **It makes up details of a reserved topic** and attributes other people's works to the author (*Dune*, *The Lord of the Rings*…).
3. **English questions with no answer:** skiing, Star Wars, Linkin Park, Europe… The retrieved context is the English CV, which does not have that data, and the model says "not found", which is correct with that context.
4. **It repeats the context** ("[1] --- file: … ---") in some answers, instead of answering.
5. **It copies the private data marker:** one answer contains "(private; contact: …)" because it was in the LinkedIn chunk. It is not a leak, but it adds noise.

### Iteration (approved by the author): CV mode prompt, k, chunk size and threshold

Each change is measured separately with the CV `gen-bench` (60 questions plus 20 with no data, ~4 min):

| Run | Change | Contains EN / ES | Cites the right one EN / ES | "Not found" EN / ES | Reserved topic EN / ES | Leaks |
|---|---|---|---|---|---|---|
| `30-cv-base` | — | 0.50 / 0.57 | 0.57 / 0.88 | 0.23 / 0.13 | ✗ / ✗ | 0 |
| `31-cv-prompt` | CV prompt + `[dato privado]` marker | 0.40 / 0.67 | 0.30 / 0.77 | 0.33 / 0.10 | ✓ / ✓ | 0 |
| `31b-cv-prompt-patterns` | + "not found" patterns | 0.40 / 0.67 | 0.30 / 0.77 | 0.33 / 0.13 | ✓ / ✓ | 0 |
| `32-cv-k8` | + 8 sources to answer | 0.53 / 0.57 | 0.38 / 0.77 | 0.17 / 0.13 | ✓ / ✓ | 0 |
| `33-cv-chunks800` | + chunks of 800 / 400 | 0.50 / 0.67 | 0.64 / 0.96 | 0.43 / 0.20 | ✓ / ✓ | 0 |
| **`34-cv-chunks800-gate3`** | **+ threshold −3.0** | **0.57 / 0.70** | **0.62 / 0.92** | 0.37 / 0.13 | **✓ / ✓** | **0** |

**What each change brings:**
- **CV prompt** (`prompt_rules`): answers in the third person, each fact with its company, his tastes are not his works, and reserved topics are not developed. **It fixes the reserved topics** in both languages: now it answers that the topic is reserved or gives the author's message, and it no longer makes things up.
- **"Not found" patterns** (`src/generator.py`): the model also refuses with sentences like "No se proporciona…", "no se menciona…" or "No se encuentra en los proporcionados", which the detector did not recognise. Now they end in the author's message.
  - **On vLLM** it changes two answers, and both were real negatives: a rejection on Spanish *code* and one on Spanish *near* (which goes from 0.70 to 0.80 of right rejections). The rest, the same (`22-fase4b-vllm-check`).
- **`answer_k = 8`:** more sources so that the biography gets in when the question is in English. With 2,000-character chunks they did not fit in the token budget and added noise (in Spanish it dropped from 0.67 to 0.57).
- **Chunks of 800 / 400** (`chunk_size`/`child_size` per source): one job or section per chunk. **Right citations go up** from 0.30–0.38 to 0.64 (EN) and from 0.77 to 0.96 (ES), which means it mixes jobs much less. The trade-off:
  - Retrieval in English gets worse (`51-cv-chunks800`: R@10 from 1.00 to 0.70, with more pieces of the English CV ahead).
  - The gate's scores go down, so with −2.0 more valid questions were rejected.
- **Threshold −3.0** (recalibrated with `gate_scores --label chunks800`): no *far*/*near* out-of-domain question passes with −3.0, and the valid ones go up to 0.83 (EN) / 0.90 (ES). Only in "CV only" mode would 13% of the vLLM docs questions pass, but without a filter those go to vLLM (router: 100%).

**Configuration after this round** (`34`): the CV prompt, `answer_k = 8`, chunks of 800 / 400, threshold −3.0 and the `[dato privado]` marker.

### English biography and contact rule (approved by the author)

- **`data/raw/cv/autobiography_en.md`:** a faithful translation of the biography, with the same sections. It is indexed together with the original (62 parents, 162 children).
- **Benchmark:** the English questions point to their evidence in the English version (`evidence_en` in `questions.json`), and the Spanish ones to the original. That way the ground truth is in the question's language.
- **Prompt rule 11:** the only public contact is cdonairevillen@gmail.com. If another contact detail is asked for, the answer says it is private and gives that email.
- **Threshold recalibrated** (`gate_scores --label bio-en`): −3.0 is still valid. 93% of the valid questions pass in both languages, and no *far*/*near* out-of-domain question.

| Run | EN retrieval @1/@3/@5/@10 | Contains EN / ES | Cites the right one EN / ES | "Not found" EN / ES | Missing data → message or "it is reserved" | Leaks |
|---|---|---|---|---|---|---|
| `34` (before) | 0.13 / 0.43 / 0.57 / 0.70 | 0.57 / 0.70 | 0.62 / 0.92 | 0.37 / 0.13 | EN 9/10 · ES 9/10 | 0 |
| **`35-cv-bio-en`** | **0.47 / 0.80 / 0.93 / 0.97** | **0.73 / 0.80** | 0.73 / 0.89 | **0.10 / 0.07** | **EN 10/10 · ES 9/10** | **0** |
| `36-cv-rule12` (discarded) | the same | 0.60 / 0.73 | 0.74 / 0.89 | 0.17 / 0.07 | EN 10/10 · ES 9/10 | 0 |

- **The English version closes the gap for English questions:** "not found" goes down from 37% to 10% and "contains the answer" goes up from 0.57 to 0.73. Spanish also improves (from 0.70 to 0.80).
- **Private contact data ends in the author's message** in both languages: it no longer gives the Gmail as if it were another contact.
- **What fails:** "Is he married?" → "He is not married". It makes it up, because the data is not there.
- **`36`, discarded:** a rule 12 was tried ("do not answer yes or no about personal data that is not there"). It fixes that question, but correct answers drop 13 points in English and 7 in Spanish, and one contact question stops giving the author's message. Reverted.

**Final CV mode configuration** (`35`): the biography in Spanish and English, the CV and LinkedIn, chunks of 800 / 400, `answer_k = 8`, threshold −3.0, a prompt with rules 7–11, the `[dato privado]` marker and the author's "not found" message.

**What was still open in the previous round** (before the English biography):
- **English questions about data that is only in the biography:** birth, neighbourhood, secondary school, Eastbourne, Istanbul, guitar, skiing, relocating in Europe, LanguageCert… (11 of 30 end in "not found"). The context that arrives is the English CV, which does not have them. It is a limit of cross-language retrieval, not of the LLM; the direct solution would be an English version of the biography.
- **Private contact data:**
  - To a question about a private contact detail it answers "it is [dato privado]". No leak, but it does not give the author's message.
  - To another, it gives the Gmail as if it were the contact asked for. No leak, but the statement is false.
  - A possible fix in the prompt: "the only public contact is cdonairevillen@gmail.com".
- **Router with the three domains** (`46-router-cv`): 100% of the 42 and CV questions reach their domain. XQuAD stays at 98%, and only 5 of 2,380 go to the CV.
<!-- /about:skip -->

## 4a — General knowledge: XQuAD

### 1. Result

The retrieval benchmark (`search_smart`, k = 10, the stable base: `bge-m3` + `mmarco` + BM25), the 1,190 questions of each language over the mixed `xquad` domain:

| Run | EN @1/@3/@5/@10 | ES @1/@3/@5/@10 | Time EN/ES (s) |
|---|---|---|---|
| **`40-xquad-base`** (base) | **0.95 / 0.99 / 0.99 / 1.00** | **0.92 / 0.99 / 0.99 / 1.00** | 42 / 49 |
| `41-xquad-bm25-only` (no embeddings) | 0.92 / 0.97 / 0.98 / 0.99 | 0.88 / 0.97 / 0.98 / 0.99 | 0 / 0 |
| `42-xquad-rerank-docs` (reranker also in the doc branch) | 0.95 / 0.99 / 1.00 / 1.00 | 0.94 / 0.99 / 1.00 / 1.00 | 189 / 194 |

**vLLM unchanged:** `43-fase4a-vllm-check` gives docs 0.76 / 0.91 / 0.92 / 0.94 and code 0.51 / 0.72 / 0.80 / 0.88, identical to the baseline.

**Reading:**
- **XQuAD is easy for this system:** 96 files (48 articles × 2 languages) and questions very close to the text. It measures multilinguality, but it hardly distinguishes between configurations. MLQA, which is bigger, will be needed for that, as the roadmap already foresaw.
- **Spanish is ~3 points behind on R@1.** In 32 of the 1,190 Spanish questions, the first result is the same article **in English**: the answer is right, but in the other language, and the evaluator counts it as a miss. In English it happens 14 times.
- **The embeddings add** +3–4 points on R@1 (above all in Spanish) and +1–2 on R@3/@5.
- **The reranker in the doc branch** only raises Spanish on R@1 (+0.02) and R@5 (+0.01), and costs 4× the time. On vLLM it made docs worse, so it **is not adopted**: it would need a per-domain option, and the gain does not justify it.

### 2. Changes

**Data (`make data-xquad`)**
- **Origin:** the questions, paragraphs and answers come from the Hugging Face parquet (`google/xquad`), a first step of P10. The article titles, which the parquet does not have, are taken from the original GitHub JSON and matched by question ID. Both sources are pinned to a revision and checked by SHA256.
- **Corpus:** one Markdown file per article in `data/raw/xquad/<lang>/<Title>.md` (48 per language), with the title as the header and the paragraphs separated by blank lines. It is ignored by git because it is regenerated.
- **Ground truth:** `bench/datasets/xquad/{Answered,Unanswered}Questions/dataset_{en,es}_xquad.json`, in `RagDataset` format. Each source is the **exact answer span**, and the script checks all 2,380.
- **CC-BY-SA attribution:** `bench/datasets/xquad/README.md`.

**Ingestion**
- `[sources.xquad]` in `rag.toml`: a mixed en+es domain, the `markdown_headers_packed` chunker, the `rag_xquad` collection. `make index SOURCE=xquad` indexes it in ~10 s on GPU.
- Result: 285 parents and 1,217 children.

**Benchmark**
- `bench --suite xquad` uses the `xquad` domain and the `en`/`es` datasets. The results format and the vLLM table do not change.

**Indexing every source**
- `make index` (or `index` without `--source`) indexes every source in `rag.toml` one after another, each in its collection (`rag_vllm`, `rag_xquad`). `make index SOURCE=xquad` indexes just one. `index-xquad` is removed.
- The embeddings model is loaded only once for all the sources. Indexing vLLM and XQuAD on the 3080 Ti takes ~6 min.
- Reindexing everything gives exactly the same 42 figures (`45-fase4a-index-all`).

**Router (`src/router.py`, `DomainRouter`)**
- **Without a filter:** it searches every indexed domain with each one's `search_smart`. It scores the 5 best sources of each domain with the cross-encoder, and the one with the highest score wins. The out-of-domain gate (B15) applies to the winner: if not even the best domain is relevant, it returns "not found".
- **With a filter:** `answer "…" --domains xquad` (or `vllm,xquad`) searches only those domains. With a single domain it behaves exactly like its `Retriever`.
- **The same interface as `Retriever`** (`search_smart`, `search_for_generation`, `get_parent_chunk_map`, `reranker`, `chunks`), so `RagPipeline` and the web use it unchanged. The embedder and the reranker are loaded only once and shared between domains.
- **Where it is used:** the CLI's `answer` and the web. The 42 commands (`search_dataset`, `answer_dataset`, `evaluate`), `bench` and `gen-bench` stay with the domain fixed (`vllm`), so the official benchmark does not depend on the router.
- **`make route-bench`** measures routing accuracy and recall with the router (see §1.1).
- **Known limitation:** the winner takes it all. A question that mixes two domains only gets sources from one.

**Web**
- It loads the router over every domain. The XQuAD source cards show the attribution "XQuAD (Google), CC-BY-SA 4.0 · Wikipedia". The domain picker is left for Phase 6.

### 1.1 Router without a filter (`44-router-base`)

| Set | To the right domain | Recall @1/@3/@5/@10 with the router |
|---|---|---|
| 42 docs / code (100 + 100) | **1.000 / 1.000** | the same as with the domain fixed |
| XQuAD EN (1,190) | **0.982** | 0.94 / 0.97 / 0.98 / 0.98 |
| XQuAD ES (1,190) | **0.978** | 0.91 / 0.97 / 0.97 / 0.98 |

The 2% of XQuAD that ends up in vLLM are questions that are ambiguous out of context (*"In the article's title, what did the machine hope to end?"*, *"What are stators attached to?"*). Details in `BENCHMARK_REPORT.md` §6.1.

### 1.2 Case: the out-of-domain gate rejected valid XQuAD questions

**The symptom.** The first XQuAD `gen-bench` (`20-xquad-base`) answered "not found" to **22%** of the English questions and **19%** of the Spanish ones, although the retriever brings the right source among the top 5 in 99% of the cases (§1).

**The diagnosis.** The benchmark separates two causes of "not found": the right source reaches the generator and it still refuses (an LLM failure), and no source reaches it at all. Result:

| | EN | ES |
|---|---|---|
| "Not found" answers | 262 | 229 |
| … with the right source in the context (LLM failure) | 55 | 4 |
| … **with no source at all** (the gate dropped them) | **207** | **225** |

Almost all of them came from the **out-of-domain gate (B15)**. That gate (`search_for_generation`) takes the retrieved sources, scores them with the cross-encoder (`mmarco-mMiniLMv2-L12`) and, if the best score does not reach `relevance_threshold`, passes nothing to the LLM and answers "not found".

**The cause.** The threshold (0.0, a 50% relevance according to the reranker) was calibrated in Phase 3 **with vLLM only**. But the cross-encoder does not score every corpus on the same scale. On vLLM, valid questions get a median of **9.1** (docs) and **5.8** (code), far above 0. On XQuAD the median is **3.9** (EN) and **3.5** (ES), and the worst 10% is below **−1.3**. *A hypothesis, not verified:* XQuAD questions are freer paraphrases of the paragraph and ask for a specific fact inside a long text, and the reranker, trained on MS MARCO, gives them less confidence even if the paragraph has the answer. With 0.0, 17% of the valid XQuAD questions were left out.

**The measurement (`gate_scores`, new).** For each domain, the gate's score is computed, exactly as `search_for_generation` computes it with k = 5, over two groups:
- **What the domain must accept:** its datasets.
- **What it must reject:** the out-of-domain set (40 questions: EN/ES, *far*/*near*) and the other domains' datasets.

It is saved in `bench/results/gate/`. For XQuAD (fraction of questions above each threshold):

| Group | Must | Median | −3.0 | **−2.0** | −1.0 | 0.0 |
|---|---|---|---|---|---|---|
| XQuAD EN | accept | 3.9 | 0.96 | **0.93** | 0.89 | 0.83 |
| XQuAD ES | accept | 3.5 | 0.96 | **0.93** | 0.87 | 0.81 |
| 42 docs / code | reject | −6.3 / −7.5 | 0.01 / 0.01 | **0.00 / 0.00** | 0.00 | 0.00 |
| Out of domain *far* EN / ES | reject | −4.6 / −4.3 | 0.10 / 0.10 | **0.00 / 0.00** | 0.00 | 0.00 |
| Out of domain *near* EN / ES | reject | −5.4 / −5.7 | 0.00 / 0.00 | **0.00 / 0.00** | 0.00 | 0.00 |

**The decision.** `relevance_threshold = -2.0` for XQuAD only, in `[sources.xquad]` of `rag.toml`. It is the lowest threshold that **does not let a single** unrelated question through in any group, and it raises the acceptance of valid questions from 83% to 93%. With −3.0, 96% would be accepted, but one in ten *far* questions would get in (for example, general knowledge that is not in the 48 articles).

**vLLM does not change.** It keeps the global 0.0 threshold, and the same measurement confirms it. Valid vLLM questions pass at 98–100%, and what it lets through matches the Phase 3 `gen-bench`: 20% of *near* EN and 30% of *near* ES, that is, right rejections of 0.80 and 0.70. That validates the tool. The 2,380 XQuAD questions, scored against vLLM, pass at 0% with the 0.0 threshold.

**The result** (the full `gen-bench`, 1,190 questions per language, Qwen3-0.6B, k = 5):

| | EN before (`20`) | **EN after (`22`)** | ES before (`20`) | **ES after (`22`)** |
|---|---|---|---|---|
| Contains the right answer | 0.59 | **0.65** | 0.51 | **0.57** |
| Answers "not found" | 0.22 | **0.13** | 0.19 | **0.08** |
| … dropped by the gate | 0.17 | **0.07** | 0.19 | **0.07** |
| … with the answer in the context (LLM failure) | 0.05 | 0.06 | 0.00 | 0.00 |
| Contains the answer, among those it answers | 0.76 | 0.74 | 0.64 | 0.62 |
| F1 | 0.152 | 0.167 | 0.149 | 0.169 |
| Cites / cites the right one / language | 1.00 / 0.99 / 0.99 | 1.00 / 0.99 / 0.99 | 0.99 / 1.00 / 0.98 | 0.99 / 0.99 / 0.98 |

- **+6 points of right answers** in both languages. The gate's drops go down from ~18% to 7%.
- **"Contains the answer, among those it answers" drops ~2 points.** That is expected: the questions that now pass the gate are the ones the reranker saw as less clear, and they are somewhat harder.
- **What remains is the LLM's, not retrieval's:**
  - In English, 6% of "not found" with the answer in the context.
  - In Spanish, the answer is picked up less well (0.62 vs 0.74). A likely explanation, not verified: the model rephrases the data (numbers, translated names) instead of copying them from the paragraph, and the metric requires the answer to appear literally.
  - These are generation topics (prompt per mode, model), not this gate's.

**How it works now.**
- Each source can have its own `relevance_threshold`. Without one, it uses `retrieval.relevance_threshold`.
- `Retriever.from_store` applies the threshold of the domain it loads.
- The router applies the threshold of the **winning domain**: routing compares the raw scores, and the gate uses the chosen domain's scale.

**What remains open.**
- **The 7% of valid questions still below −2.0.** Lowering it further would let unrelated questions through. A reranker better calibrated on Wikipedia (for example `bge-reranker-v2-m3`, the `gpu-quality` profile) could separate the two groups better. Not measured.
- **The threshold depends on k.** It is the maximum of the k sources' scores, so with more sources the score tends to go up. It was calibrated with k = 5, the web's and `gen-bench`'s. The CLI's `answer` uses k = 10 by default, so the gate is somewhat more permissive there.
- **The out-of-domain set is small** (10 questions per group). When there are more domains (CV, Gulliver), it will be worth extending it with questions unrelated to all of them.
- **Calibrating new domains:** each one must go through `gate_scores` before setting its threshold. It is one more step when adding a domain.

### 1.3 A fixed subset for the XQuAD `gen-bench`

**Why it took so long.** The full XQuAD `gen-bench` lasts ~70–90 min. ~96% of that time is **generation**: retrieval takes ~50–65 ms per question and generation 1.3–2.5 s.
- **One question at a time:** Qwen3-0.6B in fp16 with `generate()` and batch 1. With such a small model, what limits is the fixed cost of each token, not the GPU's power.
- **Long prompts:** about 2,000 context tokens with k = 5.
- **Spanish is slower:** the paragraphs are ~25% longer, and the tokenizer splits Spanish into more tokens.

**What is done.**
- `make gen-bench SUITE=xquad` asks **300 fixed questions per language** by default (`even_sample`): spread evenly over the 48 articles (about 6 per article) and with the same IDs in English and Spanish. It takes ~20 min.
- `FULL=1` (`--full`) asks all 2,380 and is kept **only for full tests**.
- Each result stores `"sample"` (300 or `null`).
- The vLLM suite does not change.

**It is representative.** Checked on the answers of the two full runs, taking the 300 questions of the subset:

| Run | Set | Contains (full / 300) | "Not found" (full / 300) |
|---|---|---|---|
| `20` (threshold 0.0) | EN | 0.593 / 0.573 | 0.22 / 0.24 |
| | ES | 0.513 / 0.520 | 0.19 / 0.21 |
| `22` (threshold −2.0) | EN | 0.646 / 0.633 | 0.13 / 0.14 |
| | ES | 0.570 / 0.590 | 0.08 / 0.10 |

The differences are ±2 points, and the threshold's improvement shows the same in both (+6 points). It works for comparing configurations. The official figures always come from a full run.

**Batching, discarded for now.** Generating several answers at once would multiply the speed without touching `llm_sdk`. But with fp16 and padding, the greedy answers may change compared with batch 1, and comparability with the earlier runs would be lost.

### 3. Files

| File | Change |
|---|---|
| `src/sources/__init__.py`, `src/sources/xquad.py` | **New.** Download, verification, corpus and datasets of XQuAD. |
| `src/router.py` | **New.** `DomainRouter`: search in every domain or in the filtered ones. |
| `src/evaluation/routing.py` | **New.** Routing benchmark (`route_bench`). |
| `src/cli.py` | `fetch_xquad`, `route_bench`; `index` without `--source` indexes every source (`index_source`); `answer --domains`; `answer_dataset` stays with a single domain. |
| `src/retriever.py` | `from_store`/`load_embedder` accept an already loaded embedder to share it. |
| `src/rag.py` | `RagPipeline` accepts a `Retriever` or a `DomainRouter`; `answer(..., domains=)`. |
| `src/web.py` | Uses the router and shows the XQuAD attribution. |
| `src/evaluation/bench.py` | `SUITE_DATASETS` and `SUITE_DOMAINS`; the table uses each suite's names. |
| `rag.toml` | The `xquad` source. |
| `Makefile` | `data-xquad`, `index` with an optional `SOURCE=`, and `route-bench`. |
| `tests/test_router.py` | **New.** Winner, filter, out-of-domain gate (with the winning domain's threshold) and merging of maps. |
| `src/evaluation/gen_bench.py` | `vllm`/`xquad` suites (`GEN_SUITES`), the `contains_answer` metric, the out-of-domain set separated into `run_ood`, a fixed subset (`even_sample`) and `--full`. |
| `src/evaluation/gate.py` | **New.** Per-domain calibration of the out-of-domain gate (`gate_scores`). |
| `src/config.py` | `SourceConfig.relevance_threshold` (a per-source threshold). |
| `src/retriever.py` | `from_store` applies the source's threshold. |
| `tests/test_config.py`, `tests/test_storage.py`, `tests/test_gen_bench.py` | Per-source threshold and `contains_answer`. |
| **4b** | |
| `src/ingestion/loaders.py` | **New.** The text of each file; `.docx`/`.pdf` with Docling. |
| `src/ingestion/pipeline.py` | Reads the files with `read_text`. |
| `src/domain_rules.py` | **New.** Private data, "not found" and prompt rules per domain. |
| `src/config.py` | `SourceConfig`: `private_data`, `public_emails`, `private_replacement`, `not_found_message`, `prompt_rules`, `answer_k`, `chunk_size`, `child_size`. |
| `src/rag.py` | Masks the context and the answer, uses the domain's "not found" and rules. |
| `src/generator.py` | `extra_rules` in the prompt; new "not found" patterns. |
| `src/retriever.py`, `src/router.py` | Per-domain `answer_k` when answering. |
| `src/cli.py` | `build_cv_bench`; per-source chunk sizes; sources and "not found" are shown with the domain's rules. |
| `src/web.py` | Shows the domain's "not found" and the masked sources. |
| `src/sources/cv.py`, `bench/datasets/cv/` | **New.** CV questions (in git) and the dataset builder. |
| `src/evaluation/{bench,routing,gate,gen_bench}.py` | The `cv` suite, the CV questions with no data, leaks and `handled`. |
| `rag.toml` | The `cv` source. |
| `pyproject.toml`, `uv.lock` | `docling`, `torchvision` (cu126) and pytest without `faulthandler`. |
| `.gitignore` | `cv/` → `/cv/`. |
| `tests/test_domain_rules.py` | **New.** Masking and messages per domain. |
| `pyproject.toml`, `uv.lock` | `pyarrow` declared (before, it only came indirectly through streamlit). |
| `bench/datasets/xquad/` | **New.** en/es datasets and the license README. |
| `tests/test_xquad.py` | **New.** File format, spans and offset correction. |

### 4. What to know

- **The Hugging Face offsets are shifted in one paragraph.** The parquet trims the spaces of each paragraph, but keeps the original `answer_start` values. The *Apollo_program* paragraph starts with a space, so its 5 answers (in each language) were shifted by one character. The script fixes it by subtracting what was trimmed, and fails if any answer does not match.
- **The ground-truth paths use `/`** on every system. An `os.path.join` on Windows put in `\` and recall came out as 0; it is fixed and covered by a test.
- **The headers of the Spanish files carry the English title:** XQuAD does not translate the titles.
- **BOM left as it is (the author's decision):** two Spanish articles bring an invisible BOM character inside the original text. It is left as it is: ingestion reproduces the source material without altering it, so that any new machine gets exactly the same. The only transformations are grouping the paragraphs by article and fixing the Hugging Face offsets, and both are checked against the text.
- **XQuAD has no code**, so all its questions go down the doc branch of `search_smart` (BM25 + dense with RRF, no reranker).
- **Lint:** Windows Application Control blocks `mypy.exe` on this machine; `python -m mypy` works and passes with no errors.
