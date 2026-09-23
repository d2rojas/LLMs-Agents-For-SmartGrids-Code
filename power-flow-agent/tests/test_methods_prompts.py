"""Pin every prompt text in methods/ to the hash stamped on the runs behind the paper tables.

If a test here fails, a prompt changed. That is allowed, but it makes new runs incomparable
with the committed ones, so update the pinned value here on purpose, in the same commit, and
say so in the commit message.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import methods  # noqa: E402
from methods import prompt_hash, read_text, system_prompt_for, planner_prompt_for  # noqa: E402

# Hashes of the raw texts, recorded from the module constants on 2026-09-23 before the
# constants were moved to methods/*.txt.
PINNED_TEXTS = {
    "_shared/agent_system_prompt.txt": "7da5e2a37ec4",
    "_shared/agent_system_prompt_zh_ui.txt": "96e8ca25a690",
    "_shared/llm_only_system_prompt.txt": "e6649caa90af",
    "_shared/llm_only_user_template.txt": "27694cb49698",
    "_shared/llm_only_bus_id_note.txt": "2fe74c2cfcd8",
    "_shared/cot_system_suffix.txt": "1847f5d898fb",
    "_shared/final_answer_instruction.txt": "98fdc16e073d",
    "llm_only_cot/reasoning_section.txt": "bad7f5c07dde",
    "llm_only_nr/reasoning_section.txt": "36a6acb2c5d7",
    "llm_only_forced_structured/escape_clause_removed.txt": "728177f8847a",
    "llm_only_forced_structured/forced_replacement.txt": "124f3cf9adf4",
    "single_call_structured/task_statement.txt": "251986811430",
    "single_call_structured/output_section.txt": "2304fa83ea46",
    "single_call_cot/reasoning_section.txt": "e0bd7a11b9d9",
    "plan_act/plan_system_prompt_structured.txt": "5e9fee34a0db",
    "_shared/formulation_probe_system_prompt.txt": "dc7bdf5c5b61",
    "_shared/formulation_probe_section.txt": "537f737bee76",
    "_shared/formulation_probe_output_section.txt": "7781da365dcd",
}

# ``system_prompt_hash`` values found on the rows of the N=40 case14 runs that fill Table 5
# (results_validation_split_tool_launch, results_validation_sol_n40_clean, 2026-09-21).
PINNED_SYSTEM_PROMPTS = {
    "react": "7da5e2a37ec4",
    "react_nogate": "7da5e2a37ec4",
    "plan_act": "7da5e2a37ec4",
    "plan_act_nogate": "7da5e2a37ec4",
    "pfagent": "7da5e2a37ec4",
    "single_call:structured": "23e5d9b407f9",
    "llm_only:structured": "1b4712c641b5",
    "llm_only:cot": "063482ad676f",
    "llm_only_forced:structured": "3fdf007e43a0",
    "llm_only_forced:cot": "563a38e7a450",
    # 2026-09-23: Formulation for the prompting rows comes from this companion probe (no numbers asked)
    "formulation_probe:structured": "dc7bdf5c5b61",
    "formulation_probe:cot": "ecf6dde0930c",
}

PINNED_PLANNER_PROMPTS = {"v1": "6dfbc78e5795", "load_split": "a82318af7571"}


@pytest.mark.parametrize("rel,expected", sorted(PINNED_TEXTS.items()))
def test_prompt_text_unchanged(rel: str, expected: str) -> None:
    assert prompt_hash(read_text(rel)) == expected, f"{rel} changed; update the pin on purpose"


@pytest.mark.parametrize("name,expected", sorted(PINNED_SYSTEM_PROMPTS.items()))
def test_assembled_system_prompt_matches_paper_runs(name: str, expected: str) -> None:
    assert prompt_hash(system_prompt_for(name)) == expected


@pytest.mark.parametrize("variant,expected", sorted(PINNED_PLANNER_PROMPTS.items()))
def test_planner_prompt_matches_engine(variant: str, expected: str) -> None:
    from llm import engine

    text = planner_prompt_for("plan_act", tool_variant=variant)
    assert text == engine._plan_system_prompt(variant)
    assert prompt_hash(text) == expected


def test_modules_import_from_methods() -> None:
    """The modules must read the same bytes as methods/ (no second copy of a prompt)."""
    from baselines import prompts_baseline as pb
    from llm import engine, prompt_variants as pv, prompts

    assert prompts.SYSTEM_PROMPT_EN == read_text("_shared/agent_system_prompt.txt")
    assert pb.BASELINE_SYSTEM_PROMPT == read_text("_shared/llm_only_system_prompt.txt")
    assert pb.BASELINE_PROMPT_TEMPLATE == read_text("_shared/llm_only_user_template.txt")
    assert pv.SINGLE_CALL_TASK_STATEMENT == read_text("single_call_structured/task_statement.txt")
    assert pv.COT_SYSTEM_SUFFIX == read_text("_shared/cot_system_suffix.txt")
    assert engine.FINAL_ANSWER_INSTRUCTION == read_text("_shared/final_answer_instruction.txt")


def test_every_method_folder_is_registered_and_runnable() -> None:
    from benchmarks.evaluate_llms import parse_method

    folders = {p.name for p in methods.METHODS_DIR.iterdir() if p.is_dir() and not p.name.startswith("_")}
    registered = {m.folder for m in methods.list_methods()}
    assert folders == registered
    for m in methods.list_methods():
        parse_method(m.runner_name)  # raises on an unknown runner name
        for rel in m.prompt_files:
            assert (methods.METHODS_DIR / rel).is_file(), rel


# --------------------------------------------------------------------------- declared formulation (2026-09-23)


def test_answer_prompts_unchanged_and_probe_asks_only_for_formulation() -> None:
    from benchmarks.evaluate_llms import perturbed_case
    from llm.prompt_variants import build_messages

    net = perturbed_case("case14", seed=0, k=1)
    req = "Load case14 and disconnect the line between bus 10 and bus 11."
    for strategy in ("structured", "cot"):
        answer = build_messages(strategy, "llm_only", req, net, "case14")
        assert "formulation" not in answer[0]["content"].lower() and "## Formulation" not in answer[1]["content"]
        probe = build_messages(strategy, "llm_only", req, net, "case14", probe=True)
        user = probe[1]["content"]
        assert user.count("## Formulation") == 1 and "## Output Requirements" in user and "bus_voltages" not in user
        assert "- set_active_load(bus_id: integer*, p_mw: number*)" in user  # load_split catalogue by default
        assert "do not compute anything" in probe[0]["content"]
    v1 = build_messages("structured", "llm_only", req, net, "case14", probe=True, tool_variant="v1")[1]["content"]
    assert "- modify_load(" in v1 and "set_active_load" not in v1


def test_declared_formulation_is_scored_like_executed_calls() -> None:
    from benchmarks.evaluate_llms import declared_formulation, declared_formulation_check

    intended = [{"tool": "load_case", "args": {"case_name": "case14"}}, {"tool": "disconnect_line", "args": {"from_bus": 10, "to_bus": 11}}]
    exact = '{"formulation": [{"tool": "load_case", "args": {"case_name": "case14"}}, {"tool": "disconnect_line", "args": {"from_bus": 10, "to_bus": 11}}], "converged": true, "bus_voltages": [], "line_flows": [], "total_generation_mw": 0, "total_load_mw": 0, "total_loss_mw": 0}'
    fm, decl = declared_formulation_check(exact, intended, "case14")
    assert fm["formulation_exact"] is True and len(decl) == 2

    # load_case may be omitted: the case tables are in the prompt
    no_load = '{"formulation": [{"tool": "disconnect_line", "args": {"from_bus": 11, "to_bus": 10}}], "converged": false}'
    fm, _ = declared_formulation_check(no_load, intended, "case14")
    assert fm["formulation_exact"] is True  # endpoints in either order

    wrong = '{"formulation": [{"tool": "disconnect_line", "args": {"from_bus": 1, "to_bus": 5}}], "converged": false}'
    fm, _ = declared_formulation_check(wrong, intended, "case14")
    assert fm["formulation_exact"] is False and fm["formulation_error_type"] == "wrong_id"

    missing = '{"converged": false, "bus_voltages": []}'
    fm, decl = declared_formulation_check(missing, intended, "case14")
    assert decl is None and fm["formulation_exact"] is False and fm["formulation_error_type"] == "unparsed"
    assert fm["detail"].startswith("no formulation field")

    # tolerant shapes: OpenAI-style name/arguments, and bare strings
    assert declared_formulation('{"formulation": [{"name": "run_powerflow", "arguments": "{}"}, "get_status"]}') == [{"tool": "run_powerflow", "args": {}}, {"tool": "get_status", "args": {}}]
