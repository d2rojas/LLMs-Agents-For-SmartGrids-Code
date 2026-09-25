"""Freeze the 20 benchmark days from ACN-Data into data/benchmark/ so they stay reproducible.

Run once, with a token. After that the benchmark loads from the committed files and needs
neither a token nor the network, and the manifest pins what the API returned: the fetch
timestamp, the number of records per day, and a content hash of each day.

Usage (from the project root):
  python -m scripts.freeze_benchmark_days --dry-run    # list what would be fetched
  python -m scripts.freeze_benchmark_days              # fetch missing days
  python -m scripts.freeze_benchmark_days --force      # re-fetch and overwrite
  python -m scripts.freeze_benchmark_days --dates 2019-05-01 2019-05-08

Existing day files are never overwritten unless --force is given; without it an existing
day is kept and only its manifest entry is refreshed from the file on disk.

Requires:
  - ACN_DATA_API_TOKEN in .env or the environment (not needed for --dry-run)

Output:
  - data/benchmark/<site>_<YYYY-MM-DD>.json  one file per day, raw API records
  - data/benchmark/manifest.json             site, dates, timestamps, counts, hashes
"""

import argparse
import os
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

try:
    from dotenv import load_dotenv
    load_dotenv(_project_root / ".env")
except ImportError:
    pass

from data.benchmark import store
from data.loader.loader import ACN_API_BASE, fetch_sessions_from_api


def _parse_date(text: str) -> date:
    """Parse a YYYY-MM-DD argument into a date."""
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Invalid date {text!r}; expected YYYY-MM-DD") from exc


def _existing_entries(manifest_path: Path) -> Dict[str, Dict[str, Any]]:
    """Return the manifest rows already on disk, keyed by date string."""
    if not manifest_path.exists():
        return {}
    try:
        manifest = store.read_manifest(manifest_path)
    except (ValueError, OSError):
        return {}
    return {str(row["date"]): row for row in manifest.get("days", [])}


def freeze_days(
    site_id: str,
    dates: List[date],
    out_dir: Path,
    api_token: Optional[str] = None,
    force: bool = False,
) -> int:
    """Fetch and write one day file per date, then rewrite the manifest.

    Args:
        site_id: ACN-Data site (the benchmark uses 'caltech').
        dates: Days to freeze.
        out_dir: Destination folder (data/benchmark/).
        api_token: ACN-Data token; falls back to ACN_DATA_API_TOKEN.
        force: Overwrite day files that already exist.

    Returns:
        Process exit code: 0 if every requested day is on disk afterwards, 1 otherwise.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / store.MANIFEST_NAME
    entries: Dict[str, Dict[str, Any]] = _existing_entries(manifest_path)

    written = 0
    kept = 0
    failed: List[date] = []

    for day_date in dates:
        path = out_dir / store.day_filename(site_id, day_date)
        if path.exists() and not force:
            print(f"keep   {path.name} (exists; pass --force to re-fetch)")
            try:
                entries[day_date.isoformat()] = store.build_manifest_entry(
                    store.read_day_file(path), path
                )
            except ValueError as exc:
                print(f"       WARNING: {exc}", file=sys.stderr)
            kept += 1
            continue

        try:
            records = fetch_sessions_from_api(site_id, day_date, api_token=api_token)
        except Exception as exc:  # network, auth, or API payload error
            print(f"FAIL   {path.name}: {exc}", file=sys.stderr)
            failed.append(day_date)
            continue

        payload = store.build_day_file(
            site_id=site_id,
            day_date=day_date,
            records=records,
            data_source=store.SOURCE_ACN_API,
            synthetic=False,
            extra={"api_base": ACN_API_BASE, "frozen_by": "scripts/freeze_benchmark_days.py"},
        )
        store.write_day_file(path, payload, force=True)
        entries[day_date.isoformat()] = store.build_manifest_entry(payload, path)
        written += 1
        print(f"write  {path.name}  {payload['record_count']:3d} sessions")

    store.write_manifest(
        manifest_path,
        site_id=site_id,
        entries=list(entries.values()),
        data_source=store.SOURCE_ACN_API,
        synthetic=False,
        extra={
            "api_base": ACN_API_BASE,
            "frozen_by": "scripts/freeze_benchmark_days.py",
            "purpose": (
                "The evaluation days behind paper Table 4 (§VI-B), frozen so the benchmark "
                "reproduces without an ACN-Data token."
            ),
        },
    )

    print(f"\n{written} written, {kept} kept, {len(failed)} failed. Manifest: {manifest_path}")
    if failed:
        print("Failed dates: " + ", ".join(d.isoformat() for d in failed), file=sys.stderr)
        return 1
    return 0


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Freeze ACN-Data benchmark days into data/benchmark/ for offline reproduction."
    )
    parser.add_argument(
        "--site",
        default=store.BENCHMARK_SITE_ID,
        choices=["caltech", "jpl", "office001"],
        help=f"ACN-Data site (default: {store.BENCHMARK_SITE_ID})",
    )
    parser.add_argument(
        "--dates",
        type=_parse_date,
        nargs="+",
        default=store.BENCHMARK_DATES,
        help="Dates as YYYY-MM-DD (default: the 20 benchmark dates)",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=store.BENCHMARK_DIR,
        help="Destination folder (default: data/benchmark)",
    )
    parser.add_argument("--force", action="store_true", help="Overwrite day files that already exist")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List what would be fetched and exit; no token and no network needed",
    )
    args = parser.parse_args()

    if args.dry_run:
        print(f"Site: {args.site}")
        print(f"Destination: {args.out_dir}")
        print(f"Dates ({len(args.dates)}):")
        for day_date in args.dates:
            path = Path(args.out_dir) / store.day_filename(args.site, day_date)
            if path.exists():
                action = "re-fetch (--force)" if args.force else "keep (already frozen)"
            else:
                action = "fetch"
            print(f"  {day_date.isoformat()}  {action}")
        print("\nDry run: nothing fetched and nothing written.")
        return 0

    token = os.environ.get("ACN_DATA_API_TOKEN", "").strip()
    if not token:
        print(
            "ACN_DATA_API_TOKEN is not set. Put it in .env or the environment, or use "
            "--dry-run to see what would be fetched.",
            file=sys.stderr,
        )
        return 2

    return freeze_days(
        site_id=args.site,
        dates=list(args.dates),
        out_dir=args.out_dir,
        api_token=token,
        force=args.force,
    )


if __name__ == "__main__":
    raise SystemExit(main())
