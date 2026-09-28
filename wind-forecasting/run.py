#!/usr/bin/env python3
"""The one entry point of the wind forecasting case study, with the same verbs as every other case study.

    python run.py list-methods                                the six methods under methods/
    python run.py show-prompt --method windagent              a method's card, its texts and the assembled system prompt
    python run.py freeze-data --source <wtbdata_245days.csv>  write data/benchmark/ and its manifest (on purpose only)
    python run.py train-gru [--force]                         train the conventional forecaster on the frozen training slices
    python run.py run --dry-run                               the plan and the cost estimate; spends nothing
    python run.py run --method windagent --n 3 --horizon 48 --tag smoke --model openrouter:openai/gpt-4o-mini
    python run.py postprocess results/sdwpf/<date>/<model>/<method>   re-render after a scoring change
    python run.py rescore results/sdwpf/<date>/<model>/<method>       re-score the rows from the traces, then re-render
    python run.py index                                       rebuild results/INDEX.md and INDEX.json
    python run.py serve                                       the shared evaluation site, on a local server

Every verb delegates to the module that owns it: ``evaluation/runner.py``,
``evaluation/postprocess.py``, ``evaluation/rescore.py``, ``data/freeze.py``, ``solver/gru.py``.
"""

from __future__ import annotations

import argparse
import http.server
import json
import socketserver
import sys
import webbrowser
from pathlib import Path
from typing import List, Optional, Sequence

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def cmd_list_methods(_args: argparse.Namespace) -> int:
    import methods

    print(f"{'folder':22s} {'runner name':22s} {'LLM':4s} {'tools':6s} {'gate':5s}  description")
    for c in methods.cards():
        print(f"{c['folder']:22s} {c['runner_name']:22s} {'yes' if c['uses_llm'] else 'no':4s} {'yes' if c['uses_tools'] else 'no':6s} "
              f"{'yes' if c['gate'] else 'no':5s}  {c['description']}")
    return 0


def cmd_show_prompt(args: argparse.Namespace) -> int:
    import methods
    from methods.common import planner_system_prompt, system_prompt_for

    c = methods.card(args.method)
    print(json.dumps(c, indent=2))
    for rel, text in methods.texts(args.method):
        print(f"\n===== {rel}  (sha {methods.prompt_hash(text)}, {len(text)} chars) =====\n{text}")
    sp = system_prompt_for(args.method)
    if sp is not None:
        print(f"\n===== assembled system prompt  (sha {methods.prompt_hash(sp)}) =====\n{sp}")
    if c.get("architecture") == "plan_act":
        pp_ = planner_system_prompt()
        print(f"\n===== planner system prompt  (sha {methods.prompt_hash(pp_)}) =====\n{pp_}")
    if c.get("dynamic_parts"):
        print("\nbuilt at run time:")
        for d in c["dynamic_parts"]:
            print(f"  - {d}")
    return 0


def cmd_run(argv: List[str]) -> int:
    from evaluation import runner

    code = int(runner.main(argv) or 0)
    if "--dry-run" not in argv and code == 0:
        cmd_index(argparse.Namespace())
    return code


def cmd_postprocess(argv: List[str]) -> int:
    from evaluation import postprocess

    code = int(postprocess.main(argv) or 0)
    cmd_index(argparse.Namespace())
    return code


def cmd_rescore(argv: List[str]) -> int:
    from evaluation import rescore

    code = int(rescore.main(argv) or 0)
    cmd_index(argparse.Namespace())
    return code


def cmd_freeze(argv: List[str]) -> int:
    from data import freeze

    return int(freeze.main(argv) or 0)


def cmd_train_gru(args: argparse.Namespace) -> int:
    from solver import gru

    gru.train(force=args.force, epochs=args.epochs, seed=args.seed)
    return 0


