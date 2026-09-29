// Check a case study's page against the rows it was built from, and against the
// aggregate Python stored beside them (2026-09-28).
//
// Three things compute the same quantities over one dataset: the page, the
// aggregate in each run's summary.json, and the report written from it. Two of
// them disagreeing is invisible, because each looks right on its own. It has
// already happened here: a value renamed on one side was still read by the old
// name on the other, so a run reported no API failures where there were three and
// averaged its tokens over twenty requests where the page used the seventeen that
// were answered. The power-flow case study found five real disagreements that way
// and GridDebug sixteen, which is why this is part of the standard rather than
// something each case study bolts on afterwards.
//
// What it checks, for every run a case study's table names:
//
//   1. one outcome vocabulary on both sides, so "wrong" and "wrong_unflagged"
//      cannot quietly be two different columns;
//   2. every count the page rendered, against a recount of that run's
//      summary.csv. `shell.counted` writes each figure's numerator and
//      denominator into the markup as data, so what the page shows can be read
//      back rather than inferred;
//   3. the same recount against the aggregate in summary.json, under the key
//      names that case study uses.
//
// Needs node, spends nothing, reads only files already on disk.
//
//   node visuals/crosscheck.mjs <case-folder> <site/case.html> [spec.json]
//
// The spec names the case study's aggregate keys; without one, only 1 and 2 run.
import { readFileSync, existsSync, statSync, readdirSync } from "node:fs";
import { join } from "node:path";

// Exit 3, distinct from a disagreement: the page is older than the runs it would
// be compared against, so there is nothing to conclude from comparing them.
const STALE = 3;

const [folder, pagePath, specPath] = process.argv.slice(2);
if (!folder || !pagePath) {
  console.error("usage: node visuals/crosscheck.mjs <case-folder> <page.html> [spec.json]");
  process.exit(2);
}

// The three outcomes are exhaustive and exclusive in every case study, plus the
// one that is not an outcome of the method at all: a request that never ran.
const VOCAB = new Set(["solved", "escalated", "wrong_unflagged", "run_error"]);
const T = (v) => String(v ?? "").trim().toLowerCase() === "true" || String(v).trim() === "1";

export function parseCSV(text) {
  const rows = [];
  let row = [], field = "", quoted = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (quoted) {
      if (c === '"' && text[i + 1] === '"') { field += '"'; i++; }
      else if (c === '"') quoted = false;
      else field += c;
    } else if (c === '"') quoted = true;
    else if (c === ",") { row.push(field); field = ""; }
    else if (c === "\n") { row.push(field); rows.push(row); row = []; field = ""; }
    else if (c !== "\r") field += c;
  }
  if (field || row.length) { row.push(field); rows.push(row); }
  const head = rows.shift() || [];
  return rows.filter((r) => r.length > 1).map((r) => Object.fromEntries(head.map((h, i) => [h, r[i]])));
}

// The same three-way rule every case study scores by, so the check does not
// invent a fourth definition of the thing it is checking. A blank outcome beside
// a non-empty error column is a run that never happened, not a wrong answer:
// falling straight through to wrong_unflagged would take the worst of the four
// readings available, and silently. Asked for by the EV session, which had a row
// counted as wrong because its summary.csv did not yet write the label.
const outcome = (r) => {
  if (r.outcome) return r.outcome;
  if (String(r.error ?? "").trim()) return "run_error";
  return T(r.solved) ? "solved" : T(r.escalated) ? "escalated" : "wrong_unflagged";
};

/** Every `<tr data-run=...>` of the page, with the counts each of its cells rendered. */
export function pageRows(html) {
  const out = [];
  const tables = [...html.matchAll(/<table class='cmp'(?: data-cols='([^']*)')?>([\s\S]*?)<\/table>/g)];
  for (const [, colsAttr, body] of tables) {
    const unesc = (s) => s.replace(/&quot;/g, '"').replace(/&#x27;/g, "'")
      .replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&amp;/g, "&");
    const cols = colsAttr ? JSON.parse(unesc(colsAttr)) : [];
    for (const [, run, tr] of body.matchAll(/<tr data-run='([^']*)'>([\s\S]*?)<\/tr>/g)) {
      if (!run) continue;
      const cells = [...tr.matchAll(/<td class='num'>([\s\S]*?)<\/td>/g)].map(([, td]) => {
        const m = td.match(/data-k='(\d+)' data-n='(\d+)'/);
        return m ? { k: +m[1], n: +m[2] } : null;
      });
      out.push({ run, cols, cells });
    }
  }
  return out;
}

