import json
import sys
from pathlib import Path

import pytest

# Ensure project root is on path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from llm.tools import ToolContext, build_default_dispatcher
from models.schemas import SessionState
from solver.llm_pf import PROVIDER_ERROR, solve_from_matpower_text
from solver.matpower_meta import MatpowerMeta
from solver.matpower_text import FETCH_CMD, get_case_m_path


def _valid_payload(*, debug_mode: bool, debug_pd_delta: float = 0.0) -> dict:
    base = {
        "case_name": "case14",
        "converged": True,
        "totals": {
            "total_generation_mw": 95.0,
            "total_load_mw": 90.0,
            "total_loss_mw": 5.0,
        },
        "bus_voltages": [
            {"bus_id": 1, "vm_pu": 1.02, "va_deg": 0.0},
            {"bus_id": 2, "vm_pu": 0.99, "va_deg": -5.0},
        ],
        "line_flows": [
            {
                "line_id": 1,
                "from_bus": 1,
                "to_bus": 2,
                "p_from_mw": 10.0,
                "q_from_mvar": 1.5,
                "loading_percent": 0.0,
            }
        ],
        "voltage_violations": [],
        "thermal_violations": [],
        "summary_text": "ok",
        "debug_routing_step": None,
    }
    if debug_mode:
        base["debug_routing_step"] = {
            "slack_bus": 1,
            "loss_factor_assumed": 0.05,
            "path_assignments": [{"load_bus": 2, "pd_mw": 90.0, "path_str": "1-2"}],
            "branch_pd_sums": [{"line_id": 1, "from_bus": 1, "to_bus": 2, "pd_sum_mw": 10.0 + debug_pd_delta}],
        }
    return base


def test_llm_only_blueprint_schema_and_assertions_pass(monkeypatch):
    payload = _valid_payload(debug_mode=False)
    captured: dict[str, str] = {}

    def fake_generate(**kwargs):
        captured["system_instruction"] = kwargs["system_instruction"]
        captured["user_text"] = kwargs["user_text"]
        return json.dumps(payload, ensure_ascii=False)

    monkeypatch.setattr(
        "solver.llm_pf.get_matpower_meta",
        lambda _: MatpowerMeta(total_load_mw_ref=90.0, zero_rateA_line_ids={1}, slack_bus_id_ref=1),
    )
    monkeypatch.setattr("solver.llm_pf._generate_json_with_gemini", fake_generate)

    matpower_text = "function mpc = case14;\nmpc.version = '2';\n"
    result = solve_from_matpower_text(
        matpower_text=matpower_text,
        m_file_path="C:/tmp/case14.m",
        case_name="case14",
        debug_mode=False,
        llm_provider="gemini",
        llm_model="gemini-2.5-flash",
        api_key="dummy-key",
        temperature=0.1,
        timeout_s=5.0,
    )

    assert result.converged is True
    assert result.debug_routing_step is None
    assert result.totals.total_load_mw == pytest.approx(90.0)
    assert "Heuristic AC Power Flow Estimator" in captured["system_instruction"]
    assert matpower_text in captured["user_text"]


def test_llm_only_blueprint_debug_mismatch_returns_failed_result(monkeypatch):
    payload = _valid_payload(debug_mode=True, debug_pd_delta=1.0)

    monkeypatch.setattr(
        "solver.llm_pf.get_matpower_meta",
        lambda _: MatpowerMeta(total_load_mw_ref=90.0, zero_rateA_line_ids={1}, slack_bus_id_ref=1),
    )
    monkeypatch.setattr("solver.llm_pf._generate_json_with_gemini", lambda **_: json.dumps(payload, ensure_ascii=False))

    result = solve_from_matpower_text(
        matpower_text="function mpc = case14;\n",
        m_file_path="C:/tmp/case14.m",
        case_name="case14",
        debug_mode=True,
        llm_provider="gemini",
        llm_model="gemini-2.5-flash",
        api_key="dummy-key",
        temperature=0.1,
        timeout_s=5.0,
    )

    assert result.converged is False
    assert "A5 failed" in result.summary_text


def test_llm_only_blueprint_rejects_non_gemini_provider():
    with pytest.raises(ValueError, match="Gemini"):
        solve_from_matpower_text(
            matpower_text="function mpc = case14;\n",
            m_file_path="C:/tmp/case14.m",
            case_name="case14",
            debug_mode=False,
            llm_provider="openai",
            llm_model="gpt-4o-mini",
            api_key="dummy-key",
            temperature=0.1,
            timeout_s=5.0,
        )
    assert "Gemini" in PROVIDER_ERROR


def test_llm_only_blueprint_coerces_legacy_payload(monkeypatch):
    legacy_payload = {
        "case": "case14",
        "converged": True,
        "total_generation": 95.0,
        "total_load": 90.0,
        "total_loss": 5.0,
        "bus_results": [
            {"bus_id": 1, "vm": 1.02, "va": 0.0},
            {"bus_id": 2, "vm": 0.99, "va": -5.0},
        ],
        "branch_results": [
            {"line_id": 1, "from_bus": 1, "to_bus": 2, "p_mw": 10.0, "q_mvar": 1.5, "loading_percent": None}
        ],
        "summary": "legacy ok",
    }
    monkeypatch.setattr(
        "solver.llm_pf.get_matpower_meta",
        lambda _: MatpowerMeta(total_load_mw_ref=90.0, zero_rateA_line_ids={1}, slack_bus_id_ref=1),
    )
    monkeypatch.setattr("solver.llm_pf._generate_json_with_gemini", lambda **_: json.dumps(legacy_payload, ensure_ascii=False))

    result = solve_from_matpower_text(
        matpower_text="function mpc = case14;\n",
        m_file_path="C:/tmp/case14.m",
        case_name="case14",
        debug_mode=False,
        llm_provider="gemini",
        llm_model="gemini-2.5-flash",
        api_key="dummy-key",
        temperature=0.0,
        timeout_s=5.0,
    )
    assert result.converged is True
    assert result.case_name == "case14"
    assert result.totals.total_load_mw == pytest.approx(90.0)


