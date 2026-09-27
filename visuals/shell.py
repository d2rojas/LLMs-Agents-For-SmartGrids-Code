"""The look and the building blocks every case study's evaluation page uses.

One copy of the stylesheet, the tab skeleton, the chips, the tables and the
prompt blocks, imported by each case study's page generator. The reason it is
shared rather than copied is the reason the pages exist at all: the case studies
are read side by side, and a difference in how two pages look or name things is
read as a difference between the case studies. A shared shell cannot drift.

What a case study provides is content, never chrome: a list of tabs, and the
HTML of each one, built with the helpers here. ``visuals/build.py`` collects
those fragments and writes the site.

Pure standard library on purpose. This module is imported by generators running
in different projects with different dependencies, and it must not add one.
"""

from __future__ import annotations

from html import escape as _escape
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

__all__ = [
    "CSS",
    "E",
    "card",
    "chip",
    "verdict",
    "table",
    "kv",
    "flow",
    "note",
    "prompt_block",
    "diagram",
    "diagram_card",
    "tab",
    "page",
]


def E(x: Any) -> str:
    """HTML-escape any value."""
    return _escape(str(x), quote=True)


# --------------------------------------------------------------------- style

CSS = """
:root{--bg:#f3f5f8;--panel:#fff;--line:#e3e7ee;--text:#0f172a;--muted:#64748b;--acc:#2f5fd0;
--ok:#1f9d55;--esc:#e0891a;--bad:#d53f3f;--side:#0f1b2d;--side2:#16243a;--sidetext:#c7d0dd;
--shadow:0 1px 2px rgba(15,23,42,.06),0 4px 14px rgba(15,23,42,.05)}
*{box-sizing:border-box}html,body{height:100%}
body{margin:0;font:14px/1.5 Inter,-apple-system,Segoe UI,Helvetica,Arial,sans-serif;color:var(--text);
background:var(--bg);display:flex;flex-direction:column}

.top{height:48px;background:var(--side);color:#fff;display:flex;align-items:center;gap:14px;padding:0 16px;
flex:none;border-bottom:1px solid #22314a}
.top .brand{font-weight:700;letter-spacing:.2px}.top .sp{flex:1}
.top .note{font-size:12px;color:var(--sidetext)}
.top .burger{display:none;background:none;border:0;color:#fff;font-size:20px;cursor:pointer}
.top select{font:inherit;font-size:13px;padding:3px 8px;border-radius:7px;border:1px solid #2a3b57;
background:var(--side2);color:#fff}

.wrap{flex:1;display:flex;min-height:0}
aside{width:236px;flex:none;background:var(--side2);color:var(--sidetext);overflow:auto;padding:12px 0;
border-right:1px solid #22314a}
/* one row per case study, always all of them */
aside .cs{display:flex;align-items:flex-start;gap:10px;padding:11px 14px;color:var(--sidetext);
text-decoration:none;border-left:3px solid transparent;border-top:1px solid #22314a}
aside .cs:first-child{border-top:0}
aside a.cs:hover{background:#1e2f49;color:#fff}
aside .cs .n{width:21px;height:21px;flex:none;border-radius:50%;background:#2a3b57;color:#fff;font-size:11px;
display:inline-flex;align-items:center;justify-content:center;font-weight:700;margin-top:1px}
aside .cs .t{font-size:13.5px;font-weight:600;line-height:1.3}
aside .cs .t small{display:block;font-weight:400;font-size:11.5px;color:#8290a5;margin-top:1px}
aside .cs.on{background:#243a5c;color:#fff;border-left-color:#7aa2ff}
aside .cs.on .n{background:#7aa2ff;color:#0f1b2d}
aside .cs.off{opacity:.45}
/* the sections of the case study being read */
aside a.sub{display:block;padding:7px 18px 7px 45px;color:var(--sidetext);text-decoration:none;font-size:13px;
border-left:3px solid transparent;cursor:pointer;background:#1a2b44}
aside a.sub:hover{background:#1e2f49;color:#fff}
aside a.sub.on{color:#fff;border-left-color:#7aa2ff;font-weight:600;background:#1e3151}
aside hr{border:0;border-top:1px solid #22314a;margin:10px 18px}

main{flex:1;min-width:0;overflow:auto;padding:18px 22px}
.inner{max-width:1500px;margin:0 auto}
.tab{display:none}.tab.on{display:block}

.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:14px 16px;
box-shadow:var(--shadow);margin-bottom:12px}
.card h2{font-size:16px;margin:0 0 6px}.card h3{font-size:14px;margin:12px 0 6px}
.card p{margin:0 0 9px}.card ul,.card ol{margin:6px 0;padding-left:20px}.card li{margin:3px 0}
.card>:last-child{margin-bottom:0}

.grid{display:grid;gap:12px}.g2{grid-template-columns:repeat(2,minmax(0,1fr))}
.g3{grid-template-columns:repeat(3,minmax(0,1fr))}.g4{grid-template-columns:repeat(4,minmax(0,1fr))}
.g6{grid-template-columns:repeat(6,minmax(0,1fr))}
@media(max-width:1000px){.g3,.g4,.g6{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:820px){.grid{grid-template-columns:1fr!important}main{padding:14px 12px}
aside{position:fixed;top:48px;bottom:0;left:0;transform:translateX(-100%);transition:transform .2s;z-index:10}
aside.open{transform:none}.top .burger{display:block}.top .note{display:none}}

.muted{color:var(--muted);font-size:12.5px}
.chip{display:inline-block;padding:2px 9px;border-radius:999px;font-size:11.5px;font-weight:600;
background:#eef1f5;color:#334155;margin:2px 4px 2px 0}
.chip.acc{background:var(--acc);color:#fff}.chip.ok{background:#e6f4ea;color:#166534}
.chip.bad{background:#fdecec;color:#991b1b}.chip.warn{background:#fdf0e3;color:#9a5b0a}
.vd{display:inline-block;padding:1px 8px;border-radius:999px;color:#fff;font-size:11px;font-weight:600;
white-space:nowrap}
.vd.solved{background:var(--ok)}.vd.escalated{background:var(--esc)}.vd.wrong{background:var(--bad)}

.dg{background:#fafbfd;border:1px solid var(--line);border-radius:10px;padding:8px}
.dg h4{margin:0;font-size:12.5px}.dg .muted{font-size:11.5px;margin-bottom:4px}
.flow{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin:8px 0}
.flow .box{background:#fff;border:1px solid var(--line);border-radius:10px;padding:8px 12px;box-shadow:var(--shadow)}
.flow .box b{display:block;font-size:13px}.flow .box span{font-size:12px;color:var(--muted)}
.flow .arr{color:var(--muted);font-size:18px}

.tw{overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:13px;background:#fff}
th,td{border:1px solid var(--line);padding:6px 8px;vertical-align:top;text-align:left}
th{background:#f6f8fb;font-weight:600}th.g{text-align:center;background:#eef2fb}
code{font-family:"JetBrains Mono",ui-monospace,Menlo,Consolas,monospace;font-size:12px;background:#f1f4f9;
padding:1px 4px;border-radius:4px}
pre{background:#fafbfd;border:1px solid var(--line);border-radius:8px;padding:10px;white-space:pre-wrap;
word-break:break-word;font:12px/1.45 "JetBrains Mono",ui-monospace,Menlo,Consolas,monospace;margin:4px 0;
max-height:460px;overflow:auto}
details summary{cursor:pointer;color:var(--acc);font-size:12.5px;margin:6px 0}
.kv{display:grid;grid-template-columns:auto 1fr;gap:3px 12px;font-size:13px}
.kv b{color:var(--muted);font-weight:500}

.blk{border-left:5px solid #ccc;background:#fff;border-radius:0 8px 8px 0;padding:8px 12px;margin:8px 0;
border-top:1px solid var(--line);border-right:1px solid var(--line);border-bottom:1px solid var(--line)}
.blk-h{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:4px}
.blk-h b{font-size:13px}.blk-h .src{color:var(--muted);font-size:11.5px;font-family:ui-monospace,Menlo,monospace}
.sw{width:10px;height:10px;border-radius:3px;display:inline-block}

.note{border-radius:10px;padding:10px 12px;font-size:13px;margin:10px 0 0}
.note.warn{background:#fdf7ec;border:1px solid #f0dcbc}
.note.info{background:#eef2fb;border:1px solid #d6e0f7}
.note.bad{background:#fdecec;border:1px solid #f3c9c9}

.math{background:#fafbfd;border:1px solid var(--line);border-radius:10px;padding:12px 14px;margin:8px 0;
font:14px/1.9 "JetBrains Mono",ui-monospace,Menlo,Consolas,monospace;overflow-x:auto}
.math .lbl{color:var(--muted);font-size:11.5px;font-family:Inter,sans-serif;display:block;margin-top:8px}
.math .eq{display:block;padding-left:8px}
.math sub{font-size:.72em}.math sup{font-size:.72em}
.math em{font-style:italic;font-family:Georgia,"Times New Roman",serif}
"""


