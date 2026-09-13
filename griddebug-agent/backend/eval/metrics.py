"""
Repair metrics for the GridDebugAgent evaluation harness.

Pure functions (standard library only, no pandapower / openai imports) over the
per-scenario result dicts written by ``eval/run_eval.py`` to
``eval/results/full_eval_<network>.json``.  They exist so that the numbers in
the paper and in the public README can be regenerated from a saved JSON with a
single, explicit definition per column.

Three success definitions, worded as in the submitted paper (Table, Sec. VI-D):

- **Rep.**  (``repaired``)  — final network converges with zero violations.
- **Imp.**  (``improved``)  — converges with fewer violations than initially.
- **Feas.** (``feasible``)  — converges at all.

They are nested: repaired => improved => feasible.

The legacy ``fix_success`` flag that the README's "Repair (%)" column was
computed from is *not* any of the three:

    fix_success = final_converged and (final_total <= initial_total or initial_total == 0)

It is kept (``legacy_fix_success``) only for backward comparison.

A *record* is a flat dict with at least::

    {
        "network": str, "category": str, "scenario_id": str,
        "initial_converged": bool, "initial_violations": int,
        "final_converged": bool,   "final_violations": int,
        "tool_calls": int, "latency_ms": float,
    }

``to_record()`` builds one from a raw ``run_eval`` scenario dict for either
arm.  The LLM-only baseline never acts on the network, so its "final" state is
the untreated initial state (its Rep./Imp./Feas. are therefore the floor that
the agentic loop must beat).
"""
import argparse
import json
import statistics
from pathlib import Path

DEFINITIONS = {
    "repaired": "Rep.: final network converges with zero violations",
    "improved": "Imp.: converges with fewer violations than initially",
    "feasible": "Feas.: converges at all",
    "fix_success": (
        "legacy: final_converged and (final_violations <= initial_violations "
        "or initial_violations == 0); used by the README 'Repair (%)' column"
    ),
}

ARMS = ("baseline", "agentic")
METHOD_LABELS = {"baseline": "LLM-only", "agentic": "GridDebugAgent"}
NETWORK_ORDER = ["case14", "case30", "case57", "case118"]
NETWORK_LABELS = {
    "case14": "IEEE 14-bus",
    "case30": "IEEE 30-bus",
    "case57": "IEEE 57-bus",
    "case118": "IEEE 118-bus",
}


# ── Per-scenario predicates ──────────────────────────────────────────────

def feasible(r: dict) -> bool:
    """Feas.: converges at all.

    True when the final power flow converged, regardless of violations.
    """
    return bool(r["final_converged"])


def repaired(r: dict) -> bool:
    """Rep.: final network converges with zero violations.

    Normal base case (zero initial violations): counts as repaired only if it
    *stays* converged with zero violations.  No special-casing is needed —
    the rule is the same for every scenario.
    """
    return feasible(r) and int(r["final_violations"]) == 0


def improved(r: dict) -> bool:
    """Imp.: converges with fewer violations than initially.

    Nested with the other two (repaired => improved => feasible):

    - a repaired network is always counted as improved, so the normal base
      case (0 -> 0) is improved as well as repaired;
    - if the *initial* network did not converge, ``count_violations`` records
      0 violations for it (nothing can be counted); restoring convergence is
      treated as an improvement in that case, since a non-converged state is
      worse than any converged one;
    - otherwise the final violation total must be strictly lower than the
      initial one.  Equal or more violations is *not* improved.
    """
    if not feasible(r):
        return False
    if repaired(r):
        return True
    if not r.get("initial_converged", True):
        return True
    return int(r["final_violations"]) < int(r["initial_violations"])


def legacy_fix_success(r: dict) -> bool:
    """Legacy ``fix_success`` from run_eval.py, kept for backward comparison.

    converged AND (violations did not increase OR there were none initially).
    Not one of the paper's three definitions.
    """
    initial = int(r["initial_violations"])
    final = int(r["final_violations"])
    return feasible(r) and (final <= initial or initial == 0)


