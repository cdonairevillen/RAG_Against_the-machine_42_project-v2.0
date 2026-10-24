*Started as part of the 42 curriculum by cdonaire (RAG against the Machine). Version 2.0 is a personal rework of that project into a full, production-style RAG system.*

# RAG against the Machine v2.0

A multi-domain **Retrieval-Augmented Generation** system with an agent, an MCP server and a web interface. It answers questions with citations from three knowledge bases:

| Domain | What it holds | Size |
|---|---|---|
| `vllm` | The vLLM 0.10.1 documentation and source code (the 42 benchmark corpus) | 37,381 chunks |
| `xquad` | General knowledge: 48 Wikipedia articles from XQuAD, in English and Spanish | 1,217 chunks |
| `cv` | The author's CV, LinkedIn profile and biography (English and Spanish) | 162 chunks |

The base language model is **Qwen3-0.6B**, the model of the original 42 project, so the results stay comparable with other 42 RAGs. Larger models (Qwen3-1.7B, Qwen3-4B, Phi-4-mini) are optional profiles.

The project was rebuilt phase by phase, and every change was measured before it was kept. The full history, with the numbers, is in [`docs/`](docs/).

**Live demo:** *coming soon* (Hugging Face Space). <!-- TODO: link to the Space once deployed -->

---

## Contents

