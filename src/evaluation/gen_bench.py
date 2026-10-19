import json
import os
import re
from collections import Counter
from datetime import datetime
from typing import Any, Optional

from tqdm import tqdm

from src.evaluation.bench import SUITES, git_revision
from src.config import RagConfig, get_config
from src.evaluation.evaluator import Evaluator
from src.generator import Generator
from src.language import ARTICLES, detect_language, words
from src.models import MinimalSource
from src.rag import RagPipeline
from src.retriever import Retriever

RESULTS_DIR = "bench/results/gen"
OUTPUT_DIR = "data/output/gen_bench"
OOD_PATH = "bench/datasets/ood/questions.json"

FILE_PATTERN = re.compile(r"[\w./-]+\.(?:py|pyi|md|rst|txt)\b")
INDEX_CITATION = re.compile(r"\[(\d{1,2})\]")


def normalise_tokens(text: str) -> list[str]:
    """SQuAD-style normalisation: lowercase, no punctuation or articles."""
    return [t for t in words(text) if t not in ARTICLES]


def token_f1(prediction: str, reference: str) -> float:
    """Token-overlap F1 between a prediction and a reference answer."""
    pred, ref = normalise_tokens(prediction), normalise_tokens(reference)
    common = sum((Counter(pred) & Counter(ref)).values())
    if not pred or not ref or common == 0:
        return 0.0
    precision, recall = common / len(pred), common / len(ref)
    return 2 * precision * recall / (precision + recall)


def cited_files(answer: str, sources: list[MinimalSource]) -> set[str]:
    """File basenames an answer cites, by name or by [n] index."""
    names = {os.path.basename(m) for m in FILE_PATTERN.findall(answer)}
    for match in INDEX_CITATION.findall(answer):
        index = int(match) - 1
        if 0 <= index < len(sources):
            names.add(os.path.basename(sources[index].file_path))
    return names


def load_questions(suite: str, name: str,
                   limit: Optional[int]) -> list[dict[str, Any]]:
    """Answered questions of one dataset of a suite."""
    folder, suffix = SUITES[suite]
    path = os.path.join(folder, "AnsweredQuestions",
                        f"dataset_{name}_{suffix}.json")
    with open(path, encoding="utf-8") as fh:
        questions: list[dict[str, Any]] = json.load(fh)["rag_questions"]
    return questions[:limit] if limit else questions