# ── Record extraction ────────────────────────────────────────────────────

def _violation_total(v) -> int:
    """``final_violations`` is a dict in current JSON, an int in very old ones."""
    if isinstance(v, dict):
        return int(v.get("total", 0))
    return int(v or 0)


def to_record(scenario: dict, arm: str = "agentic") -> dict | None:
    """Flatten one run_eval scenario dict into a metrics record for ``arm``.

    Returns None when the scenario errored or lacks the requested arm.
    """
    if arm not in ARMS:
        raise ValueError(f"Unknown arm '{arm}', expected one of {ARMS}")
    if "error" in scenario or arm not in scenario or "initial_state" not in scenario:
        return None

    initial_state = scenario["initial_state"]
    initial_converged = bool(initial_state.get("converged", False))
    initial_violations = _violation_total(initial_state.get("violations", {}))
    data = scenario[arm]

    if arm == "agentic":
        final_converged = bool(data.get("final_converged", False))
        final_violations = _violation_total(data.get("final_violations", {}))
        # Support both old (iterations_used) and new (tool_calls) field names
        tool_calls = int(data.get("tool_calls", data.get("iterations_used", 0)) or 0)
    else:
        # The LLM-only baseline is diagnosis-only: it never mutates the network,
        # so its final state is the untreated initial state.
        final_converged = initial_converged
        final_violations = initial_violations
        tool_calls = 0

    record = {
        "scenario_id": scenario.get("scenario_id", ""),
        "category": scenario.get("category", "unknown"),
        "network": scenario.get("network", "unknown"),
        "initial_converged": initial_converged,
        "initial_violations": initial_violations,
        "final_converged": final_converged,
        "final_violations": final_violations,
        "tool_calls": tool_calls,
        "latency_ms": float(data.get("latency_ms", 0.0) or 0.0),
    }
    record["fix_success"] = bool(data.get("fix_success", legacy_fix_success(record)))
    return record


def _as_records(results: list, arm: str) -> list:
    """Accept raw run_eval scenario dicts or already-flat records."""
    records = []
    for r in results:
        if "initial_state" in r or any(a in r for a in ARMS):
            rec = to_record(r, arm)
            if rec is not None:
                records.append(rec)
        elif "final_converged" in r:
            records.append(r)
    return records


# ── Aggregation ──────────────────────────────────────────────────────────

def _pct(count: int, n: int) -> float:
    return round(count / n * 100, 1) if n else 0.0


def _stats(records: list) -> dict:
    n = len(records)
    counts = {
        "repaired": sum(1 for r in records if repaired(r)),
        "improved": sum(1 for r in records if improved(r)),
        "feasible": sum(1 for r in records if feasible(r)),
        "fix_success": sum(1 for r in records if r.get("fix_success", legacy_fix_success(r))),
    }
    tool_calls = [int(r.get("tool_calls", 0)) for r in records]
    latencies = [float(r.get("latency_ms", 0.0)) for r in records]
    stats = {"n": n}
    for key, count in counts.items():
        stats[key] = {"count": count, "pct": _pct(count, n)}
    stats["violations_initial"] = sum(int(r["initial_violations"]) for r in records)
    stats["violations_final"] = sum(int(r["final_violations"]) for r in records)
    stats["tool_calls_mean"] = round(statistics.mean(tool_calls), 2) if tool_calls else 0.0
    stats["tool_calls_median"] = float(statistics.median(tool_calls)) if tool_calls else 0.0
    stats["latency_mean_ms"] = round(statistics.mean(latencies), 1) if latencies else 0.0
    return stats


def _network_sort_key(network: str):
    return (NETWORK_ORDER.index(network) if network in NETWORK_ORDER else len(NETWORK_ORDER), network)


