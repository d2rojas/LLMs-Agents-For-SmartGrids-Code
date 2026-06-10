import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from benchmarks.evaluate_llms import (
    UsageStats,
    _aggregate_group,
    _estimate_cost_usd,
    _flatten_scoreboard,
)


def test_estimate_cost_usd_uses_prompt_and_completion_tokens():
    pricing = {"openai:gpt-4o-mini": {"input": 0.15, "output": 0.60}}
    usage = UsageStats(prompt_tokens=1000, completion_tokens=500, total_tokens=1500)
    cost = _estimate_cost_usd("openai:gpt-4o-mini", usage, pricing)
    assert cost == pytest.approx(0.00045)


def test_aggregate_group_includes_token_and_core_metrics():
    rows = [
        {
            "ok": True,
            "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
            "cost_usd": 0.001,
            "metrics": {
                "voltage_mae": 0.01,
                "flow_mae": 1.0,
                "loading_rmse": 2.0,
                "voltage_f1": 0.8,
                "thermal_f1": 0.5,
                "convergence_match": True,
            },
        },
        {
            "ok": False,
            "usage": {"prompt_tokens": 120, "completion_tokens": 30, "total_tokens": 150},
            "cost_usd": 0.002,
            "metrics": None,
        },
    ]
    agg = _aggregate_group(rows)
    assert agg["success_rate"] == pytest.approx(0.5)
    assert agg["voltage_mae_mean"] == pytest.approx(0.01)
    assert agg["prompt_tokens_mean"] == pytest.approx(110.0)
    assert agg["completion_tokens_mean"] == pytest.approx(40.0)
    assert agg["total_tokens_mean"] == pytest.approx(150.0)
    assert agg["cost_usd_total"] == pytest.approx(0.003)


def test_flatten_scoreboard_keeps_core_fields():
    flat = _flatten_scoreboard([
        {
            "model": "openai:gpt-4o-mini",
            "task": "baseline_pf",
            "success_rate": 1.0,
            "voltage_mae_mean": 0.01,
            "flow_mae_mean": 1.0,
            "loading_rmse_mean": 2.0,
            "voltage_f1_mean": 0.8,
            "thermal_f1_mean": 0.7,
            "convergence_match_rate": 1.0,
            "prompt_tokens_mean": 100.0,
            "completion_tokens_mean": 50.0,
            "total_tokens_mean": 150.0,
            "cost_usd_mean": 0.001,
            "cost_usd_total": 0.002,
        }
    ])
    assert flat[0]["model"] == "openai:gpt-4o-mini"
    assert flat[0]["task"] == "baseline_pf"
    assert flat[0]["cost_usd_total"] == pytest.approx(0.002)
