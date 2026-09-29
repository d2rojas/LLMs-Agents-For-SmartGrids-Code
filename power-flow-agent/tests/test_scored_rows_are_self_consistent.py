"""Invariants every scored request must satisfy, whatever the numbers turn out to be.

These began as a scratch script during the 2026-09-28 audit and were lost when the machine
restarted, which is the argument for them living here: a check kept outside the suite is a check
that disappears. They read summary.csv only and never write.

What they are for: a row can be individually plausible and still be impossible in combination --
solved and escalated at once, an answer scored for accuracy that reported no state, a gate that
abstained without spending its retry. None of that shows up in a rate.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

RESULTS = Path(__file__).resolve().parents[1] / "results"


def _t(v) -> bool:
    return str(v or "").strip().lower() in ("true", "1")


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _rows():
    for csv_path in sorted(RESULTS.rglob("summary.csv")):
        rel = csv_path.parent.relative_to(RESULTS).as_posix()
        for row in csv.DictReader(csv_path.open(encoding="utf-8")):
            yield rel, row


@pytest.mark.skipif(not RESULTS.is_dir(), reason="no results tree in this checkout")
def test_every_scored_row_is_internally_consistent():
    problems = []
    n = 0
    for rel, r in _rows():
        n += 1
        rid = f"{rel}/{r.get('request_id')}"
        err = (r.get("error") or "").strip()
        # common_eval.py: only an API failure is a run_error. Any other exception (an unparseable
        # answer, a tool the method misused) is the method's own failure and keeps its outcome.
        is_run_error = "LLM request failed" in err
        solved, esc, wrong = _t(r.get("solved")), _t(r.get("escalated")), _t(r.get("wrong_silently"))
        outcome = r.get("outcome")

        if is_run_error:
            if solved or esc or wrong:
                problems.append(f"{rid}: run_error also flagged as an outcome")
            if outcome != "run_error":
                problems.append(f"{rid}: outcome {outcome!r}, expected run_error")
            if r.get("formulation_exact") not in ("", "None", None):
                problems.append(f"{rid}: formulation scored on a request that never got an answer")
            if _num(r.get("voltage_mae_pu")) is not None:
                problems.append(f"{rid}: voltage error measured on a request that never got an answer")
        else:
            if solved + esc + wrong != 1:
                problems.append(f"{rid}: {solved+esc+wrong} outcome flags set, expected exactly 1")
            want = "solved" if solved else "escalated" if esc else "wrong_unflagged"
            if outcome != want:
                problems.append(f"{rid}: outcome {outcome!r} disagrees with its flags ({want})")
            if solved and _num(r.get("voltage_mae_pu")) is None:
                problems.append(f"{rid}: solved but carries no voltage error")

        vo, va = r.get("verification_outcome"), _num(r.get("verification_attempts"))
        if vo and va is not None:
            if vo == "abstained" and va < 2:
                problems.append(f"{rid}: abstained after {va:g} attempt(s); the retry was never spent")
            if vo == "pass_first" and va != 1:
                problems.append(f"{rid}: pass_first with {va:g} attempts")
        if vo == "abstained" and not esc:
            problems.append(f"{rid}: the gate abstained but the row is not escalated")

        nn, nu = _num(r.get("n_numbers")), _num(r.get("n_untraceable_numbers"))
        if nn is not None and nu is not None and nu > nn:
            problems.append(f"{rid}: {nu:g} untraceable numbers out of {nn:g} reported")

        calls = _num(r.get("n_llm_calls"))
        if "rule_based" in rel and calls not in (None, 0):
            problems.append(f"{rid}: the deterministic parser called an LLM {calls:g} times")
        if "rule_based" not in rel and not is_run_error and calls in (None, 0):
            problems.append(f"{rid}: an LLM method made no model call")
        if any(m in rel for m in ("llm_only_structured", "llm_only_cot")):
            nt = _num(r.get("n_tool_calls"))
            if nt not in (None, 0):
                problems.append(f"{rid}: a no-tools row called {nt:g} tools")

    assert n, "no scored rows found"
    assert not problems, f"{len(problems)} of {n} rows inconsistent:\n" + "\n".join(problems[:30])
