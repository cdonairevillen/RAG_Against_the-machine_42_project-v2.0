from typing import Any, Optional

from src.agent.agent import Agent
from src.agent.memory import Session, Turn
from src.agent.toolcalls import parse_tool_calls, render, tool_style
from src.config import RagConfig
from src.rag.domain_rules import DomainRules
from src.rag.ingestion.chunk import Chunk


def test_parses_every_tool_call_convention() -> None:
    qwen = ('<tool_call>\n{"name": "search", "arguments": '
            '{"query": "a"}}\n</tool_call>')
    phi = ('<|tool_call|>[{"type": "function", "function": {"name": '
           '"search", "arguments": "{\\"query\\": \\"b\\"}"}}]<|/tool_call|>')
    bare = '{"name": "search", "parameters": {"query": "c"}}'
    cut = "<tool_call>\n{'name': 'search', 'arguments': {'query': 'd'}}"
    for text, query in ((qwen, "a"), (phi, "b"), (bare, "c"), (cut, "d")):
        [call] = parse_tool_calls(text)
        assert call == {"name": "search", "arguments": {"query": query}}
    assert parse_tool_calls("DONE") == []
    assert parse_tool_calls("The answer is 42 [1].") == []


def test_tool_style_from_the_chat_template() -> None:
    assert tool_style("{% if tools %}<tools>{% endif %}") == "native"
    assert tool_style("{% if 'tools' in message and "
                      "message['tools'] %}") == "system_tools"
    assert tool_style("{{ message['content'] }}") == "prompt"


class PlainTokenizer:
    chat_template = "{{ message['content'] }}"

    def apply_chat_template(self, messages: list[dict[str, Any]],
                            **kwargs: Any) -> str:
        return "\n".join(f"{m['role']}: {m['content']}" for m in messages)


def test_prompt_style_describes_tools_and_maps_tool_role() -> None:
    prompt = render(PlainTokenizer(), [
        {"role": "system", "content": "SYS"},
        {"role": "tool", "content": "RESULT"},
    ], [{"type": "function", "function": {"name": "search"}}])
    assert "<tool_call>" in prompt and '"search"' in prompt
    assert "user: Tool result:\nRESULT" in prompt


def test_session_transcript_keeps_recent_turns() -> None:
    session = Session()
    for i in range(6):
        session.add(Turn(f"q{i}", f"a{i}"))
    text = session.transcript()
    assert "q0" not in text and "User: q5\nAssistant: a5" in text


class FakeGenerator:
    tokenizer = PlainTokenizer()

    def __init__(self, plans: list[str]) -> None:
        self.plans = plans
        self.prompts: list[str] = []
        self.answered: list[str] = []

    def complete(self, prompt: str, max_new_tokens: int) -> str:
        self.prompts.append(prompt)
        return self.plans.pop(0) if self.plans else "DONE"

    def answer_with_text(self, question: str, blocks: list[str],
                         extra: str = "",
                         language: Optional[str] = None) -> str:
        self.answered.append(question)
        return f"Answer to {question} [1]"


class FakeRouter:
    domains = ["cv"]
    retrievers: dict[str, Any] = {}

    def get_parent_chunk_map(self) -> dict:
        return {("cv.md", 0): Chunk("born in 1996", "cv.md", 0, 12, "doc",
                                    domain="cv")}


class FakeTools:
    def __init__(self, generator: FakeGenerator) -> None:
        self.router = FakeRouter()
        self.rules = DomainRules(RagConfig())
        self.generator = generator
        self.queries: list[str] = []

    def get_pipeline(self) -> Any:
        return self

    def list_domains(self) -> list[dict[str, Any]]:
        return [{"name": "cv", "description": "the author"}]

    def search(self, query: str, domains: Any, k: int) -> dict[str, Any]:
        self.queries.append(query)
        return {"domain": "cv", "score": 1.0, "sources": [{
            "domain": "cv", "file_path": "cv.md",
            "first_character_index": 0, "last_character_index": 12,
            "text": "born in 1996"}]}


def test_agent_searches_with_the_models_query_then_answers() -> None:
    generator = FakeGenerator([
        '<tool_call>{"name": "search", "arguments": '
        '{"query": "When was Chrystian born?"}}</tool_call>',
        "DONE",
    ])
    tools = FakeTools(generator)
    answer = Agent(tools).ask("When was he born?")  # type: ignore[arg-type]
    assert tools.queries == ["When was Chrystian born?"]
    assert answer.queries == ["When was Chrystian born?"]
    assert not answer.fallback and answer.steps == 2
    assert generator.answered == ["When was Chrystian born?"]


