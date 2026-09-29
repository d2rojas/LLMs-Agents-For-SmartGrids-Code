"""The page's arithmetic against the scorer's, in Python so it cannot silently stop.

results.html recomputes every cell in JavaScript from each run's summary.csv; postprocess.py
computes the same quantities in Python into summary.json. Two implementations of one metric can
disagree, and they did: the page filtered run errors on "run_error" while summary.csv wrote
"error", so three failed requests sat in the denominator and the page and REPORT.md reported
different rates for the same run (fixed in a8f983ac).

This existed as tests/crosscheck_page.mjs and ran under node. After the 2026-09-29 OS update node
was gone from the machine entirely, the test skipped, and the suite still reported green -- the one
check that keeps the page honest was off and nothing said so. A verification that only runs when a
toolchain happens to be installed is a verification that stops without telling you, so it lives
here now, in the interpreter the rest of the suite already needs.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

RESULTS = ROOT / "results"
TOL = 1e-6
VOCAB = {"solved", "escalated", "wrong_unflagged", "run_error"}


def _truthy(v) -> bool:
    return str(v or "").strip().lower() in ("true", "1")


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _outcome(row) -> str:
    return row.get("outcome") or (
        "solved" if _truthy(row.get("solved"))
        else "escalated" if _truthy(row.get("escalated"))
        else "wrong_unflagged"
    )


def _run_dirs():
    return sorted(p.parent for p in RESULTS.rglob("summary.json") if (p.parent / "summary.csv").is_file())


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


@pytest.mark.skipif(not RESULTS.is_dir(), reason="no results tree in this checkout")
def test_every_run_page_arithmetic_matches_the_stored_aggregate():
    dirs = _run_dirs()
    assert dirs, "no run directories with both summary.csv and summary.json"
    problems, compared = [], 0

    for d in dirs:
        agg = json.loads((d / "summary.json").read_text(encoding="utf-8")).get("aggregate") or {}
        all_rows = list(csv.DictReader((d / "summary.csv").open(encoding="utf-8")))
        rel = d.relative_to(RESULTS).as_posix()

        for r in all_rows:                                   # one vocabulary on both sides
            if _outcome(r) not in VOCAB:
                problems.append(f"{rel}: unknown outcome {_outcome(r)!r}")

        answered = [r for r in all_rows if _outcome(r) != "run_error"]
        errors = [r for r in all_rows if _outcome(r) == "run_error"]

        def check(name, page, stored, tol=0.0):
            nonlocal compared
            compared += 1
            if stored is None or page is None:
                return
            if abs(page - stored) > max(tol * max(1.0, abs(stored)), 0.0 if tol else 0.0):
                problems.append(f"{rel}: {name} page={page} stored={stored}")

        check("n", len(answered), agg.get("n"))
        check("solved", sum(1 for r in answered if _outcome(r) == "solved"), agg.get("solved_autonomously"))
        check("escalated", sum(1 for r in answered if _outcome(r) == "escalated"), agg.get("escalated"))
        check("wrong_unflagged", sum(1 for r in answered if _outcome(r) == "wrong_unflagged"), agg.get("wrong_unflagged"))
        check("run_errors", len(errors), agg.get("run_errors"))

        fr = [r for r in answered if (r.get("formulation_exact") or "") != ""]
        check("formulation_total", len(fr), agg.get("formulation_total"))
        check("formulation_exact", sum(1 for r in fr if _truthy(r["formulation_exact"])), agg.get("formulation_exact"))

        tr = [r for r in answered if (r.get("faithful_answers") or "") != ""]
        check("traceable_total", len(tr), agg.get("traceable_total"))
        check("traceable_answers", sum(1 for r in tr if _truthy(r["faithful_answers"])), agg.get("traceable_answers"))

        check("voltage_mae_mean", _mean([_num(r.get("voltage_mae_pu")) for r in answered]), agg.get("voltage_mae_mean"), TOL)
        check("kcl_mismatch_mean", _mean([_num(r.get("kcl_mismatch_mw")) for r in answered]), agg.get("kcl_mismatch_mean"), TOL)
        check("wall_time_s_mean", _mean([_num(r.get("wall_time_s")) for r in answered]), agg.get("wall_time_s_mean"), TOL)
        check("prompt_tokens_mean", _mean([_num(r.get("prompt_tokens")) for r in answered]), agg.get("prompt_tokens_mean"), TOL)
        check("completion_tokens_mean", _mean([_num(r.get("completion_tokens")) for r in answered]), agg.get("completion_tokens_mean"), TOL)

        # Cost is the one figure summed over what was ATTEMPTED: the money was spent on the failed
        # calls too. Rates are earned on answered requests; billing is not (2026-09-28).
        costs = [_num(r.get("cost_usd")) for r in all_rows]
        if any(c is not None for c in costs):
            check("cost_usd_total", sum(c for c in costs if c is not None), agg.get("cost_usd_total"), TOL)

    assert not problems, f"{len(problems)} disagreements out of {compared} numbers:\n" + "\n".join(problems[:30])


@pytest.mark.skipif(not RESULTS.is_dir(), reason="no results tree in this checkout")
def test_one_evaluator_scored_the_whole_tree():
    """A tree scored by two versions of the rules is not one experiment, whatever the numbers say."""
    stamps = {}
    for d in _run_dirs():
        header = json.loads((d / "summary.json").read_text(encoding="utf-8")).get("header") or {}
        stamps.setdefault(header.get("evaluator_hash"), []).append(d.relative_to(RESULTS).as_posix())
    assert len(stamps) == 1 and None not in stamps, (
        "the tree mixes evaluator versions: "
        + "; ".join(f"{k}: {len(v)} runs (e.g. {v[0]})" for k, v in stamps.items())
    )
