"""Build the one site the case studies share.

Each case study is a separate project with packages of the same name
(``evaluation``, ``config``, ``data``) and dependencies of its own, so they
cannot be imported into one process. Each therefore runs as a subprocess in its
own directory and writes a fragment file; this module reads those and assembles
the pages, so the chrome, the stylesheet and the navigation exist once.

The fragment protocol, written by a case study to the path given as the only
argument of its ``evaluation.page_fragments`` module:

    {
      "id":     "evagent",                      folder and URL name
      "title":  "EVAgent",                      name in the case selector
      "brand":  "EVAgent · EV charging",        top bar
      "note":   "20 Caltech ACN days",          small text, top right
      "groups": [["Design", [["overview", "Overview"], ...]], ...],
      "tabs":   {"overview": "<div class=...>", ...},
      "script": "…"                             optional, page-specific JS
    }

Usage (from the repository root):
    python -m visuals.build                 every case study
    python -m visuals.build --case evagent  one of them

Writes ``site/index.html`` and ``site/<case>.html``.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from visuals import shell
from visuals.shell import E, card, chip, table

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"

# Case study id -> the directory its generator runs in. Order is the order of
# the case selector and of the landing page.
CASES: Tuple[Tuple[str, str], ...] = (
    ("pfagent", "power-flow-agent"),
    ("evagent", "ev-scheduling"),
)

# Fallback interpreter, used for a case study that has no environment of its
# own. Each case study pins different packages -- pandapower and
# matpowercaseframes here, cvxpy there -- and no single interpreter on a
# developer's machine reliably has all of them, which is the other reason the
# generators run as subprocesses.
PYTHON = sys.executable


def interpreter(folder: str, fallback: str) -> str:
    """The case study's own virtualenv if it has one, else the fallback."""
    own = ROOT / folder / ".venv" / "bin" / "python"
    return str(own) if own.exists() else fallback


