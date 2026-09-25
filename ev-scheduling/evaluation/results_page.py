"""The runs that exist, read against the table the design says they should fill.

The companion of ``evaluation/design_page.py``. The design page states what the
comparison is meant to be; this page states what has actually been measured, and
puts the two next to each other so the distance is visible rather than inferred.
Every run set under ``results/`` that carries a ``run_manifest.json`` is listed,
with the arms it covers, the arms of the target design it does not, and the
per-day rows behind each rate.

The data is embedded in the page at build time rather than fetched. A fetched
page cannot be opened from the file system without a local server, and the point
of this page is that it opens.

Usage (from ev-scheduling/):
    python -m evaluation.results_page

Writes ``results/visuals/results.html``.
"""

from __future__ import annotations

import csv
import json
from html import escape as _escape
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]

from evaluation.design_page import CSS, ROWS, E  # noqa: E402  (shared look and target design)

# Columns of rows.csv worth showing per day. Everything else stays in the file.
ROW_COLUMNS = (
    ("date", "day"),
    ("variant", "variant"),
    ("outcome", "outcome"),
    ("outcome_reason", "why"),
    ("formulation_status", "form."),
    ("state_status", "state"),
    ("traceability_status", "trace"),
    ("answer_status", "answer"),
    ("gap_pct", "gap %"),
    ("cost_usd", "cost $"),
    ("unmet_kwh", "unmet kWh"),
    ("peak_kw", "peak kW"),
    ("gate_passed", "gate"),
    ("total_tokens", "tokens"),
    ("wall_s", "s"),
)


def run_dirs() -> List[Path]:
    root = PROJECT_ROOT / "results"
    if not root.is_dir():
        return []
    return [d for d in sorted(root.iterdir()) if (d / "run_manifest.json").exists()]


def read_rows(d: Path) -> List[Dict[str, str]]:
    f = d / "rows.csv"
    if not f.exists():
        return []
    with f.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def read_json(path: Path) -> Optional[Any]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return None


def outcome_pill(value: str) -> str:
    cls = {"solved": "solved", "escalated": "escalated", "wrong_unflagged": "wrong"}.get(value, "")
    return f"<span class='vd {cls}'>{E(value or '-')}</span>" if cls else E(value or "-")


def headline_card(dirs: List[Path]) -> str:
    """The solver-grounded row against the target it was given, computed here.

    The mission for that row, fixed for both case studies, is Solved + Escalated
    = 100 % and Wrong-unflagged = 0. Whether it holds is the first thing anyone
    opening this page wants to know, so it is not left for them to add up.
    """
    rows: List[Dict[str, str]] = []
    src = ""
    for d in dirs:
        r = [x for x in read_rows(d) if x.get("arm") == "evagent"]
        if r:
            rows, src = r, d.name
    if not rows:
        return ""
    n = len(rows)
    solved = sum(1 for r in rows if r.get("outcome") == "solved")
    esc = sum(1 for r in rows if r.get("outcome") == "escalated")
    bad = sum(1 for r in rows if r.get("outcome") == "wrong_unflagged")
    gate_ok = sum(1 for r in rows if str(r.get("gate_passed")).lower() == "true")
    exact = sum(int(r["n_sessions_exact"] or 0) for r in rows if r.get("n_sessions_exact"))
    truth = sum(int(r["n_sessions_truth"] or 0) for r in rows if r.get("n_sessions_truth"))
    form_days = sum(1 for r in rows if r.get("formulation_status") == "pass")
    share = (100.0 * exact / truth) if truth else 0.0
    ok = bad == 0 and solved + esc == n
    return (
        "<div class='card'><h2>The solver-grounded row against its target</h2>"
        f"<p class='muted'>Computed from <code>{E(src)}</code>, arm <code>evagent</code>, {n} days.</p>"
        f"<p style='font-size:15px'><span class='vd solved'>solved {solved}/{n}</span> "
        f"<span class='vd escalated'>escalated {esc}/{n}</span> "
        f"<span class='vd wrong'>wrong, unflagged {bad}/{n}</span></p>"
        f"<p>Target: solved + escalated = {n}, wrong-unflagged = 0. "
        f"{'<b>Met.</b>' if ok else f'<b>Not met:</b> {solved + esc} of {n}, and {bad} wrong-unflagged.'}</p>"
        f"<p>The gate accepted <b>{gate_ok} of {n}</b> answers. Formulation was exact on "
        f"<b>{exact} of {truth} sessions ({share:.1f} %)</b> and on <b>{form_days} of {n} days</b>, because a day "
        f"counts only when every one of its sessions is exact.</p>"
        "<p class='warn-box'>Those three numbers together are the finding, not three separate ones. The agent misread "
        "a field on a few sessions per day, optimised the day it had parsed, and the gate accepted the result because "
        "the LP was optimal and every reported number came from it. The gate sees only the agent's own evidence, by "
        "design, so a misread request is invisible to it. The design page, under <b>Gate &amp; scoring</b>, states "
        "the three ways out and which of them is a decision rather than a fix.</p></div>"
    )


