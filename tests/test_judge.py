from pathlib import Path

import pytest

from src.evaluation.judge import Judge, JudgeError, load_env, parse_verdict


def test_parse_verdict_reads_json_and_fallbacks() -> None:
    assert parse_verdict('{"score": 2, "reason": "ok"}') == {
        "score": 2, "reason": "ok",
    }
    assert parse_verdict('Sure!\n{"score": 1, "reason": "partial"}')[
        "score"] == 1
    assert parse_verdict('"score": 2 but broken json')["score"] == 2
    assert parse_verdict("no verdict at all")["score"] == 0


def test_load_env_does_not_override_existing(tmp_path: Path,
                                             monkeypatch: pytest.MonkeyPatch
                                             ) -> None:
    env = tmp_path / ".env"
    env.write_text("JUDGE_MODEL=from-file\nexport X_TEST_VAR='quoted'\n",
                   encoding="utf-8")
    monkeypatch.setenv("JUDGE_MODEL", "from-env")
    monkeypatch.delenv("X_TEST_VAR", raising=False)

    load_env(str(env))

    import os
    assert os.environ["JUDGE_MODEL"] == "from-env"
    assert os.environ["X_TEST_VAR"] == "quoted"


def test_judge_requires_configuration(monkeypatch: pytest.MonkeyPatch
                                      ) -> None:
    for name in ("JUDGE_BASE_URL", "JUDGE_MODEL", "GROQ_API_KEY",
                 "JUDGE_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr("src.evaluation.judge.load_env",
                        lambda path=".env": None)

    with pytest.raises(JudgeError, match="JUDGE_BASE_URL"):
        Judge()
