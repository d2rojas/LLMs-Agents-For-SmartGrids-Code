#!/usr/bin/env python3
"""Offline re-scorer for ``benchmarks/evaluate_llms.py`` reports (no API key, no LLM).

Runs are expensive and metrics evolve. This tool re-derives every per-item metric
that can be computed from stored data and re-aggregates with the same functions
as the runner, writing ``report.rescored.json`` and ``scoreboard*.rescored.*``
next to the originals (or under ``--out-dir``). Originals are never overwritten.

Usage:
  .venv/bin/python benchmarks/rescore.py benchmarks/results_matrix_gpt-4o-mini/pfagent/case30 \
      [more report.json files or directories] [--trace-dir DIR] [--stored-truth] [--out-dir DIR]

What is recomputed per row
--------------------------
* trace: the untruncated per-item trace file ``<report dir>/traces/<method>/<case>/
  <request_id|default>_run<run>.json`` (``--trace-dir`` adds search roots); when
  absent, the truncated ``trace`` stored in the row.
* ground truth: ``benchmarks.evaluate_llms.execute_intended(case, intended_calls,
  seed, k)`` on the seed-perturbed case (exactly what the runner did), giving the
  ``PowerFlowResult`` needed for the numeric metrics. When the row carries
  ``request_id`` / ``gen_seed`` and the report was request-driven, the request is
  regenerated with ``benchmarks.requests.generate_requests`` (verified against the
  stored text/seed/intended_calls) and ``compute_ground_truth`` supplies the
  ``answer`` field used by ``solved``. ``--stored-truth`` skips the solver and
  keeps ``truth_converged`` / ``metrics`` from the row.
* final state: LLM-only rows re-parse ``raw_response``; tool rows take the last
  PowerFlowResult payload in the trace. With a recomputed truth, Tier I-III
  ``metrics`` are recomputed from it; otherwise the stored ``metrics`` are kept.
* ``executed_calls`` / ``formulation_*``, ``faithful_numbers``, ``stale_state_*``,
  cost counters (``metrics.py``), and ``solved`` / JSON-aware ``safe_failure`` /
  ``claimed_success_on_failure`` / ``abstained_on_solvable`` (``scoring.py``).
``ok`` / ``error`` / usage / cost_usd describe the run and are kept as stored.
Each row gets a ``rescore`` block naming its trace, truth and metrics sources.
"""

from __future__ import annotations

import argparse
import copy
import json
import logging
import re
import sys
import time
import warnings
from pathlib import Path
from typing import Any, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from benchmarks import evaluate_llms as ev  # noqa: E402
from benchmarks import metrics as bm  # noqa: E402
from benchmarks import scoring as bs  # noqa: E402

RESCORED_SUFFIX = ".rescored"
DIFF_FIELDS = (
    "success_rate",
    "solved_rate",
    "formulation_exact_rate",
    "converged_rate",
    "convergence_match_rate",
    "voltage_mae_mean",
    "flow_mae_mean",
    "faithful_numbers_mean",
    "safe_failure_rate",
    "claimed_success_on_failure_rate",
    "abstained_on_solvable_rate",
    "stale_state_rate",
)


# --------------------------------------------------------------------------- discovery


def find_reports(paths: list[str]) -> list[Path]:
    found: list[Path] = []
    for raw in paths:
        p = Path(raw)
        if p.is_dir():
            found.extend(sorted(p.rglob("report.json")))
        elif p.is_file():
            found.append(p)
        else:
            raise FileNotFoundError(f"{raw}: not a report.json or a directory")
    return [p for p in found if not p.name.endswith(f"{RESCORED_SUFFIX}.json")]


def _method_dir(method: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(method))


def trace_file_candidates(row: dict[str, Any], trace_dirs: list[Path]) -> list[Path]:
    method = str(row.get("method") or row.get("task") or "")
    name = f"{row.get('request_id') or 'default'}_run{int(row.get('run') or 0)}.json"
    return [d / _method_dir(method) / str(row.get("case_name")) / name for d in trace_dirs]


def load_full_trace(row: dict[str, Any], trace_dirs: list[Path]) -> Optional[dict[str, Any]]:
    """The per-item trace payload written by ``evaluate_item(full_trace_dir=...)``, if present."""
    for p in trace_file_candidates(row, trace_dirs):
        if p.is_file():
            try:
                payload = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                continue
            if isinstance(payload, dict):
                return payload
    return None


