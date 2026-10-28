import json
from typing import Any, Optional

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from src.api.app import create_app, short_path  # noqa: E402
from src.config import RagConfig, SourceConfig  # noqa: E402
from src.models import MinimalSource  # noqa: E402
from src.rag.domain_rules import DomainRules  # noqa: E402
from src.rag.ingestion.chunk import Chunk  # noqa: E402

CONFIG = RagConfig(sources={
    "cv": SourceConfig(root="r", include=[".md"], description="the author",
                       private_data=["phone"]),
    "vllm": SourceConfig(root="r", include=[".md"], description="vLLM"),
})
PARENT = Chunk("call 612345678 now", "data/raw/cv/bio.md", 0, 18, "doc",
               id="p1", domain="cv")


class FakeResult:
    text = "He was born in 1996 [1]."
    sources = [MinimalSource(file_path=PARENT.file_path,
                             first_character_index=0,
                             last_character_index=18)]
    not_found = False


class FakeRouter:
    domains = ["cv", "vllm"]
    last_route = [("cv", float("nan"))]
    last_ranked = [("cv", float("nan"), FakeResult.sources),
                   ("vllm", -4.0, [])]

    def __init__(self) -> None:
        self.retrievers = {"cv": type("R", (), {"parent_by_id": {"p1": PARENT},
                                                "chunks": [PARENT],
                                                "answer_k": 8})()}

    def get_parent_chunk_map(self) -> dict:
        return {(PARENT.file_path, 0): PARENT}


class FakeTokenizer:
    def encode(self, text: str) -> list[str]:
        return text.split()


class FakeGenerator:
    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self.tokenizer = FakeTokenizer()
        self.max_new_tokens = 400


class FakePipeline:
    def __init__(self, router: FakeRouter) -> None:
        self.retriever = router
        self.generator = FakeGenerator("Qwen/Qwen3-0.6B")
        self.calls: list[Any] = []
        self.answer_k: list[Any] = []

    def answer(self, question: str, k: int, domains: Any,
               on_piece: Any) -> FakeResult:
        self.calls.append(domains)
        self.answer_k.append(self.retriever.retrievers["cv"].answer_k)
        on_piece("He was ")
        on_piece("born in 1996 [1].")
        return FakeResult()

    def answered_domain(self) -> str:
        return "cv"


class FakeTools:
    def __init__(self) -> None:
        self.router = FakeRouter()
        self.rules = DomainRules(CONFIG)
        self.pipeline = FakePipeline(self.router)

    def get_pipeline(self) -> FakePipeline:
        return self.pipeline

    def list_domains(self) -> list[dict[str, Any]]:
        return [{"name": "cv", "description": "the author", "chunks": 1}]

    def search(self, query: str, domains: Optional[list[str]],
               k: int) -> dict[str, Any]:
        return {"domain": "cv", "score": 1.0, "sources": []}


@pytest.fixture
def client() -> TestClient:
    app = create_app(CONFIG, preload=False)
    service = app.state.service
    service.tools = FakeTools()
    service.models_used = []

    def pipeline_for(model: str) -> FakePipeline:
        service.models_used.append(model)
        return service.tools.pipeline

    service.pipeline_for = pipeline_for
    return TestClient(app)


def events(response: Any) -> list[tuple[str, Any]]:
    """Parse an SSE body into (event, data) pairs."""
    out = []
    for block in response.text.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines())
        out.append((lines["event"], json.loads(lines["data"])))
    return out


