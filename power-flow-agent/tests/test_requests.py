import sys
from dataclasses import asdict
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from benchmarks.requests import (
    DIFFICULTIES,
    TOOL_NAMES,
    Request,
    _case_facts,
    compute_ground_truth,
    from_jsonl,
    generate_requests,
    to_jsonl,
)
from llm.tools import TOOLS

N = 16  # 4 per difficulty


@pytest.fixture(scope="module")
def requests_case14() -> list[Request]:
    return generate_requests("case14", N, seed=0)


@pytest.fixture(scope="module")
def ground_truths(requests_case14: list[Request]) -> dict[str, dict]:
    return {r.id: compute_ground_truth(r) for r in requests_case14}


def test_same_seed_gives_identical_requests(requests_case14):
    again = generate_requests("case14", N, seed=0)
    assert [asdict(r) for r in again] == [asdict(r) for r in requests_case14]
    other = generate_requests("case14", N, seed=1)
    assert [r.text for r in other] != [r.text for r in requests_case14]


def test_every_difficulty_is_represented_and_balanced(requests_case14):
    counts = {d: sum(1 for r in requests_case14 if r.difficulty == d) for d in DIFFICULTIES}
    assert set(counts) == set(DIFFICULTIES)
    assert all(c == N // len(DIFFICULTIES) for c in counts.values())
    assert len({r.id for r in requests_case14}) == N


def test_intended_calls_use_real_tool_names_and_argument_names(requests_case14):
    schema = {t["name"]: set(t["parameters"].get("properties", {})) for t in TOOLS}
    for r in requests_case14:
        assert r.intended_calls[0] == {"tool": "load_case", "args": {"case_name": "case14"}}
        for call in r.intended_calls:
            assert call["tool"] in TOOL_NAMES
            assert set(call["args"]) <= schema[call["tool"]], (r.id, call)


def test_bus_ids_in_requests_exist_in_case(requests_case14):
    facts = _case_facts("case14")
    valid = set(facts.bus_ids)
    for r in requests_case14:
        for call in r.intended_calls:
            for key in ("bus_id", "from_bus", "to_bus"):
                if key in call["args"]:
                    assert call["args"][key] in valid, (r.id, call)
            if call["tool"] == "modify_load":
                base = facts.base_load_mw[call["args"]["bus_id"]]
                assert 0.5 * base - 0.1 <= call["args"]["p_mw"] <= 1.5 * base + 0.1


def test_ambiguous_requests_document_intended_reading(requests_case14):
    for r in requests_case14:
        if r.difficulty == "ambiguous":
            assert "Intended reading" in r.notes, r.id
        if r.difficulty == "multistep":
            assert 3 <= len(r.intended_calls) <= 6  # load_case + 2..4 ops (+ explicit run_powerflow)


def test_intended_calls_execute_without_error(requests_case14, ground_truths):
    for r in requests_case14:
        gt = ground_truths[r.id]
        assert gt["tool_errors"] == [], (r.id, r.text, gt["tool_errors"])
        assert gt["executed_tools"] == [c["tool"] for c in r.intended_calls]
        assert gt["answer"] is not None
        assert set(gt["bus_vm_pu"]) == {str(b) for b in _case_facts("case14").bus_ids} or not gt["converged"]


def test_plain_and_parameterized_ground_truth_converges(requests_case14, ground_truths):
    for r in requests_case14:
        if r.difficulty in {"plain", "parameterized"}:
            gt = ground_truths[r.id]
            assert gt["converged"] is True, (r.id, r.text)
            assert len(gt["bus_vm_pu"]) == 14
            assert gt["line_flows"] and all("loading_percent" in lf and "p_from_mw" in lf for lf in gt["line_flows"])


def test_ground_truth_is_deterministic_for_same_seed(requests_case14, ground_truths):
    r = next(r for r in requests_case14 if r.difficulty == "parameterized")
    assert compute_ground_truth(r) == ground_truths[r.id]


def test_perturbation_changes_with_seed(requests_case14, ground_truths):
    r = next(r for r in requests_case14 if r.intended_calls[-1]["tool"] == "run_powerflow")
    other = Request(**{**asdict(r), "seed": r.seed + 1})
    gt_other = compute_ground_truth(other)
    assert gt_other["converged"] is True
    assert gt_other["bus_vm_pu"] != ground_truths[r.id]["bus_vm_pu"]


def test_jsonl_round_trip_preserves_everything(tmp_path, requests_case14, ground_truths):
    for r in requests_case14:
        r.ground_truth = ground_truths[r.id]
    path = tmp_path / "requests.jsonl"
    to_jsonl(requests_case14, path)
    loaded = from_jsonl(path)
    assert [asdict(r) for r in loaded] == [asdict(r) for r in requests_case14]
