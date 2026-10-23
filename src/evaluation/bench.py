import json
import os
import subprocess
import time
from datetime import datetime
from typing import Any, Optional

from tqdm import tqdm

from src.config import RagConfig, get_config
from src.evaluation.evaluator import Evaluator
from src.models import MinimalSearchResults, RagDataset, StudentSearchResults
from src.retriever import Retriever

# Dataset suites: (directory, filename suffix). "public" is the official
# 42 benchmark; "es" is the Spanish complement (same ground truth,
# translated questions) used to measure multilingual retrieval; "en" is
# the same 20 questions in English, for a like-for-like comparison.
SUITES = {
    "public": ("data/datasets", "public"),
    "es": ("bench/datasets/es", "es"),
    "en": ("bench/datasets/en", "en"),
    "xquad": ("bench/datasets/xquad", "xquad"),
    "cv": ("bench/datasets/cv", "cv"),
}
# Datasets of each suite (default: the 42 docs/code pair) and the corpus
# its ground truth points into (default: the --domain argument). XQuAD:
# the same questions in English and Spanish over its own domain.
SUITE_DATASETS = {"xquad": ("en", "es"), "cv": ("en", "es")}
SUITE_DOMAINS = {"xquad": "xquad", "cv": "cv"}
RESULTS_DIR = "bench/results"
# Retrieval path measured (the official 42 one). Kept in result names
# and records so they stay comparable with the earlier runs.
MODE = "smart"
OUTPUT_DIR = "data/output/bench"
DATASET_NAMES = ("docs", "code")


def git_revision() -> dict[str, Any]:
    """Return the current commit hash and whether the tree is dirty.

    Returns:
        Dict with 'commit' (short hash or 'unknown') and 'dirty'.
    """
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        status = subprocess.run(
            ["git", "status", "--porcelain", "--", "src"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        return {"commit": commit, "dirty": bool(status)}
    except (OSError, subprocess.CalledProcessError):
        return {"commit": "unknown", "dirty": True}


def run_dataset(retriever: Retriever, name: str, k: int,
                output_dir: str, suite: str = "public") -> dict[str, Any]:
    """Retrieve and evaluate one public dataset.

    Args:
        retriever: Loaded Retriever (with reranker).
        name: Dataset name, 'docs' or 'code'.
        k: Number of sources retrieved per question.
        output_dir: Where the StudentSearchResults JSON is written.

    Returns:
        Dict with 'recall_at_k', 'seconds' and 'questions'.
    """
    datasets_dir, suffix = SUITES[suite]
    filename = f"dataset_{name}_{suffix}.json"
    unanswered = os.path.join(datasets_dir, "UnansweredQuestions", filename)
    answered = os.path.join(datasets_dir, "AnsweredQuestions", filename)

    with open(unanswered, "r", encoding="utf-8") as fh:
        dataset = RagDataset.model_validate_json(fh.read())

    search = retriever.search_smart
    results: list[MinimalSearchResults] = []
    start = time.perf_counter()
    for question in tqdm(dataset.rag_questions, desc=f"{name} ({MODE})"):
        results.append(MinimalSearchResults(
            question_id=question.question_id,
            question_str=question.question,
            retrieved_sources=search(question.question, k=k),
        ))
    seconds = time.perf_counter() - start

    os.makedirs(output_dir, exist_ok=True)
    student_path = os.path.join(output_dir, filename)
    with open(student_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(StudentSearchResults(
            search_results=results, k=k
        ).model_dump_json(indent=2))

    metrics = Evaluator().compute_recall(student_path, answered, k=k)
    return {
        "recall_at_k": {
            str(kv): round(v, 4) for kv, v in metrics["recall_at_k"].items()
        },
        "seconds": round(seconds, 2),
        "questions": metrics["total"],
    }


def load_history(results_dir: str = RESULTS_DIR) -> list[dict[str, Any]]:
    """Load every saved bench run, oldest first.

    Args:
        results_dir: Directory holding bench result JSON files.

    Returns:
        List of bench run dicts.
    """
    if not os.path.isdir(results_dir):
        return []
    runs: list[dict[str, Any]] = []
    for filename in sorted(os.listdir(results_dir)):
        if filename.endswith(".json"):
            path = os.path.join(results_dir, filename)
            with open(path, "r", encoding="utf-8") as fh:
                runs.append(json.load(fh))
    return runs


def print_table(runs: list[dict[str, Any]], suite: str = "public") -> None:
    """Print a comparison table of bench runs.

    Args:
        runs: Bench run dicts as returned by load_history().
    """
    names = SUITE_DATASETS.get(suite, DATASET_NAMES)
    header = (
        f"{'label':<28} {'mode':<10} "
        f"{names[0] + ' @1/@3/@5/@10':<24} "
        f"{names[1] + ' @1/@3/@5/@10':<24} "
        f"{'time (s)' if names != DATASET_NAMES else 'time d/c (s)':<12}"
    )
    print("\n" + header)
    print("-" * len(header))
    for run in runs:
        if run.get("suite", "public") != suite:
            continue
        cells = []
        for name in names:
            recall = run["datasets"][name]["recall_at_k"]
            cells.append("/".join(
                f"{recall[kv]:.2f}" for kv in ("1", "3", "5", "10")
                if kv in recall
            ))
        times = "/".join(
            f"{run['datasets'][n]['seconds']:.0f}" for n in names
        )
        print(
            f"{run['label']:<28} {run['mode']:<10} "
            f"{cells[0]:<24} {cells[1]:<24} {times:<12}"
        )


def run_bench(label: str, k: int = 10,
              suite: str = "public",
              domain: str = "vllm", config: Optional[RagConfig] = None,
              save: bool = True) -> dict[str, Any]:
    """Run the public 42 datasets end to end and record the result.

    Args:
        label: Short name for this run (e.g. 'baseline', 'fix-b1').
        k: Number of sources retrieved per question.
        domain: Indexed source the datasets are about.
        config: Pipeline configuration (defaults to rag.toml).
        save: When True, writes the run to bench/results/.

    Returns:
        The bench run dict.

    Raises:
        ValueError: If suite is unknown.
    """
    if suite not in SUITES:
        raise ValueError(f"suite must be one of {list(SUITES)}")

    config = config or get_config()
    domain = SUITE_DOMAINS.get(suite, domain)
    retriever = Retriever.from_store(domain, config=config)
    retriever.load_reranker()

    run: dict[str, Any] = {
        "label": label,
        "mode": MODE,
        "suite": suite,
        "k": k,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        **git_revision(),
        "domain": domain,
        "profile": config.profile,
        "chunking": config.chunking.model_dump(),
        "chunkers": config.source(domain).chunkers,
        "retrieval": config.retrieval.model_dump(),
        "device": config.models.resolved_device(),
        "datasets": {},
    }
    output_dir = os.path.join(OUTPUT_DIR, f"{label}_{MODE}_{suite}")
    for name in SUITE_DATASETS.get(suite, DATASET_NAMES):
        run["datasets"][name] = run_dataset(
            retriever, name, k, output_dir, suite
        )

    if save:
        os.makedirs(RESULTS_DIR, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        tag = MODE if suite == "public" else f"{MODE}_{suite}"
        path = os.path.join(RESULTS_DIR, f"{stamp}_{label}_{tag}.json")
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(run, fh, indent=2)
        print(f"Saved bench run to {path}")

    print_table(load_history() if save else [run], suite)
    return run
