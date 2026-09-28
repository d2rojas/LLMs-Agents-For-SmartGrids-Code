#!/usr/bin/env python3
"""The one entry point of the GridDebug case study, with the same verbs as every other case study.

    .venv/bin/python run.py list-methods                          the six methods under methods/
    .venv/bin/python run.py show-prompt --method griddebug        a method's card, its texts and the assembled system prompt
    .venv/bin/python run.py freeze-scenarios                      write data/scenarios/manifest.json (on purpose only)
    .venv/bin/python run.py run --dry-run                         the plan and the cost estimate; spends nothing
    .venv/bin/python run.py run --method griddebug --network case14 --model openrouter:openai/gpt-4o-mini
    .venv/bin/python run.py postprocess results/ieee14/<date>/<model>/<method>   re-render after a scoring change
    .venv/bin/python run.py rescore results/ieee14/<date>/<model>/<method>       re-score the rows from the traces, then re-render
    .venv/bin/python run.py index                                 rebuild results/INDEX.md and INDEX.json
    .venv/bin/python run.py pages                                 results/visuals/: index, design, results, viewer, failures
    .venv/bin/python run.py serve                                 serve results/ and open results/visuals/index.html

Every verb delegates to the module that owns it: ``evaluation/runner.py``,
``evaluation/postprocess.py``, ``evaluation/rescore.py``, ``evaluation/scenarios/manifest.py``.
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


def cmd_freeze(args: argparse.Namespace) -> int:
    from evaluation.scenarios import manifest

    p = manifest.write_manifest(args.network or None)
    m = json.loads(p.read_text(encoding="utf-8"))
    print(f"wrote {p.relative_to(PROJECT_ROOT)}: {len(m['entries'])} scenarios, pandapower {m['pandapower']}")
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
            "case": rel.parts[0], "date": h.get("date"), "model": h.get("model_short"), "dir": sj.parent.name, "method": h.get("method"),
            "condition": h.get("condition", "normal"), "n": a.get("n"), "solved": a.get("solved"), "escalated": a.get("escalated"),
            "wrong": a.get("wrong"), "form": a.get("form"), "trace": a.get("trace"), "repaired": a.get("repaired"),
            "tokens": a.get("tokens"), "cost": a.get("cost"), "tool_variant": "v1", "kind": cfg.get("kind", "run"), "tag": cfg.get("tag"),
            "path": str(rel),
        })
    rows.sort(key=lambda r: (str(r["date"]), str(r["case"]), str(r["model"]), str(r["method"])), reverse=True)
    root.mkdir(exist_ok=True)
    (root / "INDEX.json").write_text(json.dumps({"runs": rows}, indent=1), encoding="utf-8")
    fmt = lambda v: "-" if v is None else (f"{v:.1f}" if isinstance(v, float) else str(v))  # noqa: E731
    lines = ["# results/", "", "One line per method folder, newest first. `python run.py index` rebuilds this.", "",
             "| case | date | model | method | n | solved | escalated | wrong | diagnosis % | trace % | repaired | tokens | cost $ | kind | path |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['case']} | {r['date']} | {r['model']} | {r['dir']} | {r['n']} | {r['solved']} | {r['escalated']} | {r['wrong']} | "
                     f"{fmt(r['form'])} | {fmt(r['trace'])} | {r['repaired']} | {r['tokens']} | {fmt(r['cost'])} | {r['kind']} | `{r['path']}` |")
    (root / "INDEX.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"indexed {len(rows)} method folders")
    return 0


def cmd_pages(_args: argparse.Namespace) -> int:
    """results/visuals/: index.html, design.html and the three results pages, in the power-flow format."""
    from evaluation import design_page

    out = design_page.build()
    for f in sorted(out.glob("*.html")):
        print(f"wrote {f.relative_to(PROJECT_ROOT)} ({f.stat().st_size // 1024} KB)")
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    """Serve results/ so results/visuals/*.html can fetch INDEX.json, summary.csv and the traces."""
    root = PROJECT_ROOT / "results"
    if not (root / "visuals" / "index.html").exists():
        cmd_pages(args)
    handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("127.0.0.1", args.port), lambda *a, **k: handler(*a, directory=str(root), **k)) as httpd:
        url = f"http://127.0.0.1:{args.port}/visuals/index.html"
        print(f"serving {root} at {url}  (Ctrl-C to stop)")
        webbrowser.open(url)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    passthrough = {"run": cmd_run, "postprocess": cmd_postprocess, "rescore": cmd_rescore}
    if argv and argv[0] in passthrough:
        return passthrough[argv[0]](argv[1:])
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list-methods", help="the six methods under methods/").set_defaults(func=cmd_list_methods)
    sp = sub.add_parser("show-prompt", help="a method's card and the texts it is built from")
    sp.add_argument("--method", required=True)
    sp.set_defaults(func=cmd_show_prompt)
    fz = sub.add_parser("freeze-scenarios", help="write data/scenarios/manifest.json")
    fz.add_argument("--network", action="append")
    fz.set_defaults(func=cmd_freeze)
    for verb in passthrough:
        sub.add_parser(verb, help=f"see `python run.py {verb} --help`")
    sub.add_parser("index", help="rebuild results/INDEX.md and INDEX.json").set_defaults(func=cmd_index)
    sub.add_parser("pages", help="build results/visuals/ (index, design, results, viewer, failures)").set_defaults(func=cmd_pages)
    sv = sub.add_parser("serve", help="serve results/ and open results/visuals/index.html")
    sv.add_argument("--port", type=int, default=8766)
    sv.set_defaults(func=cmd_serve)
    args = ap.parse_args(argv)
    return int(args.func(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())