# ----------------------------------------------------------------- fragments


def chip(text: str, kind: str = "") -> str:
    """A rounded label. ``kind`` is "", "acc", "ok", "warn" or "bad"."""
    return f"<span class='chip {kind}'>{E(text)}</span>"


def verdict(name: str) -> str:
    """The coloured outcome pill: solved, escalated or wrong."""
    cls = {"solved": "solved", "escalated": "escalated", "wrong": "wrong", "wrong_unflagged": "wrong"}
    return f"<span class='vd {cls.get(name, '')}'>{E(name.replace('_', ', '))}</span>"


def note(body: str, kind: str = "warn") -> str:
    """A highlighted paragraph. ``kind`` is "warn", "info" or "bad"."""
    return f"<div class='note {kind}'>{body}</div>"


def card(title: Optional[str], *body: str, cls: str = "") -> str:
    """A panel with an optional heading."""
    head = f"<h2>{E(title)}</h2>" if title else ""
    return f"<div class='card {cls}'>{head}{''.join(body)}</div>"


def table(headers: Sequence[str], rows: Iterable[Sequence[str]], *, escape: bool = False) -> str:
    """A table. Cells are HTML unless ``escape`` is set."""
    def cell(x: Any) -> str:
        return E(x) if escape else str(x)

    head = "".join(f"<th>{E(h)}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{cell(c)}</td>" for c in r) + "</tr>" for r in rows)
    return f"<div class='tw'><table><tr>{head}</tr>{body}</table></div>"


