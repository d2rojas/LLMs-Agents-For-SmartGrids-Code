import copy
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from baselines.llm_only import (
    BaselineParsed,
    baseline_parsed_from_result,
    build_baseline_prompt,
    evaluate_against_truth,
    evaluate_against_truth_extended,
    export_case_tables,
    parse_llm_baseline_json,
    run_baseline_case,
)
from solver import case_loader
from solver.power_flow import run_power_flow


def test_export_tables_non_empty_case14():
    net, _ = case_loader.load("case14")
    tables = export_case_tables(net)
    assert "bus" in tables and len(tables["bus"]) > 20
    assert "line" in tables and len(tables["line"]) > 20


def test_build_prompt_contains_key_sections():
    net, _ = case_loader.load("case14")
    prompt = build_baseline_prompt("case14", net)
    assert "Bus Table" in prompt
    assert "Line Table" in prompt
    assert "line_id" in prompt


@pytest.mark.parametrize(
    "text",
    [
        "{\"converged\": true, \"bus_voltages\": [], \"line_flows\": [], \"total_generation_mw\": 0, \"total_load_mw\": 0, \"total_loss_mw\": 0}",
        "```json\n{\"converged\": true, \"bus_voltages\": [], \"line_flows\": [], \"total_generation_mw\": 0, \"total_load_mw\": 0, \"total_loss_mw\": 0}\n```",
        "{'converged': True, 'bus_voltages': [], 'line_flows': [], 'total_generation_mw': 0, 'total_load_mw': 0, 'total_loss_mw': 0}",
    ],
)
def test_parse_llm_json_variants(text: str):
    obj, err = parse_llm_baseline_json(text)
    assert err is None
    assert isinstance(obj, dict)
    assert "converged" in obj


def test_parse_llm_json_fenced_nested_object():
    text = (
        "结果如下：\n"
        "```json\n"
        "{\n"
        '  "converged": true,\n'
        '  "bus_voltages": [{"bus_id": 1, "vm_pu": 1.0, "va_deg": 0.0}],\n'
        '  "line_flows": [{"line_id": 0, "p_from_mw": 10.0, "loading_percent": 20.0}],\n'
        '  "total_generation_mw": 100.0,\n'
        '  "total_load_mw": 95.0,\n'
        '  "total_loss_mw": 5.0\n'
        "}\n"
        "```\n"
        "结束。"
    )
    obj, err = parse_llm_baseline_json(text)
    assert err is None
    assert isinstance(obj, dict)
    assert obj.get("total_loss_mw") == pytest.approx(5.0)


def test_baseline_parsed_converged_string_false():
    obj = {
        "converged": "false",
        "bus_voltages": [],
        "line_flows": [],
        "total_generation_mw": 0.0,
        "total_load_mw": 0.0,
        "total_loss_mw": 0.0,
    }
    parsed, err = BaselineParsed.from_json(obj)
    assert err is None
    assert parsed is not None
    assert parsed.converged is False


def test_run_baseline_case_rejects_invalid_runs():
    with pytest.raises(ValueError, match="n_runs"):
        run_baseline_case("case14", n_runs=0)


def test_metrics_zero_error_when_matching_truth():
    net, _ = case_loader.load("case14")
    truth = run_power_flow(net)
    assert truth.converged

    # 构造一个“完美 baseline 输出”
    obj = {
        "converged": True,
        "bus_voltages": [
            {"bus_id": int(b.bus_id), "vm_pu": float(b.vm_pu), "va_deg": float(b.va_deg)}
            for b in truth.bus_voltages
        ],
        "line_flows": [
            {"line_id": int(l.line_id), "p_from_mw": float(l.p_from_mw), "loading_percent": float(l.loading_percent)}
            for l in truth.line_flows
        ],
        "total_generation_mw": float(truth.total_generation_mw),
        "total_load_mw": float(truth.total_load_mw),
        "total_loss_mw": float(truth.total_loss_mw),
    }

    parsed, err = BaselineParsed.from_json(obj)
    assert err is None and parsed is not None

    metrics = evaluate_against_truth(parsed, truth)
    assert metrics["voltage_mae"] == pytest.approx(0.0, abs=1e-12)
    assert metrics["flow_mae"] == pytest.approx(0.0, abs=1e-12)
    assert metrics["voltage_violation_precision"] == 1.0
    assert metrics["voltage_violation_recall"] == 1.0
    assert metrics["thermal_violation_precision"] == 1.0
    assert metrics["thermal_violation_recall"] == 1.0


