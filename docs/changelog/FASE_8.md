# CHANGELOG — Phase 8: Granite, deployment and extra tests

> English translation of [`../es/changelog/FASE_8.md`](../es/changelog/FASE_8.md), the working version.

Phase opened on 2026-10-27, after commit `477bff9` (the end of Phase 7). The plan is in `ROADMAP.md` (Phase 8). What changes, why and what it affects is written down here, following the rules in `PLANING.md`.

**Rule added in Phase 7 (DEC-39):** this document does not copy the text of a test question about the project or a wrong answer. It uses the question's id (`A-NN`, `about-NN`, `L-N`) and a description; the verbatim text goes to `es/RESPUESTAS_ARCHIVADAS.md`, which is outside the "about" index.

## Status

| Block | Status |
|---|---|
| 8w — Web: 1.7B by default, 4B only without the agent | ✅ Implemented and checked with the real API (§8w); option A for the 4B's memory |
| 8a — Granite | ✅ Granite 4.0 Micro: matrix `110` (§8a). **It replaces the 4B in the web** (the author's decision, 2026-10-27), with a rule of its own for the CV's private data (§8a.2) |
| 8b — "about" threshold | ✅ −1.0 → **−1.25** (§8b): recovers two project questions; one Spanish XQuAD question goes from "not found" to a wrong answer. The official `route-bench` is still to run |
| 8c — Language hint (option C) | Proposed, low priority |
| 8d — Deployment | 🟡 Ready to deploy from the author's computer (§8d): `make api-public`, guide in `deploy/local/README.md` and a full rehearsal. Tunnels checked and security measures in §8d.2: Tailscale Funnel is the only free option that works (Cloudflare's quick tunnel does not support the chat's streaming). The Tailscale account is still to be created |
| 8e — Extra tests | The usual ones (the Qwen matrix), to evaluate Granite |
| 8f — Agent fallback | In (the author's decision, 2026-10-27); not started |
| 8h — Documentation for "about" | ✅ README, ROADMAP, BENCHMARK_REPORT and the Phase 8 translation up to date; "about" re-indexed (§8h). One open-bank question gets worse because of the "about" threshold (8b) |
| 8g — More elaborate answers | ✅ Measured (§8g): 6 rules on the 1.7B and S2 on Granite and the 0.6B. **None is adopted** (all of them make something worse; the best one, S5 on the 1.7B, loses on code). S5 is left commented out in `rag.toml`, ready to switch on; the CV always keeps the short rule |

## The author's decisions (2026-10-27)

- **The base is still Qwen3-0.6B** (benchmarks, CLI, comparisons with 42).
- **Web: Qwen3-1.7B by default**, to show the RAG at its best.
- **Web: Qwen3-4B is back in the list, only with the agent off.** Later, Granite replaced it (§8a.2): today the 4B is not in the web.
- **Granite:** its limits are found by testing it.
- **The decisions are the author's.**
- **The agent's fallback is part of this phase.** The 4B does not use the agent (GPU memory), so it is not affected.
- **The 4B's memory in the web: option A** (below), watching that the times do not soar.
- **Granite: Granite 4.0 Micro** (`ibm-granite/granite-4.0-micro`, the dense 3B one). If it works as it should after the author's evaluation, it stays; if not, it is dropped.
- **Tests:** the same matrix as with the Qwen models (`gen-bench`, open bank, `agent-bench`, echo, loops, language, latency).
- **Deployment: from the author's computer with a tunnel, as a stopgap.** Oracle and Hugging Face PRO stay as likely options for the future.

## What the code had (the starting point of 8w)

- **`Makefile`:** `API_MODELS ?= default,llm-qwen3-1.7b`. The 4B was out because, with the retrieval on the GPU, it does not fit in 12 GB (measured in Phase 6).
- **`src/api/app.py`, `ModelPool`:**
  - The `default` model is the base configuration's one (0.6B), loaded at start-up (`RagService.load`).
  - A single model is kept loaded (`RAG_API_MAX_LOADED=1`). Changing model unloads the previous one and, if the new one fails to load, goes back to the previous one with a clear error.
  - The API only takes the **generation** part of each `llm-*` profile. That is why the 4B's `[profiles.llm-qwen3-4b.models] device = "cpu"` (retrieval on the CPU) did not apply in the web.
- **Measured:** the 4B did not load in the web process, not even without the agent (open bank of `92`, `100` and `101`, direct mode). `llm_sdk` refused to move a model with modules offloaded to the CPU or disk. In `gen-bench` it loads, because there its full profile puts the retrieval on the CPU.

**Consequence:** turning the agent off is not enough for the 4B to work in the web. It needs room in memory. Options, none measured:

| Option | Idea | To check |
|---|---|---|
| **A** ✅ (the author's decision) | When the 4B is chosen, the retrieval (bge-m3 and the reranker) moves to the CPU, as in its profile. **This is what already happens outside the web:** there the 4B generates on the GPU (`llm_sdk` picks the device) and only the search goes to the CPU | Search latency on the CPU; moving back to the GPU when the model changes. The author's preference, if the times do not soar |
| B | The 4B on the CPU and the retrieval on the GPU | Very slow generation (minutes per answer) |
| C | The retrieval always on the CPU in the web | Affects every model |

On Oracle (CPU, 12 GB) the 4B is not measured. In float32 it would take about 16 GB; it could only fit in bf16, which is not checked.

**A first figure for option A** (from the `gen-bench` runs of `101`, nothing new measured; one domain, "about"):

| | Search (median · max) | Generation (median · max) |
|---|---|---|
| 4B, search on the CPU | 0.47 s · 1.83 s | 4.3 s · 9.3 s |
| 1.7B, search on the GPU | 0.07 s · 0.32 s | 2.8 s · 14.7 s |

The web searches the four domains, so the CPU search will take longer. An estimate, not a measurement; measured when 8w was implemented.

## 8w — Web: 1.7B by default and the 4B only without the agent (implemented, 2026-10-27)

### What changed

| File | Change |
|---|---|
| `src/api/app.py` | `ModelPool`: `RAG_API_DEFAULT_MODEL` (the model the web starts with and loads at start-up; without it, the usual `default`), `RAG_API_DIRECT_ONLY` (models offered only without the agent) and, per model, the search device set by its `rag.toml` profile. `/config` adds `model_default` and `agent` on each model. `RagService.generator_for`: if the chosen model searches on another device, it unloads the loaded LLMs, moves the embedder and the reranker (shared by every domain) and then loads the model. `chat` refuses the agent with a direct-only model, with a clear message |
| `Makefile` | `API_MODELS ?= default,llm-qwen3-1.7b,llm-qwen3-4b`, `API_DEFAULT_MODEL ?= llm-qwen3-1.7b` and `API_DIRECT_ONLY ?= llm-qwen3-4b` |
| `web/src/App.tsx`, `web/src/api.ts`, `web/src/index.css` | The web starts with `model_default`. With the agent on, the 4B shows in the picker but disabled ("Turn the agent off to use it"); turning the agent on with the 4B chosen switches to the default model. The 4B's note: "Best answers · slowest · direct RAG only". Web rebuilt |
| `tests/test_api.py` | 3 new tests: default and direct-only models, the 4B refuses the agent, and the search moves before the model loads (and back when it changes) |

**Unchanged:** the base (0.6B) in benchmarks, CLI and `rag.toml`; the deployment (`deploy/`), which does not set the new variables and stays as it was; `llm_sdk`.

**No special code for the 4B:** the search on the CPU comes from its profile (`[profiles.llm-qwen3-4b.models] device = "cpu"`), as outside the web.

### Checked with the real API (`make api`, 3080 Ti, every domain, direct mode; `data/output/night2/web8w.py`)

| Step | First token | Total | GPU used |
|---|---|---|---|
| Start-up | — | — | 1.7B loaded by default |
| 1.7B, 3 questions (vLLM, XQuAD/ES, vLLM) | 0.7–1.2 s | 1.7–9.7 s | 9.0 GB |
| 4B with the agent | Refused with the message | — | — |
| 4B without the agent, 1st question (includes loading and moving the search) | 9.7 s | 15.7 s | — |
| 4B without the agent, next ones | 3.8 s | 4.7–8.9 s | 10.5 GB |
| Back to the 1.7B, 1st (includes loading and moving the search back to the GPU) | 4.6 s | 13.1 s | — |
| 1.7B, next ones | 0.8 s | 1.7–5.5 s | 9.0 GB |
| 0.6B with the agent | 4.8 s (with loading) | 7.9 s | 6.5 GB |

The GPU figure is the whole machine's, not only the API's.

**Reading:** with the 4B, the first token takes about 3 s longer (the CPU search over four domains, plus the larger model's prompt), but the total stays under 10 s for these questions. Model changes cost about 4–10 s the first time. The 1.7B's answers start the same before and after going through the 4B (first 70 characters of each compared).

**Tests:** 126 tests; flake8 and mypy clean.

## 8a — Granite 4.0 Micro

**Profile:** `llm-granite-micro` in `rag.toml` (`ibm-granite/granite-4.0-micro`). Only the generation model changes, as with the Qwen profiles. `llm_sdk` is not touched.

### Checks before measuring (the same as with Phi, `FASE_7.md` §7b.1)

| Check | Result |
|---|---|
| Architecture | `GraniteMoeHybridForCausalLM` with **attention layers only** (the dense variant; the hybrid one with Mamba2 is `granite-4.0-h-micro`). Supported by the project's transformers version (5.12.1) |
| Chat template | Its own (`<\|start_of_role\|>…<\|end_of_role\|>…<\|end_of_text\|>`). Our system message **replaces** its default one: it does not appear in the prompt |
| End of generation | `<\|end_of_text\|>` (100257), declared in its `generation_config`; our `stop_token_ids` picks it up. `<\|im_end\|>` (Qwen's) is not in its vocabulary and is ignored |
| Precision | `llm_sdk` loads it in float16 on the GPU (Granite is published in bf16). No overflow in the first test: normal answers |
| Memory (3080 Ti) | 9.55 GB with the search on the GPU: **it fits without moving the search to the CPU**, unlike the 4B |
| Tool format | `<tool_call>{json}</tool_call>`, the one the agent already reads (`src/agent/toolcalls.py`) |
| First test (every domain, direct mode) | Answers well and cites on a vLLM question (3.4 s), a Spanish XQuAD one (1.4 s, in Spanish) and B15's known out-of-domain one (1.0 s, the vLLM documentation case) |

### Matrix (`110`, finished on 2026-10-27)

Open bank, `gen-bench` at 1,024 tokens (vllm 25 per set, cv, about, xquad) and `agent-bench`. With the 1.7B, about, xquad and `agent-bench` are repeated on the current index, to compare with the web's default model. The Qwen vllm and cv figures come from `97` (same index for those domains); the 0.6B "about" from `102` and the 4B "about" from `101`. Script: `data/output/night2/run8.sh 110` (ignored by git).

**`gen-bench`, contains the answer (EN / ES)** and, in brackets, the correct citation:

| Suite | 0.6B | 1.7B | 4B | **Granite Micro** |
|---|---|---|---|---|
| CV | 0.73 / 0.80 (0.73 / 0.89) | 0.90 / 0.90 (0.79 / 0.78) | 0.90 / 0.93 (0.82 / 0.82) | **0.87 / 0.93 (0.86 / 0.93)** |
| about | 0.50 / 0.50 | 0.56 / 0.61 | 0.67 / 0.72 | **0.67 / 0.83** |
| XQuAD (300 per language) | 0.64 / 0.59 | 0.79 / 0.68 | — | **0.81 / 0.74** (citation 0.96 / 0.97) |

**vLLM `gen-bench`, F1** ("contains" does not work on vLLM: the reference answers are long) and the correct citation:

| Set | 0.6B | 1.7B | 4B | **Granite Micro** |
|---|---|---|---|---|
| public/docs | 0.51 (0.87) | 0.50 (0.73) | 0.59 (0.80) | **0.55 (0.83)** |
| public/code | 0.43 (0.86) | 0.46 (0.86) | 0.47 (0.91) | **0.54 (0.92)** |
| es/docs | 0.19 (0.90) | 0.25 (0.80) | 0.20 (1.00) | **0.28 (1.00)** |
| es/code | 0.27 (1.00) | 0.22 (0.89) | 0.27 (0.90) | **0.29 (0.90)** |
| Out of domain, near EN / ES | 0.8 / 0.8 | 0.8 / 0.7 | 0.9 / 0.9 | 0.8 / 0.7 |

**CV questions it must not answer** (private contact data and what is not in the CV; leaks are measured separately):

| | 0.6B | 1.7B | 4B | Granite Micro |
|---|---|---|---|---|
| Leaks | 0 | 0 | 0 | 0 |
| Private ones correctly redirected (EN / ES, 2 per language) | 2 / 2 | 2 / 2 | 1 / 2 | **1 / 0** |
| Not in the CV (EN / ES, 7 per language) | 7 / 6 | 7 / 7 | 7 / 7 | 7 / 7 |

On the private ones, Granite fails in two ways. Twice it answers with the public e-mail instead of the CV message, and once it presents it as if it were the private address asked for (which is false). Once it says in Spanish that the data is private, but without the fixed message the benchmark expects. No private data comes out.

**`agent-bench`** (contains the answer, agent / direct; last column, the agent makes a valid tool call):

| Set | 1.7B (`110`) | Granite Micro (`110`) |
|---|---|---|
| Conversations, first question | 0.92 / 0.83 · 1.00 | 0.92 / 0.83 · 1.00 |
| Conversations, follow-up | 0.78 / 0.33 · 0.61 | **0.89** / 0.33 · **0.94** |
| CV EN | 0.90 / 0.90 · 0.83 | 0.87 / 0.87 · 0.93 |
| CV ES | 0.80 / 0.83 · 0.87 | **0.90** / 0.87 · 0.97 |
| XQuAD EN | 0.78 / 0.78 · 0.74 | 0.76 / 0.76 · 0.94 |
| XQuAD ES | 0.66 / 0.70 · 0.90 | **0.78** / 0.76 · 0.94 |
| Seconds per answer, agent (range per set) | 3.5–6.4 | 4.8–11.5 |

Phase 5 reference on follow-ups: 0.6B 0.78 and 4B 1.00. On vLLM (public), "contains" stays at ~0 with every model and is not used.

**Open bank** (34 questions, as in the web): 29/34 answered, none cut, no loops, the right language in all of them. Mean of 179 tokens; maximum 606.
- **Echo: 1.** Granite sometimes adds a "Sources:" list at the end, and `strip_echo` leaves it as `[n] (path)`. The echo log (`110-echo.jsonl`) has 5 cleaned cases over the whole matrix.
- **Repeated: 3**, legitimate Docker or Podman commands, not loops.
- **Questions about the project (`A-01`..`A-16`):**
  - Good: A-04, A-05, A-12 and A-13.
  - Generic about RAG (~500 tokens): A-01 and A-03.
  - Off target: A-06 (talks about the building contract) and A-10 (wrong).
  - Not found: A-02, A-08, A-09 and A-11.
  - Long: A-16 (606 tokens).
  - It is similar to what happens with the Qwen models in "about" after DEC-39 (the 8b threshold), not something specific to Granite.

**Latency and memory (3080 Ti):**
- Direct: 1.3–5.4 s per answer, between the 1.7B and the 4B.
- Agent: slower than the 1.7B, 1.4 to 2 times depending on the set.
- Memory: 9.55 GB with the search on the GPU. It fits without moving it, so in the web it would not need to be "direct only" like the 4B.

### Reading (for the author's evaluation)

- **For:**
  - Its quality is at the 4B's level or above on CV, about, XQuAD and vLLM.
  - It is the best agent measured after the 4B: follow-ups 0.89 and valid tool calls above 0.93 on every set.
  - It fits on the GPU with the agent on, which is exactly what the 4B cannot do.
- **Against:**
  - It is the worst at redirecting the CV's private questions (1 of 4), and on one it says something false about the e-mail. No leaks, but in the CV domain this is the most delicate part.
  - It is slower than the 1.7B, above all with the agent.
  - A small echo of the "Sources:" list, which is cleaned.
- **Not measured:** CPU (Oracle) and the Groq judge.

### 8a.2 — Granite in the web and its private data (2026-10-27)

**The author's decision:** Granite replaces Qwen3-4B in the web, with or without the agent. It can use it: it fits on the GPU with the search and the agent (rehearsal in §8d). The author asked for the phone number and the e-mail to stay hidden as with the other models, although it is not critical.

**What was already protected:** the phone number and the old e-mail are masked in the code (`rag.toml`, `private_data`) before the model sees them, and again in the answer and in the sources. No model can show them. Measured in `112-privacy` and `111-privacy`: 0 leaks in 84 answers (0.6B, 1.7B and Granite, with and without the agent).

**Granite's real failure:** asked for the author's Hotmail address, it gave the public Gmail address as if it were the Hotmail one. False, although it reveals nothing.

**Fix, for Granite only:**

| File | Change |
|---|---|
| `src/config.py` | `SourceConfig.model_rules`: rules of a domain for one specific model (by its Hugging Face id), added after `prompt_rules` |
| `src/rag/domain_rules.py` | `prompt_rules(domain, model)` adds the model's rule when there is one |
| `src/rag/pipeline.py`, `src/agent/agent.py` | They pass the loaded model (`generator.model_name`) |
| `rag.toml` | `[sources.cv.model_rules]` with rule 12 for `ibm-granite/granite-4.0-micro`: the Gmail address is a Gmail address; if asked for a Hotmail address, the phone number, WhatsApp or the home address, say that it is private and give the Gmail address as the public contact |

**The Qwen models do not change:** their prompt is byte-for-byte identical (checked).

**Measured:**

| | Before (`110`) | With the rule (`112`) |
|---|---|---|
| Private ones handled well, `gen-bench` (EN / ES) | 1/2 · 0/2 | **2/2** · 0/2 (*) |
| Hotmail presented as Gmail (bank of 14 contact questions, direct + agent) | 2 of 2 | **0** |
| CV contains (EN / ES) | 0.87 / 0.93 | 0.87 / 0.93 |
| CV correct citation (EN / ES) | 0.86 / 0.93 | 0.86 / 0.93 |
| Leaks | 0 | 0 |

(*) Both Spanish ones are right even though the benchmark does not count them: one says the phone number is private and the other that there is no Hotmail address. The benchmark only accepts the ones that end in the CV's fixed message.

**Still open (not Granite's):**
- Some contact questions end up in "about" instead of the CV, with every model.
- Granite gave an answer with no content (citation numbers only) to one of them in "about".
- It is the "about" threshold (8b).

**Web:**
- `Makefile`: `API_MODELS ?= default,llm-qwen3-1.7b,llm-granite-micro`, with an empty `API_DIRECT_ONLY`.
- `web/src/App.tsx`: note "IBM Granite · best answers · slowest".
- The "direct only" support stays in the code in case the 4B comes back.

## 8d — Deployment from the author's computer (prepared, 2026-10-27)

Full guide (Spanish) in `deploy/local/README.md`.

**Tunnel options** compared in the guide: Tailscale Funnel (free, fixed `*.ts.net` URL), free ngrok (a warning page before the web; 1 GB/month), Cloudflare Tunnel (see §8d.2) and DuckDNS + router + Caddy (exposes the home IP; does not work behind CGNAT). Creating the account and installing the client is up to the author.

**What changed:**

| File | Change |
|---|---|
| `src/api/app.py` | `RAG_API_MAX_QUEUE`: the most questions at a time (being answered or waiting); beyond that, the error "The server is busy… try again in a minute". 0 (the default) = no limit, as before |
| `Makefile` | `make api-public` = `make api` with `API_MAX_QUEUE=4` and `RAG_ALLOWED_ORIGINS=$(PUBLIC_ORIGIN)`. `make api` now passes `RAG_ALLOWED_ORIGINS='*'`, which was already its default |
| `web/src/App.tsx` | API errors are shown once ("Error: …"), not "Error: Error: …" |
| `tests/test_api.py` | Full-queue test |
| `deploy/local/README.md` | New guide |

**Rehearsal with `make api-public`** (`data/output/night2/web8d.py`, 3080 Ti, every domain):

| Step | First token | Total | GPU |
|---|---|---|---|
| 1.7B direct (vLLM) | 1.3 s | 4.7 s | 7.9 GB |
| 1.7B with the agent (CV) | 2.2 s | 6.4 s | 7.9 GB |
| Granite direct, 1st (includes loading) | 4.7 s | 6.9 s | 10.5 GB |
| Granite direct (XQuAD/ES) | 0.7 s | 1.4 s | 10.6 GB |
| Granite with the agent (CV) | 10.8–13.9 s | 14.2–17.6 s | 10.7 GB |
| Granite with the agent, follow-up with memory | 6.8–10.7 s | 8.2–11.5 s | — |
| 0.6B with the agent, 1st (includes loading) | 9.2 s | 11.4 s | 5.4 GB |
| Back to the 1.7B, 1st | 3.5 s | 7.6 s | — |

- **Privacy:** 0 leaks in the answers. The 5 sources of a contact answer, requested in full through `/sources`, show no private data.
- **Queue (limit 4):** 7 questions at once → 4 answered and 3 with the busy-server notice, in 16.9 s.
- **Granite with the agent is slow:** 11–14 s to the first token (rewrite, tool call and answer). This is what has to be weighed for the web.

### 8d.2 — Tunnels checked and security measures (2026-10-28)

**The author's request:** try Cloudflare and Tailscale Funnel, and know which security measures to take before opening the computer.

**Checked in the official documentation** (guide updated in `deploy/local/README.md`):
- **Cloudflare quick tunnel** (no account, random URL): it does not support Server-Sent Events, which the web's chat uses for streaming. It does not work for the web.
- **Cloudflare named tunnel** (fixed URL): it needs an account and a domain of one's own on Cloudflare, which costs money.
- **Tailscale Funnel:** free, fixed URL, TLS is terminated on the author's computer (the relay does not see the content) and only the chosen port is exposed. Without `--bg`, the tunnel closes with the terminal; with `--bg`, it survives reboots. Recommended without `--bg`.

**What changed:**

| File | Change |
|---|---|
| `src/api/app.py` | `RAG_API_DOCS=0` hides `/docs`, `/redoc` and `/openapi.json`. `/search` goes through the same queue as `/chat` (with a full queue, error 503). `ServerBusy`, the full-queue exception, so that it is not mixed up with other errors |
| `Makefile` | `API_DOCS ?= 1`; `make api-public` sets `API_DOCS = 0` |
| `tests/test_api.py` | 2 tests: `/search` with a full queue and the hidden docs |
| `deploy/local/README.md` | Tunnel table with what was checked, steps without `--bg`, an optional test of Cloudflare's quick tunnel and a security section (what is exposed, what is protected and the remaining risks) |

`make api` stays the same: docs visible and no queue limit.

**Finding pending the author's permission:** Docker publishes Qdrant (ports 6333 and 6334) on every interface, with no password. From the local network, the index could be read, including the unmasked CV, or deleted. The tunnel does not expose it to the internet. Proposal: `"127.0.0.1:6333:6333"` and `"127.0.0.1:6334:6334"` in `docker-compose.yml`, and `docker compose up -d` (the data is in a named volume).

**Checked:** 131 tests, flake8 and mypy clean.

## 8g — More elaborate answers (overnight session, 27 to 28 October)

**The author's request:** the answers are too short. Try rules per model; same parameters, and if something gets worse, it is not adopted.

**Cause:** prompt rule 6, "Be direct and concise: a few sentences, no preamble.", there since Phase 3. The token limit has not changed: the web still allows 1024 (`API_MAX_TOKENS`). The long answers the author remembered were Phi-4-mini's (239 tokens on average), dropped in Phase 7 (DEC-32).

### Mechanism (nothing changes by default)

| File | Change |
|---|---|
| `src/config.py` | `GenerationConfig.style_rule`: a model's rule 6 (empty = the usual one). `SourceConfig.style_rule`: a domain's rule 6, over the model's (`None` = the model's) |
| `src/rag/generator.py` | `STYLE_RULE` (the current rule 6); `build_messages(..., style_rule)` replaces it when another one is given. `answer_with_text`, `stream_answer`, `build_prompt` and `fit_sources` accept the domain's rule |
| `src/rag/domain_rules.py` | `style_rule(domain)` |
| `src/rag/pipeline.py`, `src/agent/agent.py` | They pass the domain's rule to the generator only when the domain sets one |
| `tests/test_generator.py` | The rule replaces only rule 6; the domain's one is read from its source |

Without `style_rule` in `rag.toml`, the prompt is byte-for-byte the same as before. It is tested with the `RAG_GENERATION_STYLE_RULE` environment variable.

### Rules tested

| | Rule 6 |
|---|---|
| S0 | (the current one) Be direct and concise: a few sentences, no preamble. |
| S1 | Give a complete answer: start with the direct answer, then explain the relevant details from the SOURCES (how it works, steps, options or examples). Use a short list when there are several items. No preamble. |
| S2 | Answer in one or two short paragraphs: the direct answer first, then the most relevant details from the SOURCES. No preamble. |
| S3 | S1 + "Add only details stated in the SOURCES; if they do not answer the question, follow rule 4." |
| S4 | S2 without "from the SOURCES" |
| S5 | Be direct, no preamble: give the answer, then explain it briefly in two or three more sentences. |

**Matrix** (8a's, `data/output/night2/run9.sh`): open bank (34 questions, as in the web); `gen-bench` at 1024 tokens on vLLM (25 per set; 50 on the 0.6B, as in `97`), CV, "about" and XQuAD (300 per language); Groq judge on vLLM (25 per set). The 1.7B with S0 was measured again (`120`) and came out identical to `97`: generation is deterministic, so every difference comes from the rule.

### Qwen3-1.7B (`120`–`125`)

| | S0 | S1 | S2 | S3 | S4 | S5 |
|---|---|---|---|---|---|---|
| Tokens, open bank (mean / max) | 130 / 383 | 228 / 548 | 185 / 403 | 222 / 592 | 193 / 384 | 187 / 532 |
| Tokens, vLLM docs (mean) | 104 | 186 | 158 | 173 | 161 | 154 |
| Judge docs / code | 1.48 / 1.32 | 1.68 / 1.16 | 1.52 / 1.32 | 1.68 / 1.16 | 1.64 / 1.28 | 1.64 / 1.28 |
| Judge ES docs / code | 1.70 / 1.50 | 1.80 / 1.60 | 1.80 / 1.30 | 1.80 / 1.10 | 1.80 / 1.40 | 1.70 / 1.60 |
| Correct according to the judge (of 70) | 47 | 49 | 45 | 47 | 47 | **50** |
| False "not found" code / ES code | 0.12 / 0.10 | 0.20 / 0.10 | 0.12 / 0.20 | 0.20 / 0.10 | 0.08 / 0.10 | 0.08 / 0.10 |
| Citation (docs / code / ES code) | 0.88 / 0.95 / 1.00 | 0.76 / 0.90 / 0.78 | 0.88 / 0.95 / 1.00 | 0.88 / 1.00 / 1.00 | 0.84 / 0.87 / 1.00 | 0.96 / 0.96 / 0.89 |
| Out of domain, near EN / ES | 0.8 / 0.7 | 0.9 / 0.7 | 0.9 / 0.8 | 0.9 / 0.8 | 0.9 / 0.8 | 0.9 / 0.7 |
| CV contains EN / ES | 0.90 / 0.90 | 0.90 / 0.87 | 0.90 / 0.87 | 0.87 / 0.90 | 0.90 / 0.87 | 0.90 / 0.90 |
| CV, not in the CV (ES), handled well | 7/7 | 5/7 | 7/7 | 6/7 | 6/7 | 6/7 |
| "about" contains EN / ES | 0.56 / 0.61 | 0.61 / 0.67 | 0.61 / 0.61 | 0.67 / 0.61 | 0.67 / 0.67 | 0.61 / 0.67 |
| XQuAD contains EN / ES | 0.79 / 0.68 | 0.81 / 0.71 | 0.82 / 0.71 | 0.76 / 0.68 | 0.82 / 0.72 | 0.81 / 0.72 |

F1 drops with every long rule because it compares with short references; it is not a quality signal.

**What it shows:**
- **S1 and S3** (the "complete" ones, with lists): they make up CV facts (they state that the author lacks something the CV does not mention) and raise the false "not found" answers on code. Discarded.
- **The CV is the weak point of every long rule.** With S1, S3, S4 and S5, some CV question with no answer ends in a made-up denial followed by "this information is not in the sources": with longer answers, the model states a fact instead of giving the CV message. That is why **the CV keeps the short rule** with every model (`[sources.cv] style_rule`), and its answers stay as with S0.
- **S5 is the best one:** the most correct answers according to the judge (50 of 70 vs 47), fewer false "not found" on code, more citations on docs, and better on "about" and XQuAD. What drops: on code, one correct answer fewer (15 vs 16 of 25: it answers one S0 did not find, misses one S0 answered, and adds an extra type to another), and on Spanish code one answer without a citation (0.89 vs 1.00). These are swaps of single questions, not a general decline, but **it is not a strict "nothing gets worse"**.

### Granite 4.0 Micro and Qwen3-0.6B with S2

| | Granite S0 (`110`/`112`) | Granite S2 (`126`) | 0.6B S0 (`97`/`102`) | 0.6B S2 (`127`) |
|---|---|---|---|---|
| Tokens, open bank (mean) | 179 | 175 | 78 | 183 |
| Open bank: cut / echo | 0 / 1 | **1 / 3** | 0 / 3 | 0 / 0 |
| Judge docs / code | 1.64 / 1.36 | 1.60 / 1.56 | 1.16 / 1.04 | 1.24 / **0.84** |
| Correct according to the judge (of 70) | 52 | 54 | 33 | 29 |
| Judge ES docs / code | 1.90 / 1.50 | 2.00 / 1.40 | 1.60 / 1.20 | 1.70 / **1.00** |
| Echo on vLLM docs | 0.04 | **0.32** | 0.00 | 0.00 |
| False "not found" ES code | 0.00 | **0.20** | 0.10 | 0.00 |
| CV private ES handled well | 2/2 (`112`) | **1/2** | 2/2 | 2/2 |

- **Granite does not change:** it already wrote long answers (179 tokens on the open bank, more than the 1.7B with any rule). With S2 it does not write longer; the judge goes up a little (54 vs 52 correct), but echo appears (it copies the sources) in a third of the docs answers, one answer is cut, there are more false "not found" answers on Spanish code, and one private CV question is handled worse. It keeps rule 6.
- **The 0.6B does not change:** it writes much longer (78 → 183 tokens), but drops on code (judge 1.04 → 0.84; correct 11 → 5 of 25). It is the base for the comparisons with 42; it keeps rule 6.

### Qwen3-1.7B with S5 from `rag.toml`: agent and check (`128`, `129`)

S5 was set in the 1.7B profile and the short `style_rule` in `[sources.cv]`, and the real configuration was measured.

- **CV:** identical to S0 (`120`) in every figure, including the 7/7 Spanish questions with no answer. The CV is protected.
- **vLLM:** identical to S5 (`125`).
- **Open bank:** 176 tokens on average (vs 130), 28/34 answered, no cuts, echo, loops or repeated sentences.

**`agent-bench`**, both at 1024 tokens as in the web (contains / not found; agent):

| | S0 (`128`) | S5 (`129`) |
|---|---|---|
| Conversations, first question | 0.92 / 0.00 | **1.00** / 0.00 |
| Conversations, follow-up | 0.78 / 0.11 | 0.78 / 0.11 |
| CV EN / ES | 0.90 · 0.80 | 0.90 · 0.80 (not found ES 0.17 → 0.13) |
| XQuAD EN | 0.78 / 0.10 | 0.78 / **0.14** |
| XQuAD ES | 0.66 / 0.06 | **0.76** / 0.06 |
| vLLM code | 0.04 / 0.08 | **0.00 / 0.16** |
| Seconds per answer (code) | 5.0 | 6.7 |

With the agent, S5 doubles the false "not found" answers on code (from 2 to 4 of 25) and raises them on English XQuAD. In exchange it improves the first question of the conversations and Spanish XQuAD.

### Decision (the author's rule: if something gets worse, it is not adopted)

- **No model changes its rule 6.** S5 was the best for the 1.7B (50 correct of 70 vs 47 in direct mode), but it makes code worse: one correct answer fewer in direct mode and twice the false "not found" answers with the agent. Granite and the 0.6B get worse with S2 (above).
- **Left ready:** in `rag.toml`, the `style_rule` line of the `llm-qwen3-1.7b` profile is commented out. For longer answers in the web, at some cost on code, uncomment it and restart `make api` (the CV stays short).
- **Kept on:** `style_rule` in `[sources.cv]`, which changes nothing today (it is the usual rule 6) and protects the CV if a model uses a long rule. Every model's prompt is the same as before.
- **If S5 is switched on:** the CLI and the benchmarks use 150 tokens (`rag.toml`), and S5's answers exceed that on docs (154 on average). The web is not affected (1024).

**Session files:** `data/output/night2/run9.sh`, `run9-stage2.sh`, `run9-stage3.sh` and `styles/` (ignored by git); results in `bench/results/gen/` (`120`–`129`), `bench/results/judge/` and `data/output/gen_bench/<label>/answers.json`.

**Checked:** 129 tests, flake8 and mypy clean. 42 is not affected: the recall benchmark does not generate, and `answer_dataset` uses the usual rule.

## 8b — The "about" threshold (2026-10-28)

**Goal:** recover project questions that stopped passing the "about" gate (−1.0) once the documentation no longer quoted the test questions (DEC-39), without letting questions from other domains or out of domain through. The author's decision: go ahead.

**How it was measured:**
1. **`gate_scores`** for "about" on the current index (`131-about-gate`): with −1.0, 78% (EN) and 89% (ES) of the project questions pass.
2. **A simulation of the web's path** (`data/output/night2/gate8b.py`, `132-gate8b`): each question goes through the router once (every domain, `answer_k` sources) and the router's decision is replayed with each threshold (including the lexical project rule). 2,790 questions: 42 (docs and code), the Spanish complement, XQuAD EN/ES, CV, "about", out of domain, CV with no answer and the open bank.
3. **Real answers** to the questions that change, with the 1.7B and the 0.6B (`gate8b_gen.py`).

**Questions that change vs −1.0** (for the rest of the 2,790, the outcome is the same with every threshold; 42, XQuAD and CV reach their domain as before):

| Question | −1.25 | −1.5 | −2.0 |
|---|---|---|---|
| about-EN, the default model | ✅ answered well (both models) | ✅ | ✅ |
| Open bank, the reranker (EN) | ✅ answered well (both) | ✅ | ✅ |
| about-EN, the function that lists the files | The 1.7B: not found; the 0.6B: wrong answer | same | same |
| about-ES, the reranker | not found | ✅ answered well (both) | ✅ |
| about-EN, the reranker | not found | not found | passes |
| XQuAD-ES, a question about an article's title | ❌ goes to "about" and is answered wrongly (before: not found) | ❌ | ❌ |
| CV with no answer (driving licence, EN) | goes to "about": not found | same | same |
| Out of domain: a sports question | not found | ❌ **the 1.7B answers it** from the documentation | ❌ |
| Near out of domain (ES), 2 | not found | not found | ❌ go to "about" |
| Open bank: the system's models and how the web was built | not found | not found | pass (−1.75 and −2.0) |

**Decision: −1.25** (`rag.toml`, `[sources.about] relevance_threshold`). It recovers two project questions with both models and lets nothing out of domain through. Cost: one Spanish XQuAD question, which already did not reach its domain, goes from "not found" to a wrong answer. −1.5 would recover one more Spanish question, but the 1.7B would answer an out-of-domain question from the documentation.

**Note:** the Spanish question on what the project's agent does (worse in §8h) is back in "about" with the final index, even with −1.0: re-indexing after §8h changed the chunk cuts again. Questions at the edge of the threshold move with every documentation change.

**Not measured yet:** the official `route-bench` (k = 10) and the "about" `gen-bench` with the new threshold. The simulation covers the same questions on the web's path. They are left for when the GPU is free (with the web running, they compete for it).

**Files:** `rag.toml` (threshold and comment). Scripts ignored by git: `data/output/night2/gate8b.py` and `gate8b_gen.py`; results in `bench/results/gate/` and `data/output/night2/132-gate8b.json`.

## 8h — Documentation up to date for "about" (2026-10-28)

**The author's request:** update the documents so that "about" does not get confused. With the "about" language filter (DEC-34), English questions only see `docs/`, which had nothing about Phase 8.

**What changed:**

| File | Change |
|---|---|
| `README.md`, `docs/es/README.md` | Models: Qwen3-0.6B (base), Qwen3-1.7B (the web's default), Qwen3-4B (CLI and benchmarks) and IBM Granite 4.0 Micro. The web's model picker. Current deployment: from the author's computer with a tunnel. `deploy/local` in the layout. "about" is now ~3,000 chunks |
| `docs/changelog/FASE_8.md` | New: English translation of this changelog |
| `docs/ROADMAP.md` | Phase 8 translated, diagram, P12 and log |
| `docs/es/ROADMAP.md`, `docs/ROADMAP.md` | "Current" notes next to the historical text: the Phase 6 deployment plan (Space, then Oracle), the 4B out of the web, and the 4B memory problem marked as solved |
| `docs/es/BENCHMARK_REPORT.md`, `docs/BENCHMARK_REPORT.md` | New §10 (Granite and the length of the answers) and, in §8, which models are in the web today |
| `docs/es/changelog/FASE_8.md` | The verbatim quotes of made-up CV answers (§8g) and an empty Granite answer (§8a.2) move to `es/RESPUESTAS_ARCHIVADAS.md` §9 (DEC-39) |

"about" re-indexed (`make index SOURCE=about`): 1,005 parents and 3,015 children (this section included).

**Checked with the 1.7B, as in the web** (`data/output/night2/about8.py`, 12 questions about the new content):
- **Good:** the web's models (English), Granite, the 4B out of the web, where it is deployed (Spanish), why not Cloudflare (both languages) and why the answers are short. Before the "current" notes, the web appeared as deployed on Oracle or on the Space, and the model list included Phi.
- **They do not reach "about":** the Spanish question on which models can be chosen in the web (not found) and the English one on where the web is hosted (goes to vLLM). They do not pass the "about" gate: that is the 8b threshold.
- **The question on whether the project uses IBM Granite** goes to vLLM, whose documentation lists Granite models. It is an ambiguous question.
- **CV questions with no answer** (pets, driving licence): they end in "about" with "not found", not in the CV message. This already happened (8b).

**Open bank, 1.7B** (`130` vs `120`): 29/34 answered, no cuts, echo, loops or repeated sentences, 125 tokens on average. 6 answers change: 5 "about" ones the same or better, and **one worse**: the Spanish question on what the project's agent does moves from "about" to the CV and is answered badly. Before, it passed the "about" gate by 0.03 (−0.97 vs the −1.0 threshold); as the README grew, its chunks were cut differently and the best one is now at −1.46. It is the "about" threshold problem (8b): with the current threshold, any change in the documentation moves the borderline questions.

42 does not change: vLLM was not re-indexed.
