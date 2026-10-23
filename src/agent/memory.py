"""Conversation memory of one session (D7: never persisted).

The agent sees the last turns as chat history, so follow-up questions
("and in which year?") can be rewritten into complete ones before
searching. Nothing is stored beyond the session object.
"""
from dataclasses import dataclass, field

# Turns shown to the agent, and characters kept of each past answer.
MAX_TURNS = 4
ANSWER_CHARS = 400


@dataclass
class Turn:
    """One question and its final answer."""

    question: str
    answer: str
    query: str = ""
    domain: str = ""
    # The query was the agent's fallback, not written by the model.
    fallback: bool = False


@dataclass
class Session:
    """The turns of one conversation, newest last."""

    turns: list[Turn] = field(default_factory=list)

    def add(self, turn: Turn) -> None:
        """Remember a finished turn."""
        self.turns.append(turn)

    def clear(self) -> None:
        """Forget the conversation."""
        self.turns.clear()

    def transcript(self) -> str:
        """The recent turns as plain text ("User: ... / Assistant: ...")."""
        return "\n".join(
            f"User: {t.question}\nAssistant: {t.answer[:ANSWER_CHARS]}"
            for t in self.turns[-MAX_TURNS:]
        )

    def messages(self) -> list[dict[str, str]]:
        """The recent turns as user/assistant chat messages."""
        messages: list[dict[str, str]] = []
        for turn in self.turns[-MAX_TURNS:]:
            messages.append({"role": "user", "content": turn.question})
            messages.append({"role": "assistant",
                             "content": turn.answer[:ANSWER_CHARS]})
        return messages
