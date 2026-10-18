import json
from pathlib import Path

from src.evaluator import Evaluator


def test_overlap_ratio_is_relative_to_ground_truth() -> None:
    ev = Evaluator()
    gt = ("a.py", 100, 200)
    assert ev.overlap_ratio(gt, ("a.py", 100, 200)) == 1.0
    assert ev.overlap_ratio(gt, ("a.py", 0, 1000)) == 1.0
    assert ev.overlap_ratio(gt, ("a.py", 150, 400)) == 0.5
    assert ev.overlap_ratio(gt, ("a.py", 200, 300)) == 0.0
    assert ev.overlap_ratio(gt, ("b.py", 100, 200)) == 0.0


def test_compute_recall_with_partial_credit(tmp_path: Path) -> None:
    source_a = {"file_path": "a.md", "first_character_index": 0,
                "last_character_index": 100}
    source_b = {"file_path": "b.md", "first_character_index": 0,
                "last_character_index": 100}
    ground_truth = {"rag_questions": [{
        "question_id": "q1", "question": "?", "answer": "!",
        "sources": [source_a, source_b],
    }]}
    student = {"k": 3, "search_results": [{
        "question_id": "q1", "question_str": "?",
        "retrieved_sources": [
            {"file_path": "x.md", "first_character_index": 0,
             "last_character_index": 100},
            source_a,
            source_b,
        ],
    }]}
    gt_path = tmp_path / "gt.json"
    st_path = tmp_path / "st.json"
    gt_path.write_text(json.dumps(ground_truth), encoding="utf-8")
    st_path.write_text(json.dumps(student), encoding="utf-8")

    metrics = Evaluator().compute_recall(str(st_path), str(gt_path), k=3)

    assert metrics["total"] == 1
    assert metrics["recall_at_k"][1] == 0.0
    assert metrics["recall_at_k"][3] == 1.0
