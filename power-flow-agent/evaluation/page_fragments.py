"""This case study's contribution to the shared evaluation site.

An adapter, on purpose. ``evaluation/design_page.py`` already builds this case
study's whole design page and is the thing that knows its content; rewriting it
onto the shared shell in one step would mean touching 669 lines of working code
for a change of chrome. So this module runs it, takes the tab bodies, the
stylesheet and the script out of what it produced, and hands them to
``visuals/build.py`` in the fragment protocol every case study uses.

That makes the two case studies share one site today. The next step is to move
``design_page`` onto ``visuals.shell`` directly, at which point this file
becomes the twenty lines that build the payload and the extraction below goes
away.

Usage (from power-flow-agent/):
    python -m evaluation.page_fragments /tmp/fragments.json

Normally invoked by ``python -m visuals.build`` from the repository root.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT.parent))  # so `visuals` is importable

CASE_ID = "pfagent"
CASE_TITLE = "PFAgent"

# The sidebar, in the order the design page defines its tabs. Labels are the
# ones a reader sees; keys must match the ``id='tab-<key>'`` the page emits.
GROUPS: Tuple[Tuple[str, Tuple[Tuple[str, str], ...]], ...] = (
    ("Design", (
        ("overview", "The task"),
        ("methods", "Methods"),
        ("scenarios", "Scenarios"),
        ("prompts", "Prompts"),
        ("tools", "Tools"),
        ("gate", "Gate & scoring"),
        ("plan", "Run plan"),
    )),
)


def _inner(html: str, open_tag: str, close_tag: str) -> str:
    """The text between the first ``open_tag`` and the last ``close_tag``."""
    i = html.find(open_tag)
    j = html.rfind(close_tag)
    if i < 0 or j < 0:
        return ""
    return html[i + len(open_tag) : j]


def _split_tabs(body: str) -> Dict[str, str]:
    """Every ``<div class='tab' id='tab-X'>`` block, by its key.

    The tabs are siblings written one after another, so each one runs from its
    own opening tag to the next one, or to the end. Cutting between markers
    rather than counting ``<div>`` depth keeps this correct even where the
    generated markup leaves a div unbalanced, which it does.
    """
    marks = list(re.finditer(r"<div class='tab[^']*' id='tab-([a-z0-9_-]+)'>", body))
    out: Dict[str, str] = {}
    for n, m in enumerate(marks):
        end = marks[n + 1].start() if n + 1 < len(marks) else len(body)
        chunk = body[m.end() : end].rstrip()
        if chunk.endswith("</div>"):
            chunk = chunk[: -len("</div>")]
        out[m.group(1)] = chunk
    return out


def payload() -> Dict[str, Any]:
    from evaluation import design_page

    html = design_page.build().read_text(encoding="utf-8")

    css = _inner(html, "<style>", "</style>")
    # The page's driver is its last script block. Taking from the first
    # ``<script>`` instead would swallow every script the content embeds, and
    # with them the megabytes of page between the first and the last.
    tail = html[html.rfind("<script>") :]
    script = _inner(tail, "<script>", "</script>")
    tabs = _split_tabs(_inner(html, "<main>", "</main>"))

    wanted = [k for _label, entries in GROUPS for k, _t in entries]
    missing = [k for k in wanted if k not in tabs]
    if missing:
        raise SystemExit(f"design_page did not emit these tabs: {', '.join(missing)}")

    # The design page drives its own tab bar; the shared shell drives the
    # sidebar instead, so that part of its script has to go or the two fight
    # over which tab is visible.
    script = re.sub(r"const tabs=document\.querySelectorAll\('\.tabs button'\);.*?fromHash\(\);", "", script, flags=re.S)

    return {
        "id": CASE_ID,
        "title": CASE_TITLE,
        "brand": "PFAgent · power flow on IEEE test systems",
        "note": "IEEE 14 to 300-bus",
        "blurb": "Answer an operator's power-flow request on an IEEE test system: run the flow, change a load, "
                 "take a line out, scan every single outage.",
        "summary": [
            ("task", "power flow and contingencies"),
            ("solver", "PandaPower Newton-Raphson"),
            ("data", "IEEE 14, 30, 57, 118, 300"),
        ],
        "groups": [[label, [list(e) for e in entries]] for label, entries in GROUPS],
        "tabs": {k: tabs[k] for k in wanted},
        "css": css,
        "script": script,
    }


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else PROJECT_ROOT / "results" / "visuals" / "fragments.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload()), encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