# --------------------------------------------------------------------------- ground truth


class TruthCache:
    """Ground truth per (case, seed, k, intended_calls) and answers per regenerated request."""

    def __init__(self, config: dict[str, Any], solver_config: Any):
        self.config = config or {}
        self.solver_config = solver_config
        self._truth: dict[str, dict[str, Any]] = {}
        self._requests: dict[tuple, dict[str, Any]] = {}
        self._answers: dict[tuple, Any] = {}
        self.n_solver_runs = 0

    def truth(self, row: dict[str, Any]) -> dict[str, Any]:
        key = json.dumps(
            [row.get("case_name"), row.get("seed"), row.get("k"), row.get("intended_calls")], sort_keys=True, default=str
        )
        if key not in self._truth:
            out: dict[str, Any] = {"result": None, "net": None, "tool_errors": [], "error": None}
            try:
                res, net, errs = ev.execute_intended(
                    str(row["case_name"]),
                    list(row.get("intended_calls") or []),
                    seed=int(row.get("seed") or 0),
                    k=int(row.get("k") or 0),
                    solver_config=self.solver_config,
                )
                self.n_solver_runs += 1
                out.update({"result": res, "net": net, "tool_errors": errs})
            except Exception as exc:  # pragma: no cover - defensive
                out["error"] = f"{type(exc).__name__}: {exc}"
            self._truth[key] = out
        return self._truth[key]

    def _requests_for(self, row: dict[str, Any]) -> dict[str, Any]:
        req_cfg = self.config.get("requests") or {}
        case = str(row.get("case_name"))
        source = req_cfg.get("source")
        if source == "generated":
            n = int(req_cfg.get("n_per_case_seed") or 0)
            diffs = tuple(req_cfg.get("difficulties") or ()) or None
            gen_seed = row.get("gen_seed")
            if not n or gen_seed is None:
                return {}
            key = (case, n, int(gen_seed), diffs)
            if key not in self._requests:
                from benchmarks.requests import generate_requests

                reqs = generate_requests(case, n, int(gen_seed), list(diffs) if diffs else None)
                self._requests[key] = {r.id: r for r in reqs}
            return self._requests[key]
        if isinstance(source, str) and Path(source).is_file():
            key = ("file", source)
            if key not in self._requests:
                from benchmarks.requests import from_jsonl

                self._requests[key] = {r.id: r for r in from_jsonl(source)}
            return self._requests[key]
        return {}

    def answer(self, row: dict[str, Any]) -> Any:
        """``compute_ground_truth(request)["answer"]`` when the request can be regenerated and matches the row."""
        rid = row.get("request_id")
        if not rid:
            return None
        key = (str(rid), row.get("seed"), row.get("k"))
        if key in self._answers:
            return self._answers[key]
        ans = None
        try:
            req = self._requests_for(row).get(str(rid))
            if (
                req is not None
                and req.text == row.get("request_text")
                and int(req.seed) == int(row.get("seed"))
                and [dict(c) for c in req.intended_calls] == [dict(c) for c in row.get("intended_calls") or []]
            ):
                from benchmarks.requests import compute_ground_truth

                ans = compute_ground_truth(req, k=int(row.get("k") or 0)).get("answer")
                self.n_solver_runs += 1
        except Exception:
            ans = None
        self._answers[key] = ans
        return ans


# --------------------------------------------------------------------------- final state


def reconstruct_final_state(row: dict[str, Any], trace: Optional[dict[str, Any]], spec: ev.MethodSpec) -> tuple[Any, Optional[bool], str]:
    """(BaselineParsed, converged, source) of the method's final power-flow state, or (None, None, reason)."""
    from baselines.llm_only import baseline_parsed_from_result
    from models.schemas import PowerFlowResult

    if spec.kind in ("task", "llm_only"):
        if spec.name == "blueprint_pf":
            return None, None, "unavailable:blueprint_parser_needs_case_file"
        try:
            parsed = ev._baseline_parser(str(row.get("raw_response") or ""), {})
        except Exception:
            return None, None, "unparsed"
        return parsed, bool(parsed.converged), "answer_json"

    records = bm._tool_records_from_trace(trace)
    fields = set(PowerFlowResult.model_fields)
    for rec in reversed(records):
        payload = bm._find_pf_payload(bm._parse_output(rec.get("output")))
        if not payload or "bus_voltages" not in payload:
            continue
        try:
            result = PowerFlowResult.model_validate({k: v for k, v in payload.items() if k in fields})
        except Exception:
            continue
        return baseline_parsed_from_result(result), bool(result.converged), "trace"
    return None, None, "unavailable:no_pf_payload_in_trace"


