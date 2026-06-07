import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from solver import case_loader
from solver.contingency import get_most_loaded_branch, run_n1_contingency
from solver.power_flow import run_power_flow


def test_get_most_loaded_branch_after_runpp():
    net, _ = case_loader.load("case14")
    _ = run_power_flow(net)

    info = get_most_loaded_branch(net)
    assert info is not None
    assert "loading_percent" in info
    assert info["loading_percent"] >= 0.0
    assert info["from_bus"] != info["to_bus"]


@pytest.mark.parametrize("criteria", ["max_violations", "max_overload", "min_voltage"])
def test_run_n1_contingency_returns_sorted_topk(criteria: str):
    net, _ = case_loader.load("case14")
    report = run_n1_contingency(net, top_k=5, criteria=criteria)

    assert report.base_converged is True
    assert report.top_k == 5
    assert len(report.results) == 5

    # score should be non-increasing (sorted desc)
    scores = [r.score for r in report.results]
    assert scores == sorted(scores, reverse=True)


def test_run_n1_contingency_adds_delta_violations_vs_base():
    net, _ = case_loader.load("case14")
    base = run_power_flow(net)
    report = run_n1_contingency(net, top_k=5, criteria="max_violations")

    base_n_v = len(base.voltage_violations)
    base_n_t = len(base.thermal_violations)
    assert report.results

    for r in report.results:
        assert r.delta_voltage_violations == r.n_voltage_violations - base_n_v
        assert r.delta_thermal_violations == r.n_thermal_violations - base_n_t
