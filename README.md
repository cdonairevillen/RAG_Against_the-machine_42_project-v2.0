*Started as part of the 42 curriculum by cdonaire (RAG against the Machine). Version 2.0 is a personal rework of that project into a full, production-style RAG system.*

# RAG against the Machine v2.0

A multi-domain **Retrieval-Augmented Generation** system with an agent, an MCP server and a web interface. It answers questions with citations from four knowledge bases:

| Domain | What it holds | Size |
|---|---|---|
| `vllm` | The vLLM 0.10.1 documentation and source code (the 42 benchmark corpus) | 37,381 chunks |
| `xquad` | General knowledge: 48 Wikipedia articles from XQuAD, in English and Spanish | 1,217 chunks |
| `cv` | The author's CV, LinkedIn profile and biography (English and Spanish) | 162 chunks |
| `about` | This project itself: this README, the documentation in `docs/` (English and Spanish) and the source code in `src/` | ~3,000 chunks |

The base language model is **Qwen3-0.6B**, the model of the original 42 project, so the results stay comparable with other 42 RAGs. Larger models are optional profiles: Qwen3-1.7B and Qwen3-4B from the same family, and IBM Granite 4.0 Micro from another one.

The project was rebuilt phase by phase, and every change was measured before it was kept. The full history, with the numbers, is in [`docs/`](docs/).

**Live demo:** *coming soon*. <!-- TODO: link once deployed -->

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
| Router, no filter | Questions sent to their own domain | 42: 99–100% · XQuAD: ~98% · CV: 90–93% · about: 89% (EN) · 94% (ES) |

### Agent vs direct RAG

Twelve conversations of 2–3 turns, where the follow-up questions only make sense with the earlier turns ("And in which year?"). The table shows how often the answer contains the right fact:

| Model | Follow-ups, agent | Follow-ups, direct |
|---|---|---|
| Qwen3-0.6B | **0.78** | 0.33 |
| Qwen3-1.7B | 0.83 | 0.33 |
| Qwen3-4B | **1.00** | 0.39 |