# --------------------------------------------------------------------------- per-row rescoring


def rescore_row(
    row: dict[str, Any],
    *,
    trace_dirs: list[Path],
    truth_cache: Optional[TruthCache],
    solver_config: Any,
) -> dict[str, Any]:
    from baselines.llm_only import evaluate_against_truth_extended

    new = copy.deepcopy(row)
    method_name = str(row.get("method") or row.get("task") or "")
    try:
        spec = ev.parse_method(method_name)
    except ValueError:
        spec = ev.MethodSpec(name=method_name, kind="engine")
    has_tools = spec.kind in ("engine", "rule_based")

    payload = load_full_trace(row, trace_dirs)
    trace = payload.get("trace") if payload and isinstance(payload.get("trace"), dict) else None
    trace_source = "file" if trace is not None else "row"
    if trace is None:
        trace = row.get("trace") if isinstance(row.get("trace"), dict) else None
    raw = row.get("raw_response")
    if raw is None and payload:
        raw = payload.get("answer")
    request_text = row.get("request_text")

    # formulation (tool methods only; LLM-only rows keep their "no tool stage" fields)
    formulation_exact = row.get("formulation_exact")
    if has_tools:
        if trace is not None:
            executed = None if trace.get("formulation_failure") else bm.executed_calls_from_trace(trace)
        else:
            executed = row.get("executed_calls")
        preloaded = str(row.get("case_name")) if spec.preload_case else None
        formulation = bm.formulation_check(list(row.get("intended_calls") or []), executed, preloaded_case=preloaded)
        formulation_exact = formulation.get("formulation_exact")
        new.update(
            {
                "executed_calls": executed,
                "formulation_exact": formulation_exact,
                "formulation_error_type": formulation.get("formulation_error_type"),
                "formulation_detail": formulation.get("detail"),
            }
        )

    # ground truth
    truth_converged = row.get("truth_converged")
    truth_result = truth_net = None
    truth_source = "stored"
    truth_answer = row.get("truth_answer")
    if truth_cache is not None and row.get("seed") is not None and row.get("intended_calls"):
        t = truth_cache.truth(row)
        if t["result"] is not None:
            truth_result, truth_net = t["result"], t["net"]
            truth_converged = bool(truth_result.converged)
            truth_source = "recomputed"
            new["truth_tool_errors"] = t["tool_errors"]
        ans = truth_cache.answer(row)
        if ans is not None:
            truth_answer = ans

    # final state and numeric metrics
    metrics = row.get("metrics")
    final_converged = row.get("final_converged")
    metrics_source = "stored"
    parsed, parsed_converged, state_source = reconstruct_final_state(row, trace, spec)
    if parsed is not None and truth_result is not None:
        net = truth_net if (not has_tools or formulation_exact is True) else None
        try:
            metrics = evaluate_against_truth_extended(
                parsed,
                truth_result,
                net=net,
                v_min=solver_config.v_min,
                v_max=solver_config.v_max,
                max_loading=solver_config.max_loading,
            )
            final_converged = parsed_converged
            metrics_source = f"recomputed:{state_source}"
        except Exception as exc:  # pragma: no cover - defensive
            metrics_source = f"stored:{type(exc).__name__}"
    elif parsed is not None:
        final_converged = parsed_converged
        metrics_source = f"stored:{state_source}"
    else:
        metrics_source = f"stored:{state_source}"

    new.update(
        {
            "metrics": metrics,
            "final_converged": final_converged,
            "truth_converged": truth_converged,
            "truth_answer": truth_answer,
        }
    )

    faith = bm.faithful_numbers(raw, bm.tool_outputs_from_trace(trace), request_text=request_text)
    stale = bm.stale_state_check(trace, raw, request_text=request_text)
    new.update(
        {
            "faithful_numbers": faith["faithful_numbers"],
            "n_numbers": faith["n_numbers"],
            "n_untraceable_numbers": faith["n_untraceable_numbers"],
            "untraceable_numbers": faith["untraceable"],
            "has_mutation": stale["has_mutation"],
            "stale_state": stale["stale_state"],
            "stale_state_no_rerun": stale["stale_state_no_rerun"],
            "stale_state_quoted_old": stale["stale_state_quoted_old"],
            "stale_state_detail": stale["detail"],
            "stale_state_trace": {
                k: stale[k]
                for k in ("last_mutation_index", "last_mutation_tool", "last_mutation_args", "prior_result_indices", "resolve_indices_after", "old_only")
            },
        }
    )
    if trace is not None:
        new.update(bm.cost_from_trace(trace))
    new.update(bs.score_row(new, truth_answer=truth_answer))
    new["rescore"] = {"trace_source": trace_source, "truth_source": truth_source, "metrics_source": metrics_source}
    if trace_source == "file":
        new["trace"] = ev._truncate_trace(trace, ev.TRACE_OUTPUT_CHARS_REPORT)
    return new


