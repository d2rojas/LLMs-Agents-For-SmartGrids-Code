"""The extraction step on its own: how much of the request does a model read correctly?

Why this exists separately from the matrix
------------------------------------------
The run of 2026-09-28 found that every method that uses a model fails for the
same upstream reason. EVAgent solved its own problem to within 0.1 % of the
optimum and still scored zero days solved, because it had misread 85 of the 894
cars it was given, and a day is a single runnable schedule: one car scheduled
for a window it is not parked in violates the real day's constraints. Eighty-nine
of the ninety-two errors were clock readings, fifty-nine of those were exactly
thirty minutes early, and fifty-eight of those fifty-nine came from one phrase,
``a quarter to``, read as a quarter past the hour before.

That makes one question worth answering on its own: is this a property of the
model, and does a stronger one read the request correctly? Answering it through
the full matrix would pay for the tool loop, the answer turn and the gate on
every day, and none of those touch the reading. This probe runs the extraction
call and nothing else, so the question can be asked of a frontier model for a
few tens of cents instead of a few dollars.

What it measures
----------------
Per car, the four parameters ``evaluation/formulation.py`` compares: arrival and
departure exactly, energy and plug limit within one per cent. It reports the
per-session rate that the results table's ``Form.`` column reports, the count by
field, and the distribution of clock errors in steps of a quarter hour, which is
where a systematic misreading shows up as a spike rather than a spread.

It is the same prompt, the same days and the same comparison as the matrix, so a
rate from here and a rate from a full run are the same measurement.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from datetime import date as _date
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from config.llm import ModelSpec, RunRecorder, build_client, parse_model_spec
from evaluation.formulation import formulation_exact
from evaluation.requests import EVRequest, load_benchmark_requests

# Steps of a quarter hour. A systematic misreading of one phrase family shows up
# as a spike at one offset; genuine confusion is spread.
_SPIKE_STEPS = -2  # thirty minutes early: "a quarter to N" read as "a quarter past N-1"

# Clock phrases the generator can emit, for the breakdown of where errors land.
_PHRASES = (
    "a quarter to",
    "quarter past",
    "half past",
    "o'clock",
    "midnight at the end of the day",
    "midnight",
    "noon",
)


def _phrase_of(text: str, label: str) -> str:
    """The clock phrase in the sentence that describes one car, or 'digits'."""
    import re

    pattern = re.compile(rf"\b{re.escape(label).replace(' ', '[ _#-]?')}\b", re.IGNORECASE)
    line = next((l for l in text.splitlines() if pattern.search(l)), "")
    lowered = line.lower()
    for phrase in _PHRASES:
        if phrase in lowered:
            return phrase
    return "digits"


def probe_one(
    request: EVRequest,
    *,
    spec: ModelSpec,
    client: Any,
    trace_dir: Optional[Path] = None,
    write_trace: bool = False,
) -> Dict[str, Any]:
    """Run the extraction call on one request and score what it extracted.

    Args:
        request: The request to read. Its ``day`` is the ground truth.
        spec: Resolved model.
        client: A client exposing ``chat.completions.create``.
        trace_dir: Where to write the call's trace, when asked for.
        write_trace: Whether to write it.

    Returns:
        A row: the day, the counts, the per-field errors and the clock offsets.
        ``status`` is "ok", "needs_clarification", or "error" with ``error`` set.
    """
    from methods.agent.parse.parse import parse_nl_problem

    recorder = RunRecorder(spec=spec, arm="parse_probe", run_id=request.id, request=request.text)
    started = time.time()
    try:
        parsed = parse_nl_problem(request.text, model=spec.key, client=client, recorder=recorder)
    except Exception as exc:  # a failed call is a row with its error, never a gap
        usage = recorder.finish(final_text="", status="error", error=str(exc))
        return {
            "request_id": request.id, "date": request.date, "status": "error", "error": str(exc),
            "n_sessions": len(request.day.sessions), "wall_s": round(time.time() - started, 2),
            "prompt_tokens": usage.prompt_tokens, "completion_tokens": usage.completion_tokens,
        }
    usage = recorder.finish(
        final_text=parsed.raw_llm_response,
        status="needs_clarification" if parsed.needs_clarification else "ok",
    )
    if write_trace and trace_dir is not None:
        recorder.write(trace_dir)

    row: Dict[str, Any] = {
        "request_id": request.id, "date": request.date, "error": "",
        "n_sessions": len(request.day.sessions), "wall_s": round(time.time() - started, 2),
        "prompt_tokens": usage.prompt_tokens, "completion_tokens": usage.completion_tokens,
        "model_resolved": spec.key,
    }
    if parsed.needs_clarification or parsed.problem is None:
        row.update({"status": "needs_clarification", "n_exact": 0, "n_parsed": 0,
                    "fields": {}, "offsets": {}, "phrases": {}})
        return row

    verdict = formulation_exact(parsed.problem, request.day, dt_hours=request.day.dt_hours)
    fields: Counter = Counter()
    offsets: Counter = Counter()
    phrases: Counter = Counter()
    for i, session in enumerate(verdict.sessions):
        for field in session.fields:
            if field.exact:
                continue
            fields[field.name] += 1
            if field.name in ("arrival_idx", "departure_idx") and field.parsed_value is not None:
                offset = int(field.parsed_value - (field.truth_value or 0))
                offsets[offset] += 1
                phrases[_phrase_of(request.text, f"EV {i + 1}")] += 1
    row.update({
        "status": "ok",
        "n_exact": verdict.n_sessions_exact,
        "n_parsed": verdict.n_parsed,
        "fields": dict(fields),
        "offsets": {str(k): v for k, v in offsets.items()},
        "phrases": dict(phrases),
    })
    return row


def summarise(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Totals over the probed days, in the shape the results table reports."""
    ok = [r for r in rows if r["status"] == "ok"]
    truth = sum(r["n_sessions"] for r in ok)
    exact = sum(r["n_exact"] for r in ok)
    fields: Counter = Counter()
    offsets: Counter = Counter()
    phrases: Counter = Counter()
    for r in ok:
        fields.update(r["fields"])
        offsets.update({int(k): v for k, v in r["offsets"].items()})
        phrases.update(r["phrases"])
    clock = fields.get("arrival_idx", 0) + fields.get("departure_idx", 0)
    return {
        "days": len(rows),
        "days_ok": len(ok),
        "sessions": truth,
        "sessions_exact": exact,
        "sessions_rate": (exact / truth) if truth else None,
        "days_exact": sum(1 for r in ok if r["n_exact"] == r["n_sessions"]),
        "errors_by_field": dict(fields),
        "clock_errors": clock,
        "clock_offsets_steps": dict(sorted(offsets.items())),
        "spike_at_minus_30_min": offsets.get(_SPIKE_STEPS, 0),
        "clock_errors_by_phrase": dict(phrases.most_common()),
        "prompt_tokens": sum(r.get("prompt_tokens", 0) for r in rows),
        "completion_tokens": sum(r.get("completion_tokens", 0) for r in rows),
    }


