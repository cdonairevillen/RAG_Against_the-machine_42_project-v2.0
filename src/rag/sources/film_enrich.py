"""Film enrichment (Phase 9, FASE_9.md 9b): summaries a film transcript
lacks, generated offline by an LLM and added to the film's Markdown
file as more sections the RAG can search and cite.

Why: the transcript is 30-second stretches of subtitles (no speaker)
and scene descriptions (characters by appearance, never by name). A
question such as "who is Puss in Boots?" or "when does Donkey first
appear?" needs the whole film, not five stretches.

Two layers, bottom-up (as RAPTOR):
1. Scene summaries: the sections grouped into windows of about
   WINDOW_SECONDS; for each, the LLM summarises what happens and lists
   the characters named in it, from that window's text only.
2. Character profiles: for every character in at least MIN_WINDOWS
   windows, the LLM writes a profile from the summaries of those
   windows and the dialogue lines that name them (picked by the code).

What the code decides, never the model: the times (a summary keeps its
window's span), which windows mention a character (a word match on the
transcript, so "a talking donkey" counts for Donkey even when the model
did not list him), and so where a character is first mentioned.

The LLM is local (llm_sdk, Qwen3-4B by default) or an OpenAI-compatible
API (NVIDIA build, DEC-50). Everything is cached in
data/film/.work/<film>/enrichment-<model>.json; film.prepare() appends
the newest one to the Markdown file. Both layers are marked as
generated, so a cited source says it is a summary and not the film.
"""
import json
import os
import re
import time
import urllib.error
import urllib.request
from collections import Counter
from typing import Any, Callable, Optional

WINDOW_SECONDS = 180.0
MIN_WINDOWS = 2
MAX_CHARACTERS = 15
MAX_EVIDENCE_LINES = 15
DEFAULT_MODEL = "Qwen/Qwen3-4B"
SUMMARY_TOKENS = 300
PROFILE_TOKENS = 350
# Bumped when the prompts change: cached profiles of another version are
# generated again (window summaries are kept if their prompt did not
# change: SUMMARY_VERSION).
SUMMARY_VERSION = 2
PROFILE_VERSION = 3

SUMMARY_SYSTEM = (
    "You summarise a stretch of a film transcript. The transcript has "
    "scene descriptions (what is seen: characters are described by "
    "their appearance, never by name) and dialogue (what is said: the "
    "speaker is not given). Use only this text: no knowledge of the "
    "film from elsewhere. Name a character only when the dialogue "
    "supports the name (someone says it, or addresses them by it). Say "
    "who says a line only when it is clear from the text."
)
SUMMARY_USER = (
    "Film: {title}. Stretch {start} - {end}.\n\n{text}\n\n"
    "Answer in English, in exactly this format:\n"
    "SUMMARY: 3 to 5 sentences: what happens, who does what, where.\n"
    "CHARACTERS: the characters named in the dialogue of this stretch, "
    "comma separated, at most 8 (or 'none')"
)
PROFILE_SYSTEM = (
    "You write a short profile of a film character from summaries of "
    "the scenes where they appear and the dialogue lines that name "
    "them (the speaker of a line is not given). Use only this material: "
    "no knowledge of the film from elsewhere."
)
PROFILE_USER = (
    "Film: {title}. Character: {name}.\n\nScenes, in film order:\n"
    "{scenes}\n\nDialogue lines that name {name}:\n{lines}\n\n"
    "Answer in exactly this format:\n"
    "PROFILE: in English, 3 to 5 sentences: who {name} is, their role in "
    "the story, their relationships with the other characters and what "
    "they do. Only what the material says: do not add how the story "
    "ends or anything else you may know. No times. If the material says "
    "little, write less.\n"
    "SPANISH NAMES: Spain: <the name of {name} in the Spanish dub from "
    "Spain>; Latin America: <the name in the Latin American dub>. If you "
    "do not know a dub, give the usual Spanish translation of the name."
)

