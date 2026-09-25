"""Rule-based (LLM-free) baseline parser tests. No network, no API keys."""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from deterministic.rule_based import MVA_WARNING, CannotParse, parse, parse_detailed, run, words_to_int
from agent.tools import TOOLS, ToolContext
from solver.schemas import SessionState

TOOL_PARAMS = {t["name"]: set(t["parameters"].get("properties", {})) for t in TOOLS}


def _assert_args_match_schema(steps):
    for step in steps:
        assert step["tool"] in TOOL_PARAMS, step
        assert set(step["args"]) <= TOOL_PARAMS[step["tool"]], step


@pytest.mark.parametrize(
    "text,expected",
    [
        ("load case14", [{"tool": "load_case", "args": {"case_name": "case14"}}]),
        ("Load the IEEE 30-bus system", [{"tool": "load_case", "args": {"case_name": "case30"}}]),
        ("please load case 118", [{"tool": "load_case", "args": {"case_name": "case118"}}]),
        ("run power flow", [{"tool": "run_powerflow", "args": {}}]),
        ("Solve the load flow", [{"tool": "run_powerflow", "args": {}}]),
        ("set load at bus 7 to 45 MW", [{"tool": "modify_load", "args": {"bus_id": 7, "p_mw": 45.0}}]),
        (
            "change the load on bus 3 to 20 MW and Q to 5 Mvar",
            [{"tool": "modify_load", "args": {"bus_id": 3, "p_mw": 20.0, "q_mvar": 5.0}}],
        ),
        ("disconnect line 4-5", [{"tool": "disconnect_line", "args": {"from_bus": 4, "to_bus": 5}}]),
        ("trip the line between bus 4 and bus 5", [{"tool": "disconnect_line", "args": {"from_bus": 4, "to_bus": 5}}]),
        ("reconnect line 4-5", [{"tool": "reconnect_line", "args": {"from_bus": 4, "to_bus": 5}}]),
        ("restore the line between bus 2 and bus 3", [{"tool": "reconnect_line", "args": {"from_bus": 2, "to_bus": 3}}]),
        ("report the worst voltage bus", [{"tool": "run_powerflow", "args": {}, "derive": {"kind": "min_voltage_bus"}}]),
        ("which bus has the lowest voltage?", [{"tool": "run_powerflow", "args": {}, "derive": {"kind": "min_voltage_bus"}}]),
        (
            "list lines with loading above 80 percent",
            [{"tool": "run_powerflow", "args": {}, "derive": {"kind": "lines_above_loading", "threshold_percent": 80.0}}],
        ),
        (
            "show overloaded lines",
            [{"tool": "run_powerflow", "args": {}, "derive": {"kind": "lines_above_loading", "threshold_percent": 100.0}}],
        ),
        ("run N-1 contingency analysis", [{"tool": "run_n1_contingency", "args": {"top_k": 5}}]),
        ("run n-1 with top 3", [{"tool": "run_n1_contingency", "args": {"top_k": 3}}]),
    ],
)
def test_each_supported_phrasing_parses_to_expected_tool_calls(text, expected):
    steps = parse(text)
    assert steps == expected
    _assert_args_match_schema(steps)


def test_words_to_digits():
    assert words_to_int("7") == 7
    assert words_to_int("seven") == 7
    assert words_to_int("Twenty") == 20
    with pytest.raises(ValueError):
        words_to_int("thirty")
    assert parse("set load at bus seven to 45 MW") == [{"tool": "modify_load", "args": {"bus_id": 7, "p_mw": 45.0}}]
    assert parse("open the branch from bus four to bus five") == [
        {"tool": "disconnect_line", "args": {"from_bus": 4, "to_bus": 5}}
    ]
    assert parse("restore the line between bus twelve and bus thirteen") == [
        {"tool": "reconnect_line", "args": {"from_bus": 12, "to_bus": 13}}
    ]


def test_mva_is_treated_as_active_power_with_flag():
    detailed = parse_detailed("Set the load at bus 9 to 30 MVA")
    assert detailed["plan"] == [{"tool": "modify_load", "args": {"bus_id": 9, "p_mw": 30.0}, "flags": ["mva_as_mw"]}]
    assert MVA_WARNING in detailed["warnings"]
    assert parse_detailed("set load at bus 9 to 30 MW")["warnings"] == []


def test_multi_clause_requests_keep_order():
    steps = parse("load case14, run power flow, then report the worst voltage bus")
    assert [s["tool"] for s in steps] == ["load_case", "run_powerflow"]
    assert steps[-1]["derive"] == {"kind": "min_voltage_bus"}

    steps = parse("Load case30 and disconnect line between bus 2 and bus 4 and list lines with loading above 50%")
    assert steps == [
        {"tool": "load_case", "args": {"case_name": "case30"}},
        {"tool": "disconnect_line", "args": {"from_bus": 2, "to_bus": 4}},
        {"tool": "run_powerflow", "args": {}, "derive": {"kind": "lines_above_loading", "threshold_percent": 50.0}},
    ]


@pytest.mark.parametrize(
    "text",
    ["what is the weather today", "increase generation at bus 2", "", "load case14 and make me a sandwich", "load case 99"],
)
def test_unknown_phrasing_is_explicit_cannot_parse(text):
    with pytest.raises(CannotParse):
        parse(text)
    out = run(text, ToolContext(session=SessionState()))
    assert out["ok"] is False
    assert out["status"] == "cannot_parse"
    assert out["plan"] == [] and out["outputs"] == []
    assert "cannot parse" in out["answer"].lower()


def test_run_executes_end_to_end_on_case14():
    session = SessionState()
    ctx = ToolContext(session=session)

    out = run("load case14, run power flow, then report the worst voltage bus and list lines with loading above 50%", ctx)

    assert out["ok"] is True and out["status"] == "ok"
    assert [o["tool"] for o in out["outputs"]] == ["load_case", "run_powerflow", "run_powerflow"]
    assert session.active_case == "case14"
    assert session.last_result is not None and session.last_result.converged is True

    pf = out["outputs"][1]["output"]
    assert pf["converged"] is True and pf["total_load_mw"] > 0

    kinds = [d["kind"] for d in out["derived"]]
    assert kinds == ["min_voltage_bus", "lines_above_loading"]
    worst = out["derived"][0]
    expected_worst = min(session.last_result.bus_voltages, key=lambda b: b.vm_pu)
    assert worst["bus_id"] == expected_worst.bus_id
    assert worst["vm_pu"] == pytest.approx(expected_worst.vm_pu)
    assert f"bus {expected_worst.bus_id}" in out["answer"]
    for line in out["derived"][1]["lines"]:
        assert line["loading_percent"] > 50.0

    # follow-up operations reuse the same context
    out2 = run("set load at bus 7 to 45 MW", ctx)
    assert out2["ok"] is True
    assert out2["outputs"][0]["output"]["converged"] is True
    assert session.modification_log[-1].action == "modify_load"
    assert session.modification_log[-1].parameters["bus_id"] == 7

    out3 = run("disconnect line 4-5 then run N-1 with top 2", ctx)
    assert out3["ok"] is True
    assert [o["tool"] for o in out3["outputs"]] == ["disconnect_line", "run_n1_contingency"]
    assert len(out3["outputs"][1]["output"]["n1_report"]["results"]) <= 2