def kv(pairs: Sequence[Tuple[str, str]]) -> str:
    """A two-column key/value list."""
    return "<div class='kv'>" + "".join(f"<b>{E(k)}</b><span>{v}</span>" for k, v in pairs) + "</div>"


def flow(steps: Sequence[Tuple[str, str]]) -> str:
    """The left-to-right pipeline strip: (title, subtitle) per box."""
    boxes = [f"<div class='box'><b>{E(t)}</b><span>{E(s)}</span></div>" for t, s in steps]
    return "<div class='flow'>" + "<span class='arr'>→</span>".join(boxes) + "</div>"


def prompt_block(label: str, body: str, *, colour: str = "#2f5fd0", source: str = "", pre: bool = True) -> str:
    """One coloured section of a prompt, with the file or function it comes from.

    The colours and the source line are the point: a reader has to be able to
    see which part of a prompt is shared, which is the one thing that differs
    between two methods, and where to go and change it.
    """
    src = f"<span class='src'>{E(source)}</span>" if source else ""
    inner = f"<pre>{E(body)}</pre>" if pre else body
    return (
        f"<div class='blk' style='border-left-color:{E(colour)}'>"
        f"<div class='blk-h'><span class='sw' style='background:{E(colour)}'></span>"
        f"<b>{E(label)}</b>{src}</div>{inner}</div>"
    )


