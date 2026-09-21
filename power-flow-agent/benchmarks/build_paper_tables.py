#!/usr/bin/env python3
r"""Regenerate every .tex table the paper cites, from named source directories, in one run.

Written 2026-09-18 because the composite two/three-model tables had been produced by hand
invocations of fill_table.py / fill_supertable.py whose exact source-directory list existed only
in a chat transcript. That is the reconstruction risk this file exists to remove permanently: the
question "which directories feed which table" is now answered by reading SOURCES below, not by
asking whoever ran it last, and the supplementary material's reproducibility promise ("each
sub-folder ships what is needed to reproduce the results") now has an actual script behind it.

Run from power-flow-agent/ with no arguments:

    .venv/bin/python benchmarks/build_paper_tables.py

Regenerates, deterministically, from the source directories declared in SOURCES:
  - benchmarks/tab_pf_protocol_rows_gpt-5.4-and-4o-mini_validation.tex  (+ .csv)
  - benchmarks/tab_pf_protocol_per_system_gpt-5.4-and-4o-mini_validation.tex
  - benchmarks/tab_pf_protocol_stress_gpt-5.4-and-4o-mini_validation.tex  (+ .csv)
  - REPORT.md for every directory named in SOURCES (via experiment_report.py, no --pdf by
    default -- pass --pdf to also render PDFs, which is slow)

Does NOT touch: per-case/per-strategy tables generated straight from a single directory
(tab_pf_protocol_rows_case*.tex, tab_pf_by_system.tex, tab_pf_protocol_per_system.tex) -- those
already have a single, unambiguous `.venv/bin/python benchmarks/fill_table.py <dir> ...` /
`fill_supertable.py <dir> ...` invocation with no composite/retagging step, documented in each
script's own --help, and are out of scope for the reconstruction problem this file solves.

rule_based has no LLM and therefore no "model" of its own (every row's ``model`` field is the
literal string "none:rule_based"), but the composite tables key blocks by model. Reusing the same
rule_based report verbatim across a GPT-5.4 block and a gpt-4o-mini block would be fine only if
both blocks have the same N and request set; when they don't (or to be robust if that ever
changes), each block needs its OWN retagged copy -- a scratch report.json with every row's
"model" field rewritten to that block's model string -- so it is picked up like any other row by
fill_supertable.py's --block-by model (see that script's per_system_values docstring). _retag()
does this into a temp directory that is cleaned up after the run.
"""

from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
VENV_PY = str(PROJECT_ROOT / ".venv" / "bin" / "python")

# --------------------------------------------------------------------------- sources
#
# Every directory below has been checked, this session, for one of two things: either it
# postdates every fix that matters for the row it feeds (the per-unit LLM-only representation
# fix and the verification-gate mutation-block fix), or it predates both and was independently
# confirmed unaffected by them (rule_based has no LLM; react_nogate/plan_act_nogate have no
# final_gate, so the verification rework does not touch them, and they call tools, so the
# no-tools representation fix does not apply either).

