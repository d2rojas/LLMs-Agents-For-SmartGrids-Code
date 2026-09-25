"""Every IEEE case in the design (14, 30, 57, 118) works for every method: the prompting
tables render with the MATPOWER 1..N bus ids, the request generator yields the same 40-request
shape, the parser accepts the case, and the tools answer with the same bus ids."""
from __future__ import annotations

import json
import re

import pytest

from baselines import rule_based
from benchmarks.requests import generate_requests
from llm.prompt_variants import build_messages
from llm.tools import SessionState, ToolContext, build_default_dispatcher
from solver.case_loader import load
from solver.power_flow import SolverConfig

CASES = ["case14", "case30", "case57", "case118"]


def _net(case):
    net = load(case)
    return net[0] if isinstance(net, tuple) else net


@pytest.mark.parametrize("case", CASES)
def test_prompting_tables_use_matpower_bus_ids(case):
    net = _net(case)
    n = len(net.bus)
    msgs = build_messages("structured", "llm_only", "Run the power flow and report the lowest voltage bus.", net, case, tool_variant="load_split")
    user = msgs[1]["content"]
    bus_block = user[user.index("### Node Data"):]
    bus_block = bus_block[: bus_block.index("###", 5)] if "###" in bus_block[5:] else bus_block
    ids = [int(m) for m in re.findall(r"^\s*\d+\s+(\d+)\s", bus_block, flags=re.M)]  # index column, then name
    assert set(range(1, n + 1)) <= set(ids), f"{case}: bus table must list ids 1..{n}"
    assert "Riversde" not in user and "nan" not in bus_block.lower()


@pytest.mark.parametrize("case", CASES)
def test_tools_report_the_same_bus_ids(case):
    d = build_default_dispatcher(ToolContext(session=SessionState(), solver_config=SolverConfig()))
    d.dispatch("load_case", {"case_name": case})
    r = d.dispatch("run_powerflow", {})
    r = json.loads(r) if isinstance(r, str) else r
    ids = [b["bus_id"] for b in r["bus_voltages"]]
    assert r["converged"] and ids == list(range(1, len(ids) + 1))


@pytest.mark.parametrize("case", CASES)
def test_parser_accepts_the_case(case):
    num = case[4:]
    steps = rule_based._parse_clause(f"Load the {num}-bus test case ({case})", [])
    assert steps == [{"tool": "load_case", "args": {"case_name": case}}]


@pytest.mark.parametrize("case", ["case30", "case118"])
def test_requests_have_the_same_shape_on_every_case(case):
    reqs = generate_requests(case, 8, 0)
    assert len(reqs) == 8
    assert {r.difficulty for r in reqs} == {"plain", "parameterized", "multistep", "ambiguous"}
    assert all(r.expected_outcome == "converged" for r in reqs)
    n = len(_net(case).bus)
    for r in reqs:
        for c in r.intended_calls:
            for k, v in (c.get("args") or {}).items():
                if k in ("bus_id", "from_bus", "to_bus"):
                    assert 1 <= int(v) <= n, (case, r.id, c)
