import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.request
from datetime import datetime
from typing import Any, Optional

from tqdm import tqdm

ENV_FILE = ".env"
CACHE_FILE = "data/output/judge_cache.json"
RESULTS_DIR = "bench/results/judge"
GEN_OUTPUT_DIR = "data/output/gen_bench"
IN_DOMAIN_SETS = ("public/docs", "public/code", "es/docs", "es/code")

JUDGE_PROMPT = """You grade answers of a retrieval-augmented assistant \
about the vLLM codebase.

QUESTION: {question}

REFERENCE ANSWER (correct): {reference}

CANDIDATE ANSWER: {answer}

The candidate may be in another language than the reference (e.g. \
Spanish); judge the meaning, not the language. Ignore citation markers \
like [1].
Score:
2 = correct: states the key facts of the reference, nothing wrong.
1 = partially correct: some key facts, or correct with a wrong detail.
0 = wrong, unrelated or a refusal.
Reply with JSON only: {{"score": 0|1|2, "reason": "<one short sentence>"}}"""


def load_env(path: str = ENV_FILE) -> None:
    """Load KEY=VALUE lines from a .env file into os.environ.

    Variables already set in the environment win. Values are never
    printed.
    """
    if not os.path.isfile(path):
        return
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.removeprefix("export ").split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip("'\""))


class JudgeError(RuntimeError):
    """The judge API could not be used."""


class Judge:
    """LLM-as-a-judge over an OpenAI-compatible API (Groq by default).

    Reads JUDGE_BASE_URL, JUDGE_MODEL and GROQ_API_KEY (or
    JUDGE_API_KEY) from the environment or the .env file. Every verdict
    is cached on disk, so re-running never spends quota twice.
    """

    def __init__(self, min_interval: float = 2.0,
                 max_retries: int = 5) -> None:
        load_env()
        self.base_url = os.environ.get("JUDGE_BASE_URL", "").rstrip("/")
        self.model = os.environ.get("JUDGE_MODEL", "")
        self.api_key = (os.environ.get("JUDGE_API_KEY")
                        or os.environ.get("GROQ_API_KEY", ""))
        missing = [name for name, value in (
            ("JUDGE_BASE_URL", self.base_url), ("JUDGE_MODEL", self.model),
            ("GROQ_API_KEY", self.api_key),
        ) if not value]
        if missing:
            raise JudgeError(f"Missing {', '.join(missing)} (see .env)")
        self.min_interval = min_interval
        self.max_retries = max_retries
        self._last_call = 0.0
        self.cache: dict[str, dict[str, Any]] = {}
        if os.path.isfile(CACHE_FILE):
            with open(CACHE_FILE, encoding="utf-8") as fh:
                self.cache = json.load(fh)

    def cache_key(self, question: str, reference: str, answer: str) -> str:
        """Key of a verdict: judge model + the three texts."""
        raw = "\x1f".join((self.model, question, reference, answer))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def save_cache(self) -> None:
        """Persist the verdict cache."""
        os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
        with open(CACHE_FILE, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(self.cache, fh, ensure_ascii=False, indent=1)

    def grade(self, question: str, reference: str,
              answer: str) -> dict[str, Any]:
        """Score an answer against the reference (cached).

        Returns:
            {"score": 0|1|2, "reason": str, "cached": bool}.
        """
        key = self.cache_key(question, reference, answer)
        if key in self.cache:
            return {**self.cache[key], "cached": True}
        content = self.complete(JUDGE_PROMPT.format(
            question=question, reference=reference, answer=answer
        ))
        verdict = parse_verdict(content)
        self.cache[key] = verdict
        return {**verdict, "cached": False}

    def complete(self, prompt: str) -> str:
        """One chat completion, with pacing and retries on rate limits."""
        body = {
            "model": self.model, "temperature": 0,
            "messages": [{"role": "user", "content": prompt}],
            "reasoning_effort": "low",
        }
        for attempt in range(self.max_retries):
            wait = self.min_interval - (time.monotonic() - self._last_call)
            if wait > 0:
                time.sleep(wait)
            self._last_call = time.monotonic()
            request = urllib.request.Request(
                f"{self.base_url}/chat/completions",
                data=json.dumps(body).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "User-Agent": "rag-judge",
                },
            )
            try:
                with urllib.request.urlopen(request, timeout=60) as resp:
                    data = json.load(resp)
                return str(data["choices"][0]["message"]["content"])
            except urllib.error.HTTPError as exc:
                if exc.code == 400 and "reasoning_effort" in body:
                    body.pop("reasoning_effort")
                    continue
                if exc.code == 429 or exc.code >= 500:
                    retry = float(exc.headers.get("retry-after") or 0)
                    time.sleep(max(retry, 5.0 * (attempt + 1)))
                    continue
                raise JudgeError(f"Judge API error {exc.code}") from exc
        raise JudgeError("Judge API kept failing (rate limit?)")


def parse_verdict(content: str) -> dict[str, Any]:
    """Extract {"score", "reason"} from the judge's reply."""
    match = re.search(r"\{.*\}", content, flags=re.DOTALL)
    try:
        data = json.loads(match.group()) if match else {}
    except json.JSONDecodeError:
        data = {}
    score = data.get("score")
    if score not in (0, 1, 2):
        found = re.search(r'"score"\s*:\s*([012])', content)
        score = int(found.group(1)) if found else 0
    return {"score": int(score), "reason": str(data.get("reason", ""))[:200]}


def run_judge(label: str, limit: Optional[int] = 10) -> dict[str, Any]:
    """Judge the in-domain answers of a gen_bench run.

    Args:
        label: gen_bench run whose answers are judged.
        limit: Answers judged per set (None = all). Refusals score 0
            without calling the API.

    Returns:
        Mean score per set (0-2) and the share of fully correct answers.
    """
    path = os.path.join(GEN_OUTPUT_DIR, label, "answers.json")
    with open(path, encoding="utf-8") as fh:
        rows = json.load(fh)
    judge = Judge()
    sets: dict[str, Any] = {}
    calls = 0
    try:
        for name in IN_DOMAIN_SETS:
            chosen = [r for r in rows if r["set"] == name][:limit]
            scores = []
            for row in tqdm(chosen, desc=f"judge {name}"):
                if row["not_found"]:
                    scores.append(0)
                    continue
                verdict = judge.grade(
                    row["question"], row["reference"], row["answer"]
                )
                calls += not verdict["cached"]
                row["judge"] = verdict
                scores.append(verdict["score"])
            if scores:
                sets[name] = {
                    "judged": len(scores),
                    "mean_score": round(sum(scores) / len(scores), 3),
                    "correct": round(scores.count(2) / len(scores), 3),
                }
    finally:
        judge.save_cache()

    run = {
        "label": label, "judge_model": judge.model, "limit": limit,
        "api_calls": calls,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "sets": sets,
    }
    os.makedirs(RESULTS_DIR, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    with open(os.path.join(RESULTS_DIR, f"{stamp}_{label}.json"), "w",
              encoding="utf-8", newline="\n") as fh:
        json.dump(run, fh, indent=2)
    print(f"\n{label} (judge {judge.model}, {calls} API calls)")
    for name, m in sets.items():
        print(f"  {name:<12} score {m['mean_score']:.2f}/2 | correct "
              f"{m['correct']:.2f}  (n={m['judged']})")
    return run