TITLES = re.compile(
    r"^(the|lord|lady|princess|prince|king|queen|sir|mr|mrs|miss|"
    r"dr)\.?\s+", re.IGNORECASE)
NOT_A_NAME = re.compile(
    r"\b(unnamed|unknown|unidentified|narrator|none|n/a|various)\b",
    re.IGNORECASE)
# Roles and common nouns, not characters (first runs, FASE_9.md 9b:
# "Princess", "Knight", "Captain" and "Dad" got profiles of their own).
GENERIC = {
    "princess", "prince", "king", "queen", "lord", "lady", "knight",
    "knights", "guard", "guards", "soldier", "soldiers", "man", "woman",
    "men", "women", "people", "crowd", "father", "mother", "witch",
    "creatures", "fairy tale creatures", "ogre", "ogres", "giant", "beast",
    "villagers", "narrator", "everyone", "dad", "mom", "mum", "daddy",
    "mommy", "mummy", "son", "daughter", "captain", "horse", "boss",
    "sir", "darling", "honey", "baby", "kid", "kids", "cat", "handsome",
}
MAX_NAMES = 8
# A profile that only says the material does not describe the character
# (first run: Lillian, Gingy) is dropped; the mention facts stay.
EMPTY_PROFILE = re.compile(
    r"not (directly )?(mentioned|featured|described|present)|cannot be "
    r"determined|no details|not enough information", re.IGNORECASE)
DIALOGUE_LINE = re.compile(r'^- "(.*)"\s*$', re.M)

Generate = Callable[[str, str, int], str]


def windows(sections: list[tuple[float, float, str]],
            seconds: float = WINDOW_SECONDS
            ) -> list[tuple[float, float, str]]:
    """Consecutive sections (start, end, text) merged until a window
    lasts at least `seconds`."""
    out: list[tuple[float, float, str]] = []
    for start, end, text in sections:
        if out and out[-1][1] - out[-1][0] < seconds:
            first, _, body = out[-1]
            out[-1] = (first, end, f"{body}\n\n{text}")
        else:
            out.append((start, end, text))
    return out


def mentions(key: str, text: str) -> bool:
    """Whether a name key appears in a text as whole words; the words
    may be split by punctuation ("Puss... in Boots!")."""
    pattern = r"\W+".join(re.escape(w) for w in key.split())
    return re.search(rf"\b{pattern}\b", text, re.IGNORECASE) is not None


def parse_summary(reply: str, source: str) -> tuple[list[str], str]:
    """(characters, summary) from a 'SUMMARY: ... CHARACTERS: ...'
    reply; tolerant of extra blank lines and markdown bold.

    A name is kept only if it appears in the window's text (`source`),
    is not a role or common noun (GENERIC) and has at most three words;
    repeated names count once (first run: the 4B looped on the list).
    """
    clean = reply.replace("**", "")
    found = re.search(r"CHARACTERS:\s*(.*?)\s*(?:\n|$)", clean,
                      re.IGNORECASE)
    summary = re.search(r"SUMMARY:\s*(.*?)\s*(?:CHARACTERS:|$)", clean,
                        re.IGNORECASE | re.DOTALL)
    names: list[str] = []
    for raw in (found.group(1) if found else "").split(","):
        name = raw.strip(" .;:-*\"'")
        key = name_key(name)
        if (not name or not name[0].isupper() or NOT_A_NAME.search(name)
                or len(name.split()) > 3 or not key or key in GENERIC
                or key in [name_key(n) for n in names]
                or not mentions(key, source)):
            continue
        names.append(name)
    text = (summary.group(1) if summary else
            re.sub(r"CHARACTERS:.*", "", clean, flags=re.DOTALL)).strip()
    return names[:MAX_NAMES], " ".join(text.split())


