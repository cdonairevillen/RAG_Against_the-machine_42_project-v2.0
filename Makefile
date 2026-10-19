PY        := python
UV        := uv
ARGS      ?=
VENV      := .venv
LABEL     ?= run

VLLM_DIR  := data/raw/vllm-0.10.1
VLLM_URL  := https://github.com/vllm-project/vllm/archive/refs/tags/v0.10.1.zip
URL_42    := https://cdn.intra.42.fr/document/document
DATASETS  := data/datasets
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

install: data
	@echo "Creating Virtual Environment and installing dependencies"
ifneq ($(BASE),)
	@mkdir -p $(BASE) $(CACHE) $(TMP) $(HF)
endif
	@mkdir -p .streamlit
	@printf '[server]\nfileWatcherType = "none"\n\n[browser]\ngatherUsageStats = false\n' > .streamlit/config.toml
	$(ENV) $(UV) venv $(VENV)
	$(ENV) $(UV) sync

# vLLM 0.10.1 from the official GitHub tag (same files and offsets as the
# 42 attachment). The public datasets are versioned in data/datasets.
data:
	@mkdir -p data/raw data/processed data/output
	@if [ ! -d "$(VLLM_DIR)" ]; then \
		echo "Downloading vLLM 0.10.1 from GitHub..."; \
		curl -fL -o vllm-0.10.1.zip $(VLLM_URL) && \
		unzip -q vllm-0.10.1.zip -d data/raw && \
		rm -f vllm-0.10.1.zip; \
	else \
		echo "vLLM already present at $(VLLM_DIR)"; \
	fi

# Original 42 download. Needs access to the intra CDN and replaces the
# versioned datasets with the ones from the attachment.
data-42:
	@mkdir -p data/raw data/processed data/output $(DATASETS)
	curl -fL -o datasets_public.zip $(URL_42)/54681/datasets_public.zip
	curl -fL -o vllm-0.10.1.zip $(URL_42)/54683/vllm-0.10.1.zip
	@unzip -q -o datasets_public.zip
	@rm -rf $(VLLM_DIR)
	@unzip -q vllm-0.10.1.zip -d data/raw
	@rm -rf $(DATASETS)/AnsweredQuestions $(DATASETS)/UnansweredQuestions
	@mv datasets_public/public/AnsweredQuestions $(DATASETS)
	@mv datasets_public/public/UnansweredQuestions $(DATASETS)
	@rm -rf datasets_public datasets_public.zip vllm-0.10.1.zip

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

index: db-up
	$(RUN) index --max_chunk_size 2000

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

bench: db-up
	$(RUN) bench --label $(LABEL) --mode smart

gen-bench: db-up
	$(RUN) gen_bench --label $(LABEL)

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

.PHONY: install data data-42 db-up db-down db-reset run web web-stop index search-docs search-code \
        eval-docs eval-code bench gen-bench test lint clean meme
