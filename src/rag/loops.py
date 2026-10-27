"""Generation loops: when a model starts repeating itself.

Small models (Phi-4-mini above all) can fall into a loop in long
answers: the same list item again and again, two lines in turn, or the
same sentence with one word changed each time ("In the seventh
stage...", "In the tenth stage..."). An exact n-gram rule misses the
last kind and fires on good answers (FASE_6.md 6g), so lines and
sentences are compared by similarity instead.

Measured (FASE_7.md 7b.2): it catches every loop reproduced with
Phi-4-mini and fires on none of 11,550 stored benchmark answers and 202
long Markdown documents.
"""
import re
from difflib import SequenceMatcher
from typing import Optional

# A loop: among the last WINDOW units (lines and sentences), REPEATS or
# more are near-copies (>= SIMILARITY) of an earlier one in the window.
# 12 catches cycles of up to 7 sentences (8 missed Phi's 4-sentence
# cycle; FASE_7.md 7b.7), with no new false positives.
WINDOW = 12
REPEATS = 5
SIMILARITY = 0.95
# Units shorter than this (in words) are not compared.
MIN_WORDS = 3
# The same word this many times in a row ("step step step...").
WORD_RUN = 12
# A repeated block: this many units in a row, each a near-copy of the
# unit the same distance back. Catches cycles longer than WINDOW allows
# and an answer written twice (FASE_7.md 7b.7).
BLOCK = 6
# Longest cycle looked for, in units (an answer of 1024 tokens has ~40
# sentences).
MAX_PERIOD = 40

LIST_MARK = re.compile(r"^\s*(?:\d+[.)]|[-*•]|#+)\s*")
CITATION = re.compile(r"\(source:?\s*\[\d+\]\)|\[\d+\]", re.IGNORECASE)
# Logs repeat their shape by nature (timestamps, levels).
LOG_LINE = re.compile(r"^\s*(?:INFO|DEBUG|WARNING|ERROR)\b|\d\d:\d\d:\d\d")
# A sentence ends at . ! or ? after a non-digit, so a list number ("5. ")
# stays with its line.
UNITS = re.compile(r"(?<=[^\d\s][.!?])[ \t]+|\n")
WORD_LOOP = re.compile(r"\b(\w+)(?:\s+\1\b){%d,}" % (WORD_RUN - 1))
# A unit just ended: worth checking the text again.
BOUNDARY = re.compile(r"[\n.!?]")


def normalise(unit: str) -> str:
    """A unit without list numbering, citations, case or extra spaces."""
    unit = CITATION.sub("", LIST_MARK.sub("", unit.lower()))
    return " ".join(unit.split())


def structured(unit: str, in_code: bool) -> bool:
    """Tables, HTML, logs and code, which repeat their shape by nature
    and are not compared."""
    stripped = unit.strip()
    return in_code or unit.startswith("    ") \
        or stripped.startswith(("|", "<", "```", "===")) \
        or bool(LOG_LINE.search(stripped))


def find_loop(text: str) -> Optional[int]:
    """Character offset where a loop starts, or None if there is none."""
    word = WORD_LOOP.search(text)
    word_at = word.start() if word else None
    units: list[str] = []
    offsets: list[int] = []
    pos = 0
    in_code = False
    for unit in UNITS.split(text):
        start = text.find(unit, pos) if unit else pos
        pos = start + len(unit)
        if unit.strip().startswith("```"):
            in_code = not in_code
        words = normalise(unit)
        if structured(unit, in_code) or len(words.split()) < MIN_WORDS:
            continue
        units.append(words)
        offsets.append(start)
        first = max(0, len(units) - WINDOW)
        recent = units[first:]
        copies = [i for i in range(1, len(recent))
                  if any(similar(recent[i], recent[j]) for j in range(i))]
        if len(copies) >= REPEATS:
            at = offsets[first + copies[0]]
            return at if word_at is None else min(at, word_at)
        block = repeated_block(units)
        if block is not None:
            at = offsets[block]
            return at if word_at is None else min(at, word_at)
    return word_at


def repeated_block(units: list[str]) -> Optional[int]:
    """Index of the unit where a repeated block starts: the last BLOCK
    or more units each match the unit `period` back. When the unit just
    before also contains its counterpart ("The answer in Spanish is:
    <first sentence again>"), the copy starts there."""
    last = len(units) - 1
    for period in range(BLOCK, min(MAX_PERIOD, len(units) // 2) + 1):
        run = 0
        while run <= last - period and similar(
                units[last - run], units[last - run - period]):
            run += 1
        if run >= BLOCK:
            start = last - run + 1
            if start > period and \
                    units[start - 1 - period] in units[start - 1]:
                return start - 1
            return start
    return None


def similar(a: str, b: str) -> bool:
    """Near-copies: equal, or at least SIMILARITY alike."""
    if a == b:
        return True
    # The ratio is at most 2 * shorter / (both lengths): skip the work
    # when the lengths alone rule it out.
    if 2 * min(len(a), len(b)) < SIMILARITY * (len(a) + len(b)):
        return False
    return SequenceMatcher(None, a, b).ratio() >= SIMILARITY


def cut_loop(text: str) -> str:
    """The text up to where a loop starts (unchanged without a loop)."""
    at = find_loop(text)
    return text if at is None else text[:at].rstrip()
