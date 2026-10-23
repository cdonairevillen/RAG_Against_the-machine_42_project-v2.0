"""Routing benchmark: does an unfiltered question reach its domain?

Every benchmark question is asked to the DomainRouter with no domain
filter (all indexed domains compete). Measured per dataset: how often
the winning domain is the right one, and the Recall@k of the routed
results with the 42 evaluator (a wrongly routed question scores 0).
"""
import json
import os
import time
from collections import Counter
from datetime import datetime
from typing import Any, Optional

from tqdm import tqdm

from src.config import RagConfig, get_config
from src.evaluation.bench import SUITES, git_revision
from src.evaluation.evaluator import Evaluator
from src.models import MinimalSearchResults, RagDataset, StudentSearchResults
from src.rag.router import DomainRouter

RESULTS_DIR = "bench/results/route"
OUTPUT_DIR = "data/output/route_bench"
# (suite, dataset, expected domain)
SETS = (
    ("public", "docs", "vllm"),
    ("public", "code", "vllm"),
    ("es", "docs", "vllm"),
    ("es", "code", "vllm"),
    ("xquad", "en", "xquad"),
    ("xquad", "es", "xquad"),
    ("cv", "en", "cv"),
    ("cv", "es", "cv"),
)


def run_set(router: DomainRouter, suite: str, name: str, expected: str,
            k: int, output_dir: str,
            limit: Optional[int]) -> dict[str, Any]:
    """Route and evaluate one dataset.

    Returns:
        Dict with routing accuracy, the domains chosen, recall_at_k,
        seconds and questions.
    """
    folder, suffix = SUITES[suite]
    filename = f"dataset_{name}_{suffix}.json"
    with open(os.path.join(folder, "UnansweredQuestions", filename),
              encoding="utf-8") as fh:
        questions = RagDataset.model_validate_json(fh.read()).rag_questions
    questions = questions[:limit] if limit else questions

    chosen: Counter[str] = Counter()
    results: list[MinimalSearchResults] = []
    start = time.perf_counter()
    for q in tqdm(questions, desc=f"{suite}/{name}"):
        sources = router.search_smart(q.question, k=k)
        chosen[router.last_route[0][0]] += 1
        results.append(MinimalSearchResults(
            question_id=q.question_id, question_str=q.question,
            retrieved_sources=sources,
        ))
    seconds = time.perf_counter() - start

    os.makedirs(output_dir, exist_ok=True)
    student = os.path.join(output_dir, f"{suite}_{filename}")
    with open(student, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(StudentSearchResults(search_results=results, k=k)
                 .model_dump_json(indent=2))
    metrics = Evaluator().compute_recall(
        student, os.path.join(folder, "AnsweredQuestions", filename), k=k
    )
    return {
        "expected": expected,
        "routing_accuracy": round(chosen[expected] / len(questions), 4),
        "chosen": dict(chosen),
        "recall_at_k": {
            str(kv): round(v, 4) for kv, v in metrics["recall_at_k"].items()
        },
        "seconds": round(seconds, 2),
        "questions": len(questions),
    }


def run_route_bench(label: str, k: int = 10, limit: Optional[int] = None,
                    config: Optional[RagConfig] = None) -> dict[str, Any]:
    """Route every benchmark set through all domains and record it.

    Args:
        label: Short name for this run.
        k: Sources retrieved per question.
        limit: Questions per dataset (None = all).
        config: Pipeline configuration (defaults to rag.toml).

    Returns:
        The run dict (also saved to bench/results/route/).
    """
    config = config or get_config()
    router = DomainRouter.from_store(config=config)
    run: dict[str, Any] = {
        "label": label,
        "k": k,
        "limit": limit,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        **git_revision(),
        "domains": router.domains,
        "profile": config.profile,
        "retrieval": config.retrieval.model_dump(),
        "device": config.models.resolved_device(),
        "sets": {},
    }
    output_dir = os.path.join(OUTPUT_DIR, label)
    for suite, name, expected in SETS:
        run["sets"][f"{suite}/{name}"] = run_set(
            router, suite, name, expected, k, output_dir, limit
        )

    os.makedirs(RESULTS_DIR, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = os.path.join(RESULTS_DIR, f"{stamp}_{label}.json")
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(run, fh, indent=2)
    print(f"Saved routing run to {path}")
    print_route_table(run)
    return run


def print_route_table(run: dict[str, Any]) -> None:
    """Print routing accuracy and routed recall per dataset."""
    header = (f"{'set':<14} {'n':>5} {'routed ok':>10} "
              f"{'recall @1/@3/@5/@10':<24} {'chosen'}")
    print("\n" + header)
    print("-" * len(header))
    for name, row in run["sets"].items():
        recall = "/".join(
            f"{row['recall_at_k'][kv]:.2f}" for kv in ("1", "3", "5", "10")
            if kv in row["recall_at_k"]
        )
        print(f"{name:<14} {row['questions']:>5} "
              f"{row['routing_accuracy']:>10.3f} {recall:<24} "
              f"{row['chosen']}")
