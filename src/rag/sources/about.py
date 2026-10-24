"""About benchmark (Phase 7a): questions on the project itself.

bench/datasets/about/questions.json holds hand-written questions (English
and Spanish), a short answer span, and where they are answered: `file`
and `evidence` (the exact text) in the English documents, plus
`file_es`/`evidence_es` in their Spanish version (docs/es/) when it
exists. Each language's question gets the source in its own language
(the code, with no translation, serves both), as in the CV benchmark: the
42 evaluator scores the fraction of ground-truth sources found, so
listing both versions would halve a question that finds one of them.
Every evidence is located in its file and written as RagDataset files
whose source is that span. The files are read live
from the repository: re-run after editing them (it fails if an evidence
is gone or no longer unique).

Outputs:
    bench/datasets/about/{Answered,Unanswered}Questions/
        dataset_<lang>_about.json
"""
import json
import os
from typing import Any

from src.models import (
    AnsweredQuestion, MinimalSource, RagDataset, UnansweredQuestion,
)
from src.rag.sources.cv import LANGUAGES, answer_for, locate

DATASETS_DIR = "bench/datasets/about"
SPEC_PATH = f"{DATASETS_DIR}/questions.json"


def load_spec() -> dict[str, Any]:
    """The hand-written questions."""
    with open(SPEC_PATH, encoding="utf-8") as fh:
        spec: dict[str, Any] = json.load(fh)
    return spec


def build() -> int:
    """Write the about datasets in every language.

    Returns:
        Number of questions per language.

    Raises:
        ValueError: If an evidence is not in its file exactly once.
    """
    questions = load_spec()["questions"]
    for lang in LANGUAGES:
        answered = []
        for q in questions:
            suffix = "_es" if lang == "es" and "file_es" in q else ""
            path, evidence = q["file" + suffix], q["evidence" + suffix]
            with open(path, encoding="utf-8", newline="") as fh:
                start, end = locate(fh.read(), evidence, q["id"], path)
            answered.append(AnsweredQuestion(
                question_id=q["id"], question=q[lang],
                answer=answer_for(q, lang),
                sources=[MinimalSource(
                    file_path=path, first_character_index=start,
                    last_character_index=end,
                )],
            ))
        unanswered = [
            UnansweredQuestion(question_id=q.question_id,
                               question=q.question)
            for q in answered
        ]
        filename = f"dataset_{lang}_about.json"
        for folder, items in (("AnsweredQuestions", answered),
                              ("UnansweredQuestions", unanswered)):
            os.makedirs(os.path.join(DATASETS_DIR, folder), exist_ok=True)
            with open(os.path.join(DATASETS_DIR, folder, filename), "w",
                      encoding="utf-8", newline="\n") as fh:
                fh.write(RagDataset(rag_questions=list(items))
                         .model_dump_json(indent=2))
    return len(questions)
