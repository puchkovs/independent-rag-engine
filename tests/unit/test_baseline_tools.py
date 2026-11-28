"""The baseline report's arithmetic and the evaluation scripts' resource gate."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]


def script(name: str) -> Any:
    sys.path.insert(0, str(ROOT / "eval" / "scripts"))
    spec = importlib.util.spec_from_file_location(name, ROOT / "eval" / "scripts" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run(**scores: dict[str, float]) -> dict[str, Any]:
    return {"modes": {"dense": {"per_question": scores}}}


def test_the_movement_of_a_mean_is_split_into_changed_and_unchanged_questions() -> None:
    report = script("baseline_report")
    metrics = ("hit@1", "mrr@10", "ndcg@10", "evidence@5")

    def row(value: float) -> dict[str, float]:
        return dict.fromkeys(metrics, value)

    old = run(a=row(0.0), b=row(1.0), c=row(0.5), d=row(0.5))
    new = run(a=row(1.0), b=row(1.0), c=row(0.5), d=row(0.4))
    effect = report.version_effect(old, new, ["a"], "dense")
    ndcg = effect["metrics"]["ndcg@10"]
    assert effect["n"] == 4
    assert ndcg["old"] == pytest.approx(0.5) and ndcg["new"] == pytest.approx(0.725)
    assert ndcg["delta"] == pytest.approx(0.225)
    assert ndcg["from_changed"] == pytest.approx(0.25)  # question a: +1.0 of four
    assert ndcg["unexplained"] == pytest.approx(-0.025)  # question d moved without a label change
    assert set(effect["questions"]) == {"a", "d"}


def test_the_tables_are_markdown_rows_of_the_right_width() -> None:
    report = script("baseline_report")
    cell = {m: {"mean": 0.5, "low": 0.4, "high": 0.6, "n": 3} for m in report.SHOWN}
    data = {"modes": {m: {"summary": {"all": cell}, "latency_ms": {}} for m in report.MODES}}
    table = report.metrics_table(data)
    assert len(table) == 2 + len(report.MODES)
    assert len({line.count("|") for line in table}) == 1


def test_a_model_run_is_refused_without_memory_and_says_why(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    guard = script("resource_guard")
    monkeypatch.setattr(guard, "available", lambda: int(1.0 * guard.GIB))
    with pytest.raises(SystemExit) as stop:
        guard.require(1.2, what="the model")
    assert stop.value.code == 3
    report = json.loads(capsys.readouterr().out)
    assert report["result"] == "refused_by_resource_gate" and report["needed_gib"] == 2.2
    monkeypatch.setattr(guard, "available", lambda: int(3.0 * guard.GIB))
    guard.require(1.2, what="the model")  # enough memory: no exit


def test_the_evaluation_script_guards_the_test_split_and_the_rerank_run_has_a_gate() -> None:
    text = (ROOT / "eval/scripts/retrieval_eval.py").read_text(encoding="utf-8")
    assert "TestSplitGuard" in text and "--final" in text and "resource_guard.require" in text
    rerank = (ROOT / "eval/scripts/rerank_bakeoff.py").read_text(encoding="utf-8")
    assert "resource_guard.require(PEAK_GIB" in rerank and "PEAK_GIB = 2.5" in rerank
