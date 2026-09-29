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
      "script": "…",                            optional, page-specific JS
      "pages":  {"viewer.html": "/abs/path/viewer.html"},   optional, files copied to site/<id>/
      "links":  {"traces": {"href": "viewer.html", "label": "Trace viewer"}}
                                                optional: a section served by one of those
                                                pages instead of a tab (same tab, own chrome)
    }

Usage (from the repository root):
    python -m visuals.build                 every case study
    python -m visuals.build --case evagent  one of them

Writes ``site/index.html`` and ``site/<case>.html``.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
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
        links = (p or {}).get("links", {})
        entries: List[Tuple[str, ...]] = []
        if case["id"] == current:
            # Every section, in the shared order, under the case study's own
            # label when it has one. Same list on every page, always. A section
            # the case study serves as a page of its own becomes a link to it.
            for key, label, _purpose in SECTIONS:
                if key in links:
                    entries.append((key, links[key].get("label", own.get(key, label)), f"{case['id']}/{links[key]['href']}"))
                else:
                    entries.append((key, own.get(key, label)))
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


# --------------------------------------------------------------- one document

# Four case studies in one HTML document means four sets of element ids, four
# stylesheets and four scripts in one global namespace. They collide: wind and
# power flow both name a selector ``exs``, both define ``.col`` and ``.ln``.
# Rather than ask four case studies to agree on prefixes for ever, the ids and
# the selectors are rewritten here, at assembly time, so each case study goes on
# writing its fragment as though it owned the page. The per-case pages still
# exist and are built from the same fragments, so nothing below changes what a
# case study has to produce.

_ID_ATTR = re.compile(r"""\bid=(['"])([A-Za-z][\w:.-]*)\1""")
_FOR_ATTR = re.compile(r"""\bfor=(['"])([A-Za-z][\w:.-]*)\1""")
_HREF_HASH = re.compile(r"""\bhref=(['"])#([A-Za-z][\w:.-]*)\1""")
_GET_BY_ID = re.compile(r"""getElementById\(\s*(['"])([A-Za-z][\w:.-]*)\1\s*\)""")
_QUERY_ID = re.compile(r"""(querySelector(?:All)?\(\s*(['"]))#([A-Za-z][\w:.-]*)""")


def namespace(text: str, case_id: str) -> str:
    """Prefix every element id in a fragment, and every lookup of one, with the case.

    Applied to the markup and to the script alike: a case study's script reaches
    its own markup through ``getElementById`` and ``querySelector('#x')``, and an
    inline ``onclick`` does it from inside the markup, so both passes run over
    both. Class names are left alone; the stylesheet is scoped instead, which
    keeps the rewriting to a handful of patterns that cannot match prose.
    """
    p = f"{case_id}-"
    text = _ID_ATTR.sub(lambda m: f"id={m.group(1)}{p}{m.group(2)}{m.group(1)}", text)
    text = _FOR_ATTR.sub(lambda m: f"for={m.group(1)}{p}{m.group(2)}{m.group(1)}", text)
    text = _HREF_HASH.sub(lambda m: f"href={m.group(1)}#{p}{m.group(2)}{m.group(1)}", text)
    text = _GET_BY_ID.sub(lambda m: f"getElementById({m.group(1)}{p}{m.group(2)}{m.group(1)})", text)
    text = _QUERY_ID.sub(lambda m: f"{m.group(1)}#{p}{m.group(3)}", text)
    return text


def _css_rules(css: str) -> List[Tuple[str, str, bool]]:
    """Split a stylesheet into (selector, body, is_at_rule), braces balanced."""
    out: List[Tuple[str, str, bool]] = []
    sel: List[str] = []
    i, n = 0, len(css)
    while i < n:
        if css[i] == "{":
            depth, j = 1, i + 1
            while j < n and depth:
                if css[j] == "{":
                    depth += 1
                elif css[j] == "}":
                    depth -= 1
                j += 1
            selector = "".join(sel).strip()
            out.append((selector, css[i + 1: j - 1], selector.startswith("@")))
            sel, i = [], j
            continue
        sel.append(css[i])
        i += 1
    return out