def test_metrics_align_by_branch_endpoints_when_line_id_semantics_differ():
    net, _ = case_loader.load("case14")
    truth = run_power_flow(net)
    assert truth.converged

    shifted = []
    for lf in truth.line_flows:
        shifted.append(
            {
                # Simulate MATPOWER-style 1-based line IDs in external result.
                "line_id": int(lf.line_id) + 1,
                "from_bus": int(lf.from_bus),
                "to_bus": int(lf.to_bus),
                "p_from_mw": float(lf.p_from_mw),
                "loading_percent": float(lf.loading_percent),
            }
        )

    obj = {
        "converged": True,
        "bus_voltages": [
            {"bus_id": int(b.bus_id), "vm_pu": float(b.vm_pu), "va_deg": float(b.va_deg)}
            for b in truth.bus_voltages
        ],
        "line_flows": shifted,
        "total_generation_mw": float(truth.total_generation_mw),
        "total_load_mw": float(truth.total_load_mw),
        "total_loss_mw": float(truth.total_loss_mw),
    }

    parsed, err = BaselineParsed.from_json(obj)
    assert err is None and parsed is not None

    metrics = evaluate_against_truth_extended(parsed, truth)
    assert metrics["flow_rmse"] == pytest.approx(0.0, abs=1e-12)
    assert metrics["flow_mae"] == pytest.approx(0.0, abs=1e-12)


def test_metrics_direction_invariant_when_line_endpoints_reversed():
    net, _ = case_loader.load("case14")
    truth = run_power_flow(net)
    assert truth.converged

    parsed = baseline_parsed_from_result(truth)
    parsed_rev = copy.deepcopy(parsed)
    parsed_rev.line_ends = {lid: (tb, fb) for lid, (fb, tb) in parsed.line_ends.items()}
    parsed_rev.line_p = {lid: -float(p) for lid, p in parsed.line_p.items()}

    metrics = evaluate_against_truth_extended(parsed_rev, truth, net=net)
    assert metrics["flow_mae"] == pytest.approx(0.0, abs=1e-9)
    assert metrics["flow_deviation_rate"] == pytest.approx(0.0, abs=1e-9)
    assert metrics["kcl_self_violation_rate"] == pytest.approx(0.0, abs=1e-9)
    assert metrics["kcl_max_mismatch_mw"] == pytest.approx(0.0, abs=1e-6)


def test_kcl_metrics_still_detect_perturbation_under_reversed_orientation():
    net, _ = case_loader.load("case14")
    truth = run_power_flow(net)
    assert truth.converged

    parsed = baseline_parsed_from_result(truth)
    parsed_rev = copy.deepcopy(parsed)
    parsed_rev.line_ends = {lid: (tb, fb) for lid, (fb, tb) in parsed.line_ends.items()}
    parsed_rev.line_p = {lid: -float(p) for lid, p in parsed.line_p.items()}

    for lid in sorted(parsed_rev.line_p.keys())[:5]:
        parsed_rev.line_p[lid] = float(parsed_rev.line_p[lid]) * 1.3

    metrics = evaluate_against_truth_extended(parsed_rev, truth, net=net)
    assert float(metrics["flow_deviation_rate"]) > 0.0
    assert float(metrics["kcl_self_violation_rate"]) > 0.0
    assert float(metrics["kcl_max_mismatch_mw"]) > 1.0
