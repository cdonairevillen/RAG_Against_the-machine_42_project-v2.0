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