def coverage_card(covered: set[str]) -> str:
    """The target design's rows against the arms any run actually covers."""
    H = [
        "<div class='card'><h2>Coverage of the target design</h2>"
        "<p class='muted'>Rows from <code>evaluation/design_page.py</code>, the same list the design page shows. "
        "A row with no arm has never been measured, on any model.</p><table>"
        "<tr><th>Row of the target table</th><th>arm</th><th>measured</th></tr>"
    ]
    for r in ROWS:
        arm = r["arm"]
        if arm and arm in covered:
            state = "<span class='chip ok'>yes</span>"
        elif arm:
            state = "<span class='chip warn'>arm registered, never run</span>"
        else:
            state = "<span class='chip bad'>no arm exists</span>"
        H.append(
            f"<tr><td>{E(r['label'])}</td><td><code>{E(arm) if arm else '—'}</code></td><td>{state}</td></tr>"
        )
    n = sum(1 for r in ROWS if r["arm"] and r["arm"] in covered)
    H.append(
        f"</table><p class='warn-box'><b>{n} of {len(ROWS)} rows of the target table have numbers.</b> "
        "A table published from this state would be missing the conventional-automation row and every agent "
        "architecture except the gated one, which is precisely the comparison R4.3 and R4.5 asked for.</p></div>"
    )
    return "".join(H)


def scoreboard_card(d: Path) -> str:
    md = d / "scoreboard.md"
    if not md.exists():
        return ""
    text = md.read_text(encoding="utf-8")
    return f"<details><summary>scoreboard.md as the run wrote it</summary><pre>{E(text)}</pre></details>"


def run_card(d: Path) -> tuple[str, set[str]]:
    man = read_json(d / "run_manifest.json") or {}
    rows = read_rows(d)
    arms_present = {r.get("arm", "") for r in rows if r.get("arm")}
    traces = len(list((d / "traces").rglob("*.json"))) if (d / "traces").is_dir() else 0

    by_arm: Dict[str, List[Dict[str, str]]] = {}
    for r in rows:
        by_arm.setdefault(r.get("arm", "?"), []).append(r)

    H = [
        f"<div class='card'><h2><code>{E(d.name)}</code></h2>"
        f"<span class='chip'>{E(man.get('model_resolved') or man.get('model_requested') or 'no model')}</span>"
        f"<span class='chip'>{E(man.get('days') or len({r.get('date') for r in rows}))} days</span>"
        f"<span class='chip'>{len(rows)} rows</span>"
        f"<span class='chip'>{traces} traces</span>"
        f"<span class='chip'>${E(man.get('spent_usd', 0))} spent</span>"
        f"<span class='chip {'ok' if not man.get('synthetic') else 'bad'}'>"
        f"{'real frozen days' if not man.get('synthetic') else 'SMOKE TEST, synthetic days'}</span>"
    ]
    digest = str(man.get("requests_digest", ""))
    if digest:
        H.append(f"<p class='muted'>request digest <code>{E(digest[:30])}…</code> — every arm below answered the same list.</p>")

    H.append("<h3>Outcome split per arm</h3><table><tr><th>arm</th><th>n</th><th>solved</th><th>escalated</th>"
             "<th>wrong, unflagged</th><th>failed</th></tr>")
    for arm, rs in by_arm.items():
        n = len(rs)
        ok = sum(1 for r in rs if r.get("outcome") == "solved")
        esc = sum(1 for r in rs if r.get("outcome") == "escalated")
        bad = sum(1 for r in rs if r.get("outcome") == "wrong_unflagged")
        failed = sum(1 for r in rs if r.get("status") != "ok")
        H.append(
            f"<tr><td><code>{E(arm)}</code></td><td>{n}</td>"
            f"<td>{ok} <span class='muted'>({100.0 * ok / n:.0f}%)</span></td>"
            f"<td>{esc} <span class='muted'>({100.0 * esc / n:.0f}%)</span></td>"
            f"<td>{bad} <span class='muted'>({100.0 * bad / n:.0f}%)</span></td><td>{failed}</td></tr>"
        )
    H.append("</table>")
    H.append(scoreboard_card(d))

    for arm, rs in by_arm.items():
        H.append(f"<details><summary>{E(arm)} — every day</summary><table><tr>"
                 + "".join(f"<th>{E(label)}</th>" for _, label in ROW_COLUMNS) + "</tr>")
        for r in sorted(rs, key=lambda x: str(x.get("date"))):
            cells = []
            for key, _ in ROW_COLUMNS:
                v = r.get(key, "")
                cells.append(f"<td>{outcome_pill(v) if key == 'outcome' else E(v)}</td>")
            H.append("<tr>" + "".join(cells) + "</tr>")
        H.append("</table></details>")
    H.append("</div>")
    return "".join(H), arms_present


def build() -> Path:
    dirs = run_dirs()
    cards: List[str] = []
    covered: set[str] = set()
    for d in dirs:
        card, arms_present = run_card(d)
        cards.append(card)
        covered |= arms_present

    H = [
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>EVAgent · Results</title>"
        "<link href='https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap' rel='stylesheet'>"
        f"<style>{CSS}details summary{{cursor:pointer;color:var(--acc);font-size:12.5px;margin:6px 0}}"
        "details table{margin-top:6px}details pre{max-height:320px}</style></head><body>"
        "<header><h1>EVAgent · Results</h1><span class='muted'>what has been measured, against what the design says "
        "should be</span></header><main>"
    ]
    if not dirs:
        H.append("<div class='card'><h2>No runs</h2><p>No directory under <code>results/</code> carries a run manifest.</p></div>")
    H.append(headline_card(dirs))
    H.append(coverage_card(covered))
    H.extend(cards)
    H.append("</main></body></html>")

    out = PROJECT_ROOT / "results" / "visuals" / "results.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(H), encoding="utf-8")
    return out


if __name__ == "__main__":
    p = build()
    print(f"wrote {p} ({p.stat().st_size // 1024} KB)")
