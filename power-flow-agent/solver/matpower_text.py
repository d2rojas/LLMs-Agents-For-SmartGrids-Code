"""Utilities for locating and reading MATPOWER case text files."""

from __future__ import annotations

from pathlib import Path


SUPPORTED_CASES = {"case14", "case30", "case57", "case118", "case300"}
FETCH_CMD = "python scripts/fetch_matpower_cases.py --ref master --date 2017-01-01"


def _normalize_case_key(case_key: str) -> str:
    s = str(case_key or "").strip().lower()
    if s in SUPPORTED_CASES:
        return s
    raise ValueError(f"Unsupported MATPOWER case: {case_key}. Supported: {sorted(SUPPORTED_CASES)}")


def _parse_case_and_date(case_name_or_dataset_id: str, default_date: str) -> tuple[str, str]:
    raw = str(case_name_or_dataset_id or "").strip()
    if not raw:
        raise ValueError("case_name_or_dataset_id is empty")

    # dataset id format: matpower/case14/2017-01-01
    parts = [p for p in raw.split("/") if p]
    if len(parts) >= 3 and parts[0].lower() == "matpower":
        case_key = _normalize_case_key(parts[1])
        date = parts[2]
        return case_key, date

    return _normalize_case_key(raw), str(default_date)


def get_case_m_path(
    case_name_or_dataset_id: str,
    date: str = "2017-01-01",
    root: str = "data/matpower",
) -> Path:
    case_key, date_key = _parse_case_and_date(case_name_or_dataset_id, date)
    path = Path(root) / case_key / date_key / f"{case_key}.m"
    if not path.exists():
        raise FileNotFoundError(
            f"MATPOWER case file not found: {path}\n"
            f"Run:\n{FETCH_CMD}"
        )
    return path.resolve()


def read_case_m_text(
    case_name_or_dataset_id: str,
    date: str = "2017-01-01",
    root: str = "data/matpower",
) -> str:
    path = get_case_m_path(case_name_or_dataset_id, date=date, root=root)
    out_lines: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("%"):
            continue
        out_lines.append(line)
    return "\n".join(out_lines) + "\n"

