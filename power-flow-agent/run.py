#!/usr/bin/env python3
"""PFAgent front door: run a method on a case, then render the results.

    .venv/bin/python run.py list-methods
    .venv/bin/python run.py show-prompt --method react
    .venv/bin/python run.py run --method pfagent --model openrouter:openai/gpt-4o-mini --case ieee14 --n 40 --dry-run
    .venv/bin/python run.py run --method pfagent --method react_nogate --model openai:gpt-4o-mini --case ieee14 --n 40
    .venv/bin/python run.py postprocess results/ieee14/2026-09-21/gpt-5.6-sol/pfagent
    .venv/bin/python run.py index

``run`` writes one directory per (method, model, case)::

    results/<case>/<YYYY-MM-DD>/<model>/<method>[__stress][__<tag>]/
        config.json      exact command, parameters, git commit, prompt hash
        raw/             what benchmarks/evaluate_llms.py wrote (report.json, traces/, run.log)
        traces/          NN_<request>.transcript.txt, NN_<request>.narrative.txt, NN_<request>.json
        summary.csv      one line per run
        REPORT.md        counts per metric, failure lists, cost

and refreshes results/INDEX.md. The engine is unchanged: ``run`` shells out to
``benchmarks/evaluate_llms.py`` with the same flags the paper runs used, so numbers stay
comparable. Methods are folders under ``methods/``; models are ``provider:model`` strings
(``openai:gpt-4o-mini``, ``openrouter:openai/gpt-5.6-sol``, ``anthropic:claude-sonnet-5``,
``gemini:gemini-2.5-flash-lite``). Keys come from the environment or ``.env``.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

import methods  # noqa: E402

RESULTS = PROJECT_ROOT / "results"
CASE_FOLDER = {"case14": "ieee14", "case30": "ieee30", "case57": "ieee57", "case118": "ieee118", "case300": "ieee300"}
DEFAULT_TOOL_VARIANT = "load_split"  # the tool set of the 2026-09-21 launch behind Table 5


# --------------------------------------------------------------------------- helpers


def normalize_case(name: str) -> str:
    from solver.case_loader import normalize_case_name

    return normalize_case_name(name)


def model_slug(model: str) -> str:
    if model.startswith("none:"):
        return "no-llm"
    return model.split("/")[-1].split(":")[-1]


def git_commit() -> str:
    try:
        sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=PROJECT_ROOT, capture_output=True, text=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain", "--", "."], cwd=PROJECT_ROOT, capture_output=True, text=True, check=True).stdout.strip()
        return sha + ("-dirty" if dirty else "")
    except Exception:
        return "unknown"


def load_pricing() -> Dict[str, Dict[str, float]]:
    p = PROJECT_ROOT / "pricing.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}


def tokens_guess(m: methods.Method) -> tuple[int, int]:
    """Rough (prompt, completion) tokens per request, for the dry-run estimate only."""
    if not m.uses_llm:
        return 0, 0
    if m.kind == "llm_only":
        return 6000, 500
    if m.architecture == "single_call":
        return 4000, 400
    return 20000, 1500


def estimate_cost(m: methods.Method, model: str, n_items: int, pricing: Dict[str, Dict[str, float]]) -> Optional[float]:
    price = pricing.get(model)
    if not price or not m.uses_llm:
        return 0.0 if not m.uses_llm else None
    tin, tout = tokens_guess(m)
    return n_items * (tin * price["input"] + tout * price["output"]) / 1e6


def run_dir_for(case: str, model: str, m: methods.Method, *, date: str, condition: str, tag: Optional[str]) -> Path:
    name = m.folder + ("__stress" if condition == "stress" else "") + (f"__{tag}" if tag else "")
    return RESULTS / CASE_FOLDER.get(case, case) / date / model_slug(model) / name


# --------------------------------------------------------------------------- commands


def cmd_list_methods(_: argparse.Namespace) -> int:
    print(f"{'folder':28s} {'runner name':27s} {'group':56s} tools  gate   final")
    for m in methods.list_methods():
        print(f"{m.folder:28s} {m.runner_name:27s} {m.group:56s} {str(m.uses_tools):5s}  {str(m.gate):5s}  {str(m.final_gate):5s}" + ("   [archived]" if m.archived else ""))
    print("\nDetails: run.py show-prompt --method <folder>. [archived] = under methods/_archive, not part of the current design.")
    return 0


def cmd_show_prompt(args: argparse.Namespace) -> int:
    print(methods.describe(args.method, tool_variant=args.tool_variant))
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    cases = [normalize_case(c) for c in args.cases] or ["case14"]
    ms = [methods.get_method(name) for name in args.methods]
    models = list(args.models) or ["openai:gpt-4o-mini"]
    date = args.date or _dt.date.today().isoformat()
    condition = args.condition or ("stress" if args.difficulties == ["stress"] else "normal")
    pricing = load_pricing()
    py = sys.executable
    planned: List[Dict[str, Any]] = []
    total_cost = 0.0
    unknown_price = False
    for m in ms:
        for model in (["none:rule_based"] if not m.uses_llm else models):
            for case in cases:
                out = run_dir_for(case, model, m, date=date, condition=condition, tag=args.tag)
                cmd = [py, "benchmarks/evaluate_llms.py", "--method", m.runner_name, "--case", case,
                       "--k", str(args.k), "--max-rounds", str(args.max_rounds), "--temperature", str(args.temperature),
                       "--timeout-s", str(args.timeout_s), "--tool-variant", args.tool_variant, "--plan-variant", args.plan_variant,
                       "--pricing-file", "pricing.json", "--out-dir", str(out / "raw"), "--condition", condition]
                if m.uses_llm:
                    cmd += ["--model", model]
                if args.requests:
                    cmd += ["--requests", args.requests]
                else:
                    cmd += ["--gen-requests", str(args.n)]
                if args.seed_list:
                    cmd += ["--seed-list", args.seed_list]
                else:
                    cmd += ["--seeds", str(args.seeds)]
                for d in args.difficulties or []:
                    cmd += ["--difficulty", d]
                if args.runs != 1:
                    cmd += ["--runs", str(args.runs)]
                n_items = args.n * (len(args.seed_list.split(",")) if args.seed_list else args.seeds) * args.runs
                cost = estimate_cost(m, model, n_items, pricing)
                if cost is None:
                    unknown_price = True
                else:
                    total_cost += cost
                planned.append({"method": m, "model": model, "case": case, "out": out, "cmd": cmd, "n_items": n_items, "cost": cost})

    print(f"# {len(planned)} run(s), date {date}, condition {condition}, tool variant {args.tool_variant}")
    for p in planned:
        status = "exists, skip" if (p["out"] / "raw" / "report.json").is_file() and not args.force else "run"
        cost = "no price in pricing.json" if p["cost"] is None else f"~${p['cost']:.2f}"
        print(f"  {status:12s} {p['method'].folder:26s} {p['model']:34s} {p['case']:8s} {p['n_items']:4d} items  {cost:22s} -> {p['out'].relative_to(PROJECT_ROOT)}")
    print(f"# estimated cost {'>= ' if unknown_price else ''}${total_cost:.2f} (rough token guesses times pricing.json)")
    if args.dry_run:
        print("# dry run: nothing executed. Commands:")
        for p in planned:
            print("  " + " ".join(_q(c) for c in p["cmd"]))
        return 0

    failures = 0
    for p in planned:
        out: Path = p["out"]
        if (out / "raw" / "report.json").is_file() and not args.force:
            print(f"skip  {out.relative_to(PROJECT_ROOT)} (report exists; --force to redo)")
            continue
        (out / "raw").mkdir(parents=True, exist_ok=True)
        m: methods.Method = p["method"]
        sp = methods.system_prompt_for(m, tool_variant=args.tool_variant)
        config = {
            "kind": "run", "date": date, "model": p["model"], "model_short": model_slug(p["model"]), "method": m.folder, "method_runner_name": m.runner_name,
            "case": p["case"], "condition": condition, "n": args.n, "seeds": args.seed_list or list(range(args.seeds)), "runs": args.runs, "k": args.k,
            "max_rounds": args.max_rounds, "temperature": args.temperature, "tool_variant": args.tool_variant, "plan_variant": args.plan_variant,
            "requests_file": args.requests, "difficulties": args.difficulties or None, "tag": args.tag,
            "system_prompt_hash": methods.prompt_hash(sp) if sp else None,
            "command": " ".join(_q(c) for c in p["cmd"]), "git_commit": git_commit(), "started_at": _dt.datetime.now().isoformat(timespec="seconds"),
            "estimated_cost_usd": p["cost"],
        }
        (out / "config.json").write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"run   {out.relative_to(PROJECT_ROOT)}")
        log = out / "raw" / "run.log"
        with log.open("w", encoding="utf-8") as fh:
            proc = subprocess.Popen(p["cmd"], cwd=PROJECT_ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env={**os.environ, "PYTHONUNBUFFERED": "1"})
            assert proc.stdout is not None
            for line in proc.stdout:
                fh.write(line)
                if not args.quiet:
                    sys.stdout.write(line)
            rc = proc.wait()
        config["finished_at"] = _dt.datetime.now().isoformat(timespec="seconds")
        config["exit_code"] = rc
        (out / "config.json").write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        if rc != 0:
            failures += 1
            print(f"FAIL  {out.relative_to(PROJECT_ROOT)} exit {rc}; see {log.relative_to(PROJECT_ROOT)}")
            continue
        if not args.no_rescore:
            # Same offline step the paper runs went through: recompute truth and every derived
            # metric with the current scoring code, writing raw/report.rescored.json.
            rs = subprocess.run([py, "benchmarks/rescore.py", str(out / "raw"), "--quiet"], cwd=PROJECT_ROOT, capture_output=True, text=True)
            (out / "raw" / "rescore.log").write_text(rs.stdout + rs.stderr, encoding="utf-8")
            if rs.returncode != 0:
                print(f"warn  rescore failed for {out.relative_to(PROJECT_ROOT)} (see raw/rescore.log); rendering from report.json")
        from benchmarks.postprocess import postprocess

        postprocess(out, method=m.runner_name, model=p["model"] if m.uses_llm else None, case=p["case"])
    build_index()
    return 1 if failures else 0


def cmd_postprocess(args: argparse.Namespace) -> int:
    from benchmarks.postprocess import postprocess

    for d in args.run_dirs:
        postprocess(Path(d), method=args.method, model=args.model, case=args.case, condition=args.condition)
    build_index()
    return 0


def _q(s: str) -> str:
    return s if re.fullmatch(r"[A-Za-z0-9_./:@%+=,-]+", s) else json.dumps(s)


# --------------------------------------------------------------------------- index


def _fmt(v: Any, digits: int = 1) -> str:
    if v is None:
        return "–"
    if isinstance(v, float):
        return f"{v:.{digits}f}"
    return str(v)


def build_index(results: Path = RESULTS) -> Path:
    """results/INDEX.md: one line per run directory, newest first, grouped by case."""
    rows: List[Dict[str, Any]] = []
    for summary in sorted(results.glob("*/*/*/*/summary.json")):
        try:
            s = json.loads(summary.read_text(encoding="utf-8"))
        except Exception:
            continue
        d = summary.parent
        cfg = {}
        if (d / "config.json").is_file():
            cfg = json.loads((d / "config.json").read_text(encoding="utf-8"))
        h, a = s.get("header", {}), s.get("aggregate", {})
        rows.append({
            "case": d.parents[2].name, "date": d.parents[1].name, "model": d.parents[0].name, "dir": d.name,
            "method": cfg.get("method") or h.get("method"), "condition": cfg.get("condition") or h.get("condition") or "normal",
            "n": a.get("n"), "solved": a.get("solved_autonomously"), "escalated": a.get("escalated"), "wrong": a.get("wrong_unflagged"),
            "form": (100.0 * a["formulation_exact"] / a["formulation_total"]) if a.get("formulation_total") else None,
            "trace": (100.0 * a["traceable_answers"] / a["traceable_total"]) if a.get("traceable_total") else None,
            "tokens": (a.get("prompt_tokens_mean") or 0) + (a.get("completion_tokens_mean") or 0) if a.get("prompt_tokens_mean") is not None else None,
            "cost": a.get("cost_usd_total"), "tool_variant": cfg.get("tool_variant") or h.get("tool_variant"),
            "role": cfg.get("role_in_paper") or ("" if cfg.get("kind") == "run" else ""), "kind": cfg.get("kind", ""),
            "path": d.relative_to(results).as_posix(),
        })
    rows.sort(key=lambda r: (r["case"], r["date"], r["model"], r["dir"]), reverse=True)
    out: List[str] = ["# Results index", "", f"Generated {_dt.datetime.now().strftime('%Y-%m-%d %H:%M')} by `run.py index`. One line per run directory, newest first. Counts are runs; Form. and Trace. are percentages. Open the folder for `REPORT.md`, `summary.csv` and `traces/`.", ""]
    for case in sorted({r["case"] for r in rows}, key=lambda c: (len(c), c)):
        out += [f"## {case}", "", "| date | model | method | cond. | tools | n | solved | escalated | wrong unflagged | Form. % | Trace. % | tokens/run | cost $ | in the paper | folder |", "|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|"]
        for r in [x for x in rows if x["case"] == case]:
            out.append(f"| {r['date']} | {r['model']} | {r['method']} | {r['condition']} | {_fmt(r['tool_variant'])} | {_fmt(r['n'])} | {_fmt(r['solved'])} | {_fmt(r['escalated'])} | {_fmt(r['wrong'])} | {_fmt(r['form'])} | {_fmt(r['trace'])} | {_fmt(r['tokens'], 0)} | {_fmt(r['cost'], 2)} | {r['role'] or ('new run' if r['kind'] == 'run' else '')} | [{r['dir']}]({r['path']}/REPORT.md) |")
        out.append("")
    results.mkdir(parents=True, exist_ok=True)
    (results / "INDEX.md").write_text("\n".join(out), encoding="utf-8")
    (results / "INDEX.json").write_text(json.dumps({"generated": _dt.datetime.now().isoformat(timespec="seconds"), "runs": rows}, indent=1, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    return results / "INDEX.md"


def cmd_serve(args: argparse.Namespace) -> int:
    """Serve results/ over HTTP and open the trace viewer (browsers refuse to read local files otherwise)."""
    import http.server
    import socketserver
    import threading
    import webbrowser

    build_index()
    handler = lambda *a, **k: http.server.SimpleHTTPRequestHandler(*a, directory=str(RESULTS), **k)  # noqa: E731
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("127.0.0.1", args.port), handler) as httpd:
        url = f"http://127.0.0.1:{args.port}/visuals/index.html"
        print(f"trace viewer at {url}   (Ctrl+C to stop)")
        if not args.no_browser:
            threading.Timer(0.5, lambda: webbrowser.open(url)).start()
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
    return 0


def cmd_index(_: argparse.Namespace) -> int:
    p = build_index()
    print(f"wrote {p.relative_to(PROJECT_ROOT)}")
    return 0


# --------------------------------------------------------------------------- cli


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command", required=True)

    sub.add_parser("list-methods", help="the methods under methods/").set_defaults(func=cmd_list_methods)

    sp = sub.add_parser("show-prompt", help="print a method's card and its assembled system prompt")
    sp.add_argument("--method", required=True)
    sp.add_argument("--tool-variant", default=DEFAULT_TOOL_VARIANT, choices=["v1", "load_split"])
    sp.set_defaults(func=cmd_show_prompt)

    r = sub.add_parser("run", help="run methods x models x cases, then render")
    r.add_argument("--method", dest="methods", action="append", required=True, help="methods/ folder or runner name; repeatable")
    r.add_argument("--model", dest="models", action="append", default=[], help="provider:model; repeatable (ignored for rule_based)")
    r.add_argument("--case", dest="cases", action="append", default=[], help="ieee14, case14, ieee30 ...; repeatable")
    r.add_argument("--n", type=int, default=40, help="requests per case and seed (--gen-requests)")
    r.add_argument("--seeds", type=int, default=1, help="number of perturbation seeds 0..N-1")
    r.add_argument("--seed-list", default=None, help="explicit seeds, comma separated")
    r.add_argument("--runs", type=int, default=1, help="repeats per request")
    r.add_argument("--k", type=int, default=1, help="perturbation strength")
    r.add_argument("--max-rounds", type=int, default=8)
    r.add_argument("--temperature", type=float, default=0.0)
    r.add_argument("--timeout-s", type=float, default=90.0)
    r.add_argument("--tool-variant", default=DEFAULT_TOOL_VARIANT, choices=["v1", "load_split"], help="tool set; load_split is the one behind Table 5")
    r.add_argument("--plan-variant", default="text", choices=["text", "structured"])
    r.add_argument("--requests", default=None, help="a frozen requests .jsonl instead of --n generated ones")
    r.add_argument("--difficulty", dest="difficulties", action="append", default=[], help="restrict generated requests (e.g. stress)")
    r.add_argument("--condition", default=None, choices=["normal", "stress"])
    r.add_argument("--date", default=None, help="results/<case>/<date>/ folder (default today)")
    r.add_argument("--tag", default=None, help="suffix for the run folder (e.g. pilot)")
    r.add_argument("--dry-run", action="store_true", help="print the plan and cost estimate, run nothing")
    r.add_argument("--force", action="store_true", help="rerun even if raw/report.json exists")
    r.add_argument("--no-rescore", action="store_true", help="skip benchmarks/rescore.py after the run")
    r.add_argument("--quiet", action="store_true", help="do not echo the runner's output (it still goes to raw/run.log)")
    r.set_defaults(func=cmd_run)

    pp = sub.add_parser("postprocess", help="re-render transcripts, narratives, summary and REPORT.md for run dirs")
    pp.add_argument("run_dirs", nargs="+")
    pp.add_argument("--method", default=None)
    pp.add_argument("--model", default=None)
    pp.add_argument("--case", default=None)
    pp.add_argument("--condition", default=None, choices=["normal", "stress"])
    pp.set_defaults(func=cmd_postprocess)

    sub.add_parser("index", help="rebuild results/INDEX.md").set_defaults(func=cmd_index)

    sv = sub.add_parser("serve", help="open the evaluation pages (results/visuals/index.html: design, results, traces) on a local web server")
    sv.add_argument("--port", type=int, default=8765)
    sv.add_argument("--no-browser", action="store_true")
    sv.set_defaults(func=cmd_serve)
    return ap


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())