On single, self-contained questions the agent stays within ±0.04 of the direct pipeline with every model. (Phi-4-mini was also measured, 0.78 / 0.33, and later dropped: see [Models](#models).)

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
- **Answer form:** a loop detector stops the generation when the model starts repeating lines, sentences or whole blocks, and the repeated part is cut. Answers that copy the prompt back are cleaned. The web allows up to 1,024 new tokens, only as a safety net.

### Models

- **Qwen3-0.6B:** the base, the 42 model. Benchmarks, the CLI and the comparisons with other 42 RAGs use it.
- **Qwen3-1.7B:** the default model of the web.
- **Qwen3-4B:** CLI and benchmarks. It was in the web for a while (with the retrieval moved to the CPU to fit in a 12 GB GPU, and without the agent); IBM Granite replaced it there in Phase 8.
- **IBM Granite 4.0 Micro** (`ibm-granite/granite-4.0-micro`, 3B, Apache 2.0): added in Phase 8 as a model from another family. Answer quality at the level of Qwen3-4B, a good agent, and it fits in the GPU with the agent on; it is the slowest model of the web. It has one extra CV rule of its own, so that it never presents the public Gmail address as another address ([`docs/changelog/FASE_8.md`](docs/changelog/FASE_8.md)).

Phi-4-mini was an option from another family until Phase 7; it was dropped because its answers copied the sources back and fell into long loops, and the fixes it needed were patches that only served it ([`docs/decisions.md`](docs/decisions.md), DEC-32).

### Agent and MCP

- **The agent is the default path in the CLI**, as in production RAG systems. In the web it is opt-in for now (marked as work in progress), because with small models its conversation memory can mix in earlier topics.
  - It keeps a **session-only memory** of the conversation (nothing is stored).
  - It rewrites follow-up questions into complete ones and searches with **native tool calls** (Qwen's `<tool_call>` format, or a prompt format for models without one). Up to 3 searches per question.
  - **Safety nets:** if the rewrite finds nothing, it searches the original question; if the model's domain choice finds nothing, it retries within the user's filter, never outside it. A deterministic fallback covers models that do not call the tool.
  - The final answer uses the same generator and domain rules as the direct path.
- **MCP server** (`make mcp`): the RAG exposed as `list_domains`, `search` and `answer` tools, over stdio or streamable HTTP, for any MCP client.

---

## Web interface

FastAPI backend and React (Vite + TypeScript) frontend, in the visual style of the original Streamlit app:

- **Chat** with streaming answers. Only the conversation scrolls, and a **Stop** button really stops the generation on the server.
- **Domain filters** (`vllm`, `xquad`, `cv`; `about` is always on), an **agent / direct** switch (direct by default; the agent is a work in progress), and pickers for the **model** (Qwen3-1.7B by default, Qwen3-0.6B and IBM Granite 4.0 Micro) and the **depth** (how many sources the LLM reads: 3, 5 or 10).
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

Optional models: `PROFILE=llm-qwen3-1.7b` (or `llm-qwen3-4b`) for the CLI. In the web, use the model picker.

### Benchmarks

```bash
make bench                     # official 42 recall (docs and code)
make bench SUITE=xquad         # other suites: xquad, cv, en, es, about
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

**For now, the web is served from the author's own computer** (an RTX 3080 Ti) through a tunnel, as a stopgap: `make api-public` limits the server to 4 questions at a time, and the API only listens on `127.0.0.1`, so it is reachable only through the tunnel. The tunnel is Tailscale Funnel: Cloudflare's free quick tunnels do not support the streaming the chat needs, and a fixed Cloudflare URL needs a paid domain. Guide, in Spanish: [`deploy/local/README.md`](deploy/local/README.md).

The planned free server, apart from the author's other cloud projects:
- **Server:** an **Oracle Cloud Always Free** ARM machine (2 OCPU, 12 GB) with Docker. It runs the API and the built web, behind Caddy for HTTPS. The plan was a Hugging Face Space, but since July 2026 Docker Spaces need a paid plan.
- **Frontend:** served by the same container, or optionally from GitHub Pages.
- **Index:** built on a local GPU and copied to the machine as a bundle (Qdrant snapshots and BM25 files, checked with SHA256). It is never published, because it holds the raw CV material.

`make bundle`, `make space-build` and `make space-run` reproduce the image locally (it is still built from `deploy/space/`). The step-by-step guide, in Spanish, is in [`deploy/README.md`](deploy/README.md).

Measured with the container limited to 2 CPUs and 12 GB: 5.0 GB of RAM at peak, and 23–37 s per answer on x86, streamed as it is written. The speed on Oracle's ARM CPUs is not measured yet.

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
deploy/         server image (deploy/space), Oracle setup (deploy/oracle) and local serving with a tunnel (deploy/local)
bench/          versioned datasets and every benchmark result
docs/           roadmap, phase changelogs, benchmark report, decisions (English)
docs/es/        the same documents in Spanish, the working version, plus this README
rag.toml        configuration: sources, models and optional profiles
```

Every pipeline piece (chunker, embeddings, reranker, LLM, agent on or off) is chosen through `rag.toml`, environment variables or a profile, not through code.

---

## Documentation

- [`docs/ROADMAP.md`](docs/ROADMAP.md): the plan and status of every phase, and the dated log of decisions.
- [`docs/BENCHMARK_REPORT.md`](docs/BENCHMARK_REPORT.md): embeddings, rerankers, LLMs, domains and the agent, compared with numbers.
- [`docs/changelog/`](docs/changelog/): what changed in each phase, why, and what it affects.
- [`docs/decisions.md`](docs/decisions.md): decisions taken along the way, with the options considered.

The documents were written in Spanish while the project was built; the originals are in [`docs/es/`](docs/es/), and the English versions are updated at the end of each phase. Spanish version of this README: [`docs/es/README.md`](docs/es/README.md).

---

## Credits

- **vLLM** documentation and code (Apache-2.0), the 42 benchmark corpus.
- **XQuAD** (Google, CC-BY-SA 4.0), based on Wikipedia.
- Models: [Qwen3](https://huggingface.co/Qwen), [BAAI/bge-m3](https://huggingface.co/BAAI/bge-m3), [cross-encoder/mmarco-mMiniLMv2-L12-H384-v1](https://huggingface.co/cross-encoder/mmarco-mMiniLMv2-L12-H384-v1).
- Tools: Qdrant, bm25s, sentence-transformers, Docling, FastAPI, React, Vite, the MCP Python SDK, uv and Python Fire.

### AI usage

Version 2.0 was updated together with Claude (Anthropic), and reviewed and designed by hand by Chrystian. The project rules are in [`docs/es/PLANING.md`](docs/es/PLANING.md) (in Spanish): measure every change, document every phase, and leave every decision to the author.

---

## License

The project's own code and documentation are released under the [MIT License](LICENSE). Third-party content in this repository keeps its own terms:
- **`bench/datasets/xquad/`:** derived from XQuAD, under CC-BY-SA 4.0 (see its README).
- **`bench/datasets/public/`:** the public datasets of the 42 project. **`bench/datasets/en/` and `bench/datasets/es/`:** a subset of their questions, and its Spanish translation. Not covered by the MIT License.
- **`llm_sdk/`:** the course SDK provided by 42. Not covered by the MIT License.
- **The indexed corpora** (vLLM, Wikipedia via XQuAD) are downloaded by `make data`, not stored in the repository, and keep their licenses (Apache-2.0 and CC-BY-SA 4.0).

---

**Author:** Chrystian Donaire Villén · [cdonairevillen@gmail.com](mailto:cdonairevillen@gmail.com)
