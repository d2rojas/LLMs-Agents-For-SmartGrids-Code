// The results page computes every cell in JavaScript from summary.csv; postprocess.py computes
// the same quantities in Python and writes them to summary.json and REPORT.md. Two renderers over
// one dataset can disagree, and in the power-flow case study they did: the page filtered run
// errors on a string the CSV never wrote, so failed requests stayed in the denominator and the
// page reported 85 % escalated where the report said 100 %.
//
// This script recomputes the table the way results.html does, for every run in the index, and
// compares it against the aggregate each run recorded. Run it after changing either side:
//
//     node tests/crosscheck_page.mjs            # from griddebug-agent/, needs node, spends nothing
//
// It exits non-zero and names every disagreement. A mismatch means one of the two is stale or the
// two definitions have drifted apart; re-render with `run.py postprocess <dir>` before assuming
// the page is wrong.
import fs from 'fs';

const ROOT = 'results';
const idx = JSON.parse(fs.readFileSync(`${ROOT}/INDEX.json`, 'utf8'));
const page = fs.readFileSync('evaluation/visuals/results.html', 'utf8');

function parseCSV(t) {
  const out = []; let row = [], f = '', q = false;
  for (let i = 0; i < t.length; i++) {
    const c = t[i];
    if (q) { if (c == '"') { if (t[i+1] == '"') { f += '"'; i++; } else q = false; } else f += c; }
    else if (c == '"') q = true;
    else if (c == ',') { row.push(f); f = ''; }
    else if (c == '\n') { row.push(f); out.push(row); row = []; f = ''; }
    else if (c != '\r') f += c;
  }
  if (f || row.length) { row.push(f); out.push(row); }
  const h = out.shift();
  return out.filter(r => r.length > 1).map(r => Object.fromEntries(h.map((k, i) => [k, r[i]])));
}
const num = v => { const x = parseFloat(v); return isNaN(x) ? null : x; };
const T = v => v === 'True';
const mean = a => a.length ? a.reduce((s, x) => s + x, 0) / a.length : null;
const outcome = x => x.outcome || 'run_error';

// the page's vocabulary has to be the CSV's vocabulary: a string the CSV never writes silently
// drops rows from a rate instead of failing
const VOCAB = ['solved', 'escalated', 'wrong_unflagged', 'run_error'];
const seen = new Set();

let checked = 0; const bad = [];
for (const r of idx.runs.filter(r => r.kind === 'run')) {
  const all = parseCSV(fs.readFileSync(`${ROOT}/${r.path}/summary.csv`, 'utf8'));
  all.forEach(x => seen.add(outcome(x)));
  const rows = all.filter(x => outcome(x) !== 'run_error');
  const n = rows.length || 1;
  const pct = k => 100 * rows.filter(x => outcome(x) === k).length / n;
  const rate = k => 100 * rows.filter(x => T(x[k])).length / n;
  const both = rows.filter(x => num(x.initial_n_new) != null && num(x.final_n_new) != null);
  const ls = rows.map(x => num(x.load_served_pct)).filter(v => v != null).map(v => Math.min(v, 100));
  const mine = {
    common_n: rows.length,
    common_solved_rate: +pct('solved').toFixed(1),
    common_escalated_rate: +pct('escalated').toFixed(1),
    common_wrong_rate: +pct('wrong_unflagged').toFixed(1),
    common_repaired_rate: +rate('repaired').toFixed(1),
    common_improved_rate: +rate('improved').toFixed(1),
    common_feasible_rate: +rate('feasible').toFixed(1),
    common_traceable_rate: +rate('traceable').toFixed(1),
    common_formulation_rate: +rate('formulation_exact').toFixed(1),
    violations_initial_new: both.reduce((s, x) => s + num(x.initial_n_new), 0),
    violations_final_new: both.reduce((s, x) => s + num(x.final_n_new), 0),
    load_served_pct_mean: ls.length ? +mean(ls).toFixed(2) : null,
    load_served_pct_min: ls.length ? Math.min(...ls) : null,
    cost_usd_total: +rows.reduce((s, x) => s + (num(x.cost_usd) || 0), 0).toFixed(4),
    wall_time_mean_s: +mean(rows.map(x => num(x.wall_time_s) || 0)).toFixed(1),
  };
  const agg = JSON.parse(fs.readFileSync(`${ROOT}/${r.path}/summary.json`, 'utf8')).aggregate;
  for (const [k, a] of Object.entries(mine)) {
    const b = agg[k];
    if (a == null || b == null) continue;
    checked++;
    if (Math.abs(a - b) > 0.051) bad.push(`${r.path} | ${k}: page ${a} vs report ${b}`);
  }
}

for (const o of seen) if (!VOCAB.includes(o)) bad.push(`summary.csv writes outcome "${o}", which the page never tests for`);
for (const o of VOCAB) if (!page.includes(`'${o}'`)) bad.push(`the page no longer tests for outcome "${o}"`);

console.log(`${idx.runs.filter(r => r.kind === 'run').length} runs, ${checked} numbers cross-checked, ${bad.length} disagreements`);
bad.forEach(b => console.log('  ' + b));
process.exit(bad.length ? 1 : 0);
