"""Run methods on the benchmark requests and write one results folder per (model, method).

    results/sdwpf/<YYYY-MM-DD>/<model>/<method>[__<tag>]/
        config.json        what was run: command, parameters, commit, prompt hash, cost estimate
        raw/rows.jsonl     one row per request, every field the scorer produced
        raw/traces/<request-id>.json    the full trace the method left
        raw/run.log        the runner's own log
    then evaluation/postprocess.py lays out summary.csv, summary.json, REPORT.md and traces/.

Every method sees the same requests (generated with the same seed from the frozen
manifest, hash checked), the same budget, the same contract. A request that fails
is written as a row with its error rather than omitted. A request whose trace
already exists in the folder is skipped unless ``--force``, so a run killed half
way resumes where it was. ``--dry-run`` prints the plan and a cost estimate from
``pricing.json`` and spends nothing.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import methods  # noqa: E402
from config import (  # noqa: E402
    DEFAULT_MODEL_SPEC, DEFAULT_TEMPERATURE, HORIZONS_H, MAX_LLM_CALLS, MAX_TOOL_CALLS, REQUEST_TIMEOUT_S,
    ModelSpec, build_client, load_pricing, parse_model_spec, price_usd,
)
from evaluation import scoring  # noqa: E402
from evaluation.requests import Request, generate_requests, requests_digest, window_for  # noqa: E402
from methods.common import Context, MethodRun  # noqa: E402
from solver.data import load_manifest  # noqa: E402

RESULTS = PROJECT_ROOT / "results"
INSTANCE_FOLDER = "sdwpf"

# Rough tokens per request for the dry-run estimate: the 14-day history is about
# 18k tokens as CSV; a 48 h series is about 1.5k tokens of output.
TOKENS_GUESS = {  # measured on the 2026-09-27 smoke: the 14-day history is 45.7k tokens as CSV for gpt-4o-mini
    "rule_based": (0, 0), "llm_only_structured": (46000, 1800), "llm_only_cot": (46000, 4000),
    "plan_act_nogate": (9000, 3200), "react_nogate": (14000, 3500), "windagent": (18000, 4200),
}
HORIZON_FACTOR = {3: 0.75, 6: 0.8, 48: 1.0}


def source_changes() -> str:
    """What differs from HEAD in the code of this case study, results excluded.

    The old check ran ``git status --porcelain -- .`` over the whole project, which
    always includes the directory the run is writing into, so every run recorded
    itself as dirty and the flag said nothing. Results are output, not the code that
    produced them: excluding them makes ``-dirty`` mean what it claims, that the code
    on disk is not the code the commit names."""
    try:
        return subprocess.run(["git", "status", "--porcelain", "--", ".", ":!results"], cwd=PROJECT_ROOT,
                              capture_output=True, text=True, check=True).stdout.strip()
    except Exception:
        return ""


def git_commit() -> str:
    try:
        sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=PROJECT_ROOT, capture_output=True, text=True, check=True).stdout.strip()
        return sha + ("-dirty" if source_changes() else "")
    except Exception:
        return "unknown"


def refuse_if_dirty(tag: Optional[str]) -> Optional[str]:
    """An untagged run is the one the paper cites, so it must name a commit that exists.

    A tagged run is a smoke test or a side condition and may run from a working tree.
    Returns the message to print and stop on, or None to go ahead."""
    changed = source_changes()
    if tag or not changed:
        return None
    sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=PROJECT_ROOT, capture_output=True, text=True).stdout.strip()
    files = "\n".join("    " + line for line in changed.splitlines()[:20])
    more = f"\n    ... and {len(changed.splitlines()) - 20} more" if len(changed.splitlines()) > 20 else ""
    return (f"the working tree differs from {sha}, so this run would record {sha}-dirty, which names no commit\n"
            f"and cannot be reproduced. Commit the code first, or pass --tag to mark this as a side run.\n{files}{more}")


def run_method(method: str, ctx: Context, req: Request) -> MethodRun:
    card = methods.card(method)
    if card["kind"] == "deterministic":
        from methods.deterministic.rule_based import run_rule_based

        return run_rule_based(ctx)
    if card["kind"] == "llm_only":
        from methods.prompting.llm_only import run_llm_only

        return run_llm_only(ctx, strategy=card["strategy"])
    if card.get("architecture") == "plan_act":
        from methods.agent.plan_act import run_plan_act

        return run_plan_act(ctx)
    from methods.agent.loop import run_react

    return run_react(ctx, gate=bool(card.get("gate")), question_kind=req.question)


def row_for(req: Request, run: MethodRun, spec: ModelSpec, pricing: Dict[str, Any], digest: str, window: Any) -> Dict[str, Any]:
    has_tools = bool(methods.card(run.method)["uses_tools"])
    scored = scoring.score_run(run, req=req, window=window, has_tools=has_tools)
    cost = price_usd(spec, run.prompt_tokens, run.completion_tokens, pricing) if spec.uses_llm else 0.0
    return {
        "request_id": req.request_id, "instance_id": req.instance_id, "turbine": req.turbine, "base_day": req.base_day,
        "history_days": req.history_days, "horizon_hours": req.horizon_hours, "question": req.question, "condition": req.condition,
        "variant": req.variant, "requests_digest": digest, "method": run.method, "model": spec.key,
        "answer_text": run.answer_text, "answer": run.answer.as_dict(),
        "n_llm_calls": run.n_llm_calls, "n_tool_calls": run.n_tool_calls,
        "prompt_tokens": run.prompt_tokens, "completion_tokens": run.completion_tokens, "cost_usd": cost,
        "wall_time_s": run.wall_time_s, "budget_exhausted": run.budget_exhausted, "harness_declared": run.harness_declared,
        "error": run.error, "system_prompt_hash": run.system_prompt_hash, "gate": run.gate,
        **scored,
    }


def out_dir_for(spec: ModelSpec, method: str, date: str, tag: Optional[str]) -> Path:
    folder = method + (f"__{tag}" if tag else "")
    return RESULTS / INSTANCE_FOLDER / date / spec.short / folder


def estimate(method: str, spec: ModelSpec, reqs: Sequence[Request], pricing: Dict[str, Any]) -> Optional[float]:
    if not spec.uses_llm or method == "rule_based":
        return 0.0
    p, c = TOKENS_GUESS.get(method, (20000, 3000))
    total = 0.0
    for r in reqs:
        f = HORIZON_FACTOR.get(int(r.horizon_hours), 1.0)
        per = price_usd(spec, int(p * f), int(c * f), pricing)
        if per is None:
            return None
        total += per
    return round(total, 4)


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--method", action="append", help="one of the six methods; repeatable; default all six")
    ap.add_argument("--model", default=DEFAULT_MODEL_SPEC, help="provider:model (rule_based always runs with no model)")
    ap.add_argument("--instance", action="append", help="instance id such as t008-d201; repeatable; default all")
    ap.add_argument("--horizon", action="append", type=int, help="3, 6, 48; repeatable; default all three")
    ap.add_argument("--condition", default="normal", choices=("normal", "stress", "scaled"),
                    help="normal, stress (the last history day is blank), or scaled (the memorisation check: the window and its rating multiplied end to end)")
    ap.add_argument("--n", type=int, help="use only the first N instances of the manifest (a smoke test)")
    ap.add_argument("--seed", type=int, default=0, help="seed of the request phrasings")
    ap.add_argument("--tag", help="suffix on the method folder (a smoke test is not the paper set)")
    ap.add_argument("--date", default=_dt.date.today().isoformat())
    ap.add_argument("--temperature", type=float, default=DEFAULT_TEMPERATURE)
    ap.add_argument("--max-llm-calls", type=int, default=MAX_LLM_CALLS)
    ap.add_argument("--max-tool-calls", type=int, default=MAX_TOOL_CALLS)
    ap.add_argument("--timeout-s", type=float, default=REQUEST_TIMEOUT_S)
    ap.add_argument("--force", action="store_true", help="re-run requests whose trace already exists")
    ap.add_argument("--dry-run", action="store_true", help="print the plan and the cost estimate; spend nothing")
    args = ap.parse_args(argv)

    method_names = args.method or list(methods.ORDER)
    for m in method_names:
        methods.card(m)
    manifest = load_manifest()
    ids = args.instance
    if ids is None and args.n:
        ids = [e["instance_id"] for e in manifest["instances"][: args.n]]
    reqs = generate_requests(instance_ids=ids, horizons=tuple(args.horizon or HORIZONS_H), condition=args.condition, seed=args.seed, manifest=manifest)
    digest = requests_digest(reqs)
    spec = parse_model_spec(args.model)
    pricing = load_pricing()
    tag = args.tag or (None if args.condition == "normal" else args.condition)

    plan = []
    total = 0.0
    priced = True
    for m in method_names:
        s = ModelSpec("none", "rule_based") if m == "rule_based" else spec
        est = estimate(m, s, reqs, pricing)
        if est is None:
            priced = False
        else:
            total += est
        plan.append((m, s, est, out_dir_for(s, m, args.date, tag)))
    print(f"plan: {len(method_names)} method(s) x {len(reqs)} request(s) ({len({r.instance_id for r in reqs})} instances x "
          f"{sorted({r.horizon_hours for r in reqs})} h, condition {args.condition}, requests digest {digest})")
    for m, s, est, out in plan:
        print(f"  {m:22s} {s.key:36s} est {'n/a' if est is None else f'{est:7.3f} USD'}  -> {out.relative_to(PROJECT_ROOT)}")
    print(f"estimated cost: {total:.2f} USD" + ("" if priced else " (some models not in pricing.json)"))
    if args.dry_run:
        return 0

    stop = refuse_if_dirty(tag)
    if stop:
        print(stop)
        return 2
    client = build_client(spec) if spec.uses_llm and any(m != "rule_based" for m in method_names) else None
    commit = git_commit()
    command = " ".join([sys.executable] + [str(a) for a in (argv if argv is not None else sys.argv)])
    from solver import gru

    for m in method_names:
        s = ModelSpec("none", "rule_based") if m == "rule_based" else spec
        out = out_dir_for(s, m, args.date, tag)
        (out / "raw" / "traces").mkdir(parents=True, exist_ok=True)
        log = (out / "raw" / "run.log").open("a", encoding="utf-8")
        rows_path = out / "raw" / "rows.jsonl"
        existing: Dict[str, Dict[str, Any]] = {}
        if rows_path.is_file() and not args.force:
            for line in rows_path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    r = json.loads(line)
                    existing[r["request_id"]] = r
        config = {
            "kind": "run", "date": args.date, "model": s.key, "model_short": s.short, "method": m,
            "method_runner_name": methods.card(m)["runner_name"], "case": INSTANCE_FOLDER, "condition": args.condition,
            "n": len(reqs), "instances": sorted({r.instance_id for r in reqs}), "horizons": sorted({r.horizon_hours for r in reqs}),
            "seed": args.seed, "requests_digest": digest, "temperature": args.temperature,
            "max_llm_calls": args.max_llm_calls, "max_tool_calls": args.max_tool_calls, "timeout_s": args.timeout_s,
            "tag": tag, "system_prompt_hash": None, "prompt_files": methods.card(m).get("prompt_files", []),
            "command": command, "git_commit": commit, "manifest_frozen_at": manifest.get("frozen_at_utc"),
            "gru_weights_hash": gru.weights_hash(),
            "started_at": _dt.datetime.now().isoformat(timespec="seconds"),
            "estimated_cost_usd": estimate(m, s, reqs, pricing),
        }
        print(f"\n== {m} / {s.key} -> {out.relative_to(PROJECT_ROOT)}")
        log.write(f"{config['started_at']} start {m} {s.key} digest {digest}\n")
        rows: List[Dict[str, Any]] = []
        for i, req in enumerate(reqs, 1):
            if req.request_id in existing:
                rows.append(existing[req.request_id])
                print(f"  [{i:2d}/{len(reqs)}] {req.request_id:40s} kept from the previous run")
                continue
            t0 = time.time()
            window = window_for(req, manifest=manifest)
            ctx = Context(request_id=req.request_id, text=req.text, window=window, horizon_hours=req.horizon_hours, spec=s,
                          client=client if m != "rule_based" else None, max_llm_calls=args.max_llm_calls, max_tool_calls=args.max_tool_calls,
                          temperature=args.temperature, request_timeout_s=args.timeout_s)
            try:
                run = run_method(m, ctx, req)
            except Exception as e:  # never lose the row
                from methods.answer import parse_answer

                run = MethodRun(method=m, answer_text="", answer=parse_answer(""), error=f"{type(e).__name__}: {e}")
            row = row_for(req, run, s, pricing, digest, window)
            config["system_prompt_hash"] = config["system_prompt_hash"] or run.system_prompt_hash
            trace = dict(run.trace or {})
            trace.setdefault("request_id", req.request_id)
            trace["request"] = req.as_record()
            trace["tool_log"] = run.tool_log
            trace["scored"] = {k: v for k, v in row.items() if k.startswith("common_")}
            (out / "raw" / "traces" / f"{req.request_id}.json").write_text(json.dumps(trace, indent=1, default=str), encoding="utf-8")
            rows.append(row)
            with rows_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row, default=str) + "\n")
            mae = row.get("common_mae")
            msg = (f"  [{i:2d}/{len(reqs)}] {req.request_id:40s} {row['common_outcome']:15s} "
                   f"form={'ok' if row['common_formulation_exact'] else row['common_formulation_error_type']:14s} "
                   f"mae={'-' if mae is None else f'{mae:6.1f}':>6s} llm={row['n_llm_calls']:2d} tools={row['n_tool_calls']:2d} "
                   f"${row['cost_usd'] or 0:.4f} {time.time() - t0:5.0f}s" + (f" ERROR {row['error']}" if row["error"] else ""))
            print(msg)
            log.write(msg.strip() + "\n")
            log.flush()
        rows_path.write_text("".join(json.dumps(r, default=str) + "\n" for r in rows), encoding="utf-8")
        config["finished_at"] = _dt.datetime.now().isoformat(timespec="seconds")
        config["cost_usd_total"] = round(sum(float(r.get("cost_usd") or 0) for r in rows), 4)
        (out / "config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
        (out / "requests.jsonl").write_text("".join(json.dumps(r.as_record()) + "\n" for r in reqs), encoding="utf-8")
        log.write(f"{config['finished_at']} done, cost {config['cost_usd_total']} USD\n")
        log.close()
        from evaluation import postprocess

        postprocess.postprocess(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