const bad = [];
const note = (where, what, page, py) => bad.push({ where, what, page, py });
let checked = 0;

const cmp = (where, what, page, py, tol = 0) => {
  checked++;
  if (page == null || py == null) return;
  if (Math.abs(page - py) > tol * Math.max(1, Math.abs(py))) note(where, what, page, py);
};

// A page older than the runs is worse than a missing one. `site/` is gitignored
// and lives in each worktree, so every checkout keeps its own copy of whatever
// age, and a checkout that simply did not rebuild regrows a stale one. Comparing
// it against today's rows fails confusingly at best; at worst it passes, because
// the runs it predates happened not to move the cells being checked. Found by
// the power-flow session, whose two-day-old page failed once and then passed.
function newestRun(dir) {
  let newest = 0;
  const walk = (d) => {
    for (const e of readdirSync(d, { withFileTypes: true })) {
      const p = join(d, e.name);
      if (e.isDirectory()) walk(p);
      else if (e.name === "summary.csv") newest = Math.max(newest, statSync(p).mtimeMs);
    }
  };
  if (existsSync(dir)) walk(dir);
  return newest;
}

const pageAt = statSync(pagePath).mtimeMs;
const runsAt = newestRun(join(folder, "results"));
if (runsAt && pageAt < runsAt) {
  const when = (t) => new Date(t).toISOString().slice(0, 16).replace("T", " ");
  console.log(`${pagePath} was written ${when(pageAt)}, and a run was scored ${when(runsAt)}.`);
  console.log("The page is older than the rows it would be checked against, so nothing can be");
  console.log(`concluded from comparing them. Rebuild it first: python -m visuals.build --require <case>`);
  process.exit(STALE);
}

const html = readFileSync(pagePath, "utf8");
const rowsOnPage = pageRows(html);
if (!rowsOnPage.length) {
  // Almost always a page built before comparison_table started tagging its rows,
  // which is the other way a page can be out of date: newer than the runs, older
  // than the code. Not a disagreement, so not a failure -- reporting it as one
  // sends whoever sees the red looking for a bug in a table that is fine, which
  // is what happened to the GridDebug session on its first run after merging.
  console.log(`${pagePath} has no table tagged with data-run, so there is nothing to check against.`);
  console.log("Either the page predates the tagging and needs rebuilding, or this case study's table");
  console.log("is not built with shell.comparison_table and is not covered by this check.");
  console.log("Rebuild first: python -m visuals.build --require <case>");
  process.exit(STALE);
}

const spec = specPath && existsSync(specPath) ? JSON.parse(readFileSync(specPath, "utf8")) : null;
const RESULTS = join(folder, "results");
const seen = new Set();

