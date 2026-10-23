import string

ES_MARKERS = {
    "el", "la", "los", "las", "que", "es", "un", "una", "para", "por",
    "con", "se", "del", "al", "como", "cómo", "qué", "cuál", "cuáles",
    "dónde", "cuándo", "más", "puede", "pueden", "usa", "usar", "este",
    "esta", "cuando", "también", "sus", "su", "hay", "hace",
}
EN_MARKERS = {
    "the", "is", "are", "of", "to", "and", "for", "with", "by", "that",
    "this", "it", "as", "on", "can", "uses", "use", "when", "its", "be",
    "what", "how", "which", "does", "do",
}
LANGUAGE_NAMES = {"es": "Spanish", "en": "English"}
ARTICLES = {"a", "an", "the"}


def words(text: str) -> list[str]:
    """Lowercase words without punctuation (¿ and ¡ included)."""
    text = text.lower()
    drop = string.punctuation + "¿¡"
    text = "".join(" " if ch in drop else ch for ch in text)
    return text.split()


def detect_language(text: str) -> str:
    """Return 'es', 'en' or '?' from function-word counts.

    A two-language heuristic (the languages of the project), enough to
    pick the answer language and to check that answers follow it.
    """
    tokens = words(text)
    es = sum(w in ES_MARKERS for w in tokens)
    en = sum(w in EN_MARKERS for w in tokens)
    if es == en == 0:
        return "?"
    return "es" if es > en else "en"
