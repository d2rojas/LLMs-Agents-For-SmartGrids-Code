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
