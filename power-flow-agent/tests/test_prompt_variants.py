"""Tests for prompting/prompt_variants.py (no network, no API keys)."""

import re
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from prompting.llm_only import parse_llm_baseline_json
from prompting.prompt_variants import (
    EXAMPLE_HEADING_PREFIX,
    EXAMPLES_HEADING,
    LLM_ONLY_OUTPUT_SECTION,
    MODES,
    REASONING_HEADING,
    SINGLE_CALL_OUTPUT_SECTION,
    STRATEGIES,
    build_messages,
    context_stats,
    few_shot_tool_calls,
    retrieve_context,
)
from agent.tools import TOOLS
from solver import case_loader

REQUEST = "Set the load at bus 9 to 40 MW and check whether any line between bus 4 and bus 9 is overloaded."


@pytest.fixture(scope="module")
def net():
    net, _ = case_loader.load("case14")
    return net


def _user(messages):
    return [m for m in messages if m["role"] == "user"][0]["content"]


@pytest.mark.parametrize("strategy", STRATEGIES)
@pytest.mark.parametrize("mode", MODES)
def test_all_combinations_well_formed(net, strategy, mode):
    msgs = build_messages(strategy, mode, REQUEST, net, "case14")
    assert isinstance(msgs, list) and len(msgs) == 2
    assert [m["role"] for m in msgs] == ["system", "user"]
    for m in msgs:
        assert set(m.keys()) == {"role", "content"}
        assert isinstance(m["content"], str) and m["content"].strip()
    assert "## Task" in _user(msgs)
    assert REQUEST in _user(msgs)


@pytest.mark.parametrize("mode", MODES)
def test_output_format_identical_within_mode(net, mode):
    expected = LLM_ONLY_OUTPUT_SECTION if mode == "llm_only" else SINGLE_CALL_OUTPUT_SECTION
    for strategy in STRATEGIES:
        user = _user(build_messages(strategy, mode, REQUEST, net, "case14"))
        assert user.rstrip().endswith(expected.rstrip()), (strategy, mode)
        assert user.count("## Output Requirements") == 1


def test_structured_llm_only_reuses_baseline_tables(net):
    user = _user(build_messages("structured", "llm_only", REQUEST, net, "case14"))
    assert "Bus Table" in user and "Line Table" in user and "Transformer Table" in user
    # braces are single (formatted), so the JSON schema is parseable as in the baseline
    assert "{{" not in user and '"bus_voltages": [{"bus_id": 1' in user


@pytest.mark.parametrize("mode", MODES)
def test_few_shot_has_exactly_two_demonstrations(net, mode):
    user = _user(build_messages("few_shot", mode, REQUEST, net, "case14"))
    assert EXAMPLES_HEADING in user
    assert user.count(EXAMPLE_HEADING_PREFIX) == 2
    assert user.count("Request: ") == 2
    for other in ("structured", "cot", "rag"):
        assert EXAMPLE_HEADING_PREFIX not in _user(build_messages(other, mode, REQUEST, net, "case14"))


def test_few_shot_llm_only_examples_parse_with_baseline_parser(net):
    user = _user(build_messages("few_shot", "llm_only", REQUEST, net, "case14"))
    fenced = re.findall(r"```json\s*(.*?)\s*```", user, re.DOTALL)
    assert len(fenced) == 2
    for block in fenced:
        obj, err = parse_llm_baseline_json(block)
        assert err is None
        assert {"converged", "bus_voltages", "line_flows", "total_generation_mw", "total_load_mw", "total_loss_mw"} <= set(obj)
    # the demonstrations describe a fictional 3-bus case, not case14
    assert "3-bus" in user
    assert all(len(parse_llm_baseline_json(b)[0]["bus_voltages"]) == 3 for b in fenced)


