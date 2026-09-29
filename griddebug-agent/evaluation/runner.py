"""Run methods on scenarios and write one results folder per (network, model, method).

    results/<ieeeNN>/<YYYY-MM-DD>/<model>/<method>[__<tag>]/
        config.json        what was run: command, parameters, commit, prompt hash, cost estimate
        raw/rows.jsonl     one row per scenario, every field the scorer produced
        raw/traces/<request-id>.json    the full trace the method left
        raw/run.log        the runner's own log
    then evaluation/postprocess.py lays out summary.csv, summary.json, REPORT.md and traces/.

Every method sees the same scenarios (built from the frozen manifest, hash checked),
the same evidence, the same budget. A scenario that fails is written as a row with
its error rather than omitted. A scenario whose trace already exists in the folder
is skipped unless ``--force``, so a run killed half way resumes where it was.
``--dry-run`` prints the plan and a cost estimate from ``pricing.json`` and spends
nothing.
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
    DEFAULT_MODEL_SPEC, DEFAULT_TEMPERATURE, MAX_LLM_CALLS, MAX_TOOL_CALLS, NETWORK_FOLDER, NETWORKS,
    SCENARIO_TIMEOUT_S, ModelSpec, build_client, load_pricing, parse_model_spec, price_usd,
)
from evaluation import scoring  # noqa: E402
from evaluation.requests import Request, build_request, fresh_network  # noqa: E402
from evaluation.scenarios import INSTANCES, N_INSTANCES, SCENARIO_IDS, manifest as M  # noqa: E402
from methods.common import Context, MethodRun  # noqa: E402

RESULTS = PROJECT_ROOT / "results"

# Rough tokens per scenario for the dry-run estimate, from the April 2026 traces
# (about 15 model calls with a growing context on the loop rows).
TOKENS_GUESS = {
    "rule_based": (0, 0), "llm_only_structured": (4500, 700), "llm_only_cot": (4700, 1400),
    "plan_act_nogate": (9000, 1200), "react_nogate": (100000, 2500), "griddebug": (110000, 2800),
}
NETWORK_FACTOR = {"case14": 0.8, "case30": 1.0, "case57": 1.3, "case118": 2.0, "case300": 3.3}


def git_commit() -> str:
    try:
        sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=PROJECT_ROOT, capture_output=True, text=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain", "--", "."], cwd=PROJECT_ROOT, capture_output=True, text=True, check=True).stdout.strip()
        return sha + ("-dirty" if dirty else "")
    except Exception:
        return "unknown"


def run_method(method: str, ctx: Context) -> MethodRun:
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

    return run_react(ctx, gate=bool(card.get("gate")))


def row_for(req: Request, run: MethodRun, spec: ModelSpec, pricing: Dict[str, Any]) -> Dict[str, Any]:
    scored = scoring.score_run(run, injected=req.injected, initial=req.initial, base_keys=req.base_keys,
                               evidence_text=req.evidence_text, request_text=req.text, base_load_mw=req.base_load_mw)
    cost = price_usd(spec, run.prompt_tokens, run.completion_tokens, pricing) if spec.uses_llm else 0.0
    tools_by_kind: Dict[str, int] = {}
    for e in run.tool_log:
        tools_by_kind[e.get("kind", "?")] = tools_by_kind.get(e.get("kind", "?"), 0) + 1
    return {
        "request_id": req.request_id, "network": req.network, "scenario_id": req.scenario_id, "variant": req.variant, "category": req.category,
        "label": req.label, "method": run.method, "model": spec.key,
        "injected_fault_type": req.injected.fault_type, "injected_components": req.injected.components,
        "initial_state": req.initial.label, "initial_converged": req.initial.converged, "initial_n_new": req.initial.n_new,
        "initial_n_violations": req.initial.n_violations, "initial_islanded": req.initial.islanded_load_buses,
        "answer_text": run.answer_text, "answer": run.answer.as_dict(),
        "n_actions": sum(1 for e in run.tool_log if e.get("kind") == "action"), "tools_by_kind": tools_by_kind,
        "n_llm_calls": run.n_llm_calls, "n_tool_calls": run.n_tool_calls,
        "prompt_tokens": run.prompt_tokens, "completion_tokens": run.completion_tokens, "cost_usd": cost,
        "wall_time_s": run.wall_time_s, "budget_exhausted": run.budget_exhausted, "harness_declared": run.harness_declared,
        "error": run.error, "system_prompt_hash": run.system_prompt_hash, "gate": run.gate,
        **scored,
    }


def out_dir_for(network: str, spec: ModelSpec, method: str, date: str, tag: Optional[str]) -> Path:
    folder = method + (f"__{tag}" if tag else "")
    return RESULTS / NETWORK_FOLDER.get(network, network) / date / spec.short / folder


def estimate(method: str, network: str, spec: ModelSpec, n: int, pricing: Dict[str, Any]) -> Optional[float]:
    if not spec.uses_llm or method == "rule_based":
        return 0.0
    p, c = TOKENS_GUESS.get(method, (20000, 1500))
    f = NETWORK_FACTOR.get(network, 1.0)
    per = price_usd(spec, int(p * f), int(c * f), pricing)
    return None if per is None else round(per * n, 4)


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--method", action="append", help="one of the six methods; repeatable; default all six")
    ap.add_argument("--model", default=DEFAULT_MODEL_SPEC, help="provider:model (rule_based always runs with no model)")
    ap.add_argument("--network", action="append", help="case14, case30, case57; repeatable; default all three")
    ap.add_argument("--scenario", action="append", help="fault class id; repeatable; every variant of it runs; default all thirteen classes (20 instances)")
    ap.add_argument("--tag", help="suffix on the method folder (a smoke test is not the paper set)")
    ap.add_argument("--date", default=_dt.date.today().isoformat())
    ap.add_argument("--temperature", type=float, default=DEFAULT_TEMPERATURE)
    ap.add_argument("--max-llm-calls", type=int, default=MAX_LLM_CALLS)
    ap.add_argument("--max-tool-calls", type=int, default=MAX_TOOL_CALLS)
    ap.add_argument("--timeout-s", type=float, default=SCENARIO_TIMEOUT_S)
    ap.add_argument("--force", action="store_true", help="re-run scenarios whose trace already exists")
    ap.add_argument("--no-manifest-check", action="store_true")
    ap.add_argument("--dry-run", action="store_true", help="print the plan and the cost estimate; spend nothing")
    args = ap.parse_args(argv)

    method_names = args.method or list(methods.ORDER)
    for m in method_names:
        methods.card(m)  # unknown method is an error before anything runs
    networks = args.network or list(NETWORKS)
    scenario_ids = args.scenario or list(SCENARIO_IDS)
    for sid in scenario_ids:
        if sid not in SCENARIO_IDS:
            raise SystemExit(f"unknown scenario class {sid!r}; known: {', '.join(SCENARIO_IDS)}")
    instances = [(sid, v) for sid, v in INSTANCES if sid in set(scenario_ids)]
    spec = parse_model_spec(args.model)
    pricing = load_pricing()

    plan = []
    total = 0.0
    priced = True
    for net in networks:
        for m in method_names:
            s = ModelSpec("none", "rule_based") if m == "rule_based" else spec
            est = estimate(m, net, s, len(instances), pricing)
            if est is None:
                priced = False
            else:
                total += est
            plan.append((net, m, s, est, out_dir_for(net, s, m, args.date, args.tag)))
    print(f"plan: {len(networks)} network(s) x {len(method_names)} method(s) x {len(instances)} instance(s) "
          f"({len(set(sid for sid, _ in instances))} fault classes) = {len(plan) * len(instances)} runs")
    for net, m, s, est, out in plan:
        print(f"  {net:8s} {m:22s} {s.key:36s} est {'n/a' if est is None else f'{est:7.3f} USD'}  -> {out.relative_to(PROJECT_ROOT)}")
    print(f"estimated cost: {total:.2f} USD" + ("" if priced else " (some models not in pricing.json)"))
    if args.dry_run:
        return 0

    # The paper set has to be reproducible from the repository. A run started from a
    # dirty tree records "<sha>-dirty", which identifies nothing: the code that
    # produced it is not in any commit. Smoke runs carry a tag and may be dirty,
    # because nobody will publish them.
    commit_now = git_commit()
    if not args.tag and commit_now.endswith("-dirty"):
        print("refusing to run the paper set from a tree with uncommitted changes.\n"
              f"  the run would record {commit_now}, which no one can check out later.\n"
              "  commit first, or pass --tag <name> if this is a smoke run.")
        return 2

    client = build_client(spec) if spec.uses_llm and any(m != "rule_based" for m in method_names) else None
    manifest = None if args.no_manifest_check else M.load_manifest()
    commit = git_commit()
    command = " ".join([sys.executable] + [str(a) for a in (argv if argv is not None else sys.argv)])

    for net_name in networks:
        requests = []
        for sid, variant in instances:
            req = build_request(net_name, sid, variant)
            if manifest is not None:
                M.check(req, manifest)
            requests.append(req)
        for m in method_names:
            s = ModelSpec("none", "rule_based") if m == "rule_based" else spec
            out = out_dir_for(net_name, s, m, args.date, args.tag)
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
                "method_runner_name": methods.card(m)["runner_name"], "case": net_name, "condition": "normal",
                "n": len(requests), "scenarios": scenario_ids, "instances": [f"{a}-v{b}" for a, b in instances],
                "instances_per_network": N_INSTANCES, "temperature": args.temperature,
                "max_llm_calls": args.max_llm_calls, "max_tool_calls": args.max_tool_calls, "timeout_s": args.timeout_s,
                "tag": args.tag, "system_prompt_hash": None, "prompt_files": methods.card(m).get("prompt_files", []),
                "command": command, "git_commit": commit, "pandapower": __import__("pandapower").__version__,
                "manifest_frozen_at": (manifest or {}).get("frozen_at_utc"),
                "started_at": _dt.datetime.now().isoformat(timespec="seconds"),
                "estimated_cost_usd": estimate(m, net_name, s, len(requests), pricing),
            }
            print(f"\n== {net_name} / {m} / {s.key} -> {out.relative_to(PROJECT_ROOT)}")
            log.write(f"{config['started_at']} start {net_name} {m} {s.key}\n")
            rows: List[Dict[str, Any]] = []
            for i, req in enumerate(requests, 1):
                if req.request_id in existing:
                    rows.append(existing[req.request_id])
                    print(f"  [{i:2d}/{len(requests)}] {req.scenario_id + '-v' + str(req.variant):33s} kept from the previous run")
                    continue
                t0 = time.time()
                ctx = Context(request_id=req.request_id, text=req.text, evidence_text=req.evidence_text, net=fresh_network(req),
                              base_keys=req.base_keys, spec=s, client=client if m != "rule_based" else None,
                              max_llm_calls=args.max_llm_calls, max_tool_calls=args.max_tool_calls,
                              temperature=args.temperature, scenario_timeout_s=args.timeout_s)
                try:
                    run = run_method(m, ctx)
                except Exception as e:  # never lose the row
                    from methods.answer import parse_answer

                    run = MethodRun(method=m, answer_text="", answer=parse_answer(""), final_net=ctx.net, error=f"{type(e).__name__}: {e}")
                row = row_for(req, run, s, pricing)
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
                msg = (f"  [{i:2d}/{len(requests)}] {req.scenario_id + '-v' + str(req.variant):33s} {row['common_outcome']:15s} "
                       f"diag={'ok' if row['common_formulation_exact'] else row['common_formulation_error_type']:16s} "
                       f"llm={row['n_llm_calls']:2d} tools={row['n_tool_calls']:2d} ${row['cost_usd'] or 0:.4f} {time.time() - t0:5.0f}s"
                       + (f" ERROR {row['error']}" if row["error"] else ""))
                print(msg)
                log.write(msg.strip() + "\n")
                log.flush()
            # rewrite rows.jsonl in scenario order (kept + new)
            rows_path.write_text("".join(json.dumps(r, default=str) + "\n" for r in rows), encoding="utf-8")
            config["finished_at"] = _dt.datetime.now().isoformat(timespec="seconds")
            config["cost_usd_total"] = round(sum(float(r.get("cost_usd") or 0) for r in rows), 4)
            (out / "config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
            log.write(f"{config['finished_at']} done, cost {config['cost_usd_total']} USD\n")
            log.close()
            from evaluation import postprocess

            postprocess.postprocess(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
