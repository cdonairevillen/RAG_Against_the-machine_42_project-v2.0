"""HTTP API of the RAG (Phase 6): what the React web talks to.

Endpoints:
    GET  /health                 liveness and whether the models are loaded
    GET  /config                 model, domains and defaults
    POST /chat                   answer a message, streamed as SSE
    POST /chat/reset             forget a session's conversation
    POST /search                 sources for a query (no generation)
    GET  /sources/{chunk_id}     full (masked) text of a source
    GET  /metrics                latest benchmark numbers for the web

/chat takes the web's controls: `agent` (off by default since Phase 7;
the CLI keeps the agent by default, D7), `domains`, the domain filters
(omitted: every domain; an empty list: every filter off, answered with
NO_FILTER_MESSAGE without searching), `model` (an LLM from the rag.toml
profiles, see ModelPool) and `depth` (sources given to the LLM; None
keeps each domain's default). Conversations live in memory only, per
session id, capped and expired (D7: nothing about visitors is stored).

Run: make api   (uvicorn on http://127.0.0.1:8000)
"""
import gc
import json
import math
import os
import queue
import threading
import time
import uuid
from collections import OrderedDict
from contextlib import asynccontextmanager, contextmanager
from typing import Any, AsyncIterator, Iterator, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.api.metrics import latest_metrics
from src.config import (
    GenerationConfig, RagConfig, get_config, load_config,
)
from src.rag.language import detect_language

# Sessions kept in memory and idle time before one is forgotten.
MAX_SESSIONS = 500
SESSION_TTL = 30 * 60
# The built React web (make web-build), served at / when present, so a
# single Space can host the whole site.
WEB_DIST = "web/dist"
# Characters of each source shown in the answer (full text: /sources).
PREVIEW_CHARS = 400
XQUAD_CREDIT = "XQuAD (Google), CC-BY-SA 4.0 · Wikipedia"
# Answer when every domain filter is off (in the question's language).
NO_FILTER_MESSAGE = {
    "es": "Activa alguno de los filtros para poder buscar en mi base de "
          "datos.",
    "en": "Turn on at least one of the filters to search my database.",
}


class ChatRequest(BaseModel):
    """A message of the chat."""

    message: str = Field(min_length=1, max_length=1000)
    session_id: Optional[str] = Field(default=None, max_length=64)
    # Direct RAG by default; the agent is opt-in in the web while its
    # conversation memory is being improved (Phase 7b).
    agent: bool = False
    # Domain filters: None = every domain, [] = none (nothing searched).
    domains: Optional[list[str]] = None
    # An id from /config "models" (None: the default model).
    model: Optional[str] = Field(default=None, max_length=64)
    # Sources given to the LLM (None: each domain's own, rag.toml).
    depth: Optional[int] = Field(default=None, ge=1, le=10)
    k: int = Field(default=5, ge=1, le=10)


class SearchRequest(BaseModel):
    """A search without generation."""

    query: str = Field(min_length=1, max_length=1000)
    domains: Optional[list[str]] = None
    k: int = Field(default=5, ge=1, le=10)


class ResetRequest(BaseModel):
    """Forget a conversation."""

    session_id: str = Field(max_length=64)


# The web's agent switch starts off (changed 2026-10-24: with small
# models the memory mixes earlier topics in; see FASE_7.md).
AGENT_DEFAULT = False

# Depth options of the web. 5 by default: the k that 42 evaluates.
DEPTHS = [3, 5, 10]
DEPTH_DEFAULT = 5


def model_label(name: str) -> str:
    """Short model name: Qwen/Qwen3-0.6B -> Qwen3-0.6B."""
    return name.rsplit("/", 1)[-1]


def parse_max_tokens(value: str, models: list[str]) -> dict[str, int]:
    """Per-model token caps from "512" (every model) or
    "default=512,llm-phi4-mini=640" (unknown ids are ignored)."""
    value = value.strip()
    if not value:
        return {}
    if "=" not in value:
        return {model: int(value) for model in models}
    caps = {}
    for item in value.split(","):
        model, _, cap = item.partition("=")
        if model.strip() in models:
            caps[model.strip()] = int(cap)
    return caps