def in_domain_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate metrics for questions the corpus can answer."""
    n = len(rows)
    answered = [r for r in rows if not r["not_found"]]
    cites = [r for r in answered if r["cited"]]
    return {
        "questions": n,
        "f1": round(sum(r["f1"] for r in rows) / n, 4),
        "f1_answered": round(
            sum(r["f1"] for r in answered) / len(answered), 4
        ) if answered else 0.0,
        "false_not_found": round(1 - len(answered) / n, 4),
        # Refusals although the reference source was in the context: the
        # generator's fault, not the retriever's.
        "refused_with_answer": round(sum(
            r["not_found"] and r["answer_in_context"] for r in rows
        ) / n, 4),
        "answer_in_context": round(
            sum(r["answer_in_context"] for r in rows) / n, 4
        ),
        "cites": round(len(cites) / len(answered), 4) if answered else 0.0,
        "citation_correct": round(
            sum(r["citation_correct"] for r in cites) / len(cites), 4
        ) if cites else 0.0,
        "language_match": round(
            sum(r["language_match"] for r in answered) / len(answered), 4
        ) if answered else 0.0,
        "seconds_per_answer": round(
            sum(r["t_gen"] + r["t_ret"] for r in rows) / n, 2
        ),
    }


def run_gen_bench(label: str, k: int = 5, limit: Optional[int] = None,
                  domain: str = "vllm",
                  config: Optional[RagConfig] = None) -> dict[str, Any]:
    """Generate answers for the benchmark sets and score them.

    Sets: public docs/code (official questions, F1 against the 42
    reference answers), the Spanish complement (answer language) and
    the out-of-domain set (correct "not found").

    Args:
        label: Short name for this run.
        k: Sources passed to the generator.
        limit: Questions per public dataset (None = all 100).
        domain: Indexed source.
        config: Pipeline configuration (defaults to rag.toml).

    Returns:
        The run dict (also saved to bench/results/gen/).
    """
    config = config or get_config()
    retriever = Retriever.from_store(domain, config=config)
    retriever.load_reranker()
    generator = Generator(config.generation)
    pipeline = RagPipeline(retriever, generator)

    details: list[dict[str, Any]] = []
    sets: dict[str, Any] = {}
    for suite, name, lang in (("public", "docs", "en"),
                              ("public", "code", "en"),
                              ("es", "docs", "es"), ("es", "code", "es")):
        rows = []
        for q in tqdm(load_questions(suite, name, limit if suite ==
                                     "public" else None),
                      desc=f"{suite}/{name}"):
            result = pipeline.answer(q["question"], k=k)
            text, sources = result.text, result.sources
            gt_files = {os.path.basename(s["file_path"])
                        for s in q["sources"]}
            gt_ranges = [(s["file_path"], s["first_character_index"],
                          s["last_character_index"]) for s in q["sources"]]
            in_context = any(
                Evaluator().overlap_ratio(gt, (
                    src.file_path, src.first_character_index,
                    src.last_character_index,
                )) >= 0.05
                for gt in gt_ranges for src in sources
            )
            cited = cited_files(text, sources)
            row = {
                "set": f"{suite}/{name}", "question": q["question"],
                "answer": text, "reference": q["answer"],
                "not_found": result.not_found,
                "answer_in_context": in_context,
                "f1": token_f1(text, q["answer"]),
                "cited": bool(cited),
                "citation_correct": bool(cited & gt_files),
                "language": detect_language(text),
                "language_match": detect_language(text) == lang,
                "t_ret": result.seconds_retrieval,
                "t_gen": result.seconds_generation,
            }
            rows.append(row)
        details.extend(rows)
        sets[f"{suite}/{name}"] = in_domain_metrics(rows)

    with open(OOD_PATH, encoding="utf-8") as fh:
        ood = json.load(fh)["questions"]
    ood_rows = []
    for q in tqdm(ood, desc="out-of-domain"):
        result = pipeline.answer(q["question"], k=k)
        ood_rows.append({
            "set": f"ood/{q['lang']}-{q['kind']}", "question": q["question"],
            "answer": result.text, "not_found": result.not_found,
            "gated": not result.sources,
            "t_ret": result.seconds_retrieval,
            "t_gen": result.seconds_generation,
        })
    details.extend(ood_rows)
    for group in ("en-far", "en-near", "es-far", "es-near"):
        rows = [r for r in ood_rows if r["set"] == f"ood/{group}"]
        sets[f"ood/{group}"] = {
            "questions": len(rows),
            "correct_not_found": round(
                sum(r["not_found"] for r in rows) / len(rows), 4
            ),
        }

    run: dict[str, Any] = {
        "label": label, "k": k, "limit": limit,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        **git_revision(), "profile": config.profile,
        "generator": generator.model_name,
        "max_new_tokens": generator.max_new_tokens,
        "device": config.models.resolved_device(),
        "sets": sets,
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
    print_gen_table(run)
    return run


def print_gen_table(run: dict[str, Any]) -> None:
    """Print the metrics of one generation run."""
    print(f"\n{run['label']} (k={run['k']}, {run['generator']})")
    for name, m in run["sets"].items():
        if name.startswith("ood/"):
            print(f"  {name:<14} correct not-found "
                  f"{m['correct_not_found']:.2f}  (n={m['questions']})")
        else:
            print(f"  {name:<14} F1 {m['f1']:.3f} | false not-found "
                  f"{m['false_not_found']:.2f} (with answer in ctx "
                  f"{m.get('refused_with_answer', 0):.2f}) | cites "
                  f"{m['cites']:.2f} "
                  f"| citation ok {m['citation_correct']:.2f} | lang "
                  f"{m['language_match']:.2f} | "
                  f"{m['seconds_per_answer']:.2f}s  (n={m['questions']})")
