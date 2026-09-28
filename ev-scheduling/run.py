"""The one entry point of the EV case study, with the same verbs as every other case study.

    python run.py list-methods                       the six methods under methods/
    python run.py show-prompt --method llm_only_cot  a method's card and the texts it is built from
    python run.py run --dry-run --days 3             cost estimate, nothing spent
    python run.py run --days 20 --data-source cache  every method on the frozen days
    python run.py report <results_dir> [--pdf]       REPORT.md from the rows, no model called
    python run.py rescore <results_dir>              re-score rows after a scoring change
    python run.py probe-parse --model M --days 10    the extraction step alone, to price a model's reading
    python run.py postprocess <run_set_dir>          lay a run set out as results/<instance>/<date>/<model>/<method>/
    python run.py freeze-days [--dry-run]            fetch and freeze the benchmark days (needs a token)
    python run.py index                              rebuild results/INDEX.md
    python run.py serve                              the shared evaluation site, on a local server

Every verb delegates to the module that owns it: ``evaluation/runner.py``,
``evaluation/report.py``, ``evaluation/rescore.py``, ``evaluation/parse_probe.py``,
``data/benchmark/freeze.py``.
This file only routes, so that a reader who learned ``run.py`` on one case
study can drive this one without reading anything else.
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

    print(f"{'folder':22s} {'runner name':28s} {'LLM':4s} {'tools':6s} {'gate':5s} {'runs':5s}  description")
    for c in methods.cards():
        print(
            f"{c['folder']:22s} {c['runner_name']:28s} {'yes' if c['uses_llm'] else 'no':4s} "
            f"{'yes' if c['uses_tools'] else 'no':6s} {'yes' if c['gate'] else 'no':5s} "
            f"{'yes' if c.get('implemented') else 'no':5s}  {c['description']}"
        )
    return 0


def cmd_show_prompt(args: argparse.Namespace) -> int:
    import hashlib

    import methods

    card = methods.card(args.method)
    print(json.dumps(card, indent=2))
    for rel, text in methods.texts(args.method):
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
        print(f"\n===== {rel}  (sha {digest}, {len(text)} chars) =====\n{text}")
    if card.get("dynamic_parts"):
        print("\nbuilt at run time:")
        for d in card["dynamic_parts"]:
            print(f"  - {d}")
    return 0


def cmd_run(argv: List[str]) -> int:
    """Run the matrix, then lay the new run set out as method folders and reindex.

    The runner writes results/ev_matrix_<model>/; a run is not finished until that
    run set is laid out in the shared layout and INDEX.md knows about it, so both
    happen here rather than being left for someone to remember. A dry run writes
    nothing and gets neither.
    """
    from evaluation import postprocess, runner

    root = PROJECT_ROOT / "results"
    before = {d for d in root.glob("ev_matrix_*") if d.is_dir()} if root.is_dir() else set()
    code = int(runner.main(argv) or 0)
    if "--dry-run" in argv:
        return code
    new = sorted({d for d in root.glob("ev_matrix_*") if d.is_dir()} - before, key=lambda d: d.stat().st_mtime)
    for d in new:
        print(f"laying out {d.name}:")
        postprocess.postprocess(d)
    if new:
        cmd_index(argparse.Namespace())
    return code


def cmd_report(argv: List[str]) -> int:
    from evaluation import report

    return int(report.main(argv) or 0)


def cmd_rescore(argv: List[str]) -> int:
    from evaluation import rescore

    return int(rescore.main(argv) or 0)


def cmd_probe_parse(argv: List[str]) -> int:
    from evaluation import parse_probe

    return int(parse_probe.main(argv) or 0)


def cmd_freeze_days(argv: List[str]) -> int:
    from data.benchmark import freeze

    sys.argv = ["freeze"] + argv
    return int(freeze.main() or 0)


def cmd_index(_args: argparse.Namespace) -> int:
    """results/INDEX.md and INDEX.json: one line per method folder, newest first.

    Same row shape as every other case study, so the shared site reads them all
    the same way: instance, date, model, method, n, solved, escalated, wrong,
    form, trace, tokens, cost, kind, path.
    """
    root = PROJECT_ROOT / "results"
    rows = []
    for sj in sorted(root.glob("*/*/*/*/summary.json")):
        d = json.loads(sj.read_text(encoding="utf-8"))
        h, a = d.get("header", {}), d.get("aggregate", {})
        cfg = sj.parent / "config.json"
        kind = json.loads(cfg.read_text(encoding="utf-8")).get("kind", "run") if cfg.exists() else "run"
        rel = sj.parent.relative_to(root)
        rows.append({
            "case": h.get("instance"), "date": h.get("date"), "model": h.get("model"),
            "dir": sj.parent.name, "method": h.get("method"), "condition": "normal",
            "n": a.get("n"), "solved": a.get("solved"), "escalated": a.get("escalated"), "wrong": a.get("wrong"),
            "form": a.get("form"), "trace": a.get("trace"), "tokens": a.get("tokens"), "cost": a.get("cost"),
            "kind": kind, "path": str(rel),
        })
    rows.sort(key=lambda r: (str(r["date"]), str(r["case"]), str(r["model"]), str(r["method"])), reverse=True)
    (root / "INDEX.json").write_text(json.dumps({"runs": rows}, indent=1), encoding="utf-8")
    lines = ["# results/", "", "One line per method folder, newest first. `python run.py index` rebuilds this.", "",
             "| instance | date | model | method | n | solved | escalated | wrong | form % | trace % | tokens | cost $ | path |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    fmt = lambda v: "-" if v is None else (f"{v:.1f}" if isinstance(v, float) else str(v))
    for r in rows:
        lines.append(f"| {r['case']} | {r['date']} | {r['model']} | {r['method']} | {r['n']} | {r['solved']} | {r['escalated']} | "
                     f"{r['wrong']} | {fmt(r['form'])} | {fmt(r['trace'])} | {r['tokens']} | {fmt(r['cost'])} | `{r['path']}` |")
    (root / "INDEX.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"indexed {len(rows)} method folders")
    return 0


def cmd_postprocess(argv: List[str]) -> int:
    from evaluation import postprocess

    return int(postprocess.main(argv) or 0)


def cmd_serve(args: argparse.Namespace) -> int:
    site = PROJECT_ROOT.parent / "site"
    if not (site / "index.html").exists():
        print("no site yet: run `python -m visuals.build` from the repository root first")
        return 1
    handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("127.0.0.1", args.port), lambda *a, **k: handler(*a, directory=str(site), **k)) as httpd:
        url = f"http://127.0.0.1:{args.port}/evagent.html"
        print(f"serving {site} at {url}  (Ctrl-C to stop)")
        webbrowser.open(url)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    # verbs that own their own argument parsers get the rest of the line untouched
    passthrough = {"run": cmd_run, "report": cmd_report, "rescore": cmd_rescore, "freeze-days": cmd_freeze_days,
                   "postprocess": cmd_postprocess, "probe-parse": cmd_probe_parse}
    if argv and argv[0] in passthrough:
        return passthrough[argv[0]](argv[1:])

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list-methods", help="the six methods under methods/").set_defaults(func=cmd_list_methods)
    sp = sub.add_parser("show-prompt", help="a method's card and the texts it is built from")
    sp.add_argument("--method", required=True)
    sp.set_defaults(func=cmd_show_prompt)
    for verb in passthrough:
        sub.add_parser(verb, help=f"see `python run.py {verb} --help`")
    sub.add_parser("index", help="rebuild results/INDEX.md and INDEX.json").set_defaults(func=cmd_index)
    sv = sub.add_parser("serve", help="open the shared evaluation site on a local server")
    sv.add_argument("--port", type=int, default=8765)
    sv.set_defaults(func=cmd_serve)
    args = ap.parse_args(argv)
    return int(args.func(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())
