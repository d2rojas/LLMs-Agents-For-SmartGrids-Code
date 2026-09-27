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

# Where the standalone pages this adapter reads are written.
DESIGN = PROJECT_ROOT / "results" / "visuals" / "design.html"
HOME = PROJECT_ROOT / "results" / "visuals" / "index.html"

# Nothing about the section list is hard-coded here. The sections are whichever
# ones the design page emits, in its order and under its own labels, so this
# case study can add, drop or rename one without anybody editing this file.


def _rules(css: str) -> List[Tuple[str, str, bool]]:
    """Split a stylesheet into (selector, declarations, is_at_rule) triples.

    Written by hand because the alternative is a dependency, and the input is
    one generated stylesheet rather than arbitrary CSS.
    """
    out: List[Tuple[str, str, bool]] = []
    sel: List[str] = []
    i, n = 0, len(css)
    while i < n:
        ch = css[i]
        if ch == "{":
            depth, j = 1, i + 1
            while j < n and depth:
                if css[j] == "{":
                    depth += 1
                elif css[j] == "}":
                    depth -= 1
                j += 1
            selector = "".join(sel).strip()
            out.append((selector, css[i + 1 : j - 1], selector.startswith("@")))
            sel, i = [], j
            continue
        sel.append(ch)
        i += 1
    return out


def _own_selectors(css: str) -> set:
    """Every selector a stylesheet defines, one per comma-separated part."""
    owned = set()
    for selector, _body, at_rule in _rules(css):
        if at_rule:
            continue
        for part in selector.split(","):
            owned.add(part.strip())
    return owned


# Chrome the shared shell owns under different names. The standalone page put
# its navigation in a sticky ``header`` with a ``.tabs`` button bar; the shared
# page has a top strip and a sidebar instead, so these rules describe elements
# that no longer exist and can only interfere.
CHROME = ("header", "header h1", ".tabs", ".tabs button", ".tabs button.on", "body.embed header")


def _strip_shared(css: str, owned: set) -> str:
    """Keep only the rules the shared shell does not already define.

    The adapter injects this case study's own stylesheet after the shell's, so
    anything it redefines wins. Its ``body``, ``main`` and ``:root`` rules were
    written for a standalone page and break the shared layout when they land on
    top of it. Dropping every selector the shell owns leaves exactly the
    components that are this case study's own, and leaves one look.
    """
    kept: List[str] = []
    for selector, body, at_rule in _rules(css):
        if at_rule:
            continue  # the shell owns the responsive rules
        parts = [
            p.strip()
            for p in selector.split(",")
            if p.strip() and p.strip() not in owned and p.strip() not in CHROME
        ]
        if parts:
            kept.append(",".join(parts) + "{" + body.strip() + "}")
    return "\n".join(kept)


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


def _home() -> Tuple[str, str]:
    """This case study's home section and the styles it needs, from its own page.

    The standalone site keeps the home in ``index.html`` and the sections in
    ``design.html``. The shared site wants the home as the first section, so it
    is lifted from there rather than written a second time here.
    """
    if not HOME.exists():
        return "", ""
    html = HOME.read_text(encoding="utf-8")
    i = html.find("<section id='home'")
    if i < 0:
        return "", ""
    i = html.find(">", i) + 1
    j = html.find("</section>", i)
    return html[i:j], _inner(html, "<style>", "</style>")


def payload() -> Dict[str, Any]:
    from evaluation import design_page
    from visuals import shell

    html = design_page.build().read_text(encoding="utf-8")
    owned = _own_selectors(shell.CSS)

    css = _strip_shared(_inner(html, "<style>", "</style>"), owned)
    # The page's driver is its last script block. Taking from the first
    # ``<script>`` instead would swallow every script the content embeds, and
    # with them the megabytes of page between the first and the last.
    tail = html[html.rfind("<script>") :]
    script = _inner(tail, "<script>", "</script>")
    tabs = _split_tabs(_inner(html, "<main>", "</main>"))

    # Section labels come from the page's own tab bar, so a rename there needs
    # no change here. A section with no button falls back to its key.
    labels = dict(re.findall(r"<button data-tab='([a-z0-9_-]+)'[^>]*>([^<]*)</button>", html))
    entries: List[Tuple[str, str]] = []

    home, home_css = _home()
    if home:
        tabs["home"] = home
        css = _strip_shared(home_css, owned) + css
        entries.append(("home", "Home"))
    entries += [(k, labels.get(k, k.replace("_", " ").capitalize())) for k in tabs if k != "home"]

    # The design page drives its own tab bar; the shared shell drives the
    # sidebar instead, so that part of its script has to go or the two fight
    # over which section is visible.
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
        "groups": [["", [list(e) for e in entries]]],
        "tabs": tabs,
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
