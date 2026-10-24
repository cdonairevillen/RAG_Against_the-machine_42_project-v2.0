# CHANGELOG — Phase 5: Agents and the RAG as an MCP server

> English translation of [`../es/changelog/FASE_5.md`](../es/changelog/FASE_5.md), the working version.

**Start date:** 2026-10-23
**Status:** ✅ completed (2026-10-24). D7's decisions, the `src/` reorganisation, the RAG's tools, the MCP server, the agent (memory, rewriting, tool loop, fallback and safety nets), `chat` with the agent/direct switch, and the agent vs direct access benchmark with four models (§7).

---

## 1. Decisions (the author's)

- **D7 — the agent by default**, as in a real RAG, with session memory. **Direct access** stays as an option. In the web it will be a **"With agent / Without agent" switch** (Phase 6), and the API will take it as a request parameter.
- **Every model can be an agent**, Qwen3-0.6B included, without restrictions. If a model fails, the benchmark will show it, and the benchmarks will decide which model is deployed.
- **Session-only memory:** nothing about the web's visitors is stored.
- **The payload's `lang` field leaves the plan:** answers already follow the question's language (90–100% on every set).

## 2. `src/` reorganisation (no logic changes)

`src/` was flat. Now it separates the RAG, the RAG as a service, and the agent:

```
src/
├── __main__.py, cli.py     entry points (python -m src …; the 42 commands do not change)
├── config.py, models.py    shared (models.py = the 42 pydantic formats)
├── rag/                    the RAG: indexing, retrieving and answering
│   ├── ingestion/  storage/  sources/
│   ├── retriever.py  router.py  embeddings.py
│   ├── generator.py  language.py  domain_rules.py
│   └── pipeline.py         (formerly src/rag.py: the answer pipeline)
├── server/                 the RAG as a service: tools.py + mcp_server.py
├── agent/                  the agent (under construction)
├── evaluation/             benchmarks and the 42 evaluator
└── web.py
```

| Before | Now |
|---|---|
| `src/ingestion/`, `src/storage/`, `src/sources/` | `src/rag/ingestion/`, `src/rag/storage/`, `src/rag/sources/` |
| `src/{retriever,router,embeddings,generator,language,domain_rules}.py` | `src/rag/…` |
| `src/rag.py` | `src/rag/pipeline.py` |
| `src/tools.py`, `src/mcp_server.py` (new) | `src/server/` |

- **Why `server/` and not inside `agent/`:** the MCP server is the RAG's door. Any client uses it, and our agent is just one more client. The agent only depends on the tools, never on the RAG's internals.
- **Checked:**
  - `make bench` gives exactly the same (`60-fase5-restructure`: docs 0.76 / 0.91 / 0.92 / 0.94, code 0.51 / 0.72 / 0.80 / 0.88).
  - 78 tests, flake8 and mypy green.
  - `answer` and the MCP server work end to end.
- **The earlier changelogs** keep the paths of their time; this table translates them.

## 3. The RAG's tools and the MCP server

- **`src/server/tools.py` (`RagTools`):**
  - `list_domains()`: name, description and chunks of each domain. The description is a new field, `description`, in each `[sources.<x>]` of `rag.toml`; the agent and MCP clients need it to choose where to search.
  - `search(query, domains, k)`: the chosen domain, its score and the sources with the **text already masked**. If it does not pass the out-of-domain gate, it returns an empty list.
  - `answer(question, domains, k)`: the direct pipeline, with its sources.
- **`src/server/mcp_server.py`:** exposes those three tools with the official MCP SDK. In `mcp` 2.x, **FastMCP is called `MCPServer`**: the same API under another name.
  - The RAG is loaded on the first call, so the server answers the handshake at once.
  - **Over stdio, the RAG's progress output** ("Loaded … chunks") is redirected to stderr, because stdout is the protocol's channel.
- **Usage:**
  - `make mcp`: stdio, for clients that launch the server (Claude Desktop, the agent…).
  - `make mcp MCP_TRANSPORT=streamable-http`: `http://127.0.0.1:8765/mcp`.
- **End-to-end test:** a real MCP client launches the server over stdio, lists the three tools and calls `list_domains` and `search`.
  - With the CV, the text comes out masked.
  - The Super Bowl question goes to XQuAD (score 2.8).
  - Fixed: with a single domain, the score came out as `NaN`, which is not valid JSON; now it comes out as `null`.

## 4. The agent (`src/agent/`)

It is inspired by AgentSmith: the loop's structure, the trace of steps and a fallback when the model does not follow the format. What is different here changes: local models instead of an API, native tool calls instead of code, and a final answer written by the RAG's generator with its guardrails.