GPT54_BASE = "results_validation_n40/gpt-5.4"
SOL_BASE = "results_validation_sol_n40_clean"
SOURCES: dict[str, dict[str, str]] = {
    "openrouter:openai/gpt-5.4": {
        "rule_based": f"{GPT54_BASE}/rule_based",
        "llm_only:structured": f"{GPT54_BASE}/llm_only_structured",
        "llm_only:cot": f"{GPT54_BASE}/llm_only_cot",
        # "LLM only, forced" row of the ladder (main.tex): same structured prompt, minus the
        # abstention clause. No tools, so unaffected by either fix, like the row above it.
        "llm_only_forced:structured": f"{GPT54_BASE}/llm_only_forced_structured",
        "react_nogate": f"{GPT54_BASE}/react_nogate",
        "plan_act_nogate": f"{GPT54_BASE}/plan_act_nogate",
        "pfagent": f"{GPT54_BASE}/pfagent",
        "single_call:structured": f"{GPT54_BASE}/single_call_structured",
    },
    "openrouter:openai/gpt-4o-mini": {
        # Safe from the pre-fix matrix: no LLM (rule_based) or no final_gate and tool-using, so
        # neither the per-unit representation fix nor the verification rework applies.
        "rule_based": "results_matrix_gpt-4o-mini/rule_based/case14",
        "react_nogate": "results_matrix_gpt-4o-mini/react_nogate/case14",
        "plan_act_nogate": "results_matrix_gpt-4o-mini/plan_act_nogate/case14",
        "single_call:structured": "results_matrix_gpt-4o-mini/single_call_structured/case14",
        # Per-unit representation rerun (2026-09-16), postdates the matrix.
        "llm_only:structured": "results_validation_nr/gpt-4o-mini/llm_only_structured",
        "llm_only:cot": "results_validation_nr/gpt-4o-mini/llm_only_cot",
        "llm_only_forced:structured": "results_validation_nr/gpt-4o-mini/llm_only_forced_structured",
        # Post-verification-rework (mutation-blocked retry), NOT the matrix and NOT the
        # "_v1" pre-fix snapshot kept only for reference.
        "pfagent": "results_validation_gpt-4o-mini_agents",
    },
    # gpt-5.6-sol, launched 2026-09-21: one clean N=40 case14 ladder, all 7 methods under
    # one prompt hash (none of the pre-fix/split-ladder history the other two blocks carry
    # caveats about). Landing over several hours; _resolve_sources/_retag skip a method
    # whose report.json does not exist yet rather than crashing, so rebuilding while only
    # some of the 7 have finished renders the rest as missing/dashes, not an error.
    "openrouter:openai/gpt-5.6-sol": {
        "rule_based": f"{SOL_BASE}/rule_based/case14",
        "llm_only:structured": f"{SOL_BASE}/llm_only_structured/case14",
        "llm_only:cot": f"{SOL_BASE}/llm_only_cot/case14",
        "react_nogate": f"{SOL_BASE}/react_nogate/case14",
        "plan_act_nogate": f"{SOL_BASE}/plan_act_nogate/case14",
        "pfagent": f"{SOL_BASE}/pfagent/case14",
        "single_call:structured": f"{SOL_BASE}/single_call_structured/case14",
    },
}

# Stress-condition sources (expected_outcome != converged; the 16-item islanded/non-converged
# set). Only the methods the stress table actually shows need to be here.
STRESS_SOURCES: dict[str, dict[str, str]] = {
    "openrouter:openai/gpt-5.4": {
        "rule_based": "results_validation_gpt-5.4_stress_rule_based",
        "react_nogate": "results_validation_gpt-5.4_stress",
        "pfagent": "results_validation_gpt-5.4_stress",
    },
    "openrouter:openai/gpt-4o-mini": {
        "rule_based": "results_stress_gpt-4o-mini/case14",
        "react_nogate": "results_validation_gpt-4o-mini_stress",
        "pfagent": "results_validation_gpt-4o-mini_stress",
    },
}

OUT_ROWS = PROJECT_ROOT / "benchmarks" / "tab_pf_protocol_rows_gpt-5.4-and-4o-mini_validation.tex"
OUT_PER_SYSTEM = PROJECT_ROOT / "benchmarks" / "tab_pf_protocol_per_system_gpt-5.4-and-4o-mini_validation.tex"
OUT_STRESS = PROJECT_ROOT / "benchmarks" / "tab_pf_protocol_stress_gpt-5.4-and-4o-mini_validation.tex"


