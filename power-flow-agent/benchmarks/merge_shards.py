#!/usr/bin/env python3
r"""Reassemble a sharded evaluate_llms.py run into the report.json a normal run
would have produced.

Written 2026-09-21 alongside evaluate_llms.py's --shard-index/--shard-count so the
larger IEEE systems (case30/57/118) can be split across concurrent processes without
paying for a full unsharded rerun to get the final report. Reassembly recomputes the
aggregate scoreboard from the union of every shard's raw per-item rows using the same
_aggregate_group() run_benchmark itself uses, rather than combining pre-aggregated
numbers, so the result is not an approximation -- it is what a single unsharded run
would have written, as long as the shards really do tile one run (checked below,
refused otherwise rather than silently merged).

Usage:
    .venv/bin/python benchmarks/merge_shards.py <out-dir> [--pdf]

Reads every report.shard<I>of<N>.json in <out-dir>, refuses to proceed if:
  - shard_count disagrees between files, or the shard indices present are not
    exactly {0, ..., shard_count-1} with no duplicate and no repeat,
  - any two shards' config disagrees on anything other than shard_index (a shard
    run under --k 1 merged with one run under --k 0 is not one run),
  - the union of raw rows contains a duplicate (model, method, case, seed,
    request_id, run) key (the same item scored twice, most likely from overlapping
    shard boundaries or two shards actually being the same shard),
  - more than one distinct system_prompt_hash appears across the union of rows
    (the mid-run prompt-edit hazard this field exists to catch -- see the code
    repo's local CLAUDE.md, "Don't edit a prompt while a run is in flight").

On success writes report.json, scoreboard.{json,csv,md}, scoreboard_per_case.{json,csv,md}
into <out-dir> via evaluate_llms.write_report, exactly as an unsharded run would --
the report.shard*.json inputs are left in place (not gitignored differently from a
normal report.json; delete them by hand once the merged report.json is verified, if
disk space matters).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from benchmarks.evaluate_llms import (  # noqa: E402
    CORE_SCOREBOARD_FIELDS,
    EXTENDED_SCOREBOARD_FIELDS,
    _aggregate_group,
    write_report,
)
import benchmarks.evaluate_llms as bm  # noqa: E402


class ShardMergeError(ValueError):
    """A shard set does not tile one run; refuse rather than guess."""


def find_shards(out_dir: Path) -> list[Path]:
    return sorted(out_dir.glob("report.shard*of*.json"))


def _row_key(row: dict[str, Any]) -> tuple:
    return (
        row.get("model"),
        row.get("method") or row.get("task"),
        row.get("case_name"),
        row.get("seed"),
        row.get("request_id"),
        row.get("run"),
    )


def load_and_validate(shard_paths: list[Path]) -> list[dict[str, Any]]:
    if not shard_paths:
        raise ShardMergeError("no report.shard*of*.json files found")

    reports = [json.loads(p.read_text(encoding="utf-8")) for p in shard_paths]

    counts = {r["config"].get("shard_count") for r in reports}
    if len(counts) != 1:
        raise ShardMergeError(f"shard_count disagrees across shards: {sorted(counts)}")
    (shard_count,) = counts
    if not shard_count:
        raise ShardMergeError("shard_count is missing or 0 in these reports -- not sharded runs")

    indices = [r["config"].get("shard_index") for r in reports]
    if sorted(indices) != list(range(shard_count)):
        raise ShardMergeError(
            f"shard indices present are {sorted(indices)}, expected exactly "
            f"{list(range(shard_count))} (missing or duplicated shard)"
        )

    def _config_sans_shard(cfg: dict[str, Any]) -> dict[str, Any]:
        return {k: v for k, v in cfg.items() if k not in ("shard_index",)}

    base_cfg = _config_sans_shard(reports[0]["config"])
    for r, p in zip(reports[1:], shard_paths[1:]):
        cfg = _config_sans_shard(r["config"])
        if cfg != base_cfg:
            diff = {k for k in set(base_cfg) | set(cfg) if base_cfg.get(k) != cfg.get(k)}
            raise ShardMergeError(f"{p.name}: config differs from {shard_paths[0].name} on {sorted(diff)} -- not one run")

    all_rows: list[dict[str, Any]] = []
    seen_keys: dict[tuple, Path] = {}
    for r, p in zip(reports, shard_paths):
        for row in r.get("runs") or []:
            key = _row_key(row)
            if key in seen_keys:
                raise ShardMergeError(f"duplicate item {key} in both {seen_keys[key].name} and {p.name} -- overlapping shard boundaries")
            seen_keys[key] = p
            all_rows.append(row)

    hashes = {row.get("system_prompt_hash") for row in all_rows if row.get("system_prompt_hash")}
    if len(hashes) > 1:
        raise ShardMergeError(
            f"{len(hashes)} distinct system_prompt_hash values across the shards ({sorted(hashes)}) -- "
            "a prompt file was edited between when two shards ran; this is not one run"
        )

    return all_rows


def build_merged_report(shard_paths: list[Path]) -> dict[str, Any]:
    raw_rows = load_and_validate(shard_paths)
    template = json.loads(shard_paths[0].read_text(encoding="utf-8"))
    config = {k: v for k, v in template["config"].items() if k not in ("shard_index", "shard_count")}

    scoreboard_rows: list[dict[str, Any]] = []
    scoreboard_case_rows: list[dict[str, Any]] = []
    by_group: dict[tuple[str, str], list[dict[str, Any]]] = {}
    by_case_group: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for row in raw_rows:
        by_group.setdefault((row["model"], row["task"]), []).append(row)
        by_case_group.setdefault((row["model"], row["task"], row["case_name"]), []).append(row)

    condition = config.get("condition", "normal")
    for (model_key, task_name), rows in sorted(by_group.items()):
        agg = _aggregate_group(rows)
        scoreboard_rows.append({"model": model_key, "task": task_name, "method": task_name, "condition": condition, **agg})
    for (model_key, task_name, case_name), rows in sorted(by_case_group.items()):
        agg = _aggregate_group(rows)
        scoreboard_case_rows.append(
            {"model": model_key, "task": task_name, "method": task_name, "case_name": case_name, "condition": condition, **agg}
        )

    return {
        "config": config,
        "core_scoreboard_fields": CORE_SCOREBOARD_FIELDS,
        "extended_scoreboard_fields": EXTENDED_SCOREBOARD_FIELDS,
        "metric_definitions": bm.__doc__,
        "scoreboard": scoreboard_rows,
        "scoreboard_per_case": scoreboard_case_rows,
        "runs": raw_rows,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("out_dir", help="directory holding report.shard<I>of<N>.json files")
    parser.add_argument("--pdf", action="store_true", help="also render REPORT.pdf via experiment_report.py")
    args = parser.parse_args(argv)

    out_dir = Path(args.out_dir)
    shard_paths = find_shards(out_dir)
    try:
        merged = build_merged_report(shard_paths)
    except ShardMergeError as e:
        print(f"refused to merge: {e}", file=sys.stderr)
        return 1

    write_report(out_dir, merged)
    n_items = len(merged["runs"])
    print(f"merged {len(shard_paths)} shards ({n_items} items) -> {out_dir / 'report.json'}")

    cmd = [str(PROJECT_ROOT / ".venv" / "bin" / "python"), "benchmarks/experiment_report.py", str(out_dir)]
    if args.pdf:
        cmd.append("--pdf")
    subprocess.run(cmd, check=True, cwd=PROJECT_ROOT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
