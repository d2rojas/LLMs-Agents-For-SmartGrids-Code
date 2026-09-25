"""The design page is generated from the code (prompts, tool outputs, source listings), but its gate
table, scoring definitions, answer-field table and method rows are written by hand. These tests tie each
of those claims to the code it describes, so the page cannot drift silently."""
from __future__ import annotations

import inspect
import re

import methods
from evaluation import common_eval, design_page as dp, scoring
from methods.agent.engine import CONDITION_LABELS


def test_gate_table_lists_exactly_the_engine_conditions_in_order():
    page = [(v, k) for v, k, _ in dp.GATE]
    code = [(label, key) for key, label in CONDITION_LABELS.items() if key != "faithfulness"]  # alias for old traces
    assert page == code


def test_gate_v9_is_advisory_in_code_and_on_the_page():
    v9 = next(d for v, k, d in dp.GATE if v == "V9")
    assert "never enforced" in v9 or "not enforced" in v9
    src = inspect.getsource(dp.__dict__["__builtins__"]["__import__"]("methods.agent.engine", fromlist=["_plausible_state_check"])._plausible_state_check)
    assert '"enforced": False' in src and '"passed": True' in src


def test_scoring_tolerances_match_the_evaluator():
    solved = next(d for g, m, d in dp.SCORING if m == "Solved")
    assert "1e-3 p.u." in solved and scoring.VOLTAGE_TOL_PU == 1e-3
    assert "1% on flows" in solved and inspect.signature(scoring._close).parameters["rel"].default == 0.01


def test_scoring_escalation_reasons_exist_in_the_evaluator():
    esc = next(d for g, m, d in dp.SCORING if m == "Escalated")
    src = inspect.getsource(common_eval)
    for reason in ("cannot_answer", "abstention_json", "round_limit", "gate_abstained", "declared_inability", "cannot_parse"):
        assert reason in src
    for phrase in ("cannot_answer", "abstention", "inability", "round limit", "gate"):
        assert phrase in esc


def test_scoring_groups_follow_the_results_table_order():
    groups = [g for g, _, _ in dp.SCORING]
    assert groups == sorted(groups, key=["Task utility", "Solver-grounded correctness", "Cost and time"].index)
    assert [m for _, m, _ in dp.SCORING][:1] == ["Formulation"] and [m for _, m, _ in dp.SCORING][-2:] == ["Tokens", "Time"]


def test_answer_fields_cover_the_contract_exactly():
    contract = methods.read_text("_shared/output_contract.txt")
    keys = re.findall(r'^  "([a-z_]+)"', contract, flags=re.M)
    page_keys = [k for f, *_ in dp.FIELDS for k in re.split(r",\s*", f)]
    assert set(page_keys) == set(keys), (set(page_keys) ^ set(keys))


def test_method_rows_are_the_six_methods_of_the_design():
    assert [r["runner"] for r in dp.ROWS] == [m.runner_name for m in methods.list_methods(include_archived=False)]


def test_run_settings_on_the_page_match_run_py_defaults():
    import run
    parser = run.build_parser() if hasattr(run, "build_parser") else None
    src = open(run.__file__, encoding="utf-8").read()
    assert f'"--max-rounds", type=int, default={dp.ROUNDS}' in src
    assert '"--temperature", type=float, default=0.0' in src
    assert dp.N == 20 and dp.TOOLS == "load_split" and f'default={dp.TOOLS!r}' in src or "DEFAULT_TOOL_VARIANT" in src