def test_health_and_config(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok", "loaded": True}
    config = client.get("/config").json()
    assert "modes" not in config and config["agent_default"] is False


def test_direct_chat_streams_tokens_then_the_answer(
        client: TestClient) -> None:
    response = client.post("/chat", json={"message": "When was he born?",
                                          "agent": False})
    stream = events(response)
    assert [e for e, _ in stream] == ["start", "token", "token", "done"]
    assert stream[0][1]["session_id"] == stream[-1][1]["session_id"]
    done = stream[-1][1]
    assert done["answer"] == "He was born in 1996 [1]."
    assert done["trace"]["mode"] == "direct" and done["session_id"]
    # A single domain's NaN score must reach the browser as valid JSON.
    assert done["trace"]["route"] == [["cv", None]]
    # One block per searched domain; the answered one holds the answer's
    # sources (same [n] indices).
    assert [(r["domain"], r["used"], r["score"])
            for r in done["retrievals"]] == [("cv", True, None),
                                             ("vllm", False, -4.0)]
    assert done["retrievals"][0]["sources"] == done["sources"]
    # Sources come masked, with a short title.
    [source] = done["sources"]
    assert "612" not in source["preview"] and source["title"] == "bio.md"


def test_domain_filters(client: TestClient) -> None:
    for domains in (["cv"], ["vllm", "unknown"], None):
        client.post("/chat", json={"message": "q", "agent": False,
                                   "domains": domains})
    calls = client.app.state.service.tools.pipeline.calls  # type: ignore
    assert calls == [["cv"], ["vllm"], None]


def test_every_filter_off_asks_to_turn_one_on(client: TestClient) -> None:
    answers = {}
    for message in ("¿Dónde nació Chrystian?", "Where was he born?"):
        done = events(client.post("/chat", json={
            "message": message, "domains": []}))[-1][1]
        answers[message] = done["answer"]
        assert done["not_found"] and done["retrievals"] == []
    assert answers["¿Dónde nació Chrystian?"].startswith("Activa alguno")
    assert answers["Where was he born?"].startswith("Turn on")
    # Nothing was searched.
    assert client.app.state.service.tools.pipeline.calls == []  # type: ignore


def test_agent_sessions_keep_their_memory(client: TestClient) -> None:
    service = client.app.state.service  # type: ignore[attr-defined]
    created: list[str] = []

    class FakeAgent:
        def __init__(self) -> None:
            self.asked: list[str] = []
            self.generator = FakeGenerator("Qwen/Qwen3-1.7B")

        def ask(self, question: str, domains: Any, on_piece: Any) -> Any:
            self.asked.append(question)
            on_piece("ok")
            return type("A", (), {
                "text": "ok", "sources": [], "not_found": True,
                "domain": "cv", "queries": [question], "steps": 1,
                "fallback": False, "retries": []})()

    agents: dict[str, FakeAgent] = {}

    def agent_for(session_id: str, model: str = "default") -> FakeAgent:
        if session_id not in agents:
            created.append(session_id)
            agents[session_id] = FakeAgent()
        return agents[session_id]

    service.agent_for = agent_for
    first = events(client.post("/chat", json={"message": "a",
                                              "agent": True}))[-1][1]
    sid = first["session_id"]
    client.post("/chat", json={"message": "b", "session_id": sid,
                               "agent": True})
    assert created == [sid] and agents[sid].asked == ["a", "b"]
    assert first["trace"]["mode"] == "agent"
    assert first["trace"]["model"] == "Qwen3-1.7B"


def test_sources_are_masked_and_unknown_ids_404(client: TestClient) -> None:
    source = client.get("/sources/p1").json()
    assert source["text"] == "call [private] now"
    assert client.get("/sources/nope").status_code == 404


def test_message_length_is_limited(client: TestClient) -> None:
    assert client.post("/chat", json={"message": ""}).status_code == 422
    assert client.post("/chat", json={"message": "x" * 1001}).status_code \
        == 422


def test_short_path() -> None:
    assert short_path("data/raw/vllm-0.10.1/docs/x.md") == "docs/x.md"
    assert short_path("other/file.md") == "other/file.md"


def test_model_and_depth_selectors(client: TestClient) -> None:
    service = client.app.state.service  # type: ignore[attr-defined]
    config = client.get("/config").json()
    assert config["models"][0]["id"] == "default"
    assert config["depths"] == [3, 5, 10] and config["depth_default"] == 5
    for body in ({}, {"model": "unknown"}, {"depth": 3}):
        done = events(client.post("/chat", json={
            "message": "q", "agent": False, **body}))[-1][1]
        assert done["trace"]["model"] == "Qwen3-0.6B"
    # Unknown models fall back to the default one.
    assert service.models_used == ["default", "default", "default"]
    # depth replaces each domain's answer_k for that request only.
    assert service.tools.pipeline.answer_k == [8, 8, 3]
    assert service.tools.router.retrievers["cv"].answer_k == 8
    assert client.post("/chat", json={"message": "q", "depth": 11}
                       ).status_code == 422


def test_switching_model_releases_the_old_one_first(
        client: TestClient) -> None:
    service = client.app.state.service  # type: ignore[attr-defined]
    old = FakeGenerator("Qwen/Qwen3-0.6B")
    agent = type("A", (), {"generator": old})()
    service.sessions["s1"] = (agent, 0.0)
    service.models.loaded["default"] = old
    seen_while_loading = []

    def load(model: str) -> FakeGenerator:
        # What the new model's loading sees: nobody holds the old LLM.
        seen_while_loading.append(agent.generator)
        return FakeGenerator("Qwen/Qwen3-1.7B")

    service.models.get = load
    service.generator_for("llm-qwen3-1.7b")
    assert seen_while_loading == [None]


def test_trim_to_sentence() -> None:
    from src.api.app import trim_to_sentence

    text = "First sentence [1]. Second one is long. Third is cut in the mi"
    assert trim_to_sentence(text) == (
        "First sentence [1]. Second one is long. …")
    # An open code block is closed.
    assert trim_to_sentence("Run it:\n```bash\nvllm serve") == (
        "Run it:\n```bash\nvllm serve\n``` …")


def test_a_stopped_request_does_nothing(client: TestClient) -> None:
    import threading

    from src.api.app import ChatRequest

    service = client.app.state.service  # type: ignore[attr-defined]
    cancel = threading.Event()
    cancel.set()
    result = service.chat(ChatRequest(message="q", agent=False),
                          lambda p: None, cancel)
    assert result["trace"] == {"mode": "stopped"}
    assert service.tools.pipeline.calls == []


def test_max_tokens_per_model() -> None:
    from src.api.app import parse_max_tokens

    models = ["default", "llm-qwen3-1.7b", "llm-phi4-mini"]
    assert parse_max_tokens("", models) == {}
    assert parse_max_tokens("512", models) == dict.fromkeys(models, 512)
    assert parse_max_tokens("default=512,llm-phi4-mini=640,nope=9",
                            models) == {"default": 512,
                                        "llm-phi4-mini": 640}


def test_the_pool_applies_the_caps(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.api.app import ModelPool

    monkeypatch.setenv("RAG_API_MAX_TOKENS", "default=321")
    pool = ModelPool(CONFIG)
    assert pool.options["default"].max_new_tokens == 321
    assert CONFIG.generation.max_new_tokens != 321  # a copy, not the config


def test_a_pinned_domain_joins_every_filter(client: TestClient) -> None:
    service = client.app.state.service  # type: ignore[attr-defined]
    service.config = CONFIG.model_copy(deep=True)
    service.config.sources["vllm"].pinned = True
    for domains in (["cv"], ["vllm"], None):
        client.post("/chat", json={"message": "q", "agent": False,
                                   "domains": domains})
    # Added to a filter (once); no filter still means every domain.
    assert service.tools.pipeline.calls == [["cv", "vllm"], ["vllm"], None]


def test_config_marks_pinned_domains(client: TestClient) -> None:
    [domain] = client.get("/config").json()["domains"]
    assert domain["name"] == "cv" and domain["pinned"] is False


def test_the_web_default_and_direct_only_models(
        monkeypatch: pytest.MonkeyPatch) -> None:
    from src.api.app import ModelPool

    config = CONFIG.model_copy(
        update={"available_profiles": ["default", "llm-a", "llm-b"]})
    monkeypatch.setattr("src.api.app.load_config",
                        lambda profile: CONFIG)
    monkeypatch.setenv("RAG_API_DEFAULT_MODEL", "llm-a")
    monkeypatch.setenv("RAG_API_DIRECT_ONLY", "llm-b,unknown")
    pool = ModelPool(config)
    assert pool.default_id == "llm-a"
    # No model, or an unknown one: the web's default, not the base.
    assert pool.resolve(None) == pool.resolve("nope") == "llm-a"
    assert pool.direct_only == {"llm-b"}
    assert {m["id"]: m["agent"] for m in pool.describe()} == {
        "default": True, "llm-a": True, "llm-b": False}
    # An unknown default falls back to the base model.
    monkeypatch.setenv("RAG_API_DEFAULT_MODEL", "nope")
    assert ModelPool(config).default_id == "default"


def test_a_direct_only_model_refuses_the_agent(client: TestClient) -> None:
    service = client.app.state.service  # type: ignore[attr-defined]
    service.models.options["llm-big"] = CONFIG.generation.model_copy(
        update={"model": "Qwen/Qwen3-4B"})
    service.models.direct_only = {"llm-big"}
    error = events(client.post("/chat", json={
        "message": "q", "agent": True, "model": "llm-big"}))[-1]
    assert error[0] == "error" and "without the agent" in error[1]["detail"]
    done = events(client.post("/chat", json={
        "message": "q", "agent": False, "model": "llm-big"}))[-1]
    assert done[0] == "done" and service.models_used == ["llm-big"]


def test_a_model_can_move_the_retrieval_to_the_cpu(
        client: TestClient) -> None:
    service = client.app.state.service  # type: ignore[attr-defined]
    moves: list[str] = []

    class Module:
        def to(self, device: str) -> None:
            moves.append(device)

    shared = Module()
    for retriever in service.tools.router.retrievers.values():
        retriever.embedder = type("E", (), {"model": shared})()
        retriever.reranker = shared  # shared modules move once
    service.retrieval_device = "cuda"
    service.models.retrieval_device.update(
        {"llm-big": "cpu", "default": "cuda"})
    service.models.loaded["default"] = FakeGenerator("Qwen/Qwen3-0.6B")
    loading: list[tuple[str, str, int]] = []

    def get(model: str) -> FakeGenerator:
        # The old LLM is gone and the retrieval moved before loading.
        loading.append((model, service.retrieval_device,
                        len(service.models.loaded)))
        service.models.loaded[model] = FakeGenerator(model)
        return service.models.loaded[model]

    service.models.get = get
    service.generator_for("llm-big")
    service.generator_for("default")
    assert loading == [("llm-big", "cpu", 0), ("default", "cuda", 0)]
    assert moves == ["cpu", "cuda"]


def test_a_full_queue_refuses_the_chat(client: TestClient) -> None:
    service = client.app.state.service
    service.max_queue = 1
    service.queued = 1  # another visitor's chat is answering
    stream = events(client.post("/chat", json={"message": "Hi"}))
    assert stream[-1][0] == "error"
    assert "busy" in stream[-1][1]["detail"]
    service.queued = 0
    stream = events(client.post("/chat", json={"message": "Hi"}))
    assert stream[-1][0] == "done" and service.queued == 0


def test_a_full_queue_refuses_the_search(client: TestClient) -> None:
    service = client.app.state.service
    service.max_queue = 1
    service.queued = 1
    response = client.post("/search", json={"query": "vllm"})
    assert response.status_code == 503 and "busy" in response.json()["detail"]
    service.queued = 0
    assert client.post("/search", json={"query": "vllm"}).status_code == 200
    assert service.queued == 0


def test_the_api_docs_can_be_hidden(monkeypatch) -> None:
    monkeypatch.setenv("RAG_API_DOCS", "0")
    hidden = TestClient(create_app(CONFIG, preload=False))
    assert hidden.get("/openapi.json").status_code == 404
    assert hidden.get("/docs").status_code == 404
    assert hidden.get("/health").status_code == 200
