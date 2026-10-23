"""Agent vs direct access (Phase 5, D7).

Every question is answered twice: through the agent (session memory,
question rewriting, tool calls) and through the direct flow (each
question on its own). Sets:
    conversations   bench/datasets/conversations: multi-turn dialogues
                    whose follow-ups need the earlier turns.
    single          one-question sets: CV (en/es), an even sample of
                    XQuAD (en/es) and of the 42 vLLM docs/code sets.
Metrics per set and mode: contains_answer (the reference span is in the
answer), token F1 (vLLM references are long), "not found" rate and
seconds per answer; for the agent also the share of turns where the
model made a valid tool call (no fallback) and the planning steps.
Results go to bench/results/agent/.
"""
import json
import os
import time
from datetime import datetime
from typing import Any, Optional

from tqdm import tqdm

from src.agent.agent import Agent
from src.config import RagConfig, get_config
from src.evaluation.bench import git_revision
from src.evaluation.gen_bench import (
    contains_answer, even_sample, load_questions, token_f1,
)
from src.rag.generator import Generator
from src.rag.pipeline import RagPipeline
from src.server.tools import RagTools

RESULTS_DIR = "bench/results/agent"
OUTPUT_DIR = "data/output/agent_bench"
CONVERSATIONS = "bench/datasets/conversations/conversations.json"
# (dataset suite, dataset, questions asked: an even sample)
SINGLE_SETS = (
    ("cv", "en", 30), ("cv", "es", 30),
    ("xquad", "en", 50), ("xquad", "es", 50),
    ("public", "docs", 25), ("public", "code", 25),
)


def score(text: str, reference: str, not_found: bool) -> dict[str, Any]:
    """Answer metrics against a reference."""
    return {
        "contains": (not not_found) and contains_answer(text, reference),
        "f1": token_f1(text, reference),
        "not_found": not_found,
    }


def ask(mode: str, agent: Agent, pipeline: RagPipeline, question: str,
        k: int) -> dict[str, Any]:
    """Answer one question in a mode; returns text, flags and timing."""
    start = time.perf_counter()
    if mode == "agent":
        a = agent.ask(question)
        return {"answer": a.text, "not_found": a.not_found,
                "domain": a.domain, "queries": a.queries,
                "steps": a.steps, "fallback": a.fallback,
                "seconds": time.perf_counter() - start}
    r = pipeline.answer(question, k=k)
    return {"answer": r.text, "not_found": r.not_found,
            "domain": pipeline.answered_domain(),
            "seconds": time.perf_counter() - start}


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Mean metrics of a group of answered rows."""
    n = len(rows)
    out: dict[str, Any] = {
        "questions": n,
        "contains_answer": round(sum(r["contains"] for r in rows) / n, 4),
        "f1": round(sum(r["f1"] for r in rows) / n, 4),
        "not_found": round(sum(r["not_found"] for r in rows) / n, 4),
        "seconds_per_answer": round(sum(r["seconds"] for r in rows) / n, 2),
    }
    if rows and "fallback" in rows[0]:
        out["tool_call_rate"] = round(
            sum(not r["fallback"] for r in rows) / n, 4)
        out["steps"] = round(sum(r["steps"] for r in rows) / n, 2)
    return out


def run_conversations(mode: str, agent: Agent, pipeline: RagPipeline,
                      k: int) -> list[dict[str, Any]]:
    """Every conversation, turn by turn, with a fresh session each."""
    with open(CONVERSATIONS, encoding="utf-8") as fh:
        conversations = json.load(fh)["conversations"]
    rows = []
    for conv in tqdm(conversations, desc=f"conversations ({mode})"):
        agent.session.clear()
        for i, turn in enumerate(conv["turns"]):
            out = ask(mode, agent, pipeline, turn["question"], k)
            rows.append({
                "set": f"conversations/{'first' if i == 0 else 'follow-up'}",
                "conversation": conv["id"], "turn": i,
                "question": turn["question"], "reference": turn["answer"],
                **out, **score(out["answer"], turn["answer"],
                               out["not_found"]),
            })
    return rows


def run_single(mode: str, agent: Agent, pipeline: RagPipeline,
               k: int) -> list[dict[str, Any]]:
    """The one-question sets (no history)."""
    rows = []
    for suite, name, n in SINGLE_SETS:
        questions = even_sample(load_questions(suite, name, None), n)
        for q in tqdm(questions, desc=f"{suite}/{name} ({mode})"):
            agent.session.clear()
            out = ask(mode, agent, pipeline, q["question"], k)
            rows.append({
                "set": f"{suite}/{name}", "question": q["question"],
                "reference": q["answer"], **out,
                **score(out["answer"], q["answer"], out["not_found"]),
            })
    return rows


def run_agent_bench(label: str, k: int = 5, sets: str = "all",
                    config: Optional[RagConfig] = None) -> dict[str, Any]:
    """Run the agent and the direct flow over the benchmark sets.

    Args:
        label: Short name for this run.
        k: Sources per search / answer.
        sets: "conversations", "single" or "all".
        config: Pipeline configuration (the profile picks the LLM).

    Returns:
        The run dict (also saved to bench/results/agent/).
    """
    config = config or get_config()
    tools = RagTools.load(config, Generator(config.generation))
    agent = Agent(tools, k=k)
    pipeline = tools.get_pipeline()

    details: list[dict[str, Any]] = []
    results: dict[str, Any] = {}
    for mode in ("agent", "direct"):
        rows: list[dict[str, Any]] = []
        if sets in ("all", "conversations"):
            rows += run_conversations(mode, agent, pipeline, k)
        if sets in ("all", "single"):
            rows += run_single(mode, agent, pipeline, k)
        for row in rows:
            row["mode"] = mode
        details += rows
        results[mode] = {
            group: aggregate([r for r in rows if r["set"] == group])
            for group in dict.fromkeys(r["set"] for r in rows)
        }

    run: dict[str, Any] = {
        "label": label, "k": k, "sets": sets,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        **git_revision(), "profile": config.profile,
        "generator": config.generation.model,
        "device": config.models.resolved_device(),
        "results": results,
    }
    os.makedirs(RESULTS_DIR, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    with open(os.path.join(RESULTS_DIR, f"{stamp}_{label}.json"), "w",
              encoding="utf-8", newline="\n") as fh:
        json.dump(run, fh, indent=2)
    out_dir = os.path.join(OUTPUT_DIR, label)
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "answers.json"), "w",
              encoding="utf-8", newline="\n") as fh:
        json.dump(details, fh, indent=2, ensure_ascii=False)
    print_agent_table(run)
    return run


def print_agent_table(run: dict[str, Any]) -> None:
    """Agent vs direct, per set."""
    print(f"\n{run['label']} ({run['generator']}, k={run['k']})")
    header = (f"{'set':<26} {'contains a/d':>13} {'not found a/d':>14} "
              f"{'s/answer a/d':>13} {'tool calls':>10}")
    print(header)
    print("-" * len(header))
    agent, direct = run["results"]["agent"], run["results"]["direct"]
    for group, a in agent.items():
        d = direct.get(group, {})
        print(f"{group:<26} "
              f"{a['contains_answer']:>6.2f}/{d.get('contains_answer', 0):.2f}"
              f" {a['not_found']:>7.2f}/{d.get('not_found', 0):.2f}"
              f" {a['seconds_per_answer']:>6.1f}/"
              f"{d.get('seconds_per_answer', 0):.1f}"
              f" {a.get('tool_call_rate', 0):>10.2f}")