# --------------------------------------------------------------------------- report level


def aggregate_rows(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Same grouping and aggregation as ``evaluate_llms.run_benchmark``."""
    by_group: dict[tuple[str, str], list[dict[str, Any]]] = {}
    by_case: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for row in rows:
        task = row.get("task") or row.get("method")
        by_group.setdefault((row["model"], task), []).append(row)
        by_case.setdefault((row["model"], task, row["case_name"]), []).append(row)
    scoreboard = [
        {"model": m, "task": t, "method": t, **ev._aggregate_group(rs)} for (m, t), rs in sorted(by_group.items())
    ]
    per_case = [
        {"model": m, "task": t, "method": t, "case_name": c, **ev._aggregate_group(rs)}
        for (m, t, c), rs in sorted(by_case.items())
    ]
    return scoreboard, per_case


def _solver_config(config: dict[str, Any]) -> Any:
    from solver.power_flow import SolverConfig

    sc = (config or {}).get("solver_config") or {}
    return SolverConfig(
        v_min=float(sc.get("v_min", 0.95)), v_max=float(sc.get("v_max", 1.05)), max_loading=float(sc.get("max_loading", 100.0))
    )


def _fmt(v: Any) -> str:
    if v is None:
        return "n/a"
    if isinstance(v, float):
        return f"{v:.4g}"
    return str(v)


def diff_lines(old: list[dict[str, Any]], new: list[dict[str, Any]], key_cols: tuple[str, ...]) -> list[str]:
    """One line per (group, field) whose value changed, plus unchanged fields compacted."""
    lines: list[str] = []
    old_by = {tuple(str(r.get(k)) for k in key_cols): r for r in old}
    for r in new:
        key = tuple(str(r.get(k)) for k in key_cols)
        o = old_by.get(key, {})
        changed, same = [], []
        for f in DIFF_FIELDS:
            a, b = o.get(f), r.get(f)
            if a == b or (isinstance(a, float) and isinstance(b, float) and abs(a - b) <= 1e-12):
                same.append(f"{f}={_fmt(b)}")
            else:
                changed.append(f"{f}: {_fmt(a)} -> {_fmt(b)}")
        lines.append(f"[{' | '.join(key)}]")
        lines.extend(f"    {c}" for c in changed)
        if same:
            lines.append("    unchanged: " + ", ".join(same))
    return lines


def rescore_report(
    path: Path,
    *,
    trace_dirs: Optional[list[Path]] = None,
    recompute_truth: bool = True,
    out_dir: Optional[Path] = None,
    verbose: bool = True,
) -> dict[str, Any]:
    """Rescore one report.json; write ``*.rescored.*`` next to it (or under ``out_dir``)."""
    t0 = time.time()
    report = json.loads(path.read_text(encoding="utf-8"))
    config = report.get("config") or {}
    solver_config = _solver_config(config)
    dirs = [path.parent / "traces", *(trace_dirs or [])]
    cache = TruthCache(config, solver_config) if recompute_truth else None

    rows = list(report.get("runs") or [])
    new_rows = [rescore_row(r, trace_dirs=dirs, truth_cache=cache, solver_config=solver_config) for r in rows]
    scoreboard, per_case = aggregate_rows(new_rows)

    sources = {
        "trace": {}, "truth": {}, "metrics": {},
    }
    for r in new_rows:
        for k in sources:
            v = r["rescore"][f"{k}_source"]
            sources[k][v] = sources[k].get(v, 0) + 1

    new_report = {
        **report,
        "core_scoreboard_fields": ev.CORE_SCOREBOARD_FIELDS,
        "extended_scoreboard_fields": ev.EXTENDED_SCOREBOARD_FIELDS,
        "metric_definitions": bm.__doc__,
        "scoring_definitions": bs.__doc__,
        "scoreboard": scoreboard,
        "scoreboard_per_case": per_case,
        "runs": new_rows,
        "rescore": {
            "source_report": str(path),
            "rescored_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "recompute_truth": bool(recompute_truth),
            "trace_dirs": [str(d) for d in dirs],
            "n_rows": len(new_rows),
            "sources": sources,
            "n_solver_runs": cache.n_solver_runs if cache else 0,
            "previous_scoreboard": report.get("scoreboard"),
        },
    }

    out = Path(out_dir) if out_dir else path.parent
    out.mkdir(parents=True, exist_ok=True)
    ev._write_json(out / f"report{RESCORED_SUFFIX}.json", new_report)
    ev._write_json(out / f"scoreboard{RESCORED_SUFFIX}.json", scoreboard)
    ev._write_csv(out / f"scoreboard{RESCORED_SUFFIX}.csv", ev._flatten_scoreboard(scoreboard))
    ev._write_markdown(out / f"scoreboard{RESCORED_SUFFIX}.md", scoreboard, config)
    ev._write_json(out / f"scoreboard_per_case{RESCORED_SUFFIX}.json", per_case)
    ev._write_csv(out / f"scoreboard_per_case{RESCORED_SUFFIX}.csv", ev._flatten_case_scoreboard(per_case))
    ev._write_case_markdown(out / f"scoreboard_per_case{RESCORED_SUFFIX}.md", per_case)

    lines = [f"== {path}  ({len(new_rows)} rows, {time.time() - t0:.1f}s)"]
    lines.append(f"   sources: trace={sources['trace']} truth={sources['truth']} metrics={sources['metrics']}")
    lines.extend(diff_lines(report.get("scoreboard") or [], scoreboard, ("model", "task")))
    if len({r.get("case_name") for r in per_case}) > 1:
        lines.extend(diff_lines(report.get("scoreboard_per_case") or [], per_case, ("model", "task", "case_name")))
    lines.append(f"   written: {out / f'report{RESCORED_SUFFIX}.json'} (+ scoreboard{RESCORED_SUFFIX}.*)")
    if verbose:
        print("\n".join(lines))
    return {"report": new_report, "out_dir": out, "summary": lines}


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("reports", nargs="+", help="report.json files or directories (searched recursively)")
    ap.add_argument("--trace-dir", dest="trace_dirs", action="append", default=[], help="extra root(s) holding <method>/<case>/<id>_run<k>.json traces")
    ap.add_argument("--stored-truth", action="store_true", help="do not run the solver; keep truth_converged/metrics from the rows")
    ap.add_argument("--out-dir", default=None, help="write outputs here instead of next to each report (one report only, or files are overwritten)")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    warnings.filterwarnings("ignore")
    logging.getLogger("pandapower").setLevel(logging.ERROR)

    paths = find_reports(args.reports)
    if not paths:
        raise SystemExit("no report.json found")
    if args.out_dir and len(paths) > 1:
        print("warning: --out-dir with several reports; using a sub-folder per report", file=sys.stderr)
    for p in paths:
        out_dir = None
        if args.out_dir:
            out_dir = Path(args.out_dir) if len(paths) == 1 else Path(args.out_dir) / p.parent.name
        rescore_report(p, trace_dirs=[Path(d) for d in args.trace_dirs], recompute_truth=not args.stored_truth, out_dir=out_dir, verbose=not args.quiet)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