def test_few_shot_single_call_uses_exact_tool_names_and_args(net):
    by_name = {t["name"]: t for t in TOOLS}
    calls = few_shot_tool_calls()
    assert len(calls) >= 2
    for name, args in calls:
        assert name in by_name, name
        props = by_name[name]["parameters"].get("properties", {})
        assert set(args) <= set(props), (name, args)
        for req in by_name[name]["parameters"].get("required", []):
            assert req in args, (name, req)
    user = _user(build_messages("few_shot", "single_call", REQUEST, net, "case14"))
    for name, _ in calls:
        assert f"{name}(" in user


@pytest.mark.parametrize("mode", MODES)
def test_cot_contains_step_by_step_instruction(net, mode):
    msgs = build_messages("cot", mode, REQUEST, net, "case14")
    user = _user(msgs)
    assert REASONING_HEADING in user
    assert "step by step" in user
    for other in ("structured", "few_shot", "rag"):
        assert REASONING_HEADING not in _user(build_messages(other, mode, REQUEST, net, "case14"))
    if mode == "single_call":
        assert "plan" in user.lower() and "tool calls" in user
    else:
        assert "final JSON" in user
        assert "Reasoning mode" in msgs[0]["content"]


@pytest.mark.parametrize("mode", MODES)
def test_rag_context_shorter_than_structured_and_keeps_mentioned_buses(net, mode):
    structured = build_messages("structured", mode, REQUEST, net, "case14")
    rag = build_messages("rag", mode, REQUEST, net, "case14")
    s_stats, r_stats = context_stats(structured), context_stats(rag)
    assert s_stats["context_chars"] > 0 and r_stats["context_chars"] > 0
    assert r_stats["context_chars"] < s_stats["context_chars"]
    assert r_stats["total_chars"] < s_stats["total_chars"]
    user = _user(rag)
    assert "bus 4 |" in user and "bus 9 |" in user
    assert "bus 1 |" in user  # slack bus is always kept
    assert "4-9" in user  # the explicitly mentioned branch


def test_retrieve_context_scoring_and_forced_rows(net):
    ctx = retrieve_context(REQUEST, net, k_rows=8)
    assert ctx["mentioned_buses"] == [4, 9]
    assert ctx["n_rows_selected"] == 8 and ctx["n_rows_total"] == 34
    assert any(r.startswith("bus 9 |") for r in ctx["bus_rows"])
    assert any("| 4-9 |" in r for r in ctx["line_rows"])
    assert "modify_load" in [t["name"] for t in ctx["tools"]]
    assert "get_most_loaded_branch" in [t["name"] for t in ctx["tools"]]

    n1 = retrieve_context("Run an N-1 contingency analysis and rank the worst 5 by overload", net)
    assert n1["line_rows"] and len(n1["bus_rows"]) == 1  # only the slack bus + branches
    assert n1["tools"][0]["name"] == "run_n1_contingency"

    ln = retrieve_context("Disconnect line 7 and report the voltages", net)
    assert ln["mentioned_lines"] == [7]
    assert any(r.startswith("line 7 |") for r in ln["line_rows"])
    assert ln["tools"][0]["name"] == "disconnect_line"

    # forced rows are kept even when they exceed the budget
    tiny = retrieve_context("Compare buses 2, 3, 6 and 13", net, k_rows=1)
    assert {2, 3, 6, 13} <= {int(r.split()[1]) for r in tiny["bus_rows"]}


def test_k_rows_controls_rag_size(net):
    small = context_stats(build_messages("rag", "llm_only", REQUEST, net, "case14", k_rows=4))
    large = context_stats(build_messages("rag", "llm_only", REQUEST, net, "case14", k_rows=20))
    assert small["context_chars"] < large["context_chars"]


def test_unknown_strategy_or_mode_raises(net):
    with pytest.raises(ValueError):
        build_messages("zero_shot", "llm_only", REQUEST, net, "case14")
    with pytest.raises(ValueError):
        build_messages("structured", "agentic", REQUEST, net, "case14")
    with pytest.raises(ValueError):
        build_messages("structured", "llm_only", "   ", net, "case14")
    with pytest.raises(ValueError):
        retrieve_context(REQUEST, net, k_rows=0)
