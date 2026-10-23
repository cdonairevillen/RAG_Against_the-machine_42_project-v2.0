"""CV-mode benchmark (Phase 4b), built from hand-written questions.

bench/datasets/cv/questions.json holds the questions (English and
Spanish), a short answer span and the exact evidence text in the
biography of each language (the Spanish original and its English
version). This module locates every evidence in its biography and
writes RagDataset files whose source is that span, like the 42 and
XQuAD datasets. The biography itself is git-ignored; the datasets are
versioned, and rebuilding them checks that the evidence is still there
(re-run after editing the biography).

Outputs:
    bench/datasets/cv/{Answered,Unanswered}Questions/dataset_<lang>_cv.json
"""
import json
import os
from typing import Any

from src.models import (
    AnsweredQuestion, MinimalSource, RagDataset, UnansweredQuestion,
)

LANGUAGES = ("en", "es")
DATASETS_DIR = "bench/datasets/cv"
SPEC_PATH = f"{DATASETS_DIR}/questions.json"
# Biography and evidence field of each question language.
BIOGRAPHIES = {
    "es": ("data/raw/cv/autobiography.md", "evidence"),
    "en": ("data/raw/cv/autobiography_en.md", "evidence_en"),
}


def load_spec() -> dict[str, Any]:
    """The hand-written questions."""
    with open(SPEC_PATH, encoding="utf-8") as fh:
        spec: dict[str, Any] = json.load(fh)
    return spec


def answer_for(question: dict[str, Any], lang: str) -> str:
    """The expected answer span in one language."""
    answer = question["answer"]
    return str(answer[lang] if isinstance(answer, dict) else answer)


def locate(text: str, evidence: str, qid: str,
           path: str) -> tuple[int, int]:
    """Offsets of an evidence that must appear exactly once.

    Raises:
        ValueError: If the evidence is missing or ambiguous.
    """
    count = text.count(evidence)
    if count != 1:
        raise ValueError(f"{qid}: evidence found {count} times in "
                         f"{path}: {evidence!r}")
    start = text.index(evidence)
    return start, start + len(evidence)


def build() -> int:
    """Write the CV datasets in every language.

    Returns:
        Number of questions per language.

    Raises:
        ValueError: If an evidence is not in the biography exactly once.
    """
    questions = load_spec()["questions"]
    for lang in LANGUAGES:
        path, field = BIOGRAPHIES[lang]
        with open(path, encoding="utf-8", newline="") as fh:
            text = fh.read()
        spans = {q["id"]: locate(text, q[field], q["id"], path)
                 for q in questions}
        answered = [
            AnsweredQuestion(
                question_id=q["id"], question=q[lang],
                answer=answer_for(q, lang),
                sources=[MinimalSource(
                    file_path=path,
                    first_character_index=spans[q["id"]][0],
                    last_character_index=spans[q["id"]][1],
                )],
            )
            for q in questions
        ]
        unanswered = [
            UnansweredQuestion(question_id=q.question_id,
                               question=q.question)
            for q in answered
        ]
        filename = f"dataset_{lang}_cv.json"
        for folder, items in (("AnsweredQuestions", answered),
                              ("UnansweredQuestions", unanswered)):
            os.makedirs(os.path.join(DATASETS_DIR, folder), exist_ok=True)
            with open(os.path.join(DATASETS_DIR, folder, filename), "w",
                      encoding="utf-8", newline="\n") as fh:
                fh.write(RagDataset(rag_questions=list(items))
                         .model_dump_json(indent=2))
    return len(questions)


def ood_questions() -> list[dict[str, str]]:
    """Out-of-data questions about him, one row per language.

    Returns:
        Dicts with id, kind ('private', 'secret', 'missing'), lang and
        question.
    """
    return [
        {"id": q["id"], "kind": q["kind"], "lang": lang,
         "question": q[lang]}
        for q in load_spec()["ood"] for lang in LANGUAGES
    ]