def collect(case_id: str, folder: str, python: str = PYTHON) -> Optional[Dict[str, Any]]:
    """Run one case study's fragment generator and return what it wrote."""
    cwd = ROOT / folder
    python = interpreter(folder, python)
    if not (cwd / "evaluation" / "page_fragments.py").exists():
        print(f"  {case_id}: no evaluation/page_fragments.py, skipped")
        return None
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "fragments.json"
        proc = subprocess.run(
            [python, "-m", "evaluation.page_fragments", str(out)],
            cwd=cwd,
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            print(f"  {case_id}: generator failed\n{proc.stdout}\n{proc.stderr}")
            return None
        payload = json.loads(out.read_text(encoding="utf-8"))
    payload.setdefault("id", case_id)
    return payload


def render(payload: Dict[str, Any], every: Sequence[Dict[str, Any]]) -> str:
    """One case study's page, with the selector listing all of them."""
    tabs = payload.get("tabs", {})
    groups = [(label, [tuple(e) for e in entries]) for label, entries in payload.get("groups", [])]
    first = True
    body: List[str] = []
    for _label, entries in groups:
        for key, _text in entries:
            body.append(shell.tab(key, tabs.get(key, ""), on=first))
            first = False
    cases = [(p["title"], f"{p['id']}.html", p["id"] == payload["id"]) for p in every]
    extra = payload.get("script", "")
    return shell.page(
        title=f"{payload['title']} · Evaluation",
        brand=payload.get("brand", payload["title"]),
        note_text=payload.get("note", ""),
        groups=groups,
        tabs_html="".join(body),
        cases=cases,
        extra_css=payload.get("css", ""),
    ).replace("</body></html>", f"<script>{extra}</script></body></html>" if extra else "</body></html>")


def landing(every: Sequence[Dict[str, Any]]) -> str:
    """The front door: what the evaluation is, and one card per case study."""
    cards: List[str] = []
    for p in every:
        rows = p.get("summary", [])
        cards.append(
            f"<a class='stg' href='{E(p['id'])}.html'><h3>{E(p['title'])}</h3>"
            f"<p>{E(p.get('blurb', ''))}</p>"
            + "".join(chip(f"{k}: {v}") for k, v in rows)
            + "<div class='st'>Open →</div></a>"
        )
    intro = card(
        "Evaluation protocol",
        "<p>Each case study poses a grid task in natural language and evaluates whether a language model can "
        "produce the answer an engineer currently obtains with a trusted numerical tool. The reference solution "
        "for every instance is computed by that tool, so correctness is decided against a known quantity rather "
        "than against a judgement.</p>",
        "<h3>Factorial design</h3>"
        "<p>Six methods answer identical instances and are scored by identical code. Tool access is itself one of "
        "the factors under study, so it varies by design; among the methods that have tools it is the same tool "
        "under the same interaction budget. Consecutive methods differ in exactly one factor, which is what "
        "allows an observed difference to be attributed to that factor.</p>"
        + table(
            ["method", "factor it adds"],
            [
                ["Deterministic parser", "none. No language model at any stage"],
                ["Structured prompting", "a language model, with no access to the solver"],
                ["Chain-of-thought prompting", "an explicit reasoning step in the prompt"],
                ["Plan-and-Act", "solver access, with the call sequence fixed in advance"],
                ["ReAct", "iteration. Each tool output is observed before the next call"],
                ["Solver-grounded agent", "verification of the answer before it is surfaced"],
            ],
        )
        + "<p class='muted'>The last contrast is the one the design turns on. The final two methods share the "
        "tool, the budget and the instances, so the difference between them measures verification and nothing "
        "else.</p>",
        "<h3>Response variable</h3>"
        "<p>Each instance terminates in one of three mutually exclusive states, which are exhaustive and "
        "therefore sum to the instance count.</p>"
        + table(
            ["state", "definition"],
            [
                [shell.verdict("solved"),
                 "the answer is correct against the reference and its numbers are traceable to the tool output"],
                [shell.verdict("escalated"),
                 "the method declared it could not answer, and produced no numbers"],
                [shell.verdict("wrong"),
                 "the answer is incorrect and nothing in the output indicates it"],
            ],
        )
        + "<p class='muted'>The third state is the quantity a solver-grounded design exists to eliminate. The "
        "second is the cost of eliminating it, since an escalated instance is one a person has to handle.</p>",
        "<h3>Measurements</h3>"
        "<p>Metrics are grouped as task utility, solver-grounded correctness, and cost of operation. The latter "
        "two groups are defined identically in every case study. Task-utility metrics are case-specific, because "
        "the tasks optimise different objectives.</p>",
        "<p class='muted'>Reproducibility: each page is generated from the executable configuration of its case "
        "study, comprising the method registry, the verification conditions, the instance generator, the prompt "
        "builders and the recorded results. No description on these pages is maintained separately from the code "
        "it describes.</p>",
    )
    return shell.page(
        title="Case studies · Evaluation",
        brand="Solver-grounded LLM agents · case studies",
        note_text="",
        groups=[("", [("home", "Overview")])],
        tabs_html=shell.tab("home", intro + "<div class='grid g3'>" + "".join(cards) + "</div>", on=True),
        cases=[(p["title"], f"{p['id']}.html", False) for p in every],
        extra_css=(
            ".stg{display:block;background:var(--panel);border:1px solid var(--line);border-radius:12px;"
            "padding:18px 20px;text-decoration:none;color:var(--text);box-shadow:var(--shadow)}"
            ".stg:hover{border-color:var(--acc)}.stg h3{margin:0 0 6px;font-size:16px}"
            ".stg p{margin:0 0 8px;color:var(--muted);font-size:13.5px}"
            ".stg .st{margin-top:10px;font-size:12px;font-weight:600;color:var(--acc)}"
        ),
    )


def build(only: Optional[str] = None, python: str = PYTHON) -> List[Path]:
    """Collect every case study and write the site. Returns the files written."""
    payloads: List[Dict[str, Any]] = []
    for case_id, folder in CASES:
        if only and case_id != only:
            continue
        print(f"collecting {case_id} …")
        p = collect(case_id, folder, python)
        if p is not None:
            payloads.append(p)
    if not payloads:
        raise SystemExit("no case study produced a fragment")

    SITE.mkdir(parents=True, exist_ok=True)
    written: List[Path] = []
    for p in payloads:
        out = SITE / f"{p['id']}.html"
        out.write_text(render(p, payloads), encoding="utf-8")
        written.append(out)
    index = SITE / "index.html"
    index.write_text(landing(payloads), encoding="utf-8")
    written.append(index)
    return written


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--case", help="build only this case study")
    ap.add_argument("--python", default=PYTHON, help="interpreter that can import every case study")
    args = ap.parse_args()
    for path in build(args.case, args.python):
        print(f"wrote {path.relative_to(ROOT)} ({path.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