**Flow per question** (`Agent.ask`):
1. **Plan:** the LLM gets the domains (with their descriptions), the conversation and the question, and calls `search` with a **complete question**: this is where follow-ups are rewritten. It can search up to 3 times and stops when it no longer calls the tool.
2. **Deterministic fallback:** if it makes no valid call, the question is searched preceded by the last query the model itself wrote. That way a follow-up keeps its topic ("Where was Chrystian born? And in which year?").
3. **Answer:** the gathered sources go to **the same generator as the direct pipeline**, with the domain's rules (citations, the CV prompt, private data, the author's "not found" message) and in **the user's language**, even if the search was rewritten in another one.
4. **Memory:** the turn is added to the session (`Session`, in memory only; D7).

**Each model with its tool convention** (`src/agent/toolcalls.py`):
- **`native`** (Qwen3): `apply_chat_template(..., tools=)`, and the calls come out as `<tool_call>{json}</tool_call>`.
- **`system_tools`** (Phi-4-mini): the tools go as JSON in a `tools` field of the system message (`<|tool|>…<|/tool|>`).
- **`prompt`** (any other model): they are described in the system prompt and the `<tool_call>` format is requested.
- **The parser accepts every wrapper** and JSON shape, even truncated or with single quotes.
- `Generator.complete()` returns the raw output with those markers; `decode()` used to remove them.

**Adjustments measured by hand with Qwen3-0.6B** (before the benchmarks):

| Problem | Fix |
|---|---|
| With the history as earlier chat turns (user/assistant), on follow-ups the model **copied the pattern and answered without searching** | The history goes **inside the user turn** ("Conversation so far: … New question: …"), so the pattern is always question → tool |
| On follow-ups it answered "DONE" without searching ("the conversation already says it") | A prompt rule: "every new question needs at least one search"; DONE only after searching |
| The fallback chained queries ("Where was… born? And in which year? In which neighbourhood…?") and lost the topic | The fallback uses the last query written by the **model**, not those of other fallbacks |

**Safety nets** (after round 1 of the benchmark; the author's proposal, bounded; `decisions.md`, DEC-03):

| Net | When it acts | What it does |
|---|---|---|
| **1. Original question** | None of the model's searches found sources (its keyword-style rewrites do not pass the relevance gate) | Searches the question as the user wrote it, within the user's filter |
| **2. Domains** | The model restricted the domains, the user did **not** set a filter, and nothing was found | Repeats the same query in every domain (exactly what direct mode searches) |

- **It never goes beyond the user's filter:** with a filter, the model's domains already are that filter, and net 2 does not act. `test_user_filter_is_never_exceeded` guarantees it.
- **If both fail**, the usual deterministic fallback is used.
- **Every use is recorded in the trace** (`AgentAnswer.retries`: `"all-domains"`, `"original-question"`), visible in the web and in `chat`.

With this, Qwen3-0.6B really rewrites: "¿Y en qué año?" → "¿Y en qué año? Chrystian Donaire Villén nació en Madrid."; "¿En qué barrio creció?" → "¿En qué barrio creció Chrystian Donaire Villén?"; "And which one unloads it?" → "which endpoint unloads a LoRA adapter in vLLM" (with `domains: vllm`).

**Usage:**
- `answer` uses **the agent by default** (D7); `--agent False` uses the direct pipeline.
- **`chat`** is an interactive conversation with memory: `/agent` toggles agent/direct (the future web switch), `/reset` forgets the conversation and `/exit` quits.
- **The user's domain filter** (for example, the web's CV mode) prevails over the domains the model picks.

**Benchmark** (`make agent-bench`, `src/evaluation/agent_bench.py`):
- Every question is answered with the agent and with the direct pipeline.
- **Conversations:** `bench/datasets/conversations/conversations.json`, 12 dialogues of 2–3 turns in English and Spanish about the CV, XQuAD and vLLM, one of them with a change of domain. The follow-ups ("¿Y cómo se llama el videojuego en el que trabaja allí?", "And which one unloads it?") need the earlier turns.
- **Single questions:** CV (30 + 30), XQuAD (50 + 50, a fixed sample) and vLLM (25 docs + 25 code).
- **Metrics:** contains the answer, F1, "not found", seconds per answer and, for the agent only, the proportion of valid tool calls (without the fallback) and the steps.
- **The LLM is the active profile's**, so the same benchmark compares models: `make agent-bench PROFILE=llm-qwen3-4b`.

## 5. Unified data download (`Makefile`, the author's request)

| Target | Before | Now |
|---|---|---|
| `make data` | vLLM only | **Every public source:** `data-vllm` + `data-xquad` |
| `make data-vllm` | — | vLLM 0.10.1 from the GitHub tag (the old `data`) |
| `make data-xquad` | The same | The same |
| `make data-42` | The original 42 download (vLLM + datasets) | **Removed.** It was redundant: its vLLM is identical to the GitHub tag's (checked in Phase 0), the public datasets are already versioned (now in `bench/datasets/public/`, see below) and the intranet CDN returns 403 without a 42 session. The `URL_42` variable is removed too |
| `make install` | It depended on `data`, which ran before creating the venv | It creates the venv, installs and **then** runs `data` (XQuAD is prepared with Python) |

