"""The page must not drift from the rows and the aggregate it is built from.

Three things compute the same quantities over one dataset: the page, each run's
``summary.json`` and the report written from it. Two of them disagreeing is
invisible, because each looks right on its own, and it has already happened in
this repository more than once. ``visuals/crosscheck.mjs`` recounts every figure
the page rendered from the run's own rows and compares both against the stored
aggregate; this runs it as part of the suite so nobody has to remember to.

It needs node and spends nothing. Where there is no node, or no page has been
built yet, the test skips rather than fails: it checks agreement between things
that exist, and a page that was never built cannot disagree with anything.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parents[1]
ROOT = PROJECT.parent
CHECK = ROOT / "visuals" / "crosscheck.mjs"
SPEC = PROJECT / "tests" / "crosscheck_spec.json"
PAGE = ROOT / "site" / "wind.html"


@pytest.mark.skipif(shutil.which("node") is None, reason="the cross-check is a node script")
def test_page_agrees_with_rows_and_aggregate() -> None:
    if not PAGE.exists():
        pytest.skip(f"no page built yet: run `python -m visuals.build --require wind` from {ROOT}")
    proc = subprocess.run(
        ["node", str(CHECK), str(PROJECT), str(PAGE), str(SPEC)],
        cwd=ROOT, capture_output=True, text=True,
    )
    # A page older than the runs is not a disagreement, and reporting it as one
    # sends whoever sees the red to look for a bug in code that is fine. Both the
    # power-flow and the wind session hit exactly that while merging this, so the
    # script says so with its own exit code and the suite turns it into an
    # instruction. site/ is gitignored and per worktree, so a checkout that has
    # not rebuilt keeps a stale page indefinitely.
    if proc.returncode == 3:
        pytest.skip(proc.stdout.strip())
    assert proc.returncode == 0, proc.stdout + proc.stderr
