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

# Every case study of the paper, in the order they appear in the sidebar and on
# the landing page. The ones with no generator yet are listed all the same: how
# many case studies there are is part of what the site has to show, and a case
# that only appears once it is finished makes the set look smaller than it is.
# The order is the paper's: Section 6.1 wind, 6.2 EV, 6.3 power flow, 6.4
# contingency diagnosis. A reader moving between the paper and the site should
# find the case studies in the same sequence in both.
CASES: Tuple[Dict[str, str], ...] = (
    {"id": "wind", "folder": "wind-forecasting", "title": "Wind",
     "subtitle": "power forecasting (Sec. 6.1)"},
    {"id": "evagent", "folder": "ev-scheduling", "title": "EVAgent",
     "subtitle": "EV charging schedules (Sec. 6.2)"},
    {"id": "pfagent", "folder": "power-flow-agent", "title": "PFAgent",
     "subtitle": "power flow, IEEE systems (Sec. 6.3)"},
    {"id": "griddebug", "folder": "griddebug-agent", "title": "GridDebug",
     "subtitle": "contingency diagnosis (Sec. 6.4)"},
)

# The sections every case study's page has, in this order. A case study that
# has not written one still gets the place, saying so, because the point of one
# site is that the case studies are read against each other: a section that
# exists on one page and is absent from another cannot be compared, and its
# absence is easy to mistake for the case study not needing it.
#
# The third field is what the section is for. It is shown where a case study
# has not filled it in, so an empty place still says what belongs there.
SECTIONS: Tuple[Tuple[str, str, str], ...] = (
    ("home", "Home",
     "the task in plain language, the problem stated formally, and what a correct answer has to "
     "contain"),
    ("methods", "Methods",
     "the methods compared, what single factor separates each from the one above it, and a diagram "
     "of each one's control flow"),
    ("scenarios", "Scenarios",
     "the instances every method answers, where they come from, and the stress set that makes some "
     "of them unanswerable"),
    ("prompts", "Prompts",
     "what each method sends to the model, block by block, with the file or function each block "
     "comes from"),
    ("tools", "Tools",
     "the tool schema the grounded methods call, identical for all of them, and the solver behind "
     "it"),
    ("gate", "Gate & scoring",
     "the verification conditions, the three-way outcome, and the definition of every column of "
     "the table"),
    ("plan", "Run plan",
     "what is to be run, on which systems and models, and what it costs"),
    ("results", "Results",
     "the numbers as the runs produced them, every method on the same instances"),
    ("traces", "Traces",
     "any single run end to end: the messages, the tool calls, the verdicts and the final answer"),
    ("analysis", "Analysis",
     "what the results mean: the report each run ends with, the failure catalogue, and the "
     "conclusions the case study draws, written only from what was measured"),
    ("status", "Implementation",
     "which methods run today and which are specified and not written yet"),
)

# Fallback interpreter, used for a case study that has no environment of its
# own. Each case study pins different packages -- pandapower and
# matpowercaseframes here, cvxpy there -- and no single interpreter on a
# developer's machine reliably has all of them, which is the other reason the
# generators run as subprocesses.
PYTHON = sys.executable


def has_generator(folder: str) -> bool:
    """Whether a case study can produce a page at all.

    Availability is a property of the repository, not of what this run
    happened to rebuild. Deriving it from the run would make ``--case`` mark
    every other case study as missing on the page it rewrites.
    """
    return (ROOT / folder / "evaluation" / "page_fragments.py").exists()


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