def scope_css(css: str, case_id: str) -> str:
    """Confine a case study's stylesheet to its own part of the document.

    Every selector is prefixed with ``.case[data-case=<id>]``, so wind's ``.col``
    and power flow's ``.col`` stop being the same rule. An at-rule keeps its
    wrapper and has its inner selectors scoped, which is what keeps the
    responsive breakpoints working. A selector that targets the document root
    (``:root``, ``body``, ``html``) is dropped: it describes a standalone page
    and can only fight the shared chrome, which is the same reason the power
    flow adapter already drops them.
    """
    root = f".case[data-case='{case_id}']"
    drop = {":root", "html", "body", "*", "main", "header", "aside"}
    out: List[str] = []
    for selector, body, at_rule in _css_rules(css):
        if at_rule:
            head = selector
            if body.strip().startswith("@") or "{" not in body:
                out.append(f"{head}{{{body}}}")          # @font-face, @keyframes: no selectors
            else:
                out.append(f"{head}{{{scope_css(body, case_id)}}}")
            continue
        parts = []
        for part in selector.split(","):
            part = part.strip()
            if not part or part.split(":")[0].split(" ")[0] in drop:
                continue
            parts.append(f"{root} {part}")
        if parts:
            out.append(",".join(parts) + "{" + body.strip() + "}")
    return "\n".join(out)


def render(payload: Dict[str, Any], built: Dict[str, Dict[str, Any]]) -> str:
    """One case study's page. Every section of SECTIONS, filled in or not."""
    tabs = payload.get("tabs", {})
    labels = {k: t for _g, entries in payload.get("groups", []) for k, t in entries}
    body: List[str] = []
    links = payload.get("links", {})
    for n, (key, label, purpose) in enumerate(SECTIONS):
        if key in links:
            continue  # served by a page of its own; the sidebar links to it
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


# The fragment cache is shared by every worktree of this repository, and lives
# outside all of them.
#
# No interpreter on this machine can import all four projects, so no checkout can
# build the whole site on its own; each one could only build its own case study
# and keep three stale or empty pages beside it. With five worktrees that meant
# five different sites, and what a reader saw depended on which folder they
# happened to open. Keeping the cache per worktree made that structural.
#
# It is a cache, not a source, so it does not belong in git either: these four
# files are 29 MB and change on every run, which is the whole site's weight in
# churn per run in a public repository. Putting it one level above the worktrees
# costs nothing, is shared by construction, and means whoever rebuilds a case
# study updates it for everybody.
FRAGMENTS = Path(os.environ.get("VISUALS_FRAGMENTS") or (ROOT.parent / ".visuals-fragments"))


def cache_put(case_id: str, payload: Dict[str, Any]) -> None:
    """Keep this case study's fragment so a build of another one can render it."""
    FRAGMENTS.mkdir(parents=True, exist_ok=True)
    stamped = dict(payload)
    stamped["_at"] = _dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    # written whole and moved into place, because another worktree may be reading
    # this file while this build writes it
    tmp = FRAGMENTS / f".{case_id}.{os.getpid()}.tmp"
    tmp.write_text(json.dumps(stamped), encoding="utf-8")
    tmp.replace(FRAGMENTS / f"{case_id}.json")


def cache_get(case_id: str) -> Optional[Dict[str, Any]]:
    """The last fragment this checkout managed to build for a case study, if any."""
    f = FRAGMENTS / f"{case_id}.json"
    if not f.exists():
        return None
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def behind_results(case_id: str, folder: str) -> bool:
    """Whether the cached fragment is older than the runs it would describe.

    Not rebuilt and out of date are different things, and only the second is
    worth a warning. No interpreter here can import all four projects, so most
    builds legitimately take three case studies from the cache; saying so on
    every one of their sections turned a normal build into four alarms about
    nothing. What matters is whether the fragment predates the newest scored
    run, which is the same question the cross-check asks of a page.
    """
    f = FRAGMENTS / f"{case_id}.json"
    if not f.exists():
        return True
    results = ROOT / folder / "results"
    if not results.is_dir():
        return False
    newest = max((p.stat().st_mtime for p in results.rglob("summary.csv")), default=0.0)
    return bool(newest and f.stat().st_mtime < newest)