class ModelPool:
    """The LLMs the web can choose: the base plus the rag.toml profiles
    that change the generator (llm-*).

    Models load on first use and at most max_loaded stay in memory (1
    by default: a free CPU Space or a 12 GB GPU does not hold them all);
    loading another one unloads the least recently used.

    Environment:
        RAG_API_MODELS: comma-separated ids to offer (default: all).
        RAG_API_MAX_LOADED: models kept loaded at once (default 1).
        RAG_API_MAX_TOKENS: answer length cap, one number for every model
            or per model ("default=512,llm-phi4-mini=640"); models not
            listed keep their configuration's max_new_tokens.
    """

    def __init__(self, config: RagConfig) -> None:
        self.options: "OrderedDict[str, GenerationConfig]" = OrderedDict()
        self.options["default"] = config.generation
        # The Qwen3 family first (the project's base), then the others.
        llm_profiles = sorted(
            (p for p in config.available_profiles if p.startswith("llm-")),
            key=lambda p: ("qwen" not in p, p))
        for profile in llm_profiles:
            self.options[profile] = load_config(profile=profile).generation
        wanted = [m.strip() for m in os.environ.get(
            "RAG_API_MODELS", "").split(",") if m.strip()]
        if wanted:
            self.options = OrderedDict(
                (k, v) for k, v in self.options.items()
                if k in wanted or k == "default")
        caps = parse_max_tokens(os.environ.get("RAG_API_MAX_TOKENS", ""),
                                list(self.options))
        for key, cap in caps.items():
            self.options[key] = self.options[key].model_copy(
                update={"max_new_tokens": cap})
        self.max_loaded = max(1, int(os.environ.get(
            "RAG_API_MAX_LOADED", "1")))
        self.loaded: "OrderedDict[str, Any]" = OrderedDict()

    def describe(self) -> list[dict[str, Any]]:
        """The options as /config shows them."""
        return [{"id": key, "label": model_label(gen.model),
                 "model": gen.model, "loaded": key in self.loaded}
                for key, gen in self.options.items()]

    def resolve(self, model: Optional[str]) -> str:
        """A valid model id (unknown ids fall back to the default)."""
        return model if model and model in self.options else "default"

    def get(self, model: str) -> Any:
        """The model's Generator, loading it (and unloading the least
        recently used one beyond max_loaded)."""
        if model in self.loaded:
            self.loaded.move_to_end(model)
            return self.loaded[model]
        previous = next(reversed(self.loaded), None)
        while len(self.loaded) >= self.max_loaded:
            self.loaded.popitem(last=False)
            free_memory()
        from src.rag.generator import Generator

        error = ""
        try:
            self.loaded[model] = Generator(self.options[model])
        except Exception as exc:
            # Usually memory: on a GPU that cannot hold it, llm_sdk
            # offloads part of the model and then fails to move it.
            error = str(exc)
        if not error:
            return self.loaded[model]
        # Outside the except block: the exception (and the half-loaded
        # model its traceback holds) is gone, so the memory is freed.
        free_memory()
        if previous is not None and previous != model:
            try:
                self.get(previous)
            except RuntimeError:
                pass
        label = model_label(self.options[model].model)
        raise RuntimeError(
            f"{label} could not be loaded on this machine (not enough "
            f"memory?). Pick another model. Details: {error}")


def free_memory() -> None:
    """Release an unloaded model's memory (and the GPU cache)."""
    gc.collect()
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except ImportError:
        pass


