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

# Sets of each generation suite: (dataset suite, dataset, answer
# language, whether --limit applies), the domain they are asked to and
# which out-of-domain set runs: "general" (bench/datasets/ood, vLLM
# only: its "far" questions are in-domain for XQuAD), "cv" (questions
# about Chrystian the CV does not answer, plus private contact data) or
# None. "sample": by default only that many evenly spaced questions per
# dataset are asked (--full asks all of them); generation is ~96% of
# the time.
GEN_SUITES: dict[str, dict[str, Any]] = {
    "vllm": {
        "domain": None,
        "sets": [("public", "docs", "en", True),
                 ("public", "code", "en", True),
                 ("es", "docs", "es", False),
                 ("es", "code", "es", False)],
        "ood": "general",
        "sample": None,
    },
    "xquad": {
        "domain": "xquad",
        "sets": [("xquad", "en", "en", True),
                 ("xquad", "es", "es", True)],
        "ood": None,
        # 300 of 1190 (about 6 per article, all 48 articles); the same
        # question ids in English and Spanish.
        "sample": 300,
    },
    "cv": {
        "domain": "cv",
        "sets": [("cv", "en", "en", True), ("cv", "es", "es", True)],
        "ood": "cv",
        "sample": None,
    },
}


def even_sample(items: list[Any], n: Optional[int]) -> list[Any]:
    """n items spread evenly over the list, in order (all if n is None).

    Deterministic, so every run asks the same questions; XQuAD lists
    questions article by article, so every article is represented.
    """
    if n is None or n >= len(items):
        return items
    return [items[i * len(items) // n] for i in range(n)]


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


def contains_answer(prediction: str, reference: str) -> bool:
    """Whether the normalised reference appears inside the prediction.

    Complements F1 for short references (XQuAD answers are spans such as
    "308"), which F1 penalises for every extra word of a full sentence.
    """
    ref = normalise_tokens(reference)
    pred = normalise_tokens(prediction)
    if not ref:
        return False
    return any(pred[i:i + len(ref)] == ref
               for i in range(len(pred) - len(ref) + 1))


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
        "contains_answer": round(
            sum(r["contains_answer"] for r in rows) / n, 4
        ),
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
        # Answers showing private data (phone, private e-mails); the
        # pipeline masks it, so anything but 0 is a bug.
        "leaks": sum(r.get("leak", False) for r in rows),
        "seconds_per_answer": round(
            sum(r["t_gen"] + r["t_ret"] for r in rows) / n, 2
        ),
    }


def run_gen_bench(label: str, k: int = 5, limit: Optional[int] = None,
                  domain: str = "vllm",
                  config: Optional[RagConfig] = None,
                  suite: str = "vllm", full: bool = False) -> dict[str, Any]:
    """Generate answers for the benchmark sets and score them.

    Suite "vllm": public docs/code (official questions, F1 against the
    42 reference answers), the Spanish complement (answer language) and
    the out-of-domain set (correct "not found"). Suite "xquad": the
    XQuAD questions in English and Spanish over the xquad domain (short
    reference spans, so contains_answer matters more than F1).

    Args:
        label: Short name for this run.
        k: Sources passed to the generator.
        limit: Questions per limited dataset (None = all).
        domain: Indexed source (the "xquad" suite always uses xquad).
        config: Pipeline configuration (defaults to rag.toml).
        suite: "vllm" or "xquad" (see GEN_SUITES).
        full: Ask every question instead of the suite's fixed sample
            (for complete runs; XQuAD takes ~70 min instead of ~15).

    Returns:
        The run dict (also saved to bench/results/gen/).

    Raises:
        ValueError: If suite is unknown.
    """
    if suite not in GEN_SUITES:
        raise ValueError(f"suite must be one of {list(GEN_SUITES)}")
    spec = GEN_SUITES[suite]
    sample = None if full else spec["sample"]
    domain = str(spec.get("domain") or domain)
    config = config or get_config()
    retriever = Retriever.from_store(domain, config=config)
    retriever.load_reranker()
    generator = Generator(config.generation)
    pipeline = RagPipeline(retriever, generator)

    details: list[dict[str, Any]] = []
    sets: dict[str, Any] = {}
    for dataset_suite, name, lang, limited in spec["sets"]:
        rows = []
        questions = even_sample(load_questions(
            dataset_suite, name, limit if limited else None
        ), sample)
        for q in tqdm(questions, desc=f"{dataset_suite}/{name}"):
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
                "set": f"{dataset_suite}/{name}",
                "question": q["question"],
                "answer": text, "reference": q["answer"],
                "not_found": result.not_found,
                "answer_in_context": in_context,
                "f1": token_f1(text, q["answer"]),
                "contains_answer": (not result.not_found
                                    and contains_answer(text, q["answer"])),
                "cited": bool(cited),
                "citation_correct": bool(cited & gt_files),
                "language": detect_language(text),
                "language_match": detect_language(text) == lang,
                "leak": pipeline.rules.redact_all(text) != text,
                "t_ret": result.seconds_retrieval,
                "t_gen": result.seconds_generation,
            }
            rows.append(row)
        details.extend(rows)
        sets[f"{dataset_suite}/{name}"] = in_domain_metrics(rows)

    if spec["ood"] == "general":
        run_ood(pipeline, k, details, sets)
    elif spec["ood"] == "cv":
        run_cv_ood(pipeline, k, details, sets)

    run: dict[str, Any] = {
        "label": label, "suite": suite, "domain": domain, "k": k,
        "limit": limit, "sample": sample,
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


def run_cv_ood(pipeline: RagPipeline, k: int,
               details: list[dict[str, Any]],
               sets: dict[str, Any]) -> None:
    """Questions about Chrystian the CV does not answer.

    Per kind (private contact data, the secret literary world, missing
    facts) and language: how often the answer is "not found", how often
    it is the CV's own message (with the contact e-mail) and how many
    answers show private data.
    """
    from src.sources.cv import ood_questions

    rows = []
    for q in tqdm(ood_questions(), desc="cv out-of-data"):
        result = pipeline.answer(q["question"], k=k)
        rows.append({
            "set": f"cv-ood/{q['lang']}-{q['kind']}",
            "question": q["question"], "answer": result.text,
            "not_found": result.not_found,
            "cv_message": result.text == pipeline.rules.not_found_message(
                "cv", q["question"]),
            # For the secret literary world, saying it is secret is also
            # a correct answer (prompt rule); describing it is not.
            "handled": result.not_found or (
                q["kind"] == "secret"
                and any(w in result.text.lower()
                        for w in ("secret", "secreto"))
            ),
            "leak": pipeline.rules.redact_all(result.text) != result.text,
            "gated": not result.sources,
            "t_ret": result.seconds_retrieval,
            "t_gen": result.seconds_generation,
        })
    details.extend(rows)
    for group in sorted({r["set"] for r in rows}):
        group_rows = [r for r in rows if r["set"] == group]
        n = len(group_rows)
        sets[group] = {
            "questions": n,
            "correct_not_found": round(
                sum(r["not_found"] for r in group_rows) / n, 4),
            "cv_message": round(
                sum(r["cv_message"] for r in group_rows) / n, 4),
            "handled": round(
                sum(r["handled"] for r in group_rows) / n, 4),
            "leaks": sum(r["leak"] for r in group_rows),
        }


def run_ood(pipeline: RagPipeline, k: int, details: list[dict[str, Any]],
            sets: dict[str, Any]) -> None:
    """Ask the out-of-domain set and record correct "not found" rates."""
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


def print_gen_table(run: dict[str, Any]) -> None:
    """Print the metrics of one generation run."""
    print(f"\n{run['label']} (k={run['k']}, {run['generator']})")
    for name, m in run["sets"].items():
        if name.startswith("cv-ood/"):
            print(f"  {name:<20} handled {m.get('handled', 0):.2f} | "
                  f"not-found {m['correct_not_found']:.2f} | CV message "
                  f"{m['cv_message']:.2f} | leaks {m['leaks']}  "
                  f"(n={m['questions']})")
        elif name.startswith("ood/"):
            print(f"  {name:<14} correct not-found "
                  f"{m['correct_not_found']:.2f}  (n={m['questions']})")
        else:
            print(f"  {name:<14} F1 {m['f1']:.3f} | contains "
                  f"{m.get('contains_answer', 0):.2f} | false not-found "
                  f"{m['false_not_found']:.2f} (with answer in ctx "
                  f"{m.get('refused_with_answer', 0):.2f}) | cites "
                  f"{m['cites']:.2f} "
                  f"| citation ok {m['citation_correct']:.2f} | lang "
                  f"{m['language_match']:.2f} | "
                  f"{m['seconds_per_answer']:.2f}s  (n={m['questions']})")
