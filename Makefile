PY        := python
UV        := uv
ARGS      ?=
VENV      := .venv
LABEL     ?= run

VLLM_DIR  := data/raw/vllm-0.10.1
VLLM_URL  := https://github.com/vllm-project/vllm/archive/refs/tags/v0.10.1.zip
DATASETS  := bench/datasets/public
SEARCH    := data/output/search_results

# On 42 clusters the home quota is tiny: redirect every cache to goinfre.
# Elsewhere the default user caches are kept (no re-download of models).
# Detected by the shell that runs the recipes; force with ON_42=yes|no.
ON_42     ?= $(shell sh -c 'test -d /goinfre && echo yes')
ifeq ($(ON_42),yes)
BASE      := /goinfre/$(shell whoami)/rag_cache
CACHE     := $(BASE)/uv_cache
TMP       := $(BASE)/tmp
HF        := $(BASE)/hf_cache
ENV       := HF_HOME=$(HF) \
			 TRANSFORMERS_CACHE=$(HF) \
			 HF_DATASETS_CACHE=$(HF) \
			 UV_CACHE_DIR=$(CACHE) \
			 TMPDIR=$(TMP)
else
BASE      :=
ENV       :=
endif

# Optional profile from rag.toml (extra models), e.g. PROFILE=gpu-quality.
PROFILE   ?=
RUN       := $(ENV) $(if $(PROFILE),RAG_PROFILE=$(PROFILE)) $(UV) run --project . $(PY) -m src

# Virtual environment, dependencies and every public data source (data
# runs after the venv: XQuAD is prepared with Python).
install:
	@echo "Creating Virtual Environment and installing dependencies"
ifneq ($(BASE),)
	@mkdir -p $(BASE) $(CACHE) $(TMP) $(HF)
endif
	@mkdir -p .streamlit
	@printf '[server]\nfileWatcherType = "none"\n\n[browser]\ngatherUsageStats = false\n' > .streamlit/config.toml
	$(ENV) $(UV) venv $(VENV)
	$(ENV) $(UV) sync
	@$(MAKE) --no-print-directory data

# Every public source in one go: vLLM (the 42 benchmark corpus) and XQuAD.
# Not included: the CV (private material, data/raw/cv/) and Gulliver
# (Phase 4c, postponed).
data: data-vllm data-xquad

# vLLM 0.10.1 from the official GitHub tag: the only vLLM download (the
# 42 attachment had the same files and offsets, checked in Phase 0). The
# public 42 datasets are versioned in bench/datasets/public.
data-vllm:
	@mkdir -p data/raw data/processed data/output
	@if [ ! -d "$(VLLM_DIR)" ]; then \
		echo "Downloading vLLM 0.10.1 from GitHub..."; \
		curl -fL -o vllm-0.10.1.zip $(VLLM_URL) && \
		unzip -q vllm-0.10.1.zip -d data/raw && \
		rm -f vllm-0.10.1.zip; \
	else \
		echo "vLLM already present at $(VLLM_DIR)"; \
	fi

# XQuAD en/es (Phase 4a): pinned Hugging Face + GitHub files (SHA256),
# turned into data/raw/xquad/ and bench/datasets/xquad/.
data-xquad:
	$(RUN) fetch_xquad

# Qdrant server (docker-compose.yml). Data lives in a named Docker volume.
db-up:
	@docker compose up -d --quiet-pull qdrant >/dev/null 2>&1
	@sh -c 'for i in $$(seq 1 30); do curl -sf localhost:6333/readyz >/dev/null && exit 0; sleep 1; done; echo "Qdrant did not start"; exit 1'

db-down:
	docker compose down

db-reset:
	docker compose down -v

run:
	$(RUN) $(ARGS)

web: db-up
	$(ENV) $(UV) run --project . $(PY) -m streamlit run src/web.py &
	@echo "Web running at http://localhost:8501"

web-stop:
	@echo "Closing web."
	@pkill -f "streamlit run" || true

# ── Phase 6: API + React web + deployment ───────────────────────────────
# API (FastAPI) on http://127.0.0.1:8000; it also serves web/dist if built.
# API_MODELS: the LLMs the web offers (rag.toml profiles). Qwen3-4B is left
# out: with retrieval on the GPU it does not fit in 12 GB (measured).
API_MODELS ?= default,llm-qwen3-1.7b,llm-phi4-mini
# Answer length cap in the web (rag.toml keeps 150 so gen-bench stays
# comparable). A safety net only: generation loops stop by themselves
# (src/rag/loops.py), and the longest legit answer measured was 464
# tokens. Capped answers are trimmed at their last sentence, and the
# Stop button cuts any of them. One number for every model, or per model
# ("default=1024,llm-phi4-mini=640").
API_MAX_TOKENS ?= 1024
# API_DOMAINS: the domains the web serves (empty: every indexed one).
API_DOMAINS ?=
api: db-up
	RAG_API_DOMAINS=$(API_DOMAINS) RAG_API_MODELS=$(API_MODELS) RAG_API_MAX_TOKENS=$(API_MAX_TOKENS) \
		$(ENV) $(UV) run --project . $(PY) -m src.api

# React web in development (Vite, http://localhost:5173, talks to make api).
web-dev:
	cd web && npm install && npm run dev

web-build:
	cd web && npm ci && npm run build

