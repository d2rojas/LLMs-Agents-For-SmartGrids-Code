"""Freeze the benchmark instances from the raw SDWPF file into data/benchmark/, once, on purpose.

    python -m data.freeze --source /path/to/wtbdata_245days.csv            # the paper set
    python -m data.freeze --source ... --dry-run                             # list what would be written
    python -m data.freeze --source ... --force                               # overwrite

What it writes:

    data/benchmark/t<TTT>-d<DDD>.csv      sixteen days of one turbine: the 14-day history and the 2 target days
    data/benchmark/manifest.json          the instances, a content hash per file, the choice rule, the raw file's hash
    data/gru/train_t<TTT>.csv.gz             days 1..214 of each benchmark turbine, the GRU's training slice

The instances are chosen by a fixed rule, not by hand: ``--seed`` draws ``--n-turbines``
turbines among those whose target days carry at most ``--max-abnormal`` abnormal
points, and the base days are fixed so that every target day lies in the KDD Cup
test period (days 215 to 245), which the GRU never sees in training.

Existing files are never overwritten unless ``--force`` is given.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import DATASET_DAYS, HISTORY_DAYS, TARGET_DAYS, TRAIN_LAST_DAY  # noqa: E402
from solver.data import BENCHMARK_DIR, COLUMNS, MANIFEST_PATH, abnormal_mask, content_hash  # noqa: E402

GRU_DIR = PROJECT_ROOT / "data" / "gru"
BASE_DAYS_DEFAULT = (201, 207, 212, 229)   # targets 215-216, 221-222, 226-227, 243-244: the test-period days where the farm was running, not curtailed


def choose_turbines(df: pd.DataFrame, base_days: List[int], n: int, seed: int, max_abnormal: int) -> List[int]:
    """Turbines whose target days have few abnormal points, then a seeded draw among them."""
    target_days = sorted({d for b in base_days for d in range(b + HISTORY_DAYS, b + HISTORY_DAYS + TARGET_DAYS)})
    t = df[df["Day"].isin(target_days)].copy()
    t["abn"] = abnormal_mask(t)
    counts = t.groupby("TurbID")["abn"].sum()
    rows = df[df["Day"].isin(target_days)].groupby("TurbID").size()
    eligible = sorted(int(x) for x in counts.index if counts[x] <= max_abnormal and rows.get(x, 0) == len(target_days) * 144)
    if len(eligible) < n:
        raise SystemExit(f"only {len(eligible)} turbines have <= {max_abnormal} abnormal target points; lower the bar or n")
    rng = np.random.default_rng(seed)
    return sorted(int(x) for x in rng.choice(eligible, size=n, replace=False))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", required=True, help="path to wtbdata_245days.csv (SDWPF, KDD Cup 2022)")
    ap.add_argument("--n-turbines", type=int, default=5)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--base-days", type=int, nargs="+", default=list(BASE_DAYS_DEFAULT))
    ap.add_argument("--max-abnormal", type=int, default=60, help="abnormal points allowed across a turbine's target days")
    ap.add_argument("--train-turbines", default="all", choices=("all", "benchmark"),
                    help="whose days 1..214 to freeze as training data: every complete turbine (more data, no leakage) or only the benchmark five")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    src = Path(args.source).expanduser()
    print(f"reading {src} ...")
    raw = pd.read_csv(src, usecols=lambda c: c in set(["TurbID"] + COLUMNS))
    raw = raw[["TurbID"] + [c for c in COLUMNS if c in raw.columns]]
    for b in args.base_days:
        if b + HISTORY_DAYS + TARGET_DAYS - 1 > DATASET_DAYS or b + HISTORY_DAYS <= TRAIN_LAST_DAY:
            raise SystemExit(f"base day {b}: target days must lie in {TRAIN_LAST_DAY + 1}..{DATASET_DAYS}")
    turbines = choose_turbines(raw, args.base_days, args.n_turbines, args.seed, args.max_abnormal)
    print(f"turbines: {turbines}; base days: {args.base_days}")

    inst: List[Dict[str, Any]] = []
    plan = [(t, b) for t in turbines for b in args.base_days]
    for t, b in plan:
        name = f"t{t:03d}-d{b:03d}.csv"
        p = BENCHMARK_DIR / name
        sel = raw[(raw["TurbID"] == t) & (raw["Day"] >= b) & (raw["Day"] <= b + HISTORY_DAYS + TARGET_DAYS - 1)]
        frame = sel.drop(columns=["TurbID"]).reset_index(drop=True)
        n_abn_target = int(abnormal_mask(frame[frame["Day"] >= b + HISTORY_DAYS]).sum())
        n_abn_hist = int(abnormal_mask(frame[frame["Day"] < b + HISTORY_DAYS]).sum())
        if args.dry_run:
            print(f"  would write {name}: {len(frame)} rows, abnormal history {n_abn_hist}, target {n_abn_target}")
            continue
        BENCHMARK_DIR.mkdir(parents=True, exist_ok=True)
        if p.exists() and not args.force:
            print(f"  kept {name} (exists; --force to overwrite)")
        else:
            frame.to_csv(p, index=False, lineterminator="\n")
            print(f"  wrote {name}: {len(frame)} rows")
        inst.append({
            "instance_id": f"t{t:03d}-d{b:03d}", "turbine": t, "base_day": b, "history_days": [b, b + HISTORY_DAYS - 1],
            "target_days": [b + HISTORY_DAYS, b + HISTORY_DAYS + TARGET_DAYS - 1], "file": name, "content_hash": content_hash(p),
            "record_count": int(len(frame)), "abnormal_points_history": n_abn_hist, "abnormal_points_target": n_abn_target,
        })
    if args.dry_run:
        return 0

    GRU_DIR.mkdir(parents=True, exist_ok=True)
    train_files = []
    # Which turbines' history may be used for training. Every complete turbine is allowed,
    # but only its days 1..TRAIN_LAST_DAY: the turbines of one farm see nearly the same weather,
    # so a target day of a benchmark turbine would leak through any other turbine's same day.
    complete = sorted(int(t) for t, n in raw.groupby("TurbID").size().items() if n == DATASET_DAYS * 144)
    train_turbines = complete if args.train_turbines == "all" else list(turbines)
    print(f"training turbines: {len(train_turbines)} of {raw['TurbID'].nunique()} ({args.train_turbines}), days 1..{TRAIN_LAST_DAY} only")
    for t in train_turbines:
        p = GRU_DIR / f"train_t{t:03d}.csv.gz"
        sel = raw[(raw["TurbID"] == t) & (raw["Day"] <= TRAIN_LAST_DAY)].drop(columns=["TurbID"]).reset_index(drop=True)
        if p.exists() and not args.force:
            print(f"  kept {p.name}")
        else:
            sel.to_csv(p, index=False, lineterminator="\n", compression={"method": "gzip", "mtime": 0})
            print(f"  wrote {p.name}: {len(sel)} rows (days 1..{TRAIN_LAST_DAY})")
        train_files.append({"turbine": t, "file": p.name, "content_hash": content_hash(p), "record_count": int(len(sel)), "days": [1, TRAIN_LAST_DAY]})

    manifest = {
        "data_source": "SDWPF (Baidu KDD Cup 2022; Zhou et al., Scientific Data 2024), wtbdata_245days.csv",
        "source_file_hash": "sha256:" + hashlib.sha256(src.read_bytes()).hexdigest(),
        "frozen_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "frozen_by": "data/freeze.py",
        "choice_rule": {"n_turbines": args.n_turbines, "seed": args.seed, "max_abnormal_target_points": args.max_abnormal,
                        "base_days": list(args.base_days), "history_days": HISTORY_DAYS, "target_days": TARGET_DAYS,
                        "test_period": [TRAIN_LAST_DAY + 1, DATASET_DAYS]},
        "turbines": turbines,
        "instances": inst,
        "gru_training": {"days": [1, TRAIN_LAST_DAY], "turbines": train_turbines, "selection": args.train_turbines,
                         "note": "only days 1 to 214, of any complete turbine. Turbines of one farm share their weather, so a benchmark "
                                 "turbine's target day would leak through another turbine's same day; the day bound closes that path.",
                         "files": train_files},
        "note": "No future information is available to any method: every input is SCADA history up to the day before the forecast start. "
                "The farm's location and calendar dates are not published with the dataset, so no weather forecast is attached.",
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    print(f"wrote {MANIFEST_PATH.relative_to(PROJECT_ROOT)}: {len(inst)} instances")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
