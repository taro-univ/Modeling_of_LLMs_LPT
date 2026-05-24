from __future__ import annotations

from dataclasses import fields
from pathlib import Path

import numpy as np
import pytest

from analysis.base_analyzer import AnalysisResult, BaseAnalyzer, ConditionData


class DummyAnalyzer(BaseAnalyzer):
    def run_analysis(self) -> AnalysisResult:
        return AnalysisResult("dummy", [], {}, "")


def test_base_analyzer_is_abstract():
    with pytest.raises(TypeError):
        BaseAnalyzer(data_dir=".", out_dir=".")


def test_condition_data_fields():
    expected = {
        "N",
        "T",
        "trials",
        "n_trials",
        "accuracy",
        "pm_rate",
        "sg_rate",
        "ordered_rate",
        "early_stop",
        "hidden",
        "move_steps",
        "move_texts",
        "is_fallback",
    }
    assert {f.name for f in fields(ConditionData)} == expected


def test_load_condition_missing_dir_returns_none(tmp_path: Path):
    analyzer = DummyAnalyzer(data_dir=tmp_path, out_dir=tmp_path)
    assert analyzer._load_condition(2, 0.5) is None


def test_load_condition_summary_only():
    data_dir = Path(__file__).parent / "fixtures"
    analyzer = DummyAnalyzer(data_dir=data_dir, out_dir=data_dir, ns=[2], ts=[0.5])
    cond = analyzer._load_condition(2, 0.5, load_hidden=False)

    assert cond is not None
    assert cond.N == 2
    assert cond.T == 0.5
    assert cond.n_trials == 3
    assert cond.early_stop == ["goal_reached", "no_move_catchall", "goal_reached"]
    assert cond.accuracy == pytest.approx(2 / 3)
    assert cond.pm_rate == pytest.approx(1 / 3)
    assert cond.sg_rate == pytest.approx(0.0)
    assert cond.ordered_rate == pytest.approx(2 / 3)
    assert cond.hidden == {}
    assert cond.move_steps == []
    assert cond.move_texts == []
    assert cond.is_fallback == []
    assert np.isnan(DummyAnalyzer(data_dir=data_dir, out_dir=data_dir)._load_summary(data_dir / "missing")[2])
