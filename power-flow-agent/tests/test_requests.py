import sys
from dataclasses import asdict
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from evaluation.requests import (
    DIFFICULTIES,
    TOOL_NAMES,
    Request,
    _case_facts,
    compute_ground_truth,
    from_jsonl,
    generate_requests,
    to_jsonl,
)
from agent.tools import TOOLS

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


def test_zero_based_ambiguous_requests_carry_the_tag_in_visible_text():
    """The `notes` field (e.g. "Intended reading: 0-based index 4 is MATPOWER bus 5...") is
    generator-only bookkeeping, never shown to the model (see evaluation/requests.py::_assemble).
    A zero-based item is only fair/solvable if the "(0-based)" tag itself is in the request
    text the model actually sees -- this pins that it is, for both templates that can carry it
    (modify_load's bus_text, disconnect's fb_text/tb_text)."""
    from evaluation.requests import op_disconnect, op_modify_load

    op = op_modify_load(5, 20.0, bus_text="bus 4 (0-based)")
    assert "bus 4 (0-based)" in op.clause

    op = op_disconnect(5, 6, fb_text="bus 4", tb_text="bus 5 (0-based)")
    assert "bus 4" in op.clause and "bus 5 (0-based)" in op.clause

    seen_zero_based = False
    for seed in range(200):
        for r in generate_requests("case14", 6, seed=seed):
            if r.difficulty == "ambiguous" and "0-based" in r.notes:
                seen_zero_based = True
                assert "(0-based)" in r.text, r.id
        if seen_zero_based:
            break
    assert seen_zero_based, "no zero-based ambiguous item found across 200 seeds; noise-type odds may have changed"


def test_system_prompt_does_not_unconditionally_override_stated_indexing():
    """agent/prompts.py:SYSTEM_PROMPT_EN used to say identifiers are always MATPOWER 1-based and
    should be "passed as given", which flatly contradicted the "(0-based)" tag above and made
    every method (LLM and rule_based alike) get those items wrong the same way -- see
    notes/failure_examples_verbatim.md, case14-ambiguous-039-s0/-027-s0 (fixed 2026-09-17)."""
    from agent.prompts import SYSTEM_PROMPT_EN

    assert "0-based" in SYSTEM_PROMPT_EN
    assert "convert" in SYSTEM_PROMPT_EN.lower()


def test_prompt_hash_is_stable_and_sensitive_to_wording():
    from agent.prompts import SYSTEM_PROMPT_EN, prompt_hash

    assert prompt_hash(SYSTEM_PROMPT_EN) == prompt_hash(SYSTEM_PROMPT_EN)
    assert prompt_hash(SYSTEM_PROMPT_EN) != prompt_hash(SYSTEM_PROMPT_EN + " ")


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


# ----------------------------------------------------------------------------- stress difficulty

from evaluation.requests import (  # noqa: E402
    ALL_DIFFICULTIES,
    EXPECTED_OUTCOMES,
    STRESS_DIFFICULTY,
    STRESS_FACTORS,
)

N_STRESS = 10
MIN_STRESS_FAILURE_RATE = 0.8


@pytest.fixture(scope="module", params=["case14", "case30"])
def stress_case(request) -> str:
    return request.param


@pytest.fixture(scope="module")
def stress_requests(stress_case) -> list[Request]:
    return generate_requests(stress_case, N_STRESS, seed=0, difficulties=[STRESS_DIFFICULTY])


@pytest.fixture(scope="module")
def stress_ground_truths(stress_requests) -> dict[str, dict]:
    return {r.id: compute_ground_truth(r) for r in stress_requests}


def test_stress_is_opt_in_and_default_mix_is_unchanged(requests_case14):
    assert STRESS_DIFFICULTY not in DIFFICULTIES and ALL_DIFFICULTIES == DIFFICULTIES + (STRESS_DIFFICULTY,)
    assert all(r.difficulty != STRESS_DIFFICULTY and r.expected_outcome == "converged" for r in requests_case14)
    with pytest.raises(ValueError):
        generate_requests("case14", 2, seed=0, difficulties=["impossible"])
    mixed = generate_requests("case14", 5, seed=3, difficulties=list(ALL_DIFFICULTIES))
    assert [r.difficulty for r in mixed] == list(ALL_DIFFICULTIES)