def unified(pages: Dict[str, Dict[str, Any]], fresh: Sequence[str] = ()) -> str:
    """Every case study in one document, the sections of each under its own name.

    Daniela reads the site by opening the file, so the site is one file. The
    sidebar lists the four case studies expanded rather than one expanded and
    three as links, and a section key becomes ``<case>-<section>``: four
    ``results`` sections can coexist because they are four different ids, while
    the eleven names under each case study stay the same eleven, in the same
    order, which is the thing that makes the cases comparable.

    Ids, scripts and stylesheets are isolated per case study by ``namespace``
    and ``scope_css``. A case study that serves a section as a page of its own
    keeps that link; the page is copied next to this one as before.
    """
    nav: List[Dict[str, Any]] = []
    body: List[str] = []
    css: List[str] = []
    scripts: List[str] = []
    # The protocol is site-level, not a case study's section, so it sits above
    # the four rather than inside one of them. It is the page that opens.
    body.append(shell.tab("overview", protocol_card(), on=True))
    nav.append({"title": "The evaluation", "subtitle": "the protocol the four share",
                "href": "#overview", "current": True, "available": True,
                "entries": [("overview", "Protocol")]})
    first = False
    for case in CASES:
        p = pages.get(case["id"])
        if p is None:
            continue
        cid = case["id"]
        # Only a fragment that is actually behind its own results is worth saying
        # anything about. One merely taken from the cache is the normal case.
        stale_note = "" if (cid in fresh or not behind_results(cid, case["folder"])) else shell.note(
            f"This section is older than the runs it describes. What follows is the fragment of "
            f"{E(str(p.get('_at', 'an earlier build')))}, and a run has been scored since. Rebuild it from a "
            f"checkout whose interpreter can import this project: "
            f"<code>python -m visuals.build --require {E(cid)}</code>.", "warn")
        labels = {k: t for _g, entries in p.get("groups", []) for k, t in entries}
        links = p.get("links", {})
        tabs = p.get("tabs", {})
        entries: List[Tuple[str, ...]] = []
        parts: List[str] = []
        for key, label, purpose in SECTIONS:
            text = labels.get(key, label)
            if key in links:
                entries.append((f"{cid}-{key}", links[key].get("label", text), f"{cid}/{links[key]['href']}"))
                continue
            entries.append((f"{cid}-{key}", text))
            content = tabs.get(key)
            content = namespace(content, cid) if content else placeholder(p["title"], key, text, purpose)
            # One document is rewritten on every build, including the parts of
            # it this build could not rebuild. Without this the file's date
            # would vouch for content that is older than the file, which is the
            # failure the per-case pages avoided by simply not being rewritten.
            parts.append(shell.tab(f"{cid}-{key}", stale_note + content, on=first))
            first = False
        body.append(f"<div class='case' data-case='{E(cid)}'>" + "".join(parts) + "</div>")
        if p.get("css"):
            css.append(scope_css(p["css"], cid))
        if p.get("script"):
            # wrapped, so a case study's `var` and `function` stay out of the
            # way of the next one's, and a throw in one does not stop the rest
            scripts.append("try{(function(){" + namespace(p["script"], cid) + "})()}catch(e){"
                           f"console.error('{E(cid)} script:',e)}}")
        nav.append({
            "title": case["title"], "subtitle": case["subtitle"], "href": f"#{cid}-home",
            "current": True, "available": has_generator(case["folder"]), "entries": entries,
        })
    cases = len(nav) - 1                              # the protocol entry is not a case study
    html = shell.page(
        title="Evaluation · four case studies",
        brand="LLMs and agentic AI for smart grids · evaluation",
        note_text=f"{cases} case studies, {len(SECTIONS)} sections each",
        nav=nav,
        tabs_html="".join(body),
        extra_css="\n".join(css),
    )
    # Every case study is expanded in the sidebar, so the highlight has to follow
    # the section being read rather than mark all four at once.
    scripts.insert(0, """
(function(){
  var items=Array.prototype.slice.call(document.querySelectorAll('aside .cs, aside a.sub'));
  function sync(){
    var k=(location.hash||'').slice(1)||FIRST, last=null;
    document.querySelectorAll('aside .cs').forEach(function(c){c.classList.remove('on');});
    items.forEach(function(el){
      if(el.classList.contains('cs')) last=el;
      else if(el.dataset.t===k && last) last.classList.add('on');
    });
  }
  window.addEventListener('hashchange',sync);
  document.querySelectorAll('aside a.sub').forEach(function(a){
    a.addEventListener('click',function(){setTimeout(sync,0);});});
  sync();
})();""")
    tail = "".join(scripts)
    return html.replace("</body></html>", f"<script>{tail}</script></body></html>" if tail else "</body></html>")


def protocol_card() -> str:
    """The protocol every case study shares, stated once for the whole site."""
    return card(
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
        "the tasks optimize different objectives.</p>",
        "<p class='muted'>Reproducibility: each page is generated from the executable configuration of its case "
        "study, comprising the method registry, the verification conditions, the instance generator, the prompt "
        "builders and the recorded results. No description on these pages is maintained separately from the code "
        "it describes.</p>",
    )


