"""Calibration of the out-of-domain gate, per domain.

The gate (search_for_generation) answers "not found" when the best
cross-encoder score of the retrieved sources is below a threshold. This
measures that score, exactly as the gate computes it, for questions the
domain should answer (its benchmark sets) and questions it should reject
(the out-of-domain set and the benchmark sets of the other domains), and
prints the trade-off of candidate thresholds.
"""
import json
import os
from datetime import datetime
from typing import Any, Optional

import numpy as np
from tqdm import tqdm

from src.config import RagConfig, get_config
from src.evaluation.bench import SUITES
from src.evaluation.gen_bench import OOD_PATH
from src.evaluation.routing import SETS
from src.rag.retriever import Retriever
from src.rag.sources.cv import ood_questions

RESULTS_DIR = "bench/results/gate"
CANDIDATES = (-6.0, -5.0, -4.0, -3.0, -2.0, -1.0, 0.0, 1.0)


def load_set(suite: str, name: str) -> list[str]:
    """Questions of a benchmark dataset."""
    folder, suffix = SUITES[suite]
    path = os.path.join(folder, "UnansweredQuestions",
                        f"dataset_{name}_{suffix}.json")
    with open(path, encoding="utf-8") as fh:
        return [q["question"] for q in json.load(fh)["rag_questions"]]


def question_groups(domain: str) -> dict[str, tuple[bool, list[str]]]:
    """Question groups to score: name -> (should pass, questions)."""
    groups: dict[str, tuple[bool, list[str]]] = {}
    for suite, name, expected in SETS:
        groups[f"{suite}/{name}"] = (expected == domain,
                                     load_set(suite, name))
    with open(OOD_PATH, encoding="utf-8") as fh:
        for q in json.load(fh)["questions"]:
            key = f"ood/{q['lang']}-{q['kind']}"
            groups.setdefault(key, (False, []))[1].append(q["question"])
    # Questions about Chrystian the CV does not answer: "near" negatives
    # for the CV domain (and far ones for the rest).
    for q in ood_questions():
        key = f"cv-ood/{q['lang']}"
        groups.setdefault(key, (False, []))[1].append(q["question"])
    return groups


def gate_score(retriever: Retriever, question: str, k: int) -> float:
    """The score search_for_generation compares with the threshold."""
    sources = retriever.search_smart(question, k)
    return retriever.top_relevance(question, sources) if sources \
        else float("-inf")


def run_gate_scores(domain: str, k: int = 5, label: str = "run",
                    limit: Optional[int] = None,
                    config: Optional[RagConfig] = None) -> dict[str, Any]:
    """Score every group against one domain and save the distribution.

    Args:
        domain: Domain whose gate is calibrated.
        k: Sources retrieved (the gen-bench and web use k = 5).
        label: Short name for this run.
        limit: Questions per group (None = all).
        config: Pipeline configuration (defaults to rag.toml).

    Returns:
        The run dict (also saved to bench/results/gate/).
    """
    config = config or get_config()
    retriever = Retriever.from_store(domain, config=config)
    retriever.load_reranker()

    groups: dict[str, Any] = {}
    for name, (positive, questions) in question_groups(domain).items():
        questions = questions[:limit] if limit else questions
        scores = [gate_score(retriever, q, k)
                  for q in tqdm(questions, desc=name)]
        groups[name] = {"positive": positive, "scores": scores}

    run: dict[str, Any] = {
        "label": label, "domain": domain, "k": k, "limit": limit,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "reranker": config.retrieval.reranker_model,
        "current_threshold": config.retrieval.relevance_threshold,
        "groups": groups,
    }
    os.makedirs(RESULTS_DIR, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = os.path.join(RESULTS_DIR, f"{stamp}_{domain}_{label}.json")
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(run, fh)
    print(f"Saved gate scores to {path}")
    print_gate_table(run)
    return run


def print_gate_table(run: dict[str, Any]) -> None:
    """Percentiles per group and pass rate for each candidate threshold.

    For groups that should pass, the rate is the share accepted; for the
    others, the share accepted is the error (it should be 0).
    """
    header = (f"{'group':<14} {'n':>5} {'p10':>6} {'p50':>6} {'p90':>6}  "
              + " ".join(f"{t:>6.1f}" for t in CANDIDATES))
    print(f"\nGate scores for '{run['domain']}' (k={run['k']}); columns = "
          f"share of questions with score >= threshold")
    print(header)
    print("-" * len(header))
    for name, group in run["groups"].items():
        scores = np.array(group["scores"], dtype=float)
        p10, p50, p90 = np.percentile(scores, [10, 50, 90])
        rates = " ".join(f"{(scores >= t).mean():>6.2f}" for t in CANDIDATES)
        mark = "+" if group["positive"] else "-"
        print(f"{mark} {name:<12} {len(scores):>5} {p10:>6.1f} {p50:>6.1f} "
              f"{p90:>6.1f}  {rates}")