def test_stress_requests_are_deterministic_and_well_formed(stress_case, stress_requests):
    again = generate_requests(stress_case, N_STRESS, seed=0, difficulties=[STRESS_DIFFICULTY])
    assert [asdict(r) for r in again] == [asdict(r) for r in stress_requests]
    facts = _case_facts(stress_case)
    schema = {t["name"]: set(t["parameters"].get("properties", {})) for t in TOOLS}
    for r in stress_requests:
        assert r.difficulty == STRESS_DIFFICULTY and r.expected_outcome in EXPECTED_OUTCOMES
        assert r.intended_calls[0] == {"tool": "load_case", "args": {"case_name": facts.case_name}}
        for call in r.intended_calls:
            assert call["tool"] in TOOL_NAMES and set(call["args"]) <= schema[call["tool"]], (r.id, call)
            for key in ("bus_id", "from_bus", "to_bus"):
                if key in call["args"]:
                    assert call["args"][key] in set(facts.bus_ids), (r.id, call)
        assert r.notes.startswith("Stress") and f"Expected outcome: {r.expected_outcome}" in r.notes, r.notes
        if "islanding" in r.notes:
            assert "becomes isolated" in r.notes or "become isolated" in r.notes or "splits" in r.notes
        else:
            assert "should not converge" in r.notes or "still converges" in r.notes


def test_stress_kinds_are_documented(stress_requests):
    facts = _case_facts(stress_requests[0].case_name)
    kinds = {"islanding" if "islanding" in r.notes else ("multi" if "multi-step" in r.notes else "ramp") for r in stress_requests}
    assert {"ramp", "multi"} <= kinds or len(stress_requests) < 6
    for r in stress_requests:
        if "islanding" in r.notes:
            # the breaking branch is NOT a safe line and its removal isolates a bus
            branch = [c for c in r.intended_calls if c["tool"] == "disconnect_line"][-1]["args"]
            fb, tb = branch["from_bus"], branch["to_bus"]
            assert (fb, tb) not in facts.safe_lines and (tb, fb) not in facts.safe_lines
            assert any({fb, tb} == {a, b} for a, b, _, _ in facts.unsafe_branches)
        else:
            ramps = [c for c in r.intended_calls if c["tool"] == "modify_load" and "nominal value" in r.text]
            assert ramps
            for c in ramps:
                base = facts.base_load_mw[c["args"]["bus_id"]]
                factor = c["args"]["p_mw"] / base
                if factor > 1.5 + 1e-6:  # the benign prefix stays within +/-50 %
                    assert min(STRESS_FACTORS) - 0.01 <= factor <= max(STRESS_FACTORS) + 0.01, (r.id, c)


def test_stress_ground_truth_is_verified_by_pandapower(stress_case, stress_requests, stress_ground_truths):
    n_fail = 0
    for r in stress_requests:
        gt = stress_ground_truths[r.id]
        assert gt["tool_errors"] == [], (r.id, gt["tool_errors"])
        assert gt["executed_tools"] == [c["tool"] for c in r.intended_calls]
        assert gt["expected_outcome"] in EXPECTED_OUTCOMES and isinstance(gt["island"], bool)
        assert gt["expected_outcome"] == r.expected_outcome and gt["outcome_matches_request"] is True, (r.id, r.text)
        if gt["expected_outcome"] == "non_converged":
            assert gt["converged"] is False and gt["bus_vm_pu"] == {} and gt["answer"]["converged"] is False
            assert "did not converge" in gt["answer"]["description"]
        elif gt["expected_outcome"] == "islanded":
            assert gt["converged"] is True and gt["island"] is True and gt["isolated_buses"]
            assert all(gt["bus_vm_pu"][str(b)] is None for b in gt["isolated_buses"])
            assert any(v is not None for v in gt["bus_vm_pu"].values())
            assert gt["answer"]["island"] is True and gt["answer"]["isolated_buses"] == gt["isolated_buses"]
            if r.query["kind"] == "worst_voltage_bus":
                assert gt["answer"]["bus_id"] not in gt["isolated_buses"] and gt["answer"]["vm_pu"] is not None
        n_fail += gt["expected_outcome"] != "converged"
    assert n_fail / len(stress_requests) >= MIN_STRESS_FAILURE_RATE, f"{stress_case}: only {n_fail}/{len(stress_requests)} stress items fail"


def test_stress_jsonl_round_trip_keeps_expected_outcome(tmp_path, stress_requests, stress_ground_truths):
    for r in stress_requests:
        r.ground_truth = stress_ground_truths[r.id]
    path = tmp_path / "stress.jsonl"
    to_jsonl(stress_requests, path)
    text = path.read_text(encoding="utf-8")
    assert "NaN" not in text and '"expected_outcome"' in text
    loaded = from_jsonl(path)
    assert [asdict(r) for r in loaded] == [asdict(r) for r in stress_requests]
    assert {r.expected_outcome for r in loaded} <= set(EXPECTED_OUTCOMES)
    # old files without the field still load with the default
    legacy = {k: v for k, v in asdict(stress_requests[0]).items() if k not in ("expected_outcome", "ground_truth")}
    assert Request(**legacy).expected_outcome == "converged"
