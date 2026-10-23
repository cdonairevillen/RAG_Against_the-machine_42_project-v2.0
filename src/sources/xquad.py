"""XQuAD as a knowledge source and benchmark (Phase 4a).

XQuAD (Google, CC-BY-SA 4.0): the same 1190 questions over the same 240
Wikipedia paragraphs, professionally translated. Questions, paragraphs
and answers come from the Hugging Face dataset `google/xquad`; the
article titles (absent there) from the original JSON on GitHub, joined
by question id. Both are pinned to a revision and checked by SHA256, so
every clone builds the same corpus and ground truth.

Outputs:
    data/raw/xquad/<lang>/<Title>.md   One file per article: the title
        as header and its paragraphs separated by blank lines.
    bench/datasets/xquad/{Answered,Unanswered}Questions/
        dataset_<lang>_xquad.json      RagDataset; each source is the
        exact answer span inside the article file.
"""
import hashlib
import json
import os
import urllib.request
from collections import defaultdict
from typing import Any

from src.models import (
    AnsweredQuestion, MinimalSource, RagDataset, UnansweredQuestion,
)

LANGUAGES = ("en", "es")
HF_REVISION = "51adfef1c1287aab1d2d91b5bead9bcfb9c68583"
GITHUB_REVISION = "7d30520c717524000f0d9d2f9c10a069acd9d285"
HF_URL = (
    "https://huggingface.co/datasets/google/xquad/resolve/"
    f"{HF_REVISION}/xquad.{{lang}}/validation-00000-of-00001.parquet"
)
GITHUB_URL = (
    "https://raw.githubusercontent.com/google-deepmind/xquad/"
    f"{GITHUB_REVISION}/xquad.{{lang}}.json"
)
SHA256 = {
    "xquad.en.parquet":
        "e769714c0b750622a2a70e3b5250f6040ef8578e859dff0b9faf4612287e0083",
    "xquad.es.parquet":
        "69b6ad587e2ebcb0b00105f6736661154f9b1ce95eaa581bcac240d6edfc11ce",
    "xquad.en.json":
        "e4c57d1c9143aaa1c5d265ba5987a65f4e69528d2a98f29d6e75019b10344f29",
    "xquad.es.json":
        "dcbae93ec3a9f4b9e78fd834a171d6f96c1a875e10e15b7530b7e4ef4971e37e",
}

DOWNLOAD_DIR = "data/raw/xquad_src"
CORPUS_DIR = "data/raw/xquad"
DATASETS_DIR = "bench/datasets/xquad"


def sha256(path: str) -> str:
    """Return the hex SHA256 of a file."""
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def fetch(url: str, path: str) -> None:
    """Download url to path unless a file with the pinned hash is there.

    Raises:
        ValueError: If the downloaded file does not match its SHA256.
    """
    expected = SHA256[os.path.basename(path)]
    if os.path.isfile(path) and sha256(path) == expected:
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    print(f"Downloading {url}")
    urllib.request.urlretrieve(url, path)
    actual = sha256(path)
    if actual != expected:
        raise ValueError(
            f"SHA256 mismatch for {path}: {actual} (expected {expected})"
        )


def load_rows(lang: str) -> list[dict[str, Any]]:
    """Questions of one language, with their article title.

    Hugging Face strips the whitespace around each paragraph but keeps
    the original answer offsets, which shifts the answers of a paragraph
    starting with a space (Apollo_program). Offsets are re-based on the
    stripped paragraph and every answer is checked against its text.

    Returns:
        Dicts with id, title, context, question, answer and
        answer_start, in dataset order.

    Raises:
        ValueError: If an answer does not match the paragraph text.
    """
    import pyarrow.parquet as pq

    parquet = os.path.join(DOWNLOAD_DIR, f"xquad.{lang}.parquet")
    original = os.path.join(DOWNLOAD_DIR, f"xquad.{lang}.json")
    fetch(HF_URL.format(lang=lang), parquet)
    fetch(GITHUB_URL.format(lang=lang), original)

    with open(original, encoding="utf-8") as fh:
        articles = json.load(fh)["data"]
    by_id = {
        qa["id"]: (article["title"], paragraph["context"])
        for article in articles
        for paragraph in article["paragraphs"]
        for qa in paragraph["qas"]
    }

    rows = []
    for row in pq.read_table(parquet).to_pylist():
        title, raw_context = by_id[row["id"]]
        context = row["context"]
        answer = row["answers"]["text"][0]
        start = row["answers"]["answer_start"][0] - raw_context.find(context)
        if context[start:start + len(answer)] != answer:
            raise ValueError(f"Answer of {row['id']} ({lang}) not found "
                             f"at offset {start}")
        rows.append({
            "id": row["id"], "title": title, "context": context,
            "question": row["question"], "answer": answer,
            "answer_start": start,
        })
    return rows


