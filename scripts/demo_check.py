"""Basic questions check (Phase 10): send everyday questions about every
domain to the running web API, as a visitor would, and mark the misses.
A miss points to a general cause to fix, not to a per-question patch.

Usage:
    uv run python scripts/demo_check.py [--url URL] [--model ID]
        [--direct] [--only ID,ID] [--pause SECONDS]

Each question (bench/datasets/demo/questions.json) passes when it is
answered from its domain and the answer holds one of its words (or, for
an out-of-domain one, when it is refused). Results go to
data/output/demo/<time>.json. Spends ~2-4 API requests per question with
the agent: keep an eye on the free daily quota.
"""
import argparse
import json
import os
import sys
import time
import unicodedata
from datetime import datetime
from typing import Any, Optional

import httpx

QUESTIONS = "bench/datasets/demo/questions.json"
OUTPUT_DIR = "data/output/demo"
DEFAULT_URL = "http://127.0.0.1:8000"


def plain(text: str) -> str:
    """Lowercase, without accents, and one kind of minus sign."""
    text = text.replace("−", "-").replace("–", "-").lower()
    return unicodedata.normalize("NFKD", text).encode(
        "ascii", "ignore").decode()


def ask(client: httpx.Client, url: str, body: dict[str, Any]
        ) -> dict[str, Any]:
    """One /chat request; the 'done' event (or {'error': ...})."""
    event = ""
    with client.stream("POST", f"{url}/chat", json=body) as response:
        for line in response.iter_lines():
            if line.startswith("event: "):
                event = line[7:]
            elif line.startswith("data: ") and event in ("done", "error"):
                data = json.loads(line[6:])
                return data if event == "done" else {"error": data}
    return {"error": "no answer"}


def check(item: dict[str, Any], out: dict[str, Any]) -> Optional[str]:
    """Why a question missed, or None when it passed."""
    if "error" in out:
        return f"error: {out['error']}"
    answer = plain(out.get("answer") or "")
    if item.get("not_found"):
        if not out.get("not_found"):
            return "answered (should refuse)"
        if any(plain(word) in answer for word in item.get("none", [])):
            return "a forbidden word is in the answer"
        return None
    if out.get("not_found"):
        return "not found"
    expected = item["domain"]
    if out.get("domain") not in (
            expected if isinstance(expected, list) else [expected]):
        return f"domain {out.get('domain')} (expected {expected})"
    if not any(plain(word) in answer for word in item["any"]):
        return f"none of {item['any']} in the answer"
    if any(plain(word) in answer for word in item.get("none", [])):
        return "a forbidden word is in the answer"
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--url", default=os.environ.get(
        "DEMO_URL", DEFAULT_URL))
    parser.add_argument("--model", default=None,
                        help="model id from /config (default: the API's)")
    parser.add_argument("--direct", action="store_true",
                        help="without the agent (default: with it)")
    parser.add_argument("--only", default="", help="question ids")
    parser.add_argument("--pause", type=float, default=10.0,
                        help="seconds between questions (rate limits)")
    args = parser.parse_args()

    with open(QUESTIONS, encoding="utf-8") as fh:
        questions = json.load(fh)["questions"]
    if args.only:
        wanted = set(args.only.split(","))
        questions = [q for q in questions if q["id"] in wanted]
    if args.direct:
        # Follow-ups that need the conversation: only the agent has it.
        questions = [q for q in questions if not q.get("agent_only")]
    url = args.url.rstrip("/")
    sessions: dict[str, str] = {}
    rows = []
    with httpx.Client(timeout=180) as client:
        for n, item in enumerate(questions):
            if n:
                time.sleep(args.pause)
            body: dict[str, Any] = {"message": item["q"],
                                    "agent": not args.direct}
            if args.model:
                body["model"] = args.model
            if item.get("session") in sessions:
                body["session_id"] = sessions[item["session"]]
            start = time.perf_counter()
            out = ask(client, url, body)
            seconds = time.perf_counter() - start
            if item.get("session") and out.get("session_id"):
                sessions[item["session"]] = out["session_id"]
            miss = check(item, out)
            trace = out.get("trace") or {}
            rows.append({"id": item["id"], "q": item["q"], "ok": miss is None,
                         "miss": miss, "domain": out.get("domain"),
                         "model": trace.get("model"),
                         "fallback_from": trace.get("fallback_from"),
                         "seconds": round(seconds, 1),
                         "answer": out.get("answer")})
            mark = "ok  " if miss is None else "MISS"
            print(f"{mark} {item['id']:16} {seconds:5.1f}s "
                  f"{out.get('domain') or '-':6} {miss or ''}", flush=True)
    passed = sum(r["ok"] for r in rows)
    print(f"\n{passed}/{len(rows)} passed")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    path = os.path.join(OUTPUT_DIR,
                        datetime.now().strftime("%Y%m%d-%H%M%S") + ".json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"url": url, "agent": not args.direct,
                   "model": args.model, "rows": rows}, fh,
                  ensure_ascii=False, indent=1)
    print(f"Saved {path}")
    return 0 if passed == len(rows) else 1


if __name__ == "__main__":
    sys.exit(main())
