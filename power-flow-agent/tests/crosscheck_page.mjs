// Cross-check the results page against the Python aggregate (2026-09-28).
//
// results.html computes every cell in JavaScript from summary.csv; postprocess.py computes the same
// quantities in Python into summary.json. Two implementations of one metric can disagree, and they
// did: the page filtered run errors on "run_error" while summary.csv wrote "error", so three failed
// requests sat in the denominator and the page and REPORT.md reported different rates for the same
// run (fixed in a8f983ac). This asserts they agree, and that both sides share one outcome vocabulary.
//
// Needs node, spends nothing, not wired into pytest:  node tests/crosscheck_page.mjs
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";

const T = (v) => String(v ?? "").trim().toLowerCase() === "true" || String(v).trim() === "1";
const num = (v) => { const x = parseFloat(v); return Number.isFinite(x) ? x : null; };
const VOCAB = new Set(["solved", "escalated", "wrong_unflagged", "run_error"]);

function parseCSV(text) {                       // the same parser results.html uses
  const lines = text.trim().split(/\r?\n/);
  const head = lines[0].split(",");
  return lines.slice(1).map((line) => {
    const cells = []; let cur = "", q = false;
    for (const ch of line) {
      if (ch === '"') q = !q;
      else if (ch === "," && !q) { cells.push(cur); cur = ""; }
      else cur += ch;
    }
    cells.push(cur);
    return Object.fromEntries(head.map((h, i) => [h, cells[i]]));
  });
}

function walk(dir, out = []) {
  for (const e of readdirSync(dir)) {
    const p = join(dir, e);
    if (statSync(p).isDirectory()) walk(p, out);
    else if (e === "summary.json") out.push(dir);
  }
  return out;
}

const outcome = (x) => x.outcome || (T(x.solved) ? "solved" : T(x.escalated) ? "escalated" : "wrong_unflagged");
let checked = 0, bad = [];

for (const dir of walk("results").sort()) {
  const agg = JSON.parse(readFileSync(join(dir, "summary.json"), "utf8")).aggregate || {};
  const all = parseCSV(readFileSync(join(dir, "summary.csv"), "utf8"));

  for (const r of all) {                        // one vocabulary on both sides
    const o = outcome(r);
    if (!VOCAB.has(o)) bad.push([dir, "vocabulary", `unknown outcome "${o}"`, "", ""]);
  }

  const rows = all.filter((x) => outcome(x) !== "run_error");
  const cmp = (name, page, py, tol = 1e-9) => {
    checked++;
    if (py == null || page == null) return;
    if (Math.abs(page - py) > tol * Math.max(1, Math.abs(py))) bad.push([dir, name, "", page, py]);
  };

  cmp("n", rows.length, agg.n);
  cmp("solved", rows.filter((x) => outcome(x) === "solved").length, agg.solved_autonomously);
  cmp("escalated", rows.filter((x) => outcome(x) === "escalated").length, agg.escalated);
  cmp("wrong_unflagged", rows.filter((x) => outcome(x) === "wrong_unflagged").length, agg.wrong_unflagged);
  cmp("run_errors", all.length - rows.length, agg.run_errors);

  const fr = rows.filter((x) => x.formulation_exact !== "" && x.formulation_exact != null);
  cmp("formulation_total", fr.length, agg.formulation_total);
  cmp("formulation_exact", fr.filter((x) => T(x.formulation_exact)).length, agg.formulation_exact);

  const tr = rows.filter((x) => x.faithful_answers !== "" && x.faithful_answers != null);
  cmp("traceable_total", tr.length, agg.traceable_total);
  cmp("traceable_answers", tr.filter((x) => T(x.faithful_answers)).length, agg.traceable_answers);

  const mean = (xs) => (xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : null);
  cmp("voltage_mae_mean", mean(rows.map((x) => num(x.voltage_mae_pu)).filter((x) => x != null)), agg.voltage_mae_mean, 1e-6);
  cmp("kcl_mismatch_mean", mean(rows.map((x) => num(x.kcl_mismatch_mw)).filter((x) => x != null)), agg.kcl_mismatch_mean, 1e-6);
  cmp("wall_time_s_mean", mean(rows.map((x) => num(x.wall_time_s)).filter((x) => x != null)), agg.wall_time_s_mean, 1e-6);
  cmp("prompt_tokens_mean", mean(rows.map((x) => num(x.prompt_tokens)).filter((x) => x != null)), agg.prompt_tokens_mean, 1e-6);
  cmp("completion_tokens_mean", mean(rows.map((x) => num(x.completion_tokens)).filter((x) => x != null)), agg.completion_tokens_mean, 1e-6);
}

console.log(`${checked} numbers compared across ${walk("results").length} runs`);
if (!bad.length) console.log("all agree; page and report share one outcome vocabulary");
else {
  console.log(`${bad.length} DISAGREEMENTS:`);
  for (const [d, n, note, page, py] of bad.slice(0, 40)) console.log(`  ${d}  ${n}  ${note || `page=${page} python=${py}`}`);
}
process.exit(bad.length ? 1 : 0);