[Results](#results) · [How it works](#how-it-works) · [Web interface](#web-interface) · [Running it](#running-it) · [Deployment](#deployment) · [Project layout](#project-layout) · [Documentation](#documentation) · [Credits](#credits) · [License](#license)

---

## Results

### Retrieval on the official 42 benchmark

The public 42 datasets (100 documentation and 100 code questions), the original 42 evaluator (a hit is a retrieved source overlapping the ground truth by at least 5% of its characters) and `k = 10`:

| Version | Docs R@1 / R@3 / R@5 / R@10 | Code R@1 / R@3 / R@5 / R@10 |
|---|---|---|
| v1, as delivered to 42 | 0.64 / 0.83 / 0.85 / 0.85 | 0.44 / 0.61 / 0.63 / 0.68 |
| **v2.0** | **0.76 / 0.91 / 0.92 / 0.94** | **0.51 / 0.72 / 0.80 / 0.88** |

The metric priority is R@5 > R@10 > R@3 > R@1. **Docs R@5 went up by 0.07 and code R@5 by 0.17.** The 42 commands (`search_dataset`, `answer_dataset`, `evaluate`) still work and keep their output format.

### The other domains

| Set | Measure | Result |
|---|---|---|
| XQuAD, 1,190 questions per language | Retrieval R@1 / R@3 / R@5 / R@10 | EN 0.95 / 0.99 / 0.99 / 1.00 · ES 0.92 / 0.99 / 0.99 / 1.00 |
| XQuAD (Qwen3-0.6B) | The answer contains the right fact | EN 0.65 · ES 0.57; the right source is cited in 99% of answers |
| CV, 30 questions per language | Retrieval R@1 / R@3 / R@5 / R@10 | EN 0.47 / 0.80 / 0.93 / 0.97 · ES 0.70 / 0.83 / 0.97 / 1.00 |
| CV (Qwen3-0.6B) | The answer contains the right fact | EN 0.73 · ES 0.80, with **0 leaks of private contact data** |
| Router, no filter | Questions sent to their own domain | 42: 100% · CV: 100% · XQuAD: ~98% |

### Agent vs direct RAG

Twelve conversations of 2–3 turns, where the follow-up questions only make sense with the earlier turns ("And in which year?"). The table shows how often the answer contains the right fact:

| Model | Follow-ups, agent | Follow-ups, direct |
|---|---|---|
| Qwen3-0.6B | **0.78** | 0.33 |
| Qwen3-1.7B | 0.83 | 0.33 |
| Qwen3-4B | **1.00** | 0.39 |
| Phi-4-mini | 0.78 | 0.33 |

On single, self-contained questions the agent stays within ±0.04 of the direct pipeline with all four models.

Every run is stored in [`bench/results/`](bench/results/) with its full configuration. The analysis is in [`docs/BENCHMARK_REPORT.md`](docs/BENCHMARK_REPORT.md).

---

## How it works

```
question ──► agent (optional) ──► router ──► per-domain retrieval ──► generator ──► answer + sources
               │                    │          BM25 + bge-m3 (Qdrant)    Qwen3 (llm_sdk)
               │ memory, rewriting  │          RRF + cross-encoder       citations [n]
               │ tool calls         │          relevance gate            question's language
               └─ MCP tools ────────┘
```

### Ingestion

- **Parent/child chunks.** Parents keep the full context that goes to the LLM; children (up to 600 characters) are what gets indexed.
- **Code** (`.py`) is chunked with Python's `ast`: whole functions and classes, and long classes split by method with the class signature in front.
- **Markdown** is split by headers, with small sections packed together so no chunk is a lone title.
- **The CV** (`.docx`, `.pdf`) is converted with Docling.
- **Storage:** Qdrant (server, in Docker) holds the chunks and their `bge-m3` vectors, with stable IDs and a payload per chunk (domain, type, file, character range, parent). BM25 indices (`bm25s`) sit next to it, linked by the same IDs.

### Retrieval

- **Hybrid search per branch.** A lexical classifier with English and Spanish signals sends each question to the docs branch or the code branch. Each branch combines BM25 (with a code-aware tokenizer that also splits `snake_case` and `CamelCase` identifiers) and dense `bge-m3` embeddings.
- **Reranking.** In the code branch, the multilingual cross-encoder `mmarco-mMiniLMv2-L12-H384-v1` reranks the candidates, fused with the first stage through Reciprocal Rank Fusion. The docs branch skips it, because it was measured to hurt documentation ranking on this corpus. The same cross-encoder scores the domains for the router and the relevance gate.
- **Router.** Without a filter, every domain is searched and the one whose best sources get the highest cross-encoder score answers. With a filter, only the chosen domains take part.
- **Relevance gate.** If not even the best domain is relevant enough, the LLM is not called and the system says it did not find the answer. Each domain has its own threshold, calibrated on its own data, because the cross-encoder scores each corpus on a different scale.

### Generation

- **Qwen3-0.6B** through the course SDK (`llm_sdk`, untouched), with the official chat template and thinking mode disabled.
- **Grounded answers:** numbered sources cited as `[n]`, a context budget in tokens, and an explicit instruction to answer in the language of the question.
- **Domain rules** from `rag.toml`: an extra prompt for the CV domain (third person, do not mix jobs), masking of private contact data in the context, the answer and the shown sources, and a custom "not found" message that offers the public contact address.
- **Streaming,** token by token, to the CLI and the web.

### Agent and MCP

- **The agent is the default path**, as in production RAG systems; the direct pipeline is one switch away.
  - It keeps a **session-only memory** of the conversation (nothing is stored).
  - It rewrites follow-up questions into complete ones and searches with **native tool calls**: Qwen's `<tool_call>` format, Phi-4-mini's tools in the system message, or a prompt format for other models. Up to 3 searches per question.
  - **Safety nets:** if the rewrite finds nothing, it searches the original question; if the model's domain choice finds nothing, it retries within the user's filter, never outside it. A deterministic fallback covers models that do not call the tool.
  - The final answer uses the same generator and domain rules as the direct path.
- **MCP server** (`make mcp`): the RAG exposed as `list_domains`, `search` and `answer` tools, over stdio or streamable HTTP, for any MCP client.

---

## Web interface

FastAPI backend and React (Vite + TypeScript) frontend, in the visual style of the original Streamlit app:

- **Chat** with streaming answers. Only the conversation scrolls, and a **Stop** button really stops the generation on the server.
- **Domain filters** (`vllm`, `xquad`, `cv`), an **agent / direct** switch, and pickers for the **model** and the **depth** (how many sources the LLM reads: 3, 5 or 10).
- **Sources:** the domain that answered, with its sources in a carousel and the full masked text on demand; the other searched domains are folded in one line, with their router scores.
- **Retrieval metrics** read from the latest benchmark runs.
- Optional **example questions** for the active filters.

### API

| Endpoint | Purpose |
|---|---|
| `POST /chat` | Answer a message as Server-Sent Events (`start`, `token`…, `done`). Takes `agent`, `domains`, `model`, `depth` and `session_id` |
| `POST /chat/reset` | Forget a conversation |
| `POST /search` | Retrieval only, no generation |
| `GET /sources/{id}` | Full text of a source, with private data masked |
| `GET /config` · `GET /metrics` · `GET /health` | Models, domains and options; benchmark numbers; readiness |

---

## Running it

### Requirements

- Python 3.10+ and [uv](https://github.com/astral-sh/uv).
- Docker, for Qdrant.
- Node.js, for the web.
- A GPU is optional. Everything falls back to the CPU and gives the same results, only slower.

### Setup

```bash
make install     # virtual environment, dependencies, and the public data (vLLM + XQuAD)
make index       # build every index (about 6 min on an RTX 3080 Ti; hours on a CPU)
```

The `cv` domain needs private material that is not in the repository.

### Use

```bash
make api                 # the API on http://127.0.0.1:8000 (it also serves the built web)
make web-dev             # the web in development mode on http://localhost:5173
make run ARGS="answer 'How do I enable prefix caching in vLLM?'"   # agent by default
make run ARGS="chat"     # interactive conversation; /agent toggles the agent
make mcp                 # MCP server (stdio)
```

Optional models: `PROFILE=llm-qwen3-1.7b` (or `llm-qwen3-4b`, `llm-phi4-mini`) for the CLI. In the web, use the model picker.

### Benchmarks

```bash
make bench                     # official 42 recall (docs and code)
make bench SUITE=xquad         # other suites: xquad, cv, en, es
make gen-bench SUITE=xquad     # answer quality (fixed 300-question subset; FULL=1 for all)
make agent-bench               # agent vs direct
make route-bench               # router accuracy
make judge LABEL=<run>         # LLM judge over a gen-bench run (free Groq key)
make test && make lint         # pytest, flake8, mypy
```

The original 42 commands are unchanged: `make search-docs`, `make search-code`, `make eval-docs`, `make eval-code`.

---

## Deployment

**Live demo:** *coming soon*. <!-- TODO: Space URL -->

Built to run for free:
- **Backend:** a Hugging Face Space (Docker, free CPU), with Qdrant inside the container.
- **Frontend:** served by the Space, or optionally from GitHub Pages.
- **Index:** built on a local GPU and shipped as a bundle (Qdrant snapshots and BM25 files, checked with SHA256) in a **private** Hugging Face dataset, because it holds the raw CV material.

`make bundle`, `make space-build` and `make space-run` reproduce the Space locally. The step-by-step guide is in [`deploy/README.md`](deploy/README.md).

With the free tier's limits simulated (2 vCPU, 16 GB), an answer takes about 15–25 s in direct mode and 22–32 s with the agent, streamed as it is written.

---

## Project layout

```
src/
  rag/          the RAG: ingestion, Qdrant/BM25 storage, retriever, router, generator, pipeline
  agent/        the agent: loop, tool-call formats, session memory
  server/       the RAG as tools, and the MCP server
  api/          FastAPI backend of the web
  evaluation/   42 evaluator, benchmarks, routing, agent bench, LLM judge
  deploy/       index bundle export/restore
  cli.py        Fire CLI (python -m src <command>)
web/            React frontend
deploy/space/   Hugging Face Space image
bench/          versioned datasets and every benchmark result
docs/           roadmap, phase changelogs, benchmark report, decisions
rag.toml        configuration: sources, models and optional profiles
```

Every pipeline piece (chunker, embeddings, reranker, LLM, agent on or off) is chosen through `rag.toml`, environment variables or a profile, not through code.

---

## Documentation

- [`docs/ROADMAP.md`](docs/ROADMAP.md): the plan and status of every phase, and the dated log of decisions.
- [`docs/BENCHMARK_REPORT.md`](docs/BENCHMARK_REPORT.md): embeddings, rerankers, LLMs, domains and the agent, compared with numbers.
- [`docs/changelog/`](docs/changelog/): what changed in each phase, why, and what it affects.
- [`docs/decisions.md`](docs/decisions.md): decisions taken along the way, with the options considered.

---

## Credits

- **vLLM** documentation and code (Apache-2.0), the 42 benchmark corpus.
- **XQuAD** (Google, CC-BY-SA 4.0), based on Wikipedia.
- Models: [Qwen3](https://huggingface.co/Qwen), [BAAI/bge-m3](https://huggingface.co/BAAI/bge-m3), [cross-encoder/mmarco-mMiniLMv2-L12-H384-v1](https://huggingface.co/cross-encoder/mmarco-mMiniLMv2-L12-H384-v1), [Phi-4-mini](https://huggingface.co/microsoft/Phi-4-mini-instruct).
- Tools: Qdrant, bm25s, sentence-transformers, Docling, FastAPI, React, Vite, the MCP Python SDK, uv and Python Fire.

### AI usage

Version 2.0 was updated together with Claude (Anthropic), and reviewed and designed by hand by Chrystian. The project rules are in [`docs/PLANING.md`](docs/PLANING.md): measure every change, document every phase, and leave every decision to the author.

---

## License

The project's own code and documentation are released under the [MIT License](LICENSE). Third-party content in this repository keeps its own terms:
- **`bench/datasets/xquad/`:** derived from XQuAD, under CC-BY-SA 4.0 (see its README).
- **`bench/datasets/public/`:** the public datasets of the 42 project. **`bench/datasets/en/` and `bench/datasets/es/`:** a subset of their questions, and its Spanish translation. Not covered by the MIT License.
- **`llm_sdk/`:** the course SDK provided by 42. Not covered by the MIT License.
- **The indexed corpora** (vLLM, Wikipedia via XQuAD) are downloaded by `make data`, not stored in the repository, and keep their licenses (Apache-2.0 and CC-BY-SA 4.0).

---

**Author:** Chrystian Donaire Villén · [cdonairevillen@gmail.com](mailto:cdonairevillen@gmail.com)