for (const { run, cols, cells } of rowsOnPage) {
  const dir = join(RESULTS, run);
  const csv = join(dir, "summary.csv");
  if (!existsSync(csv)) { note(run, "summary.csv missing for a row the page rendered", "", ""); continue; }
  const all = parseCSV(readFileSync(csv, "utf8"));

  for (const r of all) {
    const o = outcome(r);
    if (!VOCAB.has(o)) note(run, `unknown outcome "${o}"`, "", "");
  }
  const done = all.filter((r) => outcome(r) !== "run_error");
  const count = (k) => done.filter((r) => outcome(r) === k).length;

  // 2. what the page rendered, against a recount of the rows it was built from
  const byName = new Map();
  cols.forEach((label, i) => byName.set(String(label).toLowerCase(), cells[i]));
  for (const [needle, k] of [["solved", "solved"], ["escalated", "escalated"], ["wrong", "wrong_unflagged"]]) {
    // Anchored at the start of the label: "V_MAE (solved)" is an error averaged
    // over the solved requests, not the solved column, and matching it loosely
    // compared the wrong denominator against n on every power-flow row.
    const hit = [...byName.entries()].find(([label]) => new RegExp(`^${needle}\\b`).test(label));
    if (!hit || !hit[1]) continue;
    const { k: pk, n: pn } = hit[1];
    cmp(run, `page ${needle} count`, pk, count(k));
    cmp(run, `page ${needle} denominator`, pn, done.length);
  }
  for (const cell of cells) {
    if (!cell) continue;
    checked++;
    if (cell.k > cell.n) note(run, "a count larger than the denominator it is over", cell.k, cell.n);
    // A denominator above the number of rows is right where a case study scores
    // something smaller than a request -- EV scores formulation over the 894
    // charging sessions of its twenty days -- and wrong where it does not. The
    // case study says which it is, so the check stays meaningful for the others.
    if (cell.n > all.length && !(spec && spec.scores_subunits)) {
      note(run, "a denominator larger than the run, and this case study does not declare "
        + "scores_subunits", cell.n, all.length);
    }
  }

  // 3. the same recount against the aggregate stored beside the rows
  const sj = join(dir, "summary.json");
  if (!spec || !existsSync(sj)) continue;
  seen.add(run);
  const j = JSON.parse(readFileSync(sj, "utf8"));
  const agg = j.aggregate || j;
  const K = spec.aggregate || {};
  // `n` means the scored requests in three of the four case studies and meant the
  // attempted ones in the fourth, and the two only differ once a run fails, so the
  // difference sat untested. A case study that publishes both is checked on both
  // and on the identity between them; one that publishes only `n` says here which
  // it means, and the default is the scored count the three others use.
  const scoredKey = K.n_scored ?? (K.n_is_attempted ? null : (K.n ?? "n"));
  if (scoredKey) cmp(run, `aggregate ${scoredKey} (scored)`, done.length, agg[scoredKey]);
  if (K.n_scored && K.n) {
    cmp(run, `aggregate ${K.n} (attempted)`, all.length, agg[K.n]);
    cmp(run, `aggregate ${K.n} == ${K.n_scored} + run errors`,
        agg[K.n], (agg[K.n_scored] ?? 0) + (agg[K.run_errors] ?? 0));
  }
  if (K.solved) cmp(run, "aggregate solved", count("solved"), agg[K.solved]);
  if (K.escalated) cmp(run, "aggregate escalated", count("escalated"), agg[K.escalated]);
  if (K.wrong) cmp(run, "aggregate wrong_unflagged", count("wrong_unflagged"), agg[K.wrong]);
  if (K.run_errors) cmp(run, "aggregate run errors", all.length - done.length, agg[K.run_errors]);
  for (const [field, how] of Object.entries(spec.means || {})) {
    // A case study that stores a rounded mean says so here, and the recount is
    // rounded the same way before the comparison. Comparing a rounded number
    // under a blind tolerance would hide real drift smaller than the tolerance;
    // rounding both sides to the declared precision keeps the check exact.
    const key = typeof how === "string" ? how : how.key;
    const digits = typeof how === "string" ? null : how.round;
    const xs = done.map((r) => parseFloat(r[field])).filter((x) => Number.isFinite(x));
    let mean = xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : null;
    if (mean != null && digits != null) mean = Number(mean.toFixed(digits));
    cmp(run, `aggregate mean ${field}`, mean, agg[key], 1e-9);
  }
}

console.log(`${checked} numbers compared across ${rowsOnPage.length} table rows`
  + (spec ? `, ${seen.size} against a stored aggregate` : ", no aggregate spec given"));
if (!bad.length) {
  console.log("page, rows and aggregate agree; one outcome vocabulary on every side");
} else {
  console.log(`${bad.length} DISAGREEMENTS:`);
  for (const b of bad.slice(0, 40)) {
    console.log(`  ${b.where}  ${b.what}` + (b.page === "" ? "" : `  page=${b.page} python=${b.py}`));
  }
}
process.exit(bad.length ? 1 : 0);
