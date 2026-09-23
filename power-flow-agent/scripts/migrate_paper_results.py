#!/usr/bin/env python3
"""Copy the runs behind the paper tables into the results/ tree and render them.

Source of truth for *which* runs: ``benchmarks/build_paper_tables.py`` (SOURCES for the main
table, STRESS_SOURCES for the stress table, SPLIT_TOOL_SOURCES for the before/after appendix).
Those directories live under ``benchmarks/results_*`` of a checkout that still holds the
gitignored ``report.json`` and ``traces/`` (the working tree the runs were made in), so pass
``--source-root`` when this checkout is a fresh worktree.

Destination: ``results/<case alias>/<run date>/<model>/<method>[__stress][__<tool variant>]/``
with ``raw/`` (report.json, report.rescored.json, this method's traces, logs, the runner's
REPORT.md and scoreboards), ``config.json`` (provenance), and the rendered files from
``benchmarks/postprocess.py``. The run date is the write time of the source report.json,
which was never checked out from git, so it is the real run time.

Usage::

    .venv/bin/python scripts/migrate_paper_results.py --dry-run
    .venv/bin/python scripts/migrate_paper_results.py --source-root ../LLMs-Agents-For-SmartGrids-Code-v2/power-flow-agent/benchmarks
    .venv/bin/python scripts/migrate_paper_results.py --only gpt-5.6-sol/pfagent
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import methods  # noqa: E402
from benchmarks import build_paper_tables as bpt  # noqa: E402
from benchmarks.postprocess import CASE_ALIASES, load_report, postprocess  # noqa: E402

RESULTS = PROJECT_ROOT / "results"
CASE_FOLDER = {"case14": "ieee14", "case30": "ieee30", "case57": "ieee57", "case118": "ieee118", "case300": "ieee300"}


def model_slug(model: str) -> str:
    if model.startswith("none:"):
        return "no-llm"
    return model.split("/")[-1].split(":")[-1]


def method_slug(runner_name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", runner_name)


def run_date(src: Path) -> str:
    for name in ("report.json", "report.rescored.json"):
        p = src / name
        if p.is_file():
            return _dt.datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d")
    raise FileNotFoundError(src)


def source_commit(src: Path) -> Optional[str]:
    """Commit that last touched the tracked REPORT.md next to the source report (provenance)."""
    for name in ("REPORT.md", "scoreboard.rescored.md", "scoreboard.md"):
        p = src / name
        if p.is_file():
            try:
                out = subprocess.run(["git", "log", "-1", "--format=%h %cs %s", "--", str(p)], cwd=src, capture_output=True, text=True, check=True).stdout.strip()
                if out:
                    return out
            except Exception:
                return None
    return None


def plan() -> List[Dict[str, Any]]:
    """Every distinct (model, method, source dir) the paper tables read, with its role."""
    items: Dict[tuple, Dict[str, Any]] = {}

    def add(model: str, method: str, rel: str, role: str, condition: str) -> None:
        key = (model, method, rel)
        if key in items:
            items[key]["role_in_paper"] += "; " + role
            return
        items[key] = {"model": model, "method": method, "rel": rel, "role_in_paper": role, "condition": condition}

    for model, mm in bpt.SOURCES.items():
        for method, rel in mm.items():
            add(model, method, rel, "main protocol table (Table 5 / S8)", "normal")
    for model, mm in bpt.STRESS_SOURCES.items():
        for method, rel in mm.items():
            add(model, method, rel, "stress table (S6)", "stress")
    for model, mm in bpt.SPLIT_TOOL_SOURCES.items():
        for method, sides in mm.items():
            add(model, method, sides["before"], "split-tool appendix, before side (original modify_load tool)", "normal")
            add(model, method, sides["after"], "split-tool appendix, after side (set_active_load/set_load)", "normal")
    return list(items.values())


def copy_raw(src: Path, dst_raw: Path, method: str, case: str) -> Dict[str, Any]:
    dst_raw.mkdir(parents=True, exist_ok=True)
    copied: Dict[str, Any] = {"files": [], "traces": 0}
    for name in ("report.json", "report.rescored.json", "REPORT.md", "scoreboard.md", "scoreboard.rescored.md", "scoreboard_per_case.md", "scoreboard_per_case.rescored.md"):
        p = src / name
        if p.is_file():
            shutil.copy2(p, dst_raw / name)
            copied["files"].append(name)
    for p in sorted(src.glob("*.log")):
        shutil.copy2(p, dst_raw / p.name)
        copied["files"].append(p.name)
    tr_src = src / "traces" / method_slug(method) / case
    if tr_src.is_dir():
        tr_dst = dst_raw / "traces" / method_slug(method) / case
        if tr_dst.exists():
            shutil.rmtree(tr_dst)
        shutil.copytree(tr_src, tr_dst)
        copied["traces"] = sum(1 for _ in tr_dst.glob("*.json"))
    return copied


def migrate_one(item: Dict[str, Any], source_root: Path, *, dry_run: bool, force: bool) -> Optional[Path]:
    src = source_root / item["rel"]
    if not (src / "report.json").is_file() and not (src / "report.rescored.json").is_file():
        print(f"skip  {item['model']} {item['method']}: no report under {src}")
        return None
    report = load_report(src)
    rows = [r for r in report.get("runs") or [] if (r.get("method") == item["method"] or r.get("task") == item["method"]) and (r.get("model") == item["model"] or item["method"] == "rule_based")]
    if not rows:
        print(f"skip  {item['model']} {item['method']}: no rows for that model/method in {src}")
        return None
    case = str(rows[0].get("case_name"))
    cfg = report.get("config") or {}
    tool_variant = cfg.get("tool_variant") or "v1"
    date = run_date(src)
    folder = methods.folder_for_runner_name(item["method"])
    name = folder + ("__stress" if item["condition"] == "stress" else "")
    row_model = str(rows[0].get("model") or item["model"])
    dst = RESULTS / CASE_FOLDER.get(case, case) / date / model_slug(row_model) / name
    if dst.exists() and (dst / "config.json").is_file():
        existing = json.loads((dst / "config.json").read_text(encoding="utf-8"))
        if existing.get("source") != item["rel"]:
            # Same case, date, model and method from a different source run: keep both.
            if existing.get("tool_variant") != tool_variant:
                dst = dst.parent / f"{name}__{tool_variant}"
            else:
                top = item["rel"].split("/")[0].removeprefix("results_")
                dst = dst.parent / f"{name}__from-{top}"
    if dst.exists() and not force:
        if (dst / "config.json").is_file() and json.loads((dst / "config.json").read_text(encoding="utf-8")).get("source") == item["rel"]:
            print(f"exists {dst.relative_to(PROJECT_ROOT)} (same source; use --force to redo)")
            return dst
    print(f"{'plan ' if dry_run else 'copy '} {item['model']:34s} {item['method']:26s} {item['rel']:70s} -> {dst.relative_to(PROJECT_ROOT)}  ({len(rows)} rows)")
    if dry_run:
        return dst
    copied = copy_raw(src, dst / "raw", item["method"], case)
    config = {
        "kind": "migrated",
        "date": date,
        "model": row_model,
        "model_short": model_slug(row_model),
        "listed_under_model": item["model"],
        "method": folder,
        "method_runner_name": item["method"],
        "case": case,
        "condition": item["condition"],
        "n": len(rows),
        "tool_variant": tool_variant,
        "plan_variant": cfg.get("plan_variant"),
        "k": cfg.get("k"), "seeds": cfg.get("seeds"), "max_rounds": cfg.get("max_rounds"), "temperature": cfg.get("temperature"),
        "source": item["rel"],
        "source_root": str(source_root),
        "source_commit": source_commit(src),
        "role_in_paper": item["role_in_paper"],
        "copied": copied,
        "migrated_at": _dt.datetime.now().isoformat(timespec="seconds"),
        "notes": "Copied from benchmarks/results_* by scripts/migrate_paper_results.py; the date is the write time of the source report.json.",
    }
    (dst / "config.json").write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    postprocess(dst, method=item["method"], model=row_model, case=case, condition=None, quiet=True)
    return dst


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source-root", default=str(PROJECT_ROOT / "benchmarks"), help="the benchmarks/ dir that still holds report.json and traces/")
    ap.add_argument("--only", default=None, help="substring filter on '<model>/<method>' (e.g. gpt-5.6-sol/pfagent)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true", help="redo a destination that already exists")
    args = ap.parse_args(argv)
    source_root = Path(args.source_root).resolve()
    done: List[Path] = []
    for item in plan():
        tag = f"{model_slug(item['model'])}/{item['method']}"
        if args.only and args.only not in tag:
            continue
        d = migrate_one(item, source_root, dry_run=args.dry_run, force=args.force)
        if d is not None:
            done.append(d)
    print(f"# {len(done)} run directories" + (" planned" if args.dry_run else " written"))
    if not args.dry_run and done:
        from run import build_index  # noqa: WPS433

        build_index()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
