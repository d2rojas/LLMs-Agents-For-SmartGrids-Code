"""The frozen SDWPF windows every method and the scorer read, and the KDD Cup abnormal-data rules.

One instance of the benchmark is a turbine and a 14-day history window; the two
days after it are the target. ``data/benchmark/`` holds one CSV per instance with
the sixteen days (history and target), and ``manifest.json`` pins a content hash
of each file. ``load_window`` refuses a file whose hash no longer matches the
manifest, so a run never silently scores against edited data.

Nothing here reads the 72 MB raw SDWPF file; ``data/freeze.py`` does, once, on
purpose. The methods see the history through ``solver/tools.py``; the target
rows are read only by the scorer.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from config import (
    ABNORMAL_PAB_DEG, ABNORMAL_WSPD, FEATURES, HISTORY_DAYS, NDIR_RANGE_DEG, PROJECT_ROOT, STEPS_PER_DAY,
    TARGET_DAYS, WDIR_RANGE_DEG,
)

BENCHMARK_DIR = PROJECT_ROOT / "data" / "benchmark"
MANIFEST_PATH = BENCHMARK_DIR / "manifest.json"
COLUMNS = ["Day", "Tmstamp", "Wspd", "Wdir", "Etmp", "Patv", "Pab1", "Pab2", "Pab3", "Ndir"]


def content_hash(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def abnormal_mask(df: pd.DataFrame) -> pd.Series:
    """True where the KDD Cup 2022 rules say the actual power is unknown or abnormal (not scored)."""
    patv = pd.to_numeric(df["Patv"], errors="coerce")
    wspd = pd.to_numeric(df["Wspd"], errors="coerce")
    m = patv.isna() | wspd.isna()
    m |= (patv <= 0) & (wspd > ABNORMAL_WSPD)
    for c in ("Pab1", "Pab2", "Pab3"):
        if c in df:
            m |= pd.to_numeric(df[c], errors="coerce") > ABNORMAL_PAB_DEG
    if "Ndir" in df:
        nd = pd.to_numeric(df["Ndir"], errors="coerce")
        m |= (nd > NDIR_RANGE_DEG) | (nd < -NDIR_RANGE_DEG)
    if "Wdir" in df:
        wd = pd.to_numeric(df["Wdir"], errors="coerce")
        m |= (wd > WDIR_RANGE_DEG) | (wd < -WDIR_RANGE_DEG)
    return m.fillna(True)


@dataclass
class Window:
    """One benchmark instance: a turbine, its 14-day history and the two target days."""

    turbine: int
    base_day: int            # first day of the history
    frame: pd.DataFrame      # sixteen days, COLUMNS plus 'abnormal'
    path: Path
    file_hash: str
    condition: str = "normal"   # normal | stress (the last history day is blank)

    @property
    def history_end_day(self) -> int:
        return self.base_day + HISTORY_DAYS - 1

    @property
    def target_start_day(self) -> int:
        return self.base_day + HISTORY_DAYS

    @property
    def target_end_day(self) -> int:
        return self.target_start_day + TARGET_DAYS - 1

    @property
    def instance_id(self) -> str:
        return f"t{self.turbine:03d}-d{self.base_day:03d}"

    def history(self, days: Optional[int] = None) -> pd.DataFrame:
        """The history rows a method may see (the four features only), the last ``days`` days or all 14."""
        h = self.frame[self.frame["Day"] <= self.history_end_day]
        if days is not None:
            h = h[h["Day"] > self.history_end_day - int(days)]
        return h[["Day", "Tmstamp"] + list(FEATURES)].reset_index(drop=True)

    def target(self, horizon_h: int) -> pd.DataFrame:
        """The target rows for a horizon, with the abnormal flag; read by the scorer only."""
        t = self.frame[self.frame["Day"] >= self.target_start_day].sort_values(["Day", "Tmstamp"], kind="stable")
        return t.head(int(horizon_h) * 6)[["Day", "Tmstamp", "Wspd", "Patv", "abnormal"]].reset_index(drop=True)

    def history_valid_rows_per_day(self) -> Dict[int, int]:
        """Rows per history day that carry a measurement (wind speed and power both present).

        A curtailed row (pitch angle above 89 degrees) is a measurement of a stopped turbine
        and counts; it is excluded from scoring by the abnormal rules, not from the history.
        A blank row is a gap in the SCADA feed and does not count."""
        h = self.frame[self.frame["Day"] <= self.history_end_day]
        return {int(d): int((g["Patv"].notna() & g["Wspd"].notna()).sum()) for d, g in h.groupby("Day")}


def _sort_key(ts: pd.Series) -> pd.Series:
    parts = ts.astype(str).str.split(":", expand=True)
    return parts[0].astype(int) * 60 + parts[1].astype(int)


def read_frame(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df = df[[c for c in COLUMNS if c in df.columns]].copy()
    df["_t"] = _sort_key(df["Tmstamp"])
    df = df.sort_values(["Day", "_t"], kind="stable").drop(columns="_t").reset_index(drop=True)
    df["abnormal"] = abnormal_mask(df)
    return df


def load_manifest() -> Dict[str, Any]:
    if not MANIFEST_PATH.is_file():
        raise FileNotFoundError(f"no frozen benchmark: {MANIFEST_PATH} (run `python run.py freeze-data --source <sdwpf csv>`)")
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def instances(manifest: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    m = manifest or load_manifest()
    return list(m["instances"])


def load_window(turbine: int, base_day: int, *, condition: str = "normal", check_hash: bool = True, manifest: Optional[Dict[str, Any]] = None) -> Window:
    m = manifest or load_manifest()
    key = f"t{int(turbine):03d}-d{int(base_day):03d}"
    entry = next((e for e in m["instances"] if e["instance_id"] == key), None)
    if entry is None:
        raise KeyError(f"instance {key} is not in the frozen benchmark; known: {[e['instance_id'] for e in m['instances']]}")
    path = BENCHMARK_DIR / entry["file"]
    h = content_hash(path)
    if check_hash and h != entry["content_hash"]:
        raise ValueError(f"{path.name} was edited after freezing: hash {h} != manifest {entry['content_hash']}")
    frame = read_frame(path)
    if condition == "stress":
        # the SCADA feed stopped on the last history day: every feature of that day is missing
        last = int(base_day) + HISTORY_DAYS - 1
        sel = frame["Day"] == last
        for c in FEATURES + ("Pab1", "Pab2", "Pab3", "Ndir"):
            frame.loc[sel, c] = np.nan
        frame["abnormal"] = abnormal_mask(frame)
    elif condition != "normal":
        raise ValueError(f"unknown condition {condition!r}")
    return Window(turbine=int(turbine), base_day=int(base_day), frame=frame, path=path, file_hash=h, condition=condition)


def history_csv(window: Window, days: Optional[int] = None) -> str:
    """The history as the CSV block the prompts carry: the four features, missing values left blank."""
    h = window.history(days)
    out = h.copy()
    for c in FEATURES:
        out[c] = pd.to_numeric(out[c], errors="coerce").round(2)
    return out.to_csv(index=False, lineterminator="\n")