def parse_profile(reply: str) -> tuple[str, str]:
    """(profile, Spanish names) from a 'PROFILE: ... SPANISH NAMES:
    Spain: X; Latin America: Y' reply. The names come out as 'X / Y'
    (one name when both dubs agree), so a question with either one
    finds the profile (DEC-52: "Asno" in Spain, "Burro" in Latin
    America). The profile is '' when it only says the material is
    silent about the character (EMPTY_PROFILE)."""
    clean = reply.replace("**", "")
    profile = re.search(r"PROFILE:\s*(.*?)\s*(?:SPANISH NAMES?:|$)",
                        clean, re.IGNORECASE | re.DOTALL)
    spanish = re.search(r"SPANISH NAMES?:\s*(.*?)\s*(?:\n|$)", clean,
                        re.IGNORECASE)
    text = " ".join((profile.group(1) if profile else re.sub(
        r"SPANISH NAMES?:.*", "", clean, flags=re.DOTALL)).split())
    if EMPTY_PROFILE.search(text):
        text = ""
    names: list[str] = []
    for part in re.split(r";", spanish.group(1) if spanish else ""):
        name = re.sub(r"^\s*(spain|latin america)\s*:", "", part,
                      flags=re.IGNORECASE).strip(" .\"'*<>")
        if name and name.lower() not in [n.lower() for n in names]:
            names.append(name)
    return text, " / ".join(names)


def name_key(name: str) -> str:
    """Key that joins the variants of a name ("Lord Farquaad",
    "Farquaad" -> "farquaad")."""
    return TITLES.sub("", name.strip()).lower()


def characters(summaries: list[dict[str, Any]],
               texts: Optional[list[str]] = None) -> dict[str, dict]:
    """The film's characters, by key.

    Candidates are the names the model listed (roles and common nouns
    left out, GENERIC). A one-word key that starts or ends exactly one
    longer key joins it as an alias ("puss" -> "puss in boots",
    "godmother" -> "fairy godmother"). A character's windows are those
    where the model listed them plus, when `texts` (each window's
    transcript) is given, those whose text mentions any of their
    aliases ("Puss... in Boots!" counts through "puss"). Kept: in at
    least MIN_WINDOWS windows, the MAX_CHARACTERS most frequent.

    Returns:
        key -> {"name" (most common variant), "aliases", "windows",
        "first" (first window), "first_listed" (first window where the
        model listed them)}.
    """
    listed: dict[str, list[int]] = {}
    variants: dict[str, Counter] = {}
    for i, window in enumerate(summaries):
        for name in window["characters"]:
            key = name_key(name)
            if not key or key in GENERIC:
                continue
            if i not in listed.setdefault(key, []):
                listed[key].append(i)
            variants.setdefault(key, Counter())[name] += 1
    aliases = {key: {key} for key in listed}
    for short in [k for k in listed if " " not in k]:
        longer = [k for k in listed if k != short and (
            k.startswith(short + " ") or k.endswith(" " + short))]
        if len(longer) == 1:
            target = longer[0]
            listed[target] = sorted(set(listed[target]) | set(listed[short]))
            variants[target].update(variants.pop(short))
            aliases[target] |= aliases.pop(short)
            del listed[short]
    seen = {}
    for key, ids in listed.items():
        found = set(ids)
        if texts is not None:
            found |= {i for i, t in enumerate(texts)
                      if any(mentions(a, t) for a in aliases[key])}
        seen[key] = sorted(found)
    kept = sorted((k for k in seen if len(seen[k]) >= MIN_WINDOWS),
                  key=lambda k: (-len(seen[k]), seen[k][0]))
    return {
        key: {"name": variants[key].most_common(1)[0][0],
              "aliases": sorted(aliases[key]),
              "windows": seen[key], "first": seen[key][0],
              "first_listed": listed[key][0]}
        for key in kept[:MAX_CHARACTERS]
    }


def evidence_lines(keys: list[str],
                   groups: list[tuple[float, float, str]],
                   limit: int = MAX_EVIDENCE_LINES) -> list[str]:
    """Dialogue lines that name a character (any of its alias keys),
    with their window's start, in film order (at most `limit`, spread
    over the film)."""
    from src.rag.sources.film import stamp

    found = [f"- {stamp(start)}: \"{line}\""
             for start, _, text in groups
             for line in DIALOGUE_LINE.findall(text)
             if any(mentions(k, line) for k in keys)]
    if len(found) <= limit:
        return found
    step = len(found) / limit
    return [found[int(i * step)] for i in range(limit)]