def build_language(lang: str) -> tuple[int, int]:
    """Write the article files and datasets of one language.

    Returns:
        (articles written, questions written).
    """
    rows = load_rows(lang)
    paragraphs: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        if row["context"] not in paragraphs[row["title"]]:
            paragraphs[row["title"]].append(row["context"])

    # "/" on every OS: these paths are the ground truth's file_path.
    corpus_dir = f"{CORPUS_DIR}/{lang}"
    os.makedirs(corpus_dir, exist_ok=True)
    offsets: dict[tuple[str, str], int] = {}
    paths: dict[str, str] = {}
    for title, contexts in paragraphs.items():
        text = f"# {title.replace('_', ' ')}\n"
        for context in contexts:
            text += "\n"
            offsets[(title, context)] = len(text)
            text += context + "\n"
        path = f"{corpus_dir}/{title}.md"
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        paths[title] = path

    answered = []
    for row in rows:
        first = offsets[(row["title"], row["context"])] + row["answer_start"]
        answered.append(AnsweredQuestion(
            question_id=row["id"],
            question=row["question"],
            answer=row["answer"],
            sources=[MinimalSource(
                file_path=paths[row["title"]],
                first_character_index=first,
                last_character_index=first + len(row["answer"]),
            )],
        ))
    unanswered = [
        UnansweredQuestion(question_id=q.question_id, question=q.question)
        for q in answered
    ]

    filename = f"dataset_{lang}_xquad.json"
    for folder, questions in (("AnsweredQuestions", answered),
                              ("UnansweredQuestions", unanswered)):
        os.makedirs(os.path.join(DATASETS_DIR, folder), exist_ok=True)
        path = os.path.join(DATASETS_DIR, folder, filename)
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(RagDataset(rag_questions=list(questions))
                     .model_dump_json(indent=2))
    return len(paragraphs), len(answered)


def verify_sources(lang: str) -> int:
    """Check that every ground-truth span holds its answer.

    Returns:
        Number of questions checked.

    Raises:
        ValueError: On the first span that does not match.
    """
    path = os.path.join(DATASETS_DIR, "AnsweredQuestions",
                        f"dataset_{lang}_xquad.json")
    with open(path, encoding="utf-8") as fh:
        dataset = RagDataset.model_validate_json(fh.read())
    files: dict[str, str] = {}
    for q in dataset.rag_questions:
        assert isinstance(q, AnsweredQuestion)
        src = q.sources[0]
        if src.file_path not in files:
            with open(src.file_path, encoding="utf-8", newline="") as fh:
                files[src.file_path] = fh.read()
        span = files[src.file_path][
            src.first_character_index:src.last_character_index
        ]
        if span != q.answer:
            raise ValueError(f"{q.question_id} ({lang}): {span!r} != "
                             f"{q.answer!r}")
    return len(dataset.rag_questions)


def prepare() -> None:
    """Download XQuAD (en, es) and build the corpus and datasets."""
    for lang in LANGUAGES:
        articles, questions = build_language(lang)
        checked = verify_sources(lang)
        print(f"xquad/{lang}: {articles} articles, {questions} questions "
              f"({checked} answer spans verified)")
