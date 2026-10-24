"""Benchmark numbers for the web (read from bench/results/).

The web shows the retrieval quality of each domain (the recall bars of
the old Streamlit page) and the agent's results. Values come from the
latest recorded run of each suite, so the page always matches the
benchmark files in the repository.
"""
import json
import os
from typing import Any, Optional

RESULTS_DIR = "bench/results"
AGENT_DIR = "bench/results/agent"
# (label for the web, suite, dataset) of the recall bars.
RECALL_SETS = (
    ("vLLM docs", "public", "docs"),
    ("vLLM code", "public", "code"),
    ("XQuAD EN", "xquad", "en"),
    ("XQuAD ES", "xquad", "es"),
    ("CV EN", "cv", "en"),
    ("CV ES", "cv", "es"),
)


def load_runs(directory: str) -> list[dict[str, Any]]:
    """Every JSON run in a directory, oldest first (by file name)."""
    if not os.path.isdir(directory):
        return []
    runs = []
    for name in sorted(os.listdir(directory)):
        if name.endswith(".json"):
            with open(os.path.join(directory, name), encoding="utf-8") as fh:
                runs.append(json.load(fh))
    return runs


def latest(runs: list[dict[str, Any]], suite: str
           ) -> Optional[dict[str, Any]]:
    """The newest retrieval run of a suite with the base profile."""
    for run in reversed(runs):
        if run.get("suite", "public") == suite \
                and run.get("profile", "default") == "default":
            return run
    return None


def latest_metrics(results_dir: str = RESULTS_DIR,
                   agent_dir: str = AGENT_DIR) -> dict[str, Any]:
    """Recall@k per domain and the latest agent comparison.

    Returns:
        {"recall": [{label, run, recall_at_k}], "agent": {...} | None}
    """
    runs = load_runs(results_dir)
    recall = []
    for label, suite, name in RECALL_SETS:
        run = latest(runs, suite)
        if run and name in run.get("datasets", {}):
            recall.append({
                "label": label, "run": run["label"],
                "recall_at_k": run["datasets"][name]["recall_at_k"],
            })
    agent_runs = [r for r in load_runs(agent_dir)
                  if r.get("profile", "default") == "default"]
    agent = None
    if agent_runs:
        run = agent_runs[-1]
        agent = {
            "run": run["label"], "model": run["generator"],
            "results": {mode: {
                group: {"contains_answer": m["contains_answer"],
                        "seconds_per_answer": m["seconds_per_answer"]}
                for group, m in groups.items()
            } for mode, groups in run["results"].items()},
        }
    return {"recall": recall, "agent": agent}