def enrich_film(title: str, sections: list[tuple[float, float, str]],
                generate: Generate,
                cached: Optional[dict] = None) -> dict:
    """Both layers for one film. Window summaries and profiles already
    in `cached` (same span, same windows, same prompt version) are
    reused.

    Args:
        title: Film title.
        sections: (start, end, text) of each transcript section.
        generate: (system, user, max_new_tokens) -> reply.
        cached: A previous result of this function.

    Returns:
        {"windows": [...], "characters": {...}, versions}, JSON-ready.
    """
    from src.rag.sources.film import stamp

    cached = cached or {}
    old = {(w["start"], w["end"]): w for w in cached.get("windows", [])} \
        if cached.get("summary_version") == SUMMARY_VERSION else {}
    summaries = []
    groups = windows(sections)
    for n, (start, end, text) in enumerate(groups, 1):
        if (start, end) in old:
            summaries.append(old[(start, end)])
            continue
        reply = generate(SUMMARY_SYSTEM, SUMMARY_USER.format(
            title=title, start=stamp(start), end=stamp(end), text=text),
            SUMMARY_TOKENS)
        names, summary = parse_summary(reply, text)
        summaries.append({"start": start, "end": end,
                          "characters": names, "summary": summary})
        print(f"  window {n}/{len(groups)} {stamp(start)}: "
              f"{', '.join(names) or '-'}")

    old_profiles = cached.get("characters", {}) \
        if cached.get("profile_version") == PROFILE_VERSION else {}
    people = characters(summaries, [text for _, _, text in groups])
    for key, person in people.items():
        previous = old_profiles.get(key, {})
        if previous.get("windows") == person["windows"] \
                and "profile" in previous:
            person["profile"] = previous["profile"]
            person["spanish"] = previous.get("spanish", "")
            continue
        scenes = "\n".join(
            f"- {stamp(summaries[i]['start'])}: {summaries[i]['summary']}"
            for i in person["windows"])
        lines = "\n".join(
            evidence_lines(person["aliases"], groups)) or "(none)"
        reply = generate(PROFILE_SYSTEM, PROFILE_USER.format(
            title=title, name=person["name"], scenes=scenes, lines=lines),
            PROFILE_TOKENS)
        person["profile"], person["spanish"] = parse_profile(reply)
        print(f"  profile: {person['name']} "
              f"({len(person['windows'])} scenes"
              f"{', empty' if not person['profile'] else ''})")
    for person in people.values():
        # The first 30-second section that names them: the web plays it
        # as the profile's clip (their presentation, not a whole window).
        person["first_section"] = next(
            ([start, end] for start, end, text in sections
             if any(mentions(a, text) for a in person["aliases"])), None)
    return {"windows": summaries, "characters": people,
            "summary_version": SUMMARY_VERSION,
            "profile_version": PROFILE_VERSION}


def render(enrichment: dict, model: str) -> str:
    """The film's generated summaries file (<Title>.summaries.md, one
    chunk per section: the `markdown_sections` chunker). Summary headers
    keep the window's span and a profile names the first section that
    names the character, so the web plays the right clip of each (DEC-55).
    `model` is recorded in the cache, not in the indexed text."""
    from src.rag.sources.film import stamp

    summaries = enrichment["windows"]
    out: list[str] = []
    for w in summaries:
        out += [f"## {stamp(w['start'])} - {stamp(w['end'])} "
                f"(scene summary)", ""]
        if w["characters"]:
            out += [f"Characters: {', '.join(w['characters'])}", ""]
        out += [w["summary"], ""]
    for person in enrichment["characters"].values():
        first = summaries[person["first"]]
        times = ", ".join(stamp(summaries[i]["start"])
                          for i in person["windows"])
        out += [f"## Character: {person['name']}", ""]
        if person.get("spanish"):
            out += [f"Spanish names (given by the model): "
                    f"{person['spanish']}", ""]
        if person.get("first_section"):
            start, end = person["first_section"]
            out += [f"First named in the film at {stamp(start)} - "
                    f"{stamp(end)}.", ""]
        out += [f"First mentioned in the scene {stamp(first['start'])} - "
                f"{stamp(first['end'])}. Appears or is mentioned in the "
                f"scenes starting at {times}.", ""]
        if person.get("profile"):
            out += [person["profile"], ""]
    return "\n".join(out)


