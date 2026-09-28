#!/usr/bin/env python3
"""Build results/visuals/: the case study's own pages, in the format of the power-flow case study.

    index.html     the shell: Home, then Design / Results / Analysis in the sidebar, content in an iframe
    design.html    tabs Methods, Scenarios, Prompts, Tools, Gate & scoring, Run plan, generated from the code
    results.html, viewer.html, failures.html   static pages that read results/INDEX.json, summary.csv and traces/

The tab bodies are the same ones ``evaluation/page_fragments.py`` hands to the shared site, so
the two presentations cannot drift; only the chrome differs. The three results pages are
hand-written JavaScript kept next to this file under ``evaluation/visuals/`` and copied over.

    .venv/bin/python evaluation/design_page.py      (or: run.py pages)
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT.parent))

from visuals.shell import CSS, E  # noqa: E402

from evaluation import page_fragments as PF  # noqa: E402

OUT = PROJECT_ROOT / "results" / "visuals"
STATIC = PROJECT_ROOT / "evaluation" / "visuals"

TABS = [("methods", "Methods"), ("scenarios", "Scenarios"), ("prompts", "Prompts"), ("tools", "Tools"), ("gate", "Gate & scoring"), ("plan", "Run plan")]

DESIGN_CSS = """
header{position:sticky;top:0;z-index:5;background:var(--panel);border-bottom:1px solid var(--line);padding:10px 22px;display:flex;gap:16px;align-items:center;flex-wrap:wrap}
header h1{font-size:17px;margin:0;letter-spacing:-.01em}.tabs{display:flex;gap:4px}body.embed header{display:none}
.tabs button{font:inherit;font-weight:500;padding:7px 14px;border:1px solid transparent;border-radius:8px;background:transparent;cursor:pointer;color:var(--muted)}.tabs button.on{background:var(--acc);color:#fff}
body{display:block}main{padding:18px 22px;max-width:1500px;margin:0 auto;overflow:visible}
"""

DESIGN_JS = """
const tabs=document.querySelectorAll('.tabs button');function show(k){tabs.forEach(b=>b.classList.toggle('on',b.dataset.tab===k));document.querySelectorAll('.tab').forEach(t=>t.classList.toggle('on',t.id==='tab-'+k));window.scrollTo(0,0);}
tabs.forEach(b=>b.onclick=()=>{show(b.dataset.tab);history.replaceState(null,'','#'+b.dataset.tab);});
function fromHash(){const k=(location.hash||'#methods').slice(1);if(document.getElementById('tab-'+k)){show(k);}}
window.addEventListener('hashchange',fromHash);
if(window.self!==window.top){document.body.classList.add('embed');}
const _show=show;show=function(k){_show(k);if(window.self!==window.top){window.parent.postMessage({page:'design',tab:k},'*');}};
fromHash();
"""


def design_html() -> str:
    parts = [f"<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
             f"<title>GridDebugAgent · Evaluation design</title><style>{CSS}{DESIGN_CSS}</style></head><body>",
             "<header><h1>GridDebugAgent · Evaluation design</h1><nav class='tabs'>"
             + "".join(f"<button data-tab='{k}' class='{'on' if k == 'methods' else ''}'>{v}</button>" for k, v in TABS) + "</nav></header><main>"]
    for k, _ in TABS:
        parts.append(f"<div class='tab{' on' if k == 'methods' else ''}' id='tab-{k}'>{PF.BUILDERS[k]()}</div>")
    parts.append(f"</main><script>{DESIGN_JS}{PF.SCRIPT}</script></body></html>")
    return "".join(parts)


INDEX_CSS = """
:root{--bg:#f3f5f8;--panel:#fff;--line:#e3e7ee;--text:#0f172a;--muted:#64748b;--acc:#2f5fd0;--side:#0f1b2d;--side2:#16243a;--sidetext:#c7d0dd}
*{box-sizing:border-box}html,body{height:100%}body{margin:0;font:14px/1.5 Inter,-apple-system,Segoe UI,Helvetica,Arial,sans-serif;color:var(--text);background:var(--bg);display:flex;flex-direction:column}
.top{height:48px;background:var(--side);color:#fff;display:flex;align-items:center;gap:14px;padding:0 16px;flex:none;border-bottom:1px solid #22314a}
.top .brand{font-weight:700;letter-spacing:.2px}.top .crumb{color:var(--sidetext);font-size:13px}.top .crumb b{color:#fff;font-weight:600}.top .sp{flex:1}.top .note{font-size:12px;color:var(--sidetext)}
.top .burger{display:none;background:none;border:0;color:#fff;font-size:20px;cursor:pointer}
.wrap{flex:1;display:flex;min-height:0}
aside{width:248px;flex:none;background:var(--side2);color:var(--sidetext);overflow:auto;padding:14px 0;border-right:1px solid #22314a}
aside .grp{padding:10px 18px 6px;font-size:11px;letter-spacing:.9px;text-transform:uppercase;color:#8290a5;display:flex;align-items:center;gap:8px}
aside .grp .n{width:20px;height:20px;border-radius:50%;background:#2a3b57;color:#fff;font-size:11px;display:inline-flex;align-items:center;justify-content:center;font-weight:700}
aside a{display:block;padding:8px 18px 8px 46px;color:var(--sidetext);text-decoration:none;font-size:13.5px;border-left:3px solid transparent}
aside a:hover{background:#1e2f49;color:#fff}aside a.on{background:#243a5c;color:#fff;border-left-color:#7aa2ff;font-weight:600}
aside .off{display:block;padding:8px 18px 8px 46px;font-size:13px;color:#6f7d93}aside .off small{display:block;font-size:11.5px}
aside hr{border:0;border-top:1px solid #22314a;margin:10px 18px}
main{flex:1;min-width:0;display:flex;overflow:auto}iframe{border:0;width:100%;height:100%;background:var(--bg)}
#home{display:none;padding:34px 40px;max-width:1100px;width:100%}#home.on{display:block}#home[hidden]{display:none}
#home h1{margin:0 0 6px;font-size:24px}#home .lead{color:var(--muted);margin:0 0 26px;font-size:15px;max-width:760px}
.prob{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:20px 22px;margin:0 0 22px;box-shadow:0 1px 2px rgba(15,23,42,.06),0 4px 14px rgba(15,23,42,.05)}
.prob h2{margin:0 0 10px;font-size:17px}.prob p{margin:0 0 10px;font-size:14px;max-width:860px}.prob .g{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;margin-top:14px}@media(max-width:800px){.prob .g{grid-template-columns:1fr}#home{padding:20px 16px}}
.prob .b{background:#f8fafc;border:1px solid var(--line);border-radius:10px;padding:12px 14px}.prob .b h4{margin:0 0 6px;font-size:13px}.prob .b p,.prob .b li{font-size:13px;color:#334155;margin:0}.prob .b ul{margin:0;padding-left:18px}
.req{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12.5px;background:#0f1b2d;color:#e2e8f0;border-radius:8px;padding:10px 12px;margin:8px 0 4px}
.tag{display:inline-block;padding:1px 8px;border-radius:999px;font-size:11.5px;font-weight:600;margin-right:4px}.tag.ok{background:#e6f4ea;color:#166534}.tag.esc{background:#fdf0e3;color:#9a5b0a}.tag.bad{background:#fdecec;color:#991b1b}
@media(max-width:800px){aside{position:fixed;top:48px;bottom:0;left:0;transform:translateX(-100%);transition:transform .2s;z-index:10}aside.open{transform:none}.top .burger{display:block}.top .note{display:none}}
"""

INDEX_JS = """
const ROUTES={'design':{src:'design.html',label:'Design',note:''},
 'results/table':{src:'results.html',note:'Numbers and traces exactly as the runs produced them.'},
 'results/traces':{src:'viewer.html',note:'Any run, any scenario, the real trace.'},
 'results/failures':{src:'failures.html',note:'Every non-solved scenario, step by step, with its prompts, gate attempts and verdict.'}};
const frame=document.getElementById('frame'),crumb=document.getElementById('crumb'),note=document.getElementById('note'),side=document.getElementById('side');
let cur='';const home=document.getElementById('home');
function go(){const r=(location.hash||'#home').slice(1);const [sec,sub]=r.split('/');
 if(sec==='home'){home.classList.add('on');frame.hidden=true;document.querySelectorAll('aside a').forEach(a=>a.classList.toggle('on',a.dataset.r==='home'));crumb.innerHTML='';note.textContent='';side.classList.remove('open');return;}
 home.classList.remove('on');frame.hidden=false;
 const route=sec==='design'?ROUTES.design:(ROUTES[r]||ROUTES.design);
 if(cur!==route.src){frame.src=sec==='design'?'design.html#'+(sub||'methods'):route.src;cur=route.src;}
 else if(sec==='design'){try{frame.contentWindow.location.hash=sub||'methods';}catch(e){}}
 const key=sec==='design'?'design/'+(sub||'methods'):r;
 document.querySelectorAll('aside a').forEach(a=>a.classList.toggle('on',a.dataset.r===key));
 const item=document.querySelector('aside a.on');crumb.innerHTML=(sec==='design'?'1 · Design':'2 · Results')+' <b>› '+(item?item.textContent:'')+'</b>';note.textContent=route.note;side.classList.remove('open');}
window.addEventListener('hashchange',go);go();
window.addEventListener('message',e=>{if(e.data&&e.data.page==='design'&&e.data.tab){const h='#design/'+e.data.tab;if(location.hash!==h){history.replaceState(null,'',h);go();}}});
document.getElementById('burger').onclick=()=>side.classList.toggle('open');
"""


def index_html() -> str:
    req = PF.sample_request()
    m = PF.manifest()
    n = len(m["entries"]) if m else 0
    return (
        f"<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>GridDebugAgent · Evaluation</title><style>{INDEX_CSS}</style></head><body>"
        "<div class='top'><button class='burger' id='burger'>☰</button><span class='brand'>GridDebugAgent · Evaluation</span><span class='crumb' id='crumb'></span><span class='sp'></span><span class='note' id='note'></span></div>"
        "<div class='wrap'><aside id='side'>"
        "<a href='#home' data-r='home' style='padding-left:18px;font-weight:600'>Home</a><hr>"
        "<div class='grp'><span class='n'>1</span>Design</div>"
        "<a href='#design/methods' data-r='design/methods'>Methods</a><a href='#design/scenarios' data-r='design/scenarios'>Scenarios</a>"
        "<a href='#design/prompts' data-r='design/prompts'>Prompts</a><a href='#design/tools' data-r='design/tools'>Tools</a>"
        "<a href='#design/gate' data-r='design/gate'>Gate &amp; scoring</a><a href='#design/plan' data-r='design/plan'>Run plan &amp; cost</a><hr>"
        "<div class='grp'><span class='n'>2</span>Results</div>"
        "<a href='#results/table' data-r='results/table'>Table &amp; scenarios</a><a href='#results/traces' data-r='results/traces'>Trace viewer</a>"
        
        "<a href='#results/failures' data-r='results/failures'>Failure report</a><hr>"
        "<div class='grp'><span class='n'>3</span>Analysis</div><span class='off'>Comparisons &amp; conclusions<small>written after the results exist</small></span>"
        "</aside><main><section id='home'>"
        "<h1>GridDebugAgent · IEEE 14, 30 and 57-bus contingency diagnosis and repair</h1>"
        "<p class='lead'>Can a language model diagnose a faulted network and repair it with control-room actions, without ever claiming a repair the "
        "power flow contradicts? We compare five ways of using an LLM on the same faults, from prompting alone to the solver-grounded agent with a "
        "verification gate, against a rule engine with no LLM, on three IEEE systems, with the same scoring.</p>"
        "<div class='prob'><h2>The problem</h2><p>A power flow on an IEEE test network has failed or produced limit violations: a line is out, loads have "
        "grown, a generator is gone, a setpoint is wrong. Somebody has to say what happened and bring the network back to a secure operating point with "
        "the actions a control room has: redispatch, curtailment, switching, compensation, setpoints. Today that somebody is an engineer with a simulator.</p>"
        "<p><b>The research question of this case study:</b> when a language model takes that seat, which way of using it names the initiating fault, "
        "reaches a secure network the solver confirms, turns its own failures into escalations instead of repair claims, and at what cost in tool calls and "
        "tokens as the network grows from 14 to 57 buses?</p>"
        f"<div class='req'>{E(req.text)}</div>"
        f"<p style='font-size:12.5px;color:var(--muted)'>The request of the IEEE-14 line contingency, one of the {n} scenario instances: thirteen fault "
        "injections on each network, every one frozen with a content hash, every method receiving the same evidence block and the same action catalogue.</p>"
        "<div class='g'>"
        "<div class='b'><h4>What a correct answer needs</h4><ul><li><b>The diagnosis:</b> the fault type and the components that were changed, not the buses that show the symptom.</li>"
        "<li><b>A secure network:</b> converged, no islanded load, no violation beyond the base network, verified by the harness's own power flow.</li>"
        "<li><b>An honest report:</b> status and final state that agree with the solver, numbers that come from a tool output.</li></ul></div>"
        "<div class='b'><h4>What can go wrong</h4><ul><li>A repair claimed after actions that were never verified: <b>wrong, presented as right</b>.</li>"
        "<li>A number quoted from before the last action.</li><li>Shunts and switches piled on until the budget runs out.</li><li>A load left on an island with a NaN voltage nobody reads.</li></ul></div>"
        "<div class='b'><h4>What we expect from GridDebugAgent</h4><p>Every answer passes six verification conditions or leaves as an escalation with what remains listed. "
        "The target for the solver-grounded row: <span class='tag ok'>solved</span> + <span class='tag esc'>escalated</span> = 100%, <span class='tag bad'>wrong, unflagged</span> = 0%.</p></div>"
        "</div></div></section><iframe id='frame' title='content' hidden></iframe></main></div>"
        f"<script>{INDEX_JS}</script></body></html>"
    )


def build() -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "design.html").write_text(design_html(), encoding="utf-8")
    (OUT / "index.html").write_text(index_html(), encoding="utf-8")
    for name in ("results.html", "viewer.html", "failures.html"):
        shutil.copyfile(STATIC / name, OUT / name)
    return OUT


if __name__ == "__main__":
    p = build()
    for f in sorted(p.glob("*.html")):
        print(f"wrote {f.relative_to(PROJECT_ROOT)} ({f.stat().st_size // 1024} KB)")