def test_missing_matpower_file_error_contains_fetch_command(tmp_path):
    with pytest.raises(FileNotFoundError) as exc:
        get_case_m_path("case14", date="2017-01-01", root=str(tmp_path))
    assert FETCH_CMD in str(exc.value)


def test_llm_only_blueprint_retries_on_a2_then_succeeds(monkeypatch):
    bad = _valid_payload(debug_mode=False)
    bad["totals"]["total_load_mw"] = 312.4
    good = _valid_payload(debug_mode=False)
    calls = {"n": 0}

    def fake_gen(**kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return json.dumps(bad, ensure_ascii=False)
        return json.dumps(good, ensure_ascii=False)

    monkeypatch.setattr(
        "solver.llm_pf.get_matpower_meta",
        lambda _: MatpowerMeta(total_load_mw_ref=90.0, zero_rateA_line_ids={1}, slack_bus_id_ref=1),
    )
    monkeypatch.setattr("solver.llm_pf._generate_json_with_gemini", fake_gen)

    result = solve_from_matpower_text(
        matpower_text="function mpc = case14;\n",
        m_file_path="C:/tmp/case14.m",
        case_name="case14",
        debug_mode=False,
        llm_provider="gemini",
        llm_model="gemini-2.5-flash",
        api_key="dummy-key",
        temperature=0.0,
        timeout_s=5.0,
    )

    assert calls["n"] == 2
    assert result.converged is True


def test_llm_only_blueprint_retry_limit_two_then_fail(monkeypatch):
    bad = _valid_payload(debug_mode=False)
    bad["totals"]["total_load_mw"] = 312.4
    calls = {"n": 0}

    def fake_gen(**kwargs):
        calls["n"] += 1
        return json.dumps(bad, ensure_ascii=False)

    monkeypatch.setattr(
        "solver.llm_pf.get_matpower_meta",
        lambda _: MatpowerMeta(total_load_mw_ref=90.0, zero_rateA_line_ids={1}, slack_bus_id_ref=1),
    )
    monkeypatch.setattr("solver.llm_pf._generate_json_with_gemini", fake_gen)

    result = solve_from_matpower_text(
        matpower_text="function mpc = case14;\n",
        m_file_path="C:/tmp/case14.m",
        case_name="case14",
        debug_mode=False,
        llm_provider="gemini",
        llm_model="gemini-2.5-flash",
        api_key="dummy-key",
        temperature=0.0,
        timeout_s=5.0,
    )

    assert calls["n"] == 3  # initial + 2 retries
    assert result.converged is False
    assert "A2 failed" in result.summary_text


def test_llm_only_blueprint_autocorrects_zero_ratea_loading(monkeypatch):
    payload = _valid_payload(debug_mode=False)
    payload["line_flows"][0]["loading_percent"] = 77.7
    payload["thermal_violations"] = [
        {"line_id": 1, "from_bus": 1, "to_bus": 2, "loading_percent": 77.7}
    ]
    monkeypatch.setattr(
        "solver.llm_pf.get_matpower_meta",
        lambda _: MatpowerMeta(total_load_mw_ref=90.0, zero_rateA_line_ids={1}, slack_bus_id_ref=1),
    )
    monkeypatch.setattr("solver.llm_pf._generate_json_with_gemini", lambda **_: json.dumps(payload, ensure_ascii=False))

    result = solve_from_matpower_text(
        matpower_text="function mpc = case14;\n",
        m_file_path="C:/tmp/case14.m",
        case_name="case14",
        debug_mode=False,
        llm_provider="gemini",
        llm_model="gemini-2.5-flash",
        api_key="dummy-key",
        temperature=0.0,
        timeout_s=5.0,
    )
    assert result.converged is True
    assert result.line_flows[0].loading_percent == pytest.approx(0.0)
    assert result.thermal_violations == []
    assert "Auto-corrected" in result.summary_text


def test_llm_only_dispatcher_missing_matpower_file_returns_structured_error(tmp_path):
    session = SessionState()
    ctx = ToolContext(
        session=session,
        solver_backend="llm_only",
        llm_provider="gemini",
        llm_model="gemini-2.5-flash",
        llm_api_key="dummy-key",
        llm_temperature=0.0,
        llm_timeout_s=5.0,
        matpower_data_root=str(tmp_path),
        matpower_case_date="2017-01-01",
    )
    dispatcher = build_default_dispatcher(ctx)

    out = json.loads(dispatcher.dispatch("load_case", {"case_name": "case14"}))
    assert out.get("case_name") == "case14"

    pf_out = json.loads(dispatcher.dispatch("run_powerflow", {}))
    assert "error" in pf_out
    assert FETCH_CMD in str(pf_out.get("error", "")) or pf_out.get("fetch_command") == FETCH_CMD