def cmd_index(_args: argparse.Namespace) -> int:
    """results/INDEX.md and INDEX.json: one line per method folder, newest first, the same row keys as the other case studies."""
    root = PROJECT_ROOT / "results"
    rows = []
    for sj in sorted(root.glob("*/*/*/*/summary.json")):
        d = json.loads(sj.read_text(encoding="utf-8"))
        h, a = d.get("header", {}), d.get("aggregate", {})
        cfg_p = sj.parent / "config.json"
        cfg = json.loads(cfg_p.read_text(encoding="utf-8")) if cfg_p.exists() else {}
        rel = sj.parent.relative_to(root)
        rows.append({
            "case": h.get("case"), "date": h.get("date"), "model": h.get("model_short"), "dir": sj.parent.name, "method": h.get("method"),
            "condition": h.get("condition", "normal"), "n": a.get("n"), "solved": a.get("solved"), "escalated": a.get("escalated"),
            "wrong": a.get("wrong"), "form": a.get("form"), "trace": a.get("trace"), "mae": a.get("mae"), "rmse": a.get("rmse"),
            "tokens": a.get("tokens"), "cost": a.get("cost"), "kind": cfg.get("kind", "run"), "tag": cfg.get("tag"), "path": str(rel),
        })
    rows.sort(key=lambda r: (str(r["date"]), str(r["model"]), str(r["method"])), reverse=True)
    root.mkdir(exist_ok=True)
    (root / "INDEX.json").write_text(json.dumps({"runs": rows}, indent=1), encoding="utf-8")
    fmt = lambda v: "-" if v is None else (f"{v:.1f}" if isinstance(v, float) else str(v))  # noqa: E731
    lines = ["# results/", "", "One line per method folder, newest first. `python run.py index` rebuilds this.", "",
             "| date | model | method | cond. | n | solved | escalated | wrong | Form. % | Trace. % | MAE kW | RMSE kW | tokens | cost $ | kind | path |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['date']} | {r['model']} | {r['dir']} | {r['condition']} | {r['n']} | {r['solved']} | {r['escalated']} | {r['wrong']} | "
                     f"{fmt(r['form'])} | {fmt(r['trace'])} | {fmt(r['mae'])} | {fmt(r['rmse'])} | {r['tokens']} | {fmt(r['cost'])} | {r['kind']} | `{r['path']}` |")
    (root / "INDEX.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"indexed {len(rows)} method folders")
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    site = PROJECT_ROOT.parent / "site"
    if not (site / "index.html").exists():
        print("no site yet: run `python -m visuals.build` from the repository root first")
        return 1
    handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("127.0.0.1", args.port), lambda *a, **k: handler(*a, directory=str(site), **k)) as httpd:
        url = f"http://127.0.0.1:{args.port}/wind.html"
        print(f"serving {site} at {url}  (Ctrl-C to stop)")
        webbrowser.open(url)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    passthrough = {"run": cmd_run, "postprocess": cmd_postprocess, "rescore": cmd_rescore, "freeze-data": cmd_freeze}
    if argv and argv[0] in passthrough:
        return passthrough[argv[0]](argv[1:])
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list-methods", help="the six methods under methods/").set_defaults(func=cmd_list_methods)
    sp = sub.add_parser("show-prompt", help="a method's card and the texts it is built from")
    sp.add_argument("--method", required=True)
    sp.set_defaults(func=cmd_show_prompt)
    tg = sub.add_parser("train-gru", help="train the conventional forecaster on data/gru/train_t*.csv")
    tg.add_argument("--force", action="store_true")
    tg.add_argument("--epochs", type=int, default=12)
    tg.add_argument("--seed", type=int, default=0)
    tg.set_defaults(func=cmd_train_gru)
    for verb in passthrough:
        sub.add_parser(verb, help=f"see `python run.py {verb} --help`")
    sub.add_parser("index", help="rebuild results/INDEX.md and INDEX.json").set_defaults(func=cmd_index)
    sv = sub.add_parser("serve", help="open the shared evaluation site on a local server")
    sv.add_argument("--port", type=int, default=8767)
    sv.set_defaults(func=cmd_serve)
    args = ap.parse_args(argv)
    return int(args.func(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())
