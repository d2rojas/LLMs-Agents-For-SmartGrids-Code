"""Download MATPOWER case files into data/matpower/<case>/<date>/."""

from __future__ import annotations

import argparse
import urllib.error
import urllib.request
from pathlib import Path


CASES = ["case14", "case30", "case57", "case118", "case300"]


def _url(ref: str, case_key: str) -> str:
    return f"https://raw.githubusercontent.com/MATPOWER/matpower/{ref}/data/{case_key}.m"


def fetch_cases(*, ref: str, date: str, out_root: str) -> list[Path]:
    out_paths: list[Path] = []
    root = Path(out_root)
    for case_key in CASES:
        url = _url(ref, case_key)
        dst = root / case_key / date / f"{case_key}.m"
        dst.parent.mkdir(parents=True, exist_ok=True)
        try:
            with urllib.request.urlopen(url) as r:
                content = r.read()
        except urllib.error.URLError as e:
            raise RuntimeError(f"Failed to download {url}: {e}") from e

        dst.write_bytes(content)
        out_paths.append(dst)
    return out_paths


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch MATPOWER case .m files from GitHub.")
    parser.add_argument("--ref", default="master", help="Git ref/tag/branch in MATPOWER repo.")
    parser.add_argument("--date", default="2017-01-01", help="Dataset date folder name.")
    parser.add_argument("--out", dest="out_root", default="data/matpower", help="Output root folder.")
    args = parser.parse_args(argv)

    paths = fetch_cases(ref=str(args.ref), date=str(args.date), out_root=str(args.out_root))
    for p in paths:
        print(f"Saved: {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