# The palette of a method diagram. One meaning per colour, the same in every
# case study, so a reader learns it once: who is the language model, who is the
# trusted tool, where verification happens, and where a request can leave.
STEP_STYLE: Dict[str, Tuple[str, str]] = {
    "input": ("#eef1f5", "#cbd5e1"),
    "code": ("#f3f4f6", "#cbd5e1"),
    "llm": ("#e8eefc", "#2f5fd0"),
    "plan": ("#e8eefc", "#6d4fc4"),
    "solver": ("#e0f2f1", "#0f8f84"),
    "gate": ("#fff7db", "#c99a06"),
    "out": ("#eef1f5", "#cbd5e1"),
    "ok": ("#e6f4ea", "#1f9d55"),
    "esc": ("#fdf0e3", "#e0891a"),
}


def diagram(
    steps: Sequence[Tuple[str, str]],
    *,
    loop: Optional[Tuple[int, str]] = None,
    branch: Optional[Tuple[str, str]] = None,
    footnote: str = "",
) -> str:
    """The control flow of one method, as a small inline SVG.

    Every case study draws its methods with this, so two methods that work the
    same way look the same on two different pages, and a difference on the page
    means a difference in the method.

    Args:
        steps: (text, kind) top to bottom; kind indexes ``STEP_STYLE``.
        loop: (index, label) to draw a return arc from that step back to the
            one above it, for an iterating method.
        branch: (left, right) two outcome boxes below the last step, for a
            method that can end in more than one place.
        footnote: One line under the diagram, for what the boxes cannot say.

    Returns:
        A complete ``<svg>`` element that scales to its container's width.
    """
    W = 230
    top, bh, gap = 8, 28, 24
    n = len(steps)
    height = top + n * bh + (n - 1) * gap + (58 if branch else 0) + (24 if footnote else 8)

    def box(x: float, y: float, w: float, h: float, text: str, kind: str) -> str:
        fill, stroke = STEP_STYLE.get(kind, STEP_STYLE["out"])
        return (
            f"<rect x='{x}' y='{y}' width='{w}' height='{h}' rx='8' fill='{fill}' stroke='{stroke}'/>"
            f"<text x='{x + w / 2}' y='{y + h / 2 + 4}' text-anchor='middle' font-size='11' "
            f"font-family='Inter,Helvetica,Arial' fill='#0f172a'>{E(text)}</text>"
        )

    def arrow(y1: float, y2: float) -> str:
        return (
            f"<line x1='115' y1='{y1}' x2='115' y2='{y2}' stroke='#64748b' stroke-width='1.6' "
            "marker-end='url(#a)'/>"
        )

    d = [
        f"<svg viewBox='0 0 {W} {height}' width='100%' xmlns='http://www.w3.org/2000/svg'>"
        "<defs><marker id='a' markerWidth='8' markerHeight='8' refX='7' refY='4' orient='auto'>"
        "<path d='M0,0 L8,4 L0,8 z' fill='#64748b'/></marker></defs>"
    ]
    ys: List[float] = []
    y = float(top)
    for i, (text, kind) in enumerate(steps):
        if i:
            d.append(arrow(y - gap, y - 4))
        wide = 170 if kind in ("llm", "plan", "solver", "gate") else 140
        d.append(box((W - wide) / 2, y, wide, bh, text, kind))
        ys.append(y)
        y += bh + gap
    y -= gap

    if loop is not None:
        idx, text = loop
        idx = max(1, min(idx, n - 1))
        bottom, top_y = ys[idx] + bh / 2, ys[idx - 1] + bh / 2
        d.append(
            f"<path d='M200,{bottom} C226,{bottom} 226,{top_y} 200,{top_y}' fill='none' "
            "stroke='#64748b' stroke-width='1.6' marker-end='url(#a)'/>"
        )
        d.append(
            f"<text x='{W - 8}' y='{(bottom + top_y) / 2 - 4}' text-anchor='end' font-size='10' "
            f"font-family='Inter,Helvetica,Arial' fill='#64748b'>{E(text)}</text>"
        )

    if branch is not None:
        left, right = branch
        d.append(arrow(y + bh, y + bh + 20))
        by = y + bh + 24
        d.append(box(12, by, 96, 26, left, "ok"))
        d.append(box(122, by, 96, 26, right, "esc"))
        y = by

    if footnote:
        d.append(
            f"<text x='4' y='{height - 6}' font-size='10' font-family='Inter,Helvetica,Arial' "
            f"fill='#64748b'>{E(footnote)}</text>"
        )
    d.append("</svg>")
    return "".join(d)


