"""
Tests for eval/metrics.py — the Rep. / Imp. / Feas. repair definitions used to
regenerate the paper table from saved eval JSON.

Everything here is hand-built: no pandapower network, no API key.  Only
``eval.metrics`` is imported (``eval.run_eval`` pulls in openai/dotenv/pandapower).
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

from eval import metrics

BACKEND = Path(__file__).resolve().parent.parent


# ── Helpers ──────────────────────────────────────────────────────────────

def record(initial_converged, initial_violations, final_converged, final_violations,
           network="case14", category="voltage", scenario_id="s", tool_calls=5, latency_ms=1000.0):
    """Flat metrics record, as ``metrics.to_record`` would produce."""
    return {
        "scenario_id": scenario_id,
        "category": category,
        "network": network,
        "initial_converged": initial_converged,
        "initial_violations": initial_violations,
        "final_converged": final_converged,
        "final_violations": final_violations,
        "tool_calls": tool_calls,
        "latency_ms": latency_ms,
    }


def scenario(initial_converged, initial_violations, final_converged, final_violations,
             network="case14", category="voltage", scenario_id="s", tool_calls=5,
             agentic_latency_ms=1000.0, baseline_latency_ms=100.0):
    """Raw run_eval scenario dict (same shape run_eval.py writes to JSON)."""
    initial_total = initial_violations if initial_converged else 0  # count_violations returns 0 when not converged
    final_total = final_violations if final_converged else 0
    fix_success = final_converged and (final_total <= initial_total or initial_total == 0)
    return {
        "scenario_id": scenario_id,
        "category": category,
        "network": network,
        "initial_state": {
            "converged": initial_converged,
            "violations": {"voltage": initial_total, "thermal": 0, "total": initial_total,
                           "buses": [], "lines": [], "trafos": []},
        },
        "baseline": {"latency_ms": baseline_latency_ms, "predicted_components": {}},
        "agentic": {
            "latency_ms": agentic_latency_ms,
            "react_iterations": 2,
            "tool_calls": tool_calls,
            "final_converged": final_converged,
            "final_violations": {"voltage": final_total, "thermal": 0, "total": final_total},
            "fix_success": fix_success,
            "fix_history": [],
        },
    }


def outcomes(r):
    return (metrics.repaired(r), metrics.improved(r), metrics.feasible(r))


# ── Per-scenario predicates ──────────────────────────────────────────────

def test_converges_with_zero_violations_is_repaired_improved_feasible():
    r = record(True, 7, True, 0)
    assert outcomes(r) == (True, True, True)


def test_converges_with_fewer_violations_is_improved_and_feasible_only():
    r = record(True, 7, True, 3)
    assert outcomes(r) == (False, True, True)


@pytest.mark.parametrize("final_violations", [7, 9])
def test_converges_with_equal_or_more_violations_is_feasible_only(final_violations):
    r = record(True, 7, True, final_violations)
    assert outcomes(r) == (False, False, True)


@pytest.mark.parametrize("final_violations", [0, 3])
def test_non_converged_is_none(final_violations):
    r = record(True, 7, False, final_violations)
    assert outcomes(r) == (False, False, False)
    assert metrics.legacy_fix_success(r) is False


def test_normal_base_case_repaired_only_if_it_stays_converged_with_zero_violations():
    stays_healthy = record(True, 0, True, 0, category="normal")
    assert outcomes(stays_healthy) == (True, True, True)

    gains_violations = record(True, 0, True, 2, category="normal")
    assert outcomes(gains_violations) == (False, False, True)
    # legacy fix_success counted this as a fix (initial == 0); the paper definitions do not
    assert metrics.legacy_fix_success(gains_violations) is True

    breaks_convergence = record(True, 0, False, 0, category="normal")
    assert outcomes(breaks_convergence) == (False, False, False)


def test_non_converged_initial_state_restored_to_convergence_is_improved():
    # count_violations() records 0 violations for a non-converged initial net
    r = record(False, 0, True, 2, category="nonconvergence")
    assert outcomes(r) == (False, True, True)
    assert outcomes(record(False, 0, True, 0, category="nonconvergence")) == (True, True, True)


def test_definitions_are_nested():
    cases = [record(a, i, b, f) for a in (True, False) for b in (True, False)
             for i in (0, 3) for f in (0, 3, 5)]
    for r in cases:
        rep, imp, feas = outcomes(r)
        assert (not rep) or imp
        assert (not imp) or feas


def test_legacy_fix_success_matches_run_eval_formula():
    for init_conv, init_v, fin_conv, fin_v in [(True, 5, True, 5), (True, 5, True, 6), (True, 0, True, 4),
                                               (False, 0, True, 3), (True, 4, False, 0)]:
        r = record(init_conv, init_v, fin_conv, fin_v)
        expected = fin_conv and (fin_v <= init_v or init_v == 0)
        assert metrics.legacy_fix_success(r) == expected


# ── Record extraction ────────────────────────────────────────────────────

def test_to_record_agentic_and_baseline_arms():
    s = scenario(True, 6, True, 1, tool_calls=9, agentic_latency_ms=2500.0, baseline_latency_ms=300.0)
    ag = metrics.to_record(s, "agentic")
    assert (ag["initial_violations"], ag["final_violations"], ag["tool_calls"], ag["latency_ms"]) == (6, 1, 9, 2500.0)
    assert ag["fix_success"] is True

    # Baseline never acts on the network: final state == initial state, 0 tool calls
    bl = metrics.to_record(s, "baseline")
    assert (bl["final_converged"], bl["final_violations"], bl["tool_calls"], bl["latency_ms"]) == (True, 6, 0, 300.0)
    assert outcomes(bl) == (False, False, True)


def test_to_record_skips_errored_scenarios_and_supports_legacy_fields():
    assert metrics.to_record({"scenario_id": "x", "error": "boom"}, "agentic") is None
    old = scenario(True, 3, True, 0)
    old["agentic"]["iterations_used"] = old["agentic"].pop("tool_calls")
    old["agentic"]["final_violations"] = 0  # very old JSON stored an int
    rec = metrics.to_record(old, "agentic")
    assert rec["tool_calls"] == 5 and rec["final_violations"] == 0


# ── Aggregation: 13 scenarios per network reproduce given rates ──────────

def build_case14():
    """13 scenarios: 8 repaired, 11 improved, 13 feasible; violations 48 -> 8."""
    s = [scenario(True, 0, True, 0, category="normal", scenario_id="normal_operation")]
    # 4 non-convergence scenarios restored to a clean converged state
    for i in range(4):
        s.append(scenario(False, 0, True, 0, category="nonconvergence", scenario_id=f"nc{i}"))
    # 3 voltage scenarios fully repaired (initial 5 + 5 + 6 = 16)
    for i, v in enumerate((5, 5, 6)):
        s.append(scenario(True, v, True, 0, category="voltage", scenario_id=f"v{i}"))
    # 3 thermal scenarios improved but not repaired (30 -> 6)
    for i, f in enumerate((2, 3, 1)):
        s.append(scenario(True, 10, True, f, category="thermal", scenario_id=f"t{i}"))
    # 2 contingency scenarios converge with equal violations (2 -> 2)
    for i in range(2):
        s.append(scenario(True, 1, True, 1, category="contingency", scenario_id=f"c{i}"))
    return s


def build_case30():
    """13 scenarios: 6 repaired, 9 improved, 13 feasible."""
    s = [scenario(True, 0, True, 0, network="case30", category="normal", scenario_id="normal_operation")]
    for i in range(4):
        s.append(scenario(False, 0, True, 0, network="case30", category="nonconvergence", scenario_id=f"nc{i}"))
    for i in range(1):
        s.append(scenario(True, 8, True, 0, network="case30", category="voltage", scenario_id=f"v{i}"))
    for i in range(3):
        s.append(scenario(True, 8, True, 4, network="case30", category="thermal", scenario_id=f"t{i}"))
    for i in range(4):
        s.append(scenario(True, 8, True, 8, network="case30", category="contingency", scenario_id=f"c{i}"))
    return s


def test_per_network_aggregation_reproduces_given_rates():
    summary = metrics.summarize(build_case14() + build_case30(), arm="agentic")

    c14 = summary["per_network"]["case14"]
    assert c14["n"] == 13
    assert (c14["repaired"]["pct"], c14["improved"]["pct"], c14["feasible"]["pct"]) == (61.5, 84.6, 100.0)
    assert (c14["repaired"]["count"], c14["improved"]["count"], c14["feasible"]["count"]) == (8, 11, 13)
    assert (c14["violations_initial"], c14["violations_final"]) == (48, 8)
    assert c14["tool_calls_mean"] == 5.0 and c14["tool_calls_median"] == 5.0
    assert c14["latency_mean_ms"] == 1000.0
    # legacy fix_success counts every converged non-worsening case: 13/13 here
    assert c14["fix_success"]["pct"] == 100.0

    c30 = summary["per_network"]["case30"]
    assert (c30["repaired"]["pct"], c30["improved"]["pct"], c30["feasible"]["pct"]) == (46.2, 69.2, 100.0)

    overall = summary["overall"]
    assert overall["n"] == 26
    assert overall["repaired"]["count"] == 14 and overall["repaired"]["pct"] == 53.8

    assert summary["per_category"]["normal"]["repaired"]["count"] == 2
    assert list(summary["per_network"]) == ["case14", "case30"]  # canonical order


def test_baseline_arm_describes_untreated_network():
    summary = metrics.summarize(build_case14(), arm="baseline")
    c14 = summary["per_network"]["case14"]
    assert c14["repaired"]["count"] == 1          # only the normal base case is already clean
    assert c14["improved"]["count"] == 1          # repaired => improved; nothing else improves without acting
    assert c14["feasible"]["count"] == 9          # 4 non-convergence scenarios do not converge
    assert c14["tool_calls_mean"] == 0.0
    assert (c14["violations_initial"], c14["violations_final"]) == (48, 48)


def test_summarize_accepts_flat_records_and_is_json_serialisable():
    recs = [record(True, 3, True, 0), record(True, 3, True, 2), record(True, 3, False, 0)]
    summary = metrics.summarize(recs)
    assert summary["overall"]["n"] == 3
    assert (summary["overall"]["repaired"]["count"], summary["overall"]["improved"]["count"],
            summary["overall"]["feasible"]["count"]) == (1, 2, 2)
    json.dumps(metrics.summarize_all(build_case14()))  # what run_eval writes under "summary"


# ── Table / report ───────────────────────────────────────────────────────

def test_format_table_has_paper_layout():
    table = metrics.format_table(metrics.summarize_all(build_case14() + build_case30()))
    lines = table.splitlines()
    assert lines[0].startswith("| Method | Network | n | Rep. (%) | Imp. (%) | Feas. (%) | Viol. (initial → final) | Mean tool calls")
    assert "| GridDebugAgent | IEEE 14-bus | 13 | 61.5 | 84.6 | 100.0 | 48 → 8 | 5.0 | 1 | 100.0 |" in lines
    assert "| GridDebugAgent | IEEE 30-bus | 13 | 46.2 | 69.2 | 100.0 |" in table
    assert "| **GridDebugAgent** | **All** | **26** | **53.8** |" in table
    assert "| LLM-only | IEEE 14-bus | 13 | 7.7 | 7.7 | 69.2 | 48 → 48 | 0.0 |" in table
    assert "Rep.: final network converges with zero violations" in table


def write_json(tmp_path, scenarios, network="case14"):
    path = tmp_path / f"full_eval_{network}.json"
    path.write_text(json.dumps({"network": network, "timestamp": "2026-01-01T00:00:00", "scenarios": scenarios}))
    return path


def test_report_from_json_regenerates_table(tmp_path):
    p14 = write_json(tmp_path, build_case14(), "case14")
    p30 = write_json(tmp_path, build_case30(), "case30")
    table = metrics.report_from_json([p14, p30])
    assert "| GridDebugAgent | IEEE 14-bus | 13 | 61.5 | 84.6 | 100.0 | 48 → 8 |" in table
    assert "| **GridDebugAgent** | **All** | **26** |" in table
    # single file: no "All" row
    assert "**All**" not in metrics.report_from_json(p14)


def test_report_only_cli_prints_table(tmp_path):
    path = write_json(tmp_path, build_case14())
    proc = subprocess.run(
        [sys.executable, "-m", "eval.metrics", "--report-only", str(path)],
        cwd=BACKEND, capture_output=True, text=True, check=True,
    )
    assert "| GridDebugAgent | IEEE 14-bus | 13 | 61.5 | 84.6 | 100.0 | 48 → 8 |" in proc.stdout


def test_run_eval_report_only_cli_prints_table(tmp_path):
    """Same flag on the harness itself; needs its runtime deps (dotenv, openai, pandapower)."""
    for mod in ("dotenv", "openai", "pandapower"):
        pytest.importorskip(mod)
    path = write_json(tmp_path, build_case14())
    proc = subprocess.run(
        [sys.executable, "-m", "eval.run_eval", "--report-only", str(path)],
        cwd=BACKEND, capture_output=True, text=True, check=True,
    )
    assert "## Repair Metrics (paper definitions)" in proc.stdout
    assert "| GridDebugAgent | IEEE 14-bus | 13 | 61.5 | 84.6 | 100.0 | 48 → 8 |" in proc.stdout
    assert "| normal_operation | normal | True | True | 0->0 | Yes | Yes | Yes | Yes |" in proc.stdout