def render(summary: Dict[str, Any], *, model: str, prompt_hash: str) -> str:
    """The probe as a short markdown report, written from the rows."""
    rate = summary["sessions_rate"]
    lines = [
        "# Extraction probe",
        "",
        f"`{model}` on {summary['days_ok']} of {summary['days']} frozen days, "
        f"{summary['sessions']} cars. Extraction prompt `{prompt_hash[:20]}`. "
        "No tool call, no answer turn, no gate: this is the reading step alone.",
        "",
        f"- cars read exactly: **{summary['sessions_exact']}/{summary['sessions']}**"
        + (f" ({100 * rate:.1f} %)" if rate is not None else ""),
        f"- days with every car exact: **{summary['days_exact']}/{summary['days_ok']}**",
        f"- clock errors: **{summary['clock_errors']}**, of which "
        f"**{summary['spike_at_minus_30_min']}** are exactly thirty minutes early",
        "",
        "| field | errors |",
        "|---|---|",
    ]
    for name, count in sorted(summary["errors_by_field"].items(), key=lambda kv: -kv[1]):
        lines.append(f"| `{name}` | {count} |")
    if summary["clock_errors_by_phrase"]:
        lines += ["", "| clock phrase in that car's sentence | errors |", "|---|---|"]
        for phrase, count in summary["clock_errors_by_phrase"].items():
            lines.append(f"| {phrase} | {count} |")
    if summary["clock_offsets_steps"]:
        lines += ["", "| offset | errors |", "|---|---|"]
        for steps, count in summary["clock_offsets_steps"].items():
            lines.append(f"| {int(steps) * 15:+d} min | {count} |")
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m evaluation.parse_probe",
        description=(
            "Run the extraction step alone on the frozen days and report how much of each "
            "request the model read correctly. No tool call, no answer turn, no gate."
        ),
    )
    parser.add_argument("--model", default=None, help="Model id as provider:model.")
    parser.add_argument("--days", type=int, default=None, help="Use only the first N days.")
    parser.add_argument("--site", default="caltech")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--data-source", default="cache", choices=("fixture", "cache", "auto", "api"),
                        help="'cache' is the frozen real days; 'fixture' the synthetic smoke set.")
    parser.add_argument("--out-dir", default=None, help="Where to write rows and REPORT.md.")
    parser.add_argument("--dry-run", action="store_true", help="Price it from a past run, call nothing.")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    import methods

    spec = parse_model_spec(args.model)
    requests = load_benchmark_requests(seed=args.seed, site_id=args.site, source=args.data_source)
    if args.days:
        requests = requests[: args.days]

    prompt_hash = __import__("hashlib").sha256(
        methods.read_text("_shared/parse_extraction_system.txt").encode()
    ).hexdigest()

    if args.dry_run:
        # Priced from the measured extraction calls of the run of 2026-09-28:
        # 2,171 prompt and 2,544 completion tokens per day, averaged over 20 days.
        per_day_in, per_day_out = 2171, 2544
        from evaluation.runner import load_pricing

        price_in, price_out, source = load_pricing(None, spec.key)
        usd = len(requests) * (per_day_in * price_in + per_day_out * price_out) / 1e6
        print(f"DRY RUN: {len(requests)} days on {spec.key}")
        print(f"  prices {price_in}/{price_out} per M tokens ({source})")
        print(f"  estimated {len(requests) * per_day_in:,} prompt and "
              f"{len(requests) * per_day_out:,} completion tokens, ${usd:.4f}")
        return 0

    client = build_client(spec)
    out_dir = Path(args.out_dir) if args.out_dir else Path("results") / f"parse_probe_{spec.key.replace('/', '_').replace(':', '_')}"
    out_dir.mkdir(parents=True, exist_ok=True)

    rows: List[Dict[str, Any]] = []
    for i, request in enumerate(requests, start=1):
        row = probe_one(request, spec=spec, client=client, trace_dir=out_dir / "traces", write_trace=True)
        rows.append(row)
        note = (
            f"{row['n_exact']}/{row['n_sessions']} cars exact"
            if row["status"] == "ok"
            else f"{row['status']}: {row.get('error', '')[:60]}"
        )
        print(f"  [{i}/{len(requests)}] {row['date']}  {note}", flush=True)

    summary = summarise(rows)
    (out_dir / "rows.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8"
    )
    (out_dir / "summary.json").write_text(
        json.dumps({"model": spec.key, "prompt_sha256": prompt_hash, "summary": summary}, indent=1),
        encoding="utf-8",
    )
    report = render(summary, model=spec.key, prompt_hash=prompt_hash)
    (out_dir / "REPORT.md").write_text(report, encoding="utf-8")
    print()
    print(report)
    print(f"# wrote {out_dir}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
