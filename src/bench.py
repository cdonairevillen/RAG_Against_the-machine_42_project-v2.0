import json
import os
import subprocess
import time
from datetime import datetime
from typing import Any

from tqdm import tqdm

from src.evaluator import Evaluator
from src.models import MinimalSearchResults, RagDataset, StudentSearchResults
from src.retriever import Retriever

DATASETS_DIR = "data/datasets"
RESULTS_DIR = "bench/results"
OUTPUT_DIR = "data/output/bench"
DATASET_NAMES = ("docs", "code")
MODES = ("smart", "generation")


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


def run_dataset(retriever: Retriever, name: str, mode: str, k: int,
                output_dir: str) -> dict[str, Any]:
    """Retrieve and evaluate one public dataset.

    Args:
        retriever: Loaded Retriever (with reranker).
        name: Dataset name, 'docs' or 'code'.
        mode: 'smart' (search_smart) or 'generation'
            (search_for_generation).
        k: Number of sources retrieved per question.
        output_dir: Where the StudentSearchResults JSON is written.

    Returns:
        Dict with 'recall_at_k', 'seconds' and 'questions'.
    """
    filename = f"dataset_{name}_public.json"
    unanswered = os.path.join(DATASETS_DIR, "UnansweredQuestions", filename)
    answered = os.path.join(DATASETS_DIR, "AnsweredQuestions", filename)

    with open(unanswered, "r", encoding="utf-8") as fh:
        dataset = RagDataset.model_validate_json(fh.read())

    search = (
        retriever.search_smart if mode == "smart"
        else retriever.search_for_generation
    )
    results: list[MinimalSearchResults] = []
    start = time.perf_counter()
    for question in tqdm(dataset.rag_questions, desc=f"{name} ({mode})"):
        results.append(MinimalSearchResults(
            question_id=question.question_id,
            question_str=question.question,
            retrieved_sources=search(question.question, k=k),
        ))
    seconds = time.perf_counter() - start

    os.makedirs(output_dir, exist_ok=True)
    student_path = os.path.join(output_dir, filename)
    with open(student_path, "w", encoding="utf-8") as fh:
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


def print_table(runs: list[dict[str, Any]]) -> None:
    """Print a comparison table of bench runs.

    Args:
        runs: Bench run dicts as returned by load_history().
    """
    header = (
        f"{'label':<28} {'mode':<10} "
        f"{'docs @1/@3/@5/@10':<24} {'code @1/@3/@5/@10':<24} "
        f"{'time d/c (s)':<12}"
    )
    print("\n" + header)
    print("-" * len(header))
    for run in runs:
        cells = []
        for name in DATASET_NAMES:
            recall = run["datasets"][name]["recall_at_k"]
            cells.append("/".join(
                f"{recall[kv]:.2f}" for kv in ("1", "3", "5", "10")
                if kv in recall
            ))
        times = "/".join(
            f"{run['datasets'][n]['seconds']:.0f}" for n in DATASET_NAMES
        )
        print(
            f"{run['label']:<28} {run['mode']:<10} "
            f"{cells[0]:<24} {cells[1]:<24} {times:<12}"
        )


def run_bench(label: str, mode: str = "smart", k: int = 10,
              processed_dir: str = "data/processed",
              save: bool = True) -> dict[str, Any]:
    """Run the public 42 datasets end to end and record the result.

    Args:
        label: Short name for this run (e.g. 'baseline', 'fix-b1').
        mode: 'smart' or 'generation'.
        k: Number of sources retrieved per question.
        processed_dir: Directory with the built indices.
        save: When True, writes the run to bench/results/.

    Returns:
        The bench run dict.

    Raises:
        ValueError: If mode is not one of MODES.
    """
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}, got '{mode}'")

    retriever = Retriever.from_disk(processed_dir)
    retriever.load_reranker()

    run: dict[str, Any] = {
        "label": label,
        "mode": mode,
        "k": k,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        **git_revision(),
        "datasets": {},
    }
    output_dir = os.path.join(OUTPUT_DIR, f"{label}_{mode}")
    for name in DATASET_NAMES:
        run["datasets"][name] = run_dataset(
            retriever, name, mode, k, output_dir
        )

    if save:
        os.makedirs(RESULTS_DIR, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        path = os.path.join(RESULTS_DIR, f"{stamp}_{label}_{mode}.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(run, fh, indent=2)
        print(f"Saved bench run to {path}")

    print_table(load_history() if save else [run])
    return run