def nav_for(current: Optional[str], built: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    """The sidebar: every case study, the current one expanded into its sections."""
    out: List[Dict[str, Any]] = []
    for case in CASES:
        p = built.get(case["id"])
        own = {k: t for _g, entries in (p or {}).get("groups", []) for k, t in entries}
        entries: List[Tuple[str, str]] = []
        if case["id"] == current:
            # Every section, in the shared order, under the case study's own
            # label when it has one. Same list on every page, always.
            entries = [(key, own.get(key, label)) for key, label, _purpose in SECTIONS]
        out.append({
            "title": case["title"],
            "subtitle": case["subtitle"],
            "href": f"{case['id']}.html",
            "current": case["id"] == current,
            "available": has_generator(case["folder"]),
            "entries": entries,
        })
    return out


def placeholder(case_title: str, key: str, label: str, purpose: str) -> str:
    """The standard empty section: the place, and what belongs in it."""
    return card(
        label,
        f"<p class='muted'>{E(case_title)} has not written this section yet.</p>",
        f"<p>What belongs here: {E(purpose)}.</p>",
        shell.note(
            "The section is listed for every case study whether or not it is filled in, so the "
            "pages can be read against each other. Nothing is shown here that has not been "
            "measured or written.",
            "info",
        ),
    )


def render(payload: Dict[str, Any], built: Dict[str, Dict[str, Any]]) -> str:
    """One case study's page. Every section of SECTIONS, filled in or not."""
    tabs = payload.get("tabs", {})
    labels = {k: t for _g, entries in payload.get("groups", []) for k, t in entries}
    body: List[str] = []
    for n, (key, label, purpose) in enumerate(SECTIONS):
        content = tabs.get(key) or placeholder(payload["title"], key, labels.get(key, label), purpose)
        body.append(shell.tab(key, content, on=(n == 0)))
    extra = payload.get("script", "")
    return shell.page(
        title=f"{payload['title']} · Evaluation",
        brand=payload.get("brand", payload["title"]),
        note_text=payload.get("note", ""),
        nav=nav_for(payload["id"], built),
        tabs_html="".join(body),
        extra_css=payload.get("css", ""),
    ).replace("</body></html>", f"<script>{extra}</script></body></html>" if extra else "</body></html>")


def landing(built: Dict[str, Dict[str, Any]]) -> str:
    """The front door: the protocol, and one card per case study."""
    cards: List[str] = []
    for case in CASES:
        p = built.get(case["id"])
        if p is None:
            # The page exists and has every section, all of them empty. Saying
            # "not yet" and refusing to open it would hide the skeleton, which
            # is the thing that makes the case studies comparable.
            cards.append(
                f"<a class='stg off' href='{E(case['id'])}.html'><h3>{E(case['title'])}</h3>"
                f"<p>{E(case['subtitle'])}</p><div class='st'>the sections, still empty →</div></a>"
            )
            continue
        cards.append(
            f"<a class='stg' href='{E(p['id'])}.html'><h3>{E(p['title'])}</h3>"
            f"<p>{E(p.get('blurb', ''))}</p>"
            + "".join(chip(f"{k}: {v}") for k, v in p.get("summary", []))
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
        note_text=f"{sum(1 for c in CASES if has_generator(c['folder']))} of {len(CASES)} case studies",
        nav=nav_for(None, built),
        tabs_html=shell.tab("home", intro + "<div class='grid g4'>" + "".join(cards) + "</div>", on=True),
        extra_css=(
            ".stg{display:block;background:var(--panel);border:1px solid var(--line);border-radius:12px;"
            "padding:18px 20px;text-decoration:none;color:var(--text);box-shadow:var(--shadow)}"
            ".stg:hover{border-color:var(--acc)}.stg h3{margin:0 0 6px;font-size:16px}"
            ".stg p{margin:0 0 8px;color:var(--muted);font-size:13.5px}"
            ".stg .st{margin-top:10px;font-size:12px;font-weight:600;color:var(--acc)}"
            ".stg.off{opacity:.5}.stg.off .st{color:var(--muted)}"
        ),
    )


def build(only: Optional[str] = None, python: str = PYTHON) -> List[Path]:
    """Collect every case study and write the site. Returns the files written."""
    built: Dict[str, Dict[str, Any]] = {}
    for case in CASES:
        if only and case["id"] != only:
            continue
        if not has_generator(case["folder"]):
            continue
        print(f"collecting {case['id']} …")
        p = collect(case["id"], case["folder"], python)
        if p is not None:
            built[case["id"]] = p
    if not built:
        raise SystemExit("no case study produced a fragment")

    # A case study with no generator still gets a page: the same sections, all
    # of them empty and saying so. The skeleton is the standard; filling it in
    # is each case study's work.
    pages = dict(built)
    for case in CASES:
        pages.setdefault(case["id"], {
            "id": case["id"], "title": case["title"], "brand": f"{case['title']} · {case['subtitle']}",
            "note": "", "blurb": case["subtitle"], "summary": [], "groups": [], "tabs": {},
        })

    SITE.mkdir(parents=True, exist_ok=True)
    written: List[Path] = []
    for case_id, p in pages.items():
        out = SITE / f"{case_id}.html"
        out.write_text(render(p, pages), encoding="utf-8")
        written.append(out)
    index = SITE / "index.html"
    index.write_text(landing(built), encoding="utf-8")
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