def summarize(results: list, arm: str = "agentic") -> dict:
    """Per-network, per-category and overall rates for one method.

    ``results`` may be the ``scenarios`` list of one or several
    ``full_eval_<network>.json`` files (raw dicts) or flat records.
    Each stats block holds: n; repaired / improved / feasible / fix_success as
    {count, pct}; violations_initial / violations_final (summed);
    tool_calls_mean / tool_calls_median; latency_mean_ms.
    """
    records = _as_records(results, arm)
    networks = sorted({r["network"] for r in records}, key=_network_sort_key)
    categories = sorted({r.get("category", "unknown") for r in records})
    return {
        "arm": arm,
        "method": METHOD_LABELS.get(arm, arm),
        "definitions": dict(DEFINITIONS),
        "per_network": {
            net: _stats([r for r in records if r["network"] == net]) for net in networks
        },
        "per_category": {
            cat: _stats([r for r in records if r.get("category", "unknown") == cat])
            for cat in categories
        },
        "overall": _stats(records),
    }


def summarize_all(results: list) -> dict:
    """``{"baseline": summarize(..., "baseline"), "agentic": summarize(..., "agentic")}``."""
    return {arm: summarize(results, arm) for arm in ARMS}


# ── Table rendering ──────────────────────────────────────────────────────

TABLE_HEADER = (
    "| Method | Network | n | Rep. (%) | Imp. (%) | Feas. (%) | Viol. (initial → final) "
    "| Mean tool calls | Mean latency (s) | Legacy fix_success (%) |"
)
TABLE_RULE = "|---|---|---|---|---|---|---|---|---|---|"


def _row(method: str, network: str, s: dict, bold: bool = False) -> str:
    cells = [
        method,
        network,
        str(s["n"]),
        f"{s['repaired']['pct']:.1f}",
        f"{s['improved']['pct']:.1f}",
        f"{s['feasible']['pct']:.1f}",
        f"{s['violations_initial']} → {s['violations_final']}",
        f"{s['tool_calls_mean']:.1f}",
        f"{s['latency_mean_ms'] / 1000:.0f}",
        f"{s['fix_success']['pct']:.1f}",
    ]
    if bold:
        cells = [f"**{c}**" for c in cells]
    return "| " + " | ".join(cells) + " |"


def format_table(summaries: dict | list, with_definitions: bool = True) -> str:
    """Render the paper's Method × network table as Markdown.

    ``summaries`` is the dict returned by ``summarize_all`` (or a list of
    ``summarize`` outputs).  Rows: one per network per method, plus an
    **All** row when more than one network is present.
    """
    if isinstance(summaries, dict):
        summaries = [summaries[arm] for arm in ARMS if arm in summaries]

    lines = [TABLE_HEADER, TABLE_RULE]
    for summary in summaries:
        method = summary.get("method", summary.get("arm", ""))
        per_network = summary.get("per_network", {})
        for net in sorted(per_network, key=_network_sort_key):
            lines.append(_row(method, NETWORK_LABELS.get(net, net), per_network[net]))
        if len(per_network) > 1:
            lines.append(_row(method, "All", summary["overall"], bold=True))

    if with_definitions:
        lines.append("")
        lines.append("Definitions: " + "; ".join(DEFINITIONS[k] for k in ("repaired", "improved", "feasible")) + ".")
        lines.append(DEFINITIONS["fix_success"] + ".")
        lines.append("LLM-only is diagnosis-only (no remediation); its rows describe the untreated network.")
    return "\n".join(lines)


def load_scenarios(paths) -> list:
    """Concatenate the ``scenarios`` lists of one or more full_eval JSON files."""
    if isinstance(paths, (str, Path)):
        paths = [paths]
    scenarios = []
    for path in paths:
        with open(path) as f:
            data = json.load(f)
        network = data.get("network")
        for s in data.get("scenarios", []):
            s.setdefault("network", network)
            scenarios.append(s)
    return scenarios


def report_from_json(paths) -> str:
    """Regenerate the paper table from saved JSON without running anything."""
    scenarios = load_scenarios(paths)
    return format_table(summarize_all(scenarios))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Regenerate the repair-metrics table from saved eval JSON")
    parser.add_argument("--report-only", nargs="+", metavar="PATH", required=True,
                        help="One or more eval/results/full_eval_<network>.json files")
    args = parser.parse_args()
    print(report_from_json(args.report_only))