# Prebuilt index for the deployment (Qdrant snapshots + BM25), git-ignored:
# it holds raw CV text and must stay private (docs/decisions.md).
BUNDLE    ?= deploy/bundle
bundle: db-up
	$(RUN) bundle_export --out_dir $(BUNDLE)

# Hugging Face Space image, and a local run of it with the bundle mounted
# (http://localhost:7860, same as the Space).
SPACE_IMAGE ?= rag-space
space-build: web-build
	docker build -f deploy/space/Dockerfile -t $(SPACE_IMAGE) .

space-run:
	docker run --rm -p 7860:7860 -v "$(CURDIR)/$(BUNDLE):/home/user/app/bundle:ro" $(SPACE_IMAGE)

# The code the server builds (Dockerfile at the root): deploy/stage/
# mirrors the paths the Dockerfile copies, plus deploy/oracle/ (Caddy +
# compose). Copied to the Oracle VM (deploy/README.md) or pushed to a
# Space's git. No data and no bundle inside.
STAGE     := deploy/stage
space-stage: web-build
	@rm -rf $(STAGE) && mkdir -p $(STAGE)/deploy/space $(STAGE)/deploy/oracle $(STAGE)/bench $(STAGE)/web
	@cp -r src llm_sdk rag.toml pyproject.toml uv.lock $(STAGE)/
	@cp -r bench/results $(STAGE)/bench/
	@cp -r web/dist $(STAGE)/web/
	@cp deploy/space/entrypoint.sh $(STAGE)/deploy/space/
	@cp deploy/oracle/compose.yml deploy/oracle/Caddyfile deploy/oracle/.env.example $(STAGE)/deploy/oracle/
	@cp deploy/space/Dockerfile $(STAGE)/Dockerfile
	@cp deploy/space/README.md $(STAGE)/README.md
	@cp LICENSE $(STAGE)/LICENSE
	@find $(STAGE) -name "__pycache__" -type d -exec rm -rf {} +
	@echo "Space content ready in $(STAGE)"

# Every source in rag.toml, or only one with SOURCE=<name>.
SOURCE    ?=
index: db-up
	$(RUN) index --max_chunk_size 2000 $(if $(SOURCE),--source $(SOURCE))

search-docs: db-up
	$(RUN) search_dataset \
		--dataset_path $(DATASETS)/UnansweredQuestions/dataset_docs_public.json \
		--save_directory $(SEARCH)

search-code: db-up
	$(RUN) search_dataset \
		--dataset_path $(DATASETS)/UnansweredQuestions/dataset_code_public.json \
		--save_directory $(SEARCH)

eval-docs:
	$(RUN) evaluate \
		--student_answer_path $(SEARCH)/dataset_docs_public.json \
		--dataset_path $(DATASETS)/AnsweredQuestions/dataset_docs_public.json \
		--k 10

eval-code:
	$(RUN) evaluate \
		--student_answer_path $(SEARCH)/dataset_code_public.json \
		--dataset_path $(DATASETS)/AnsweredQuestions/dataset_code_public.json \
		--k 10

# Optional benchmark suite, e.g. SUITE=xquad.
SUITE     ?=
bench: db-up
	$(RUN) bench --label $(LABEL) $(if $(SUITE),--suite $(SUITE))

# The RAG as an MCP server (Phase 5): stdio for MCP clients that launch
# it, or MCP_TRANSPORT=streamable-http on http://127.0.0.1:$(MCP_PORT)/mcp.
MCP_TRANSPORT ?= stdio
MCP_PORT  ?= 8765
mcp: db-up
	$(RUN) mcp --transport $(MCP_TRANSPORT) --port $(MCP_PORT)

agent-bench: db-up
	$(RUN) agent_bench --label $(LABEL) $(if $(SETS),--sets $(SETS))

route-bench: db-up
	$(RUN) route_bench --label $(LABEL)

gen-bench: db-up
	$(RUN) gen_bench --label $(LABEL) $(if $(SUITE),--suite $(SUITE)) $(if $(FULL),--full)

judge:
	$(RUN) judge --label $(LABEL)

test:
	$(ENV) $(UV) run --project . pytest

lint:
	$(ENV) $(UV) run --project . flake8 src tests
	$(ENV) $(UV) run --project . mypy src \
		--warn-return-any \
		--warn-unused-ignores \
		--ignore-missing-imports \
		--disallow-untyped-defs \
		--check-untyped-defs

clean:
	@echo "Cleaning venv, caches and generated data."
ifneq ($(BASE),)
	@rm -rf $(BASE)
endif
	@rm -rf $(VENV)
	@rm -rf .mypy_cache .pytest_cache
	@rm -rf data/raw data/processed data/output
	@rm -rf .streamlit
	@find . -type d -name "__pycache__" -exec rm -rf {} +

meme:
	@echo "Killing in the name of... bad retrieval scores"
	@xdg-open "https://www.youtube.com/watch?v=bWXazVhlyxQ" 2>/dev/null & true
	@echo "https://www.youtube.com/watch?v=bWXazVhlyxQ"
	$(ENV) $(UV) run --project . $(PY) -m streamlit run src/web.py &
	@echo "Web running at http://localhost:8501"

.PHONY: install data data-vllm data-xquad db-up db-down db-reset run web web-stop index search-docs search-code \
        eval-docs eval-code bench route-bench agent-bench gen-bench judge mcp test lint clean meme \
        api web-dev web-build bundle space-build space-run