def build(only: Optional[str] = None, python: str = PYTHON,
          require: Optional[Sequence[str]] = None) -> List[Path]:
    """Collect every case study and write the site. Returns the files written.

    A case study whose generator fails keeps the page it already has, which used to
    be indistinguishable from a case study nobody changed: the page was still there,
    still had every section, and the build still exited 0. So the run said nothing
    while the page showed yesterday's numbers. Now every failure prints the page it
    is keeping and the date on it.

    Failing the whole build is not the answer, because no worktree can import all
    four projects: a global strictness would fire on every build for everyone, and a
    flag to switch it off would be typed reflexively within a day. Instead the exit
    code is scoped to what the caller asked for. ``require`` names the case studies
    this build must produce, and ``only`` is an implicit one. A failure outside that
    set is printed and does not fail the build, because it is somebody else's project
    that this checkout was never able to build.
    """
    built: Dict[str, Dict[str, Any]] = {}
    failed: List[str] = []
    for case in CASES:
        if only and case["id"] != only:
            continue
        if not has_generator(case["folder"]):
            continue
        print(f"collecting {case['id']} …")
        p = collect(case["id"], case["folder"], python)
        if p is not None:
            built[case["id"]] = p
            cache_put(case["id"], p)
        else:
            failed.append(case["id"])
    if not built:
        raise SystemExit("no case study produced a fragment")

    # One document holds all four case studies, so a build of one of them still
    # has to render the other three. Their fragments come from the cache the
    # last build that could run them left behind. A case study that has never
    # been built here has no cached fragment and shows the empty skeleton, which
    # is the same thing its own page shows.
    fresh = set(built)
    for case in CASES:
        if case["id"] in built:
            continue
        cached = cache_get(case["id"])
        if cached is not None:
            built[case["id"]] = cached

    # A case study with no generator still gets a page: the same sections, all
    # of them empty and saying so. The skeleton is the standard; filling it in
    # is each case study's work. A case study that has a generator but was not
    # rebuilt this time (--case) keeps the page it already has: overwriting it
    # with the placeholder would erase a finished page because another one was
    # being worked on.
    pages = dict(built)
    for case in CASES:
        if case["id"] in pages:
            continue
        if has_generator(case["folder"]) and (SITE / f"{case['id']}.html").exists():
            continue
        pages[case["id"]] = {
            "id": case["id"], "title": case["title"], "brand": f"{case['title']} · {case['subtitle']}",
            "note": "", "blurb": case["subtitle"], "summary": [], "groups": [], "tabs": {},
        }

    SITE.mkdir(parents=True, exist_ok=True)
    written: List[Path] = []
    for case_id, p in pages.items():
        # The per-case page is only rewritten when this build actually produced
        # the case study, so its date keeps meaning what it meant: when these
        # numbers were read. A case rendered from the cache is rewritten only
        # inside index.html, where it carries a banner saying so.
        if case_id not in fresh and (SITE / f"{case_id}.html").exists():
            continue
        out = SITE / f"{case_id}.html"
        out.write_text(render(p, pages), encoding="utf-8")
        written.append(out)
        # pages a case study serves as its own (a trace viewer too large to
        # embed) are copied next to it, under site/<id>/, and linked from the sidebar
        for name, src in (p.get("pages") or {}).items():
            dest = SITE / case_id / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(Path(src).read_bytes())
            written.append(dest)
    # One file holds the four case studies, because that is how the site is read:
    # by opening it. The per-case pages above stay as they were, so a case study
    # can still be looked at on its own, and so a stale one keeps its own date.
    index = SITE / "index.html"
    index.write_text(unified(pages, fresh), encoding="utf-8")
    written.append(index)
    if failed:
        wanted = {c for c in (require or ())} | ({only} if only else set())
        print()
        for case_id in failed:
            page = SITE / f"{case_id}.html"
            when = (_dt.datetime.fromtimestamp(page.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
                    if page.exists() else "no page at all")
            mark = "FAILED" if case_id in wanted else "failed"
            print(f"  {case_id}: generator {mark}, keeping the page from {when}")
        print("  the usual cause is the interpreter: <project>/.venv/bin/python when it exists,")
        print("  otherwise the python running this build, which may not have that project's")
        print("  dependencies. Pass --python, or build that case from its own checkout.")
        stale = [c for c in failed if c in wanted]
        if stale:
            for path in written:
                print(f"wrote {path.relative_to(ROOT)} ({path.stat().st_size // 1024} KB)")
            raise SystemExit(f"stale: {', '.join(stale)} did not rebuild and was required")
    return written


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--case", help="build only this case study")
    ap.add_argument("--python", default=PYTHON, help="interpreter that can import every case study")
    ap.add_argument("--require", action="append", metavar="CASE",
                    help="fail the build if this case study does not rebuild (repeatable; --case implies it)")
    args = ap.parse_args()
    for path in build(args.case, args.python, args.require):
        print(f"wrote {path.relative_to(ROOT)} ({path.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