def test_fallback_keeps_the_subject_of_the_last_model_query() -> None:
    generator = FakeGenerator([
        '<tool_call>{"name": "search", "arguments": '
        '{"query": "Where was Chrystian born?"}}</tool_call>',
        "DONE",
        "He was born in 1996.",          # answers without searching
    ])
    tools = FakeTools(generator)
    agent = Agent(tools)  # type: ignore[arg-type]
    agent.ask("Where was he born?")
    second = agent.ask("And in which year?")
    assert second.fallback
    assert tools.queries[-1] == "Where was Chrystian born? And in which year?"
    # The history reaches the planner inside the user turn.
    assert "Conversation so far:" in generator.prompts[-1]


def test_plan_b_answers_the_original_question_after_fallback() -> None:
    plans = [model_call("Where was Chrystian born?"), "DONE",
             "He was born in 1996."]   # answers without searching
    for mode, expected in (("mixed", "Where was Chrystian born? "
                                     "And in which year?"),
                           ("original", "And in which year?")):
        generator = FakeGenerator(list(plans))
        tools = FakeTools(generator)
        agent = Agent(tools, fallback_answer=mode)  # type: ignore[arg-type]
        agent.ask("Where was he born?")
        second = agent.ask("And in which year?")
        # Same search either way; only the question answered changes.
        assert second.fallback
        assert tools.queries[-1] == ("Where was Chrystian born? "
                                     "And in which year?")
        assert generator.answered[-1] == expected


def test_answer_with_picks_the_question_the_generator_answers() -> None:
    rewrite = "Chrystian birth date"
    for mode, first, follow in (
            ("rewrite", rewrite, rewrite),
            ("original", "When was he born?", "And where?"),
            ("context", "When was he born?",
             "And where? (Chrystian birth date)"),
            ("both", "When was he born? (Chrystian birth date)",
             "And where? (Chrystian birth date)")):
        generator = FakeGenerator([model_call(rewrite), "DONE",
                                   model_call(rewrite), "DONE"])
        tools = FakeTools(generator)
        agent = Agent(tools, answer_with=mode)  # type: ignore[arg-type]
        agent.ask("When was he born?")
        agent.ask("And where?")
        assert generator.answered == [first, follow], mode


def test_answer_with_defaults_to_the_models_setting() -> None:
    generator = FakeGenerator([model_call("Chrystian birth date"), "DONE"])
    generator.agent_answer_with = "original"  # type: ignore[attr-defined]
    Agent(FakeTools(generator)).ask(  # type: ignore[arg-type]
        "When was he born?")
    assert generator.answered == ["When was he born?"]


class PickyTools(FakeTools):
    """Finds sources only for some queries and domains."""

    def __init__(self, generator: FakeGenerator, found_query: str,
                 found_domains: Any = "any") -> None:
        super().__init__(generator)
        self.found_query = found_query
        self.found_domains = found_domains
        self.calls: list[tuple[str, Any]] = []

    def search(self, query: str, domains: Any, k: int) -> dict[str, Any]:
        self.calls.append((query, domains))
        hit = query == self.found_query and (
            self.found_domains == "any" or domains == self.found_domains)
        result = super().search(query, domains, k)
        return result if hit else {**result, "sources": []}


def model_call(query: str, domains: str = "") -> str:
    extra = f', "domains": "{domains}"' if domains else ""
    return ('<tool_call>{"name": "search", "arguments": {"query": "'
            + query + '"' + extra + '}}</tool_call>')


def test_rewrite_that_finds_nothing_falls_back_to_the_question() -> None:
    generator = FakeGenerator([model_call("keywords only"), "DONE"])
    tools = PickyTools(generator, found_query="What is it?")
    answer = Agent(tools).ask("What is it?")  # type: ignore[arg-type]
    assert answer.retries == ["original-question"]
    assert not answer.not_found
    assert [q for q, _ in tools.calls] == ["keywords only", "What is it?"]


def test_model_domain_choice_is_a_hint_without_user_filter() -> None:
    generator = FakeGenerator([model_call("Who?", "cv"), "DONE"])
    tools = PickyTools(generator, found_query="Who?", found_domains=None)
    answer = Agent(tools).ask("Who?")  # type: ignore[arg-type]
    assert answer.retries == ["all-domains"]
    assert tools.calls == [("Who?", ["cv"]), ("Who?", None)]


def test_user_filter_is_never_exceeded() -> None:
    # The model asks for another domain and nothing is found: every
    # search, retries included, stays inside the user's "cv" filter.
    generator = FakeGenerator([model_call("Who?", "vllm"), "DONE"])
    tools = PickyTools(generator, found_query="nothing matches")
    Agent(tools).ask("Who?", domains="cv")  # type: ignore[arg-type]
    assert tools.calls and all(d == "cv" for _, d in tools.calls)