- **Not downloaded:** the CV (private material) and Gulliver (4c, postponed).
- **Checked:** `make data` regenerates XQuAD identically (2,380 answers verified, the versioned datasets do not change).

**`data/` and `bench/` unified** (the author's request; the direction was chosen in `decisions.md` DEC-01):
- The public 42 datasets move from `data/datasets/` to **`bench/datasets/public/`** (`git mv`, without changing the files).
- **Now:** `bench/` is what is versioned (datasets and results) and `data/` is what is local and can be regenerated (corpora, indices, outputs), fully ignored by git with no exceptions.
- **Paths updated:** `Makefile` (`DATASETS`), the `SUITES` of `bench.py`, the examples in `cli.py`, the evaluator's docstring, `web.py` and `README.md`.
- **The 42 evaluator is kept:** it is the reference metric (D4) that every benchmark uses; it is not legacy code. A note is added to its docstring.
- **Checked:** `make bench` gives the same (`61-datasets-moved`: docs 0.76 / 0.91 / 0.92 / 0.94, code 0.51 / 0.72 / 0.80 / 0.88).

## 6. Files

| File | Change |
|---|---|
| `src/rag/**`, `src/server/**` | Moved (§2), and the new `tools.py` and `mcp_server.py`. |
| `src/cli.py` | The `mcp` command; new imports. |
| `src/config.py` | `SourceConfig.description`. |
| `rag.toml` | The description of each domain. |
| `Makefile` | `make mcp` (`MCP_TRANSPORT`, `MCP_PORT`). |
| `pyproject.toml`, `uv.lock` | `mcp>=2.3.0`. |
| The rest of `src/` and `tests/` | Only imports and paths in comments. |
| `src/agent/agent.py`, `memory.py`, `toolcalls.py` | **New.** The agent, the session memory and the tool conventions. |
| `src/rag/generator.py` | `complete()` (raw output) and an optional answer language (`language`). |
| `src/cli.py` | `answer` with the agent by default (`--agent`), the interactive `chat` and `agent_bench`. |
| `src/evaluation/agent_bench.py`, `bench/datasets/conversations/` | **New.** The agent vs direct access benchmark. |
| `Makefile` | `make agent-bench` (`SETS=`, `PROFILE=`); unified `data` (§5). |
| `tests/test_agent.py` | **New.** The parser of each convention, styles, memory and the agent loop (valid call and fallback). Later also the safety nets, and that the user's filter is never exceeded. |
| `src/agent/agent.py` | Safety nets and `AgentAnswer.retries` (after the `680f21a` checkpoint). |
| `src/evaluation/agent_bench.py` | `safety_net_rate`. |
| `data/datasets/` → `bench/datasets/public/` | Moved (§5). Paths in `Makefile`, `bench.py`, `cli.py`, `evaluator.py`, `web.py` and `README.md`; `.gitignore` without the `!data/datasets/` exception. |
| `docs/BENCHMARK_REPORT.md` | §8: agent vs direct access. |

## 7. Results and closing

Full details in `BENCHMARK_REPORT.md` §8. Contains the answer, agent / direct (round 2, with the nets):

| Model | Follow-ups | CV EN / ES | XQuAD EN / ES |
|---|---|---|---|
| **Qwen3-0.6B** | **0.78** / 0.33 | 0.70 / 0.80 (direct 0.73 / 0.80) | 0.58 / 0.70 (direct 0.62 / 0.70) |
| Qwen3-1.7B | 0.83 / 0.33 | 0.90 / 0.87 | 0.76 / 0.68 |
| Qwen3-4B | **1.00** / 0.39 | 0.87 / 0.90 | 0.80 / 0.88 |
| Phi-4-mini | 0.78 / 0.33 | 0.83 / 0.90 | 0.74 / 0.64 |

- **The agent solves the follow-ups** (direct mode cannot) and, with the nets, it is **on a par with direct mode** (±0.04) on single questions with all four models. In round 1, the 0.6B lost 0.12 on XQuAD EN and the 1.7B up to 0.32.
- **42 recall:** unchanged (`61-datasets-moved`). The agent does not touch the measured retrieval.
- **Tests:** 94 pass; flake8 and mypy clean.
- **Round 1** (`01-agent-*`) is included in the checkpoint commit; **round 2** (`02-agent-nets-*`) was left uncommitted.

> ✅ **Phase 5 completed (2026-10-24)**: the agent by default with session memory, the MCP server, direct access as an option, and the benchmark. **Pending decision:** which LLM is deployed (proposal in `BENCHMARK_REPORT.md` §8.3: Qwen3-0.6B, with Qwen3-1.7B as a candidate if the Space's CPU can take it).