def diagram_card(title: str, subtitle: str, svg: str) -> str:
    """One labelled diagram, sized for a row of them."""
    return (
        f"<div class='dg'><h4>{E(title)}</h4><div class='muted'>{E(subtitle)}</div>{svg}</div>"
    )


def tab(key: str, body: str, *, on: bool = False) -> str:
    """Wrap one tab's content."""
    return f"<div class='tab{' on' if on else ''}' id='tab-{E(key)}'>{body}</div>"


# --------------------------------------------------------------------- page

_SCRIPT = """
function show(k){
  document.querySelectorAll('aside a.sub').forEach(a=>a.classList.toggle('on',a.dataset.t===k));
  document.querySelectorAll('.tab').forEach(t=>t.classList.toggle('on',t.id==='tab-'+k));
  var m=document.querySelector('main'); if(m) m.scrollTop=0;
  document.getElementById('side').classList.remove('open');
}
document.querySelectorAll('aside a.sub').forEach(a=>a.onclick=e=>{
  e.preventDefault();show(a.dataset.t);history.replaceState(null,'','#'+a.dataset.t);});
function fromHash(){var k=(location.hash||'').slice(1);
  if(k&&document.getElementById('tab-'+k)){show(k);}else{show(FIRST);}}
window.addEventListener('hashchange',fromHash);
var b=document.getElementById('burger');
if(b) b.onclick=()=>document.getElementById('side').classList.toggle('open');
fromHash();
"""


def page(
    *,
    title: str,
    brand: str,
    note_text: str = "",
    nav: Sequence[Dict[str, Any]],
    tabs_html: str,
    extra_css: str = "",
) -> str:
    """Assemble a complete page.

    The sidebar lists every case study, always, so how many there are and what
    each one is are visible without opening anything. The one being read is
    expanded into its sections; the others are one click away. The top bar does
    not change between them.

    Args:
        title: Browser title.
        brand: Name in the top bar.
        note_text: Small right-aligned text in the top bar.
        nav: One entry per case study, in order, each a dict with ``title``,
            ``subtitle``, ``href``, ``current`` (bool), ``available`` (bool)
            and ``entries`` as [(tab key, tab label), ...]. Entries are
            rendered only for the current one.
        tabs_html: The concatenated output of ``tab()`` for the current entry.
        extra_css: Page-specific rules appended to the shared stylesheet.

    Returns:
        The full HTML document.
    """
    first = ""
    side: List[str] = []
    for n, case in enumerate(nav, start=1):
        current = bool(case.get("current"))
        available = bool(case.get("available", True))
        cls = "cs" + (" on" if current else "") + ("" if available else " off")
        head = (
            f"<span class='n'>{n}</span>"
            f"<span class='t'>{E(case['title'])}"
            f"<small>{E(case.get('subtitle', '') if available else 'not yet')}</small></span>"
        )
        if available and not current:
            side.append(f"<a class='{cls}' href='{E(case['href'])}'>{head}</a>")
        else:
            side.append(f"<div class='{cls}'>{head}</div>")
        if current:
            for key, text in case.get("entries", ()):
                first = first or key
                side.append(f"<a class='sub' data-t='{E(key)}' href='#{E(key)}'>{E(text)}</a>")

    return (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>{E(title)}</title>"
        "<link href='https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700"
        "&family=JetBrains+Mono:wght@400;500&display=swap' rel='stylesheet'>"
        f"<style>{CSS}{extra_css}</style></head><body>"
        f"<div class='top'><button class='burger' id='burger'>☰</button>"
        f"<span class='brand'>{E(brand)}</span>"
        f"<span class='sp'></span><span class='note'>{E(note_text)}</span></div>"
        f"<div class='wrap'><aside id='side'>{''.join(side)}</aside>"
        f"<main><div class='inner'>{tabs_html}</div></main></div>"
        f"<script>var FIRST=\"{E(first)}\";{_SCRIPT}</script></body></html>"
    )