class RagService:
    """The loaded RAG (router, tools, generator) and the chat sessions.

    One model is loaded for the whole process; generation is serialised
    with a lock (a single LLM on a CPU Space cannot run two at once).
    """

    def __init__(self, config: RagConfig) -> None:
        self.config = config
        self.tools: Any = None
        self.models = ModelPool(config)
        self.sessions: "OrderedDict[str, tuple[Any, float]]" = OrderedDict()
        self.lock = threading.Lock()
        self.load_lock = threading.Lock()

    def load(self) -> Any:
        """Load the RAG on first use (or at startup)."""
        with self.load_lock:
            if self.tools is None:
                from src.server.tools import RagTools

                # RAG_API_DOMAINS: the domains the web serves (default:
                # every indexed one), to keep one out until it is ready.
                domains = [d.strip() for d in os.environ.get(
                    "RAG_API_DOMAINS", "").split(",") if d.strip()]
                tools = RagTools.load(self.config, domains=domains or None)
                self.models.get("default")
                self.tools = tools
        return self.tools

    def generator_for(self, model: str) -> Any:
        """The chosen model's Generator.

        Before loading another model, every session's agent drops its
        LLM (each gets the current one on its next question): a model
        an agent still points to cannot be freed, and the new one would
        have to fit next to it (Qwen3-1.7B did not, on a 12 GB GPU).
        """
        if model not in self.models.loaded:
            for agent, _ in self.sessions.values():
                agent.generator = None
        return self.models.get(model)

    def pipeline_for(self, model: str) -> Any:
        """The direct answer flow with the chosen model."""
        from src.rag.pipeline import RagPipeline

        tools = self.load()
        return RagPipeline(tools.router, self.generator_for(model),
                           tools.rules)

    @contextmanager
    def depth(self, depth: Optional[int]) -> Iterator[None]:
        """Give the LLM `depth` sources in every domain for one request.

        Each domain's answer_k (rag.toml) is replaced while the request
        runs (requests are serialised by the lock) and restored after:
        the search code and its benchmarks are not touched.
        """
        retrievers = list(self.load().router.retrievers.values())
        saved = [r.answer_k for r in retrievers]
        if depth is not None:
            for retriever in retrievers:
                retriever.answer_k = depth
        try:
            yield
        finally:
            for retriever, answer_k in zip(retrievers, saved):
                retriever.answer_k = answer_k

    def agent_for(self, session_id: str, model: str = "default") -> Any:
        """The session's agent (its memory), created on first use, with
        the chosen model."""
        from src.agent.agent import Agent

        generator = self.generator_for(model)
        now = time.time()
        for sid, (_, seen) in list(self.sessions.items()):
            if now - seen > SESSION_TTL:
                del self.sessions[sid]
        if session_id in self.sessions:
            agent, _ = self.sessions.pop(session_id)
            agent.generator = generator
        else:
            agent = Agent(self.load(), generator=generator)
        self.sessions[session_id] = (agent, now)
        while len(self.sessions) > MAX_SESSIONS:
            self.sessions.popitem(last=False)
        return agent

    def reset(self, session_id: str) -> None:
        """Forget a session."""
        self.sessions.pop(session_id, None)

    def domains_for(self, request: ChatRequest) -> Optional[list[str]]:
        """The domain filter of a request: None for every domain, [] when
        every filter is off (unknown domains are ignored). Pinned domains
        (rag.toml `pinned`) join every filter."""
        if request.domains is None:
            return None
        loaded = self.load().router.domains
        wanted = [d for d in request.domains if d in loaded]
        return wanted + [d for d in loaded if d not in wanted
                         and self.config.sources[d].pinned]

    def describe_sources(self, sources: list[Any]) -> list[dict[str, Any]]:
        """Sources as the web shows them (masked previews and credits)."""
        tools = self.load()
        parents = tools.router.get_parent_chunk_map()
        items = []
        for i, src in enumerate(sources, 1):
            parent = parents.get((src.file_path, src.first_character_index))
            text = tools.rules.redact(parent.text, parent.domain) \
                if parent else ""
            domain = parent.domain if parent else ""
            items.append({
                "index": i,
                "id": parent.id if parent else None,
                "domain": domain,
                "file_path": src.file_path,
                "title": short_path(src.file_path),
                "first_character_index": src.first_character_index,
                "last_character_index": src.last_character_index,
                "preview": text[:PREVIEW_CHARS],
                "credit": XQUAD_CREDIT if domain == "xquad" else None,
            })
        return items

    def retrievals(self, answered: Optional[str],
                   used: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Every searched domain's results of the last search, best first.

        The answered domain shows the sources the answer used (their
        indices match its [n] citations); the others, what they found.
        """
        out = []
        for domain, score, sources in self.load().router.last_ranked:
            is_used = domain == answered and bool(used)
            out.append({
                "domain": domain,
                "score": round(score, 2) if math.isfinite(score) else None,
                "used": is_used,
                "sources": used if is_used
                else self.describe_sources(sources),
            })
        if used and not any(r["used"] for r in out):
            # The agent answered from an earlier search than the last.
            out.insert(0, {"domain": answered, "score": None,
                           "used": True, "sources": used})
        return out

    def chat(self, request: ChatRequest, on_piece: Any,
             cancel: Optional[threading.Event] = None) -> dict[str, Any]:
        """Answer one message (blocking); pieces go to on_piece.

        Setting `cancel` stops the generation (the web's Stop button or
        a closed tab): the answer keeps what was written so far.
        """
        cancel = cancel or threading.Event()
        session_id = request.session_id or uuid.uuid4().hex
        domains = self.domains_for(request)
        if domains == []:
            language = detect_language(request.message)
            text = NO_FILTER_MESSAGE.get(language, NO_FILTER_MESSAGE["en"])
            on_piece(text)
            return {"session_id": session_id, "answer": text,
                    "not_found": True, "domain": None, "sources": [],
                    "retrievals": [], "trace": {"mode": "no-filter"}}
        model = self.models.resolve(request.model)
        with self.lock, self.depth(request.depth):
            if cancel.is_set():
                # Stopped while waiting for its turn: nothing to do.
                return {"session_id": session_id, "answer": "",
                        "not_found": True, "domain": None, "sources": [],
                        "retrievals": [], "trace": {"mode": "stopped"}}
            if request.agent:
                agent = self.agent_for(session_id, model)
                generator = agent.generator
                generator.cancel = cancel
                answer = agent.ask(request.message, domains,
                                   on_piece=on_piece)
                trace = {"mode": "agent", "queries": answer.queries,
                         "model": model_label(agent.generator.model_name),
                         "steps": answer.steps,
                         "fallback": answer.fallback,
                         "retries": answer.retries}
                text, sources = answer.text, answer.sources
                not_found, domain = answer.not_found, answer.domain
            else:
                pipeline = self.pipeline_for(model)
                generator = pipeline.generator
                generator.cancel = cancel
                result = pipeline.answer(request.message, k=request.k,
                                         domains=domains,
                                         on_piece=on_piece)
                # A single domain is not scored (NaN): null in JSON.
                route = [
                    (d, round(score, 2) if math.isfinite(score) else None)
                    for d, score in pipeline.retriever.last_route]
                trace = {"mode": "direct", "route": route,
                         "model": model_label(pipeline.generator.model_name)}
                text, sources = result.text, result.sources
                not_found = result.not_found
                domain = pipeline.answered_domain()
            used = [] if not_found else self.describe_sources(sources)
            retrievals = self.retrievals(domain, used)
            if cancel.is_set():
                trace["stopped"] = True
            elif not not_found and reached_limit(text, generator):
                text = trim_to_sentence(text)
                trace["cut"] = True
        return {
            "session_id": session_id, "answer": text,
            "not_found": not_found, "domain": domain,
            "sources": used, "retrievals": retrievals, "trace": trace,
        }

    def source(self, chunk_id: str) -> dict[str, Any]:
        """Full masked text of a parent chunk, by its stable id."""
        tools = self.load()
        for retriever in tools.router.retrievers.values():
            parent = retriever.parent_by_id.get(chunk_id)
            if parent is not None:
                return {
                    "id": chunk_id, "domain": parent.domain,
                    "file_path": parent.file_path,
                    "title": short_path(parent.file_path),
                    "first_character_index": parent.first_character_index,
                    "last_character_index": parent.last_character_index,
                    "text": tools.rules.redact(parent.text, parent.domain),
                    "credit": XQUAD_CREDIT if parent.domain == "xquad"
                    else None,
                }
        raise KeyError(chunk_id)


def reached_limit(text: str, generator: Any) -> bool:
    """Whether an answer used (nearly) all of max_new_tokens."""
    tokens = len(generator.tokenizer.encode(text))
    return tokens >= int(generator.max_new_tokens * 0.95)


def trim_to_sentence(text: str) -> str:
    """Cut an answer that hit the token limit at its last complete
    sentence (if one ends past half of it), marked with an ellipsis."""
    end = max(text.rfind(mark) for mark in (". ", ".\n", "! ", "? ",
                                            "]\n", ".)"))
    if end > len(text) // 2:
        text = text[:end + 1].rstrip()
    if text.count("```") % 2:
        text += "\n```"
    return text + " …"


def short_path(file_path: str) -> str:
    """A file path without the data/raw/<source>/ prefix."""
    parts = file_path.split("/")
    return "/".join(parts[3:]) if file_path.startswith("data/raw/") \
        and len(parts) > 3 else file_path


def sse(event: str, data: Any) -> str:
    """One Server-Sent Events message."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def create_app(config: Optional[RagConfig] = None,
               preload: bool = True) -> FastAPI:
    """Build the API (preload=False: models load on the first request)."""
    config = config or get_config()
    service = RagService(config)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        if preload:
            # Load the models in the background: /health answers at once
            # and reports when they are ready.
            threading.Thread(target=service.load, daemon=True).start()
        yield

    app = FastAPI(title="RAG against the Machine", version="2.0",
                  lifespan=lifespan)
    # The web is served from another origin (GitHub Pages).
    origins = [o.strip() for o in os.environ.get(
        "RAG_ALLOWED_ORIGINS", "*").split(",") if o.strip()]
    app.add_middleware(CORSMiddleware, allow_origins=origins,
                       allow_methods=["GET", "POST"],
                       allow_headers=["Content-Type"])
    app.state.service = service

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {"status": "ok", "loaded": service.tools is not None}

    @app.get("/config")
    def get_settings() -> dict[str, Any]:
        tools = service.load()
        return {
            "model": config.generation.model,
            "profile": config.profile,
            "domains": [
                {**d, "pinned": config.sources[d["name"]].pinned}
                for d in tools.list_domains()
            ],
            "models": service.models.describe(),
            "depths": DEPTHS,
            "depth_default": DEPTH_DEFAULT,
            "agent_default": AGENT_DEFAULT,
            "k": 5,
        }

    @app.post("/chat")
    def chat(request: ChatRequest) -> StreamingResponse:
        pieces: "queue.Queue[tuple[str, Any]]" = queue.Queue()
        # Sent first, so a conversation stopped before its first answer
        # ends still keeps its session (and memory).
        request.session_id = request.session_id or uuid.uuid4().hex
        pieces.put(("start", {"session_id": request.session_id}))
        cancel = threading.Event()

        def work() -> None:
            try:
                result = service.chat(
                    request, lambda p: pieces.put(("token", p)), cancel
                )
                pieces.put(("done", result))
            except Exception as exc:  # reported to the client
                pieces.put(("error", {"detail": str(exc)}))

        threading.Thread(target=work, daemon=True).start()

        def stream() -> Iterator[str]:
            finished = False
            try:
                while True:
                    event, data = pieces.get()
                    yield sse(event, data)
                    if event in ("done", "error"):
                        finished = True
                        return
            finally:
                # The client left (Stop button, closed tab): stop the
                # generation instead of blocking the next visitor.
                if not finished:
                    cancel.set()

        return StreamingResponse(stream(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache"})

    @app.post("/chat/reset")
    def reset(request: ResetRequest) -> dict[str, str]:
        service.reset(request.session_id)
        return {"status": "reset"}

    @app.post("/search")
    def search(request: SearchRequest) -> dict[str, Any]:
        result: dict[str, Any] = service.load().search(
            request.query, request.domains or None, request.k
        )
        return result

    @app.get("/sources/{chunk_id}")
    def source(chunk_id: str) -> dict[str, Any]:
        try:
            return service.source(chunk_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="Unknown source")

    @app.get("/metrics")
    def metrics() -> dict[str, Any]:
        return latest_metrics()

    if os.path.isdir(WEB_DIST):
        from fastapi.staticfiles import StaticFiles

        # Last: the API routes above take precedence over the files.
        app.mount("/", StaticFiles(directory=WEB_DIST, html=True),
                  name="web")
    return app