def _retag(scratch: Path, model: str, method: str, src_dir: Path) -> Optional[Path]:
    """Copy src_dir's rescored (preferred) or plain report.json into its own scratch
    sub-directory, keeping only `method`'s own rows (a source file can hold other methods
    too -- e.g. a stress-set report with react_nogate/pfagent rows alongside rule_based's;
    copying the whole file would duplicate those against their own real source) with every
    row's "model" field rewritten to `model`. Returns that directory, or None if src_dir
    has no report yet (a ladder still in flight, e.g. sol's methods landing one at a time)
    -- the caller skips it rather than crashing, and the method reads as missing/dashes,
    same as any other absent source."""
    src = src_dir / "report.rescored.json"
    if not src.is_file():
        src = src_dir / "report.json"
    if not src.is_file():
        print(f"note: no report.json under {src_dir} yet; {model}/{method} will read as missing", file=sys.stderr)
        return None
    data: dict[str, Any] = json.loads(src.read_text(encoding="utf-8"))
    data = copy.deepcopy(data)

    def _keep(row: dict[str, Any]) -> bool:
        return str(row.get("method") or row.get("task")) == method

    for key in ("runs", "scoreboard", "scoreboard_per_case"):
        rows = [r for r in (data.get(key) or []) if _keep(r)]
        for row in rows:
            row["model"] = model
        data[key] = rows
    dest_dir = scratch / model.replace(":", "_").replace("/", "_") / method.replace(":", "_")
    dest_dir.mkdir(parents=True, exist_ok=True)
    (dest_dir / "report.json").write_text(json.dumps(data), encoding="utf-8")
    return dest_dir


def _resolve_sources(scratch: Path, sources: dict[str, dict[str, str]], base: Path) -> list[str]:
    """Real directories, deduplicated (react_nogate and pfagent often share one stress
    directory; passing the same path twice makes fill_table.py's loader see a genuine
    duplicate), except rule_based, which gets one retagged scratch copy per model block so
    fill_supertable.py's --block-by model can pick it up per block -- those are always
    distinct paths (one per model), so no dedup is needed or wanted there."""
    resolved: list[str] = []
    seen: set[str] = set()
    for model, methods in sources.items():
        for method, rel in methods.items():
            src_dir = base / rel
            if method == "rule_based":
                retagged = _retag(scratch, model, method, src_dir)
                if retagged is not None:
                    resolved.append(str(retagged))
                continue
            key = str(src_dir)
            if key in seen:
                continue
            if not (src_dir / "report.rescored.json").is_file() and not (src_dir / "report.json").is_file():
                print(f"note: no report.json under {src_dir} yet; {model}/{method} will read as missing", file=sys.stderr)
                continue
            seen.add(key)
            resolved.append(key)
    return resolved


def _run(cmd: list[str]) -> None:
    print("+", " ".join(cmd))
    subprocess.run(cmd, check=True, cwd=PROJECT_ROOT)


def build_composite_tables(scratch: Path) -> None:
    base = PROJECT_ROOT / "benchmarks"
    dirs = _resolve_sources(scratch, SOURCES, base)
    _run([
        VENV_PY, "benchmarks/fill_supertable.py", *dirs,
        "--block-by", "model", "--layout", "blocks", "--wrap", "rows",
        "--out", str(OUT_ROWS), "--csv", str(OUT_ROWS.with_suffix(".csv")),
    ])
    _run([
        VENV_PY, "benchmarks/fill_supertable.py", *dirs,
        "--block-by", "model", "--layout", "blocks", "--wrap", "tabular",
        "--out", str(OUT_PER_SYSTEM),
    ])

    stress_dirs = _resolve_sources(scratch, STRESS_SOURCES, base)
    _run([
        VENV_PY, "benchmarks/fill_supertable.py", *stress_dirs,
        "--block-by", "model", "--layout", "blocks", "--wrap", "rows",
        "--condition", "stress",
        "--out", str(OUT_STRESS), "--csv", str(OUT_STRESS.with_suffix(".csv")),
    ])


def regenerate_reports(with_pdf: bool) -> None:
    base = PROJECT_ROOT / "benchmarks"
    seen: set[Path] = set()
    for sources in (SOURCES, STRESS_SOURCES):
        for methods in sources.values():
            for rel in methods.values():
                d = base / rel
                if d in seen:
                    continue
                if not (d / "report.rescored.json").is_file() and not (d / "report.json").is_file():
                    continue
                seen.add(d)
                cmd = [VENV_PY, "benchmarks/experiment_report.py", str(d)]
                if with_pdf:
                    cmd.append("--pdf")
                _run(cmd)


def main(argv: list[str] | None = None) -> int:
    with_pdf = "--pdf" in (argv if argv is not None else sys.argv[1:])
    with tempfile.TemporaryDirectory(prefix="build_paper_tables_") as tmp:
        build_composite_tables(Path(tmp))
    regenerate_reports(with_pdf)
    print("done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