def cache_path(work: str, model: str) -> str:
    """Cache file of a film's enrichment by `model`."""
    return os.path.join(
        work, f"enrichment-{model.split('/')[-1].lower()}.json")


def newest_cache(work: str) -> Optional[str]:
    """The most recently written enrichment cache of a film, if any."""
    if not os.path.isdir(work):
        return None
    found = [os.path.join(work, n) for n in os.listdir(work)
             if n.startswith("enrichment-") and n.endswith(".json")]
    return max(found, key=os.path.getmtime) if found else None


def local_generator(model: str = DEFAULT_MODEL) -> Generate:
    """generate() backed by a local model (llm_sdk, greedy, official
    chat template with thinking off)."""
    from src.config import GenerationConfig
    from src.rag.generator import Generator

    generator = Generator(GenerationConfig(model=model))

    def generate(system: str, user: str, max_new_tokens: int) -> str:
        prompt = generator.tokenizer.apply_chat_template(
            [{"role": "system", "content": system},
             {"role": "user", "content": user}],
            tokenize=False, add_generation_prompt=True,
            enable_thinking=False,
        )
        return generator.complete(prompt, max_new_tokens)

    return generate


# OpenAI-compatible providers: base URL, key variable (in .env), and
# extra body fields (NVIDIA: reasoning off, measured in LLM_EXTERNO.md;
# with it on, Lightning spent every token thinking).
PROVIDERS = {
    "nvidia": ("https://integrate.api.nvidia.com/v1", "NVIDIA_API_KEY",
               {"chat_template_kwargs": {"enable_thinking": False}}),
}


def read_key(variable: str, env_file: str = ".env") -> str:
    """An API key from the environment or the .env file."""
    if os.environ.get(variable):
        return os.environ[variable]
    if os.path.isfile(env_file):
        with open(env_file, encoding="utf-8") as fh:
            for line in fh:
                name, _, value = line.strip().partition("=")
                if name == variable:
                    return value.strip().strip('"').strip("'")
    raise ValueError(f"{variable} is not set (environment or .env)")


def api_generator(model: str, provider: str = "nvidia",
                  retries: int = 6) -> Generate:
    """generate() backed by an OpenAI-compatible API (temperature 0).
    Rate limits (429) and server errors are retried with a growing
    wait; the free NVIDIA tier allows about 40 requests per minute."""
    base_url, variable, extra = PROVIDERS[provider]
    key = read_key(variable)

    def generate(system: str, user: str, max_new_tokens: int) -> str:
        body = {"model": model, "temperature": 0,
                "max_tokens": max_new_tokens,
                "messages": [{"role": "system", "content": system},
                             {"role": "user", "content": user}],
                **extra}
        request = urllib.request.Request(
            f"{base_url}/chat/completions", data=json.dumps(body).encode(),
            headers={"Authorization": f"Bearer {key}",
                     "Content-Type": "application/json"})
        for attempt in range(retries):
            try:
                with urllib.request.urlopen(request, timeout=120) as r:
                    reply = json.load(r)
                return str(reply["choices"][0]["message"].get("content")
                           or "")
            except urllib.error.HTTPError as exc:
                if exc.code != 429 and exc.code < 500 \
                        or attempt == retries - 1:
                    raise
            except (TimeoutError, urllib.error.URLError):
                if attempt == retries - 1:
                    raise
            time.sleep(5 * (attempt + 1))
        return ""

    return generate
