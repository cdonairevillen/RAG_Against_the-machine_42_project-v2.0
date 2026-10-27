"""Per-domain answer rules: private data and the "not found" message.

Applied when answering, never at indexing time: the indexed material
stays exactly as the source files are (reproducible), and what a user
can see is decided here. Configured per source in rag.toml.
"""
import re
from typing import Optional

from src.config import RagConfig, SourceConfig
from src.rag.language import detect_language

# Spanish phone numbers: 9 digits starting with 6-9, optionally with the
# +34 prefix and spaces, dots or dashes ("(+34) 612345678",
# "+34 612 34 56 78"). Shorter or longer digit runs (years, sizes) do
# not match.
PHONE = re.compile(
    r"(?:\(?\+34\)?[\s.-]*)?(?<![\d+])[6-9](?:[\s.-]?\d){8}(?!\d)"
)
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")


def redact(text: str, source: SourceConfig) -> str:
    """Mask a source's private data in a text.

    Args:
        text: Text to clean (a chunk, a context block or an answer).
        source: The domain's configuration.

    Returns:
        The text with every private item replaced by
        source.private_replacement (public emails are kept).
    """
    if "phone" in source.private_data:
        text = PHONE.sub(source.private_replacement, text)
    if "email" in source.private_data:
        public = {e.lower() for e in source.public_emails}
        text = EMAIL.sub(
            lambda m: m.group(0) if m.group(0).lower() in public
            else source.private_replacement,
            text,
        )
    return text


class DomainRules:
    """The answer rules of every configured domain."""

    def __init__(self, config: RagConfig) -> None:
        self.sources = config.sources

    def redact(self, text: str, domain: Optional[str]) -> str:
        """Mask a domain's private data (no-op for unknown domains)."""
        source = self.sources.get(domain or "")
        return redact(text, source) if source else text

    def redact_all(self, text: str) -> str:
        """Mask the private data of every domain (for answers, which may
        mix what the LLM read with what it made up)."""
        for source in self.sources.values():
            text = redact(text, source)
        return text

    def prompt_rules(self, domain: Optional[str], model: str = "") -> str:
        """Extra system-prompt rules of a domain ('' when none), plus
        the ones it sets for `model` (a Hugging Face id)."""
        source = self.sources.get(domain or "")
        if source is None:
            return ""
        own = source.model_rules.get(model, "").strip()
        if not own:
            return source.prompt_rules
        return f"{source.prompt_rules.strip()}\n{own}".strip()

    def not_found_message(self, domain: Optional[str],
                          question: str) -> Optional[str]:
        """The domain's "not found" answer in the question's language.

        Returns:
            The message, or None when the domain has no custom one.
        """
        source = self.sources.get(domain or "")
        if source is None or not source.not_found_message:
            return None
        messages = source.not_found_message
        language = detect_language(question)
        return messages.get(language) or messages.get("en") \
            or next(iter(messages.values()))
