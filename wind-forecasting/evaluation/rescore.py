"""Re-score a results folder from its traces after a scoring change, then re-render.

The traces keep the final answer text, the tool log and the request, and the
window is rebuilt from the frozen manifest, so every ``common_*`` field can be
recomputed without calling a model.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import methods  # noqa: E402
from evaluation import postprocess, scoring  # noqa: E402
from evaluation.requests import request_from_dict, window_for  # noqa: E402
from methods.answer import parse_answer  # noqa: E402
from methods.common import MethodRun  # noqa: E402


def rescore(dir_: Path) -> None:
    rows_p = dir_ / "raw" / "rows.jsonl"
    rows = [json.loads(l) for l in rows_p.read_text(encoding="utf-8").splitlines() if l.strip()]
    out = []
    for r in rows:
        trace_p = dir_ / "raw" / "traces" / f"{r['request_id']}.json"
        trace = json.loads(trace_p.read_text(encoding="utf-8")) if trace_p.is_file() else {}
        req = request_from_dict(trace["request"]) if trace.get("request") else None
        if req is None:
            out.append(r)
            continue
        window = window_for(req)
        tool_log = trace.get("tool_log") or []
        run = MethodRun(method=r["method"], answer_text=r.get("answer_text") or "", answer=parse_answer(r.get("answer_text") or ""),
                        tool_log=tool_log, trace=trace, gate=r.get("gate"), harness_declared=r.get("harness_declared"),
                        budget_exhausted=bool(r.get("budget_exhausted")), error=r.get("error"),
                        n_llm_calls=int(r.get("n_llm_calls") or 0), n_tool_calls=int(r.get("n_tool_calls") or 0),
                        prompt_tokens=int(r.get("prompt_tokens") or 0), completion_tokens=int(r.get("completion_tokens") or 0),
                        wall_time_s=float(r.get("wall_time_s") or 0))
        scored = scoring.score_run(run, req=req, window=window, has_tools=bool(methods.card(r["method"])["uses_tools"]))
        r2 = {k: v for k, v in r.items() if not k.startswith("common_")}
        r2["answer"] = run.answer.as_dict()
        r2.update(scored)
        out.append(r2)
        trace["scored"] = scored
        trace_p.write_text(json.dumps(trace, indent=1, default=str), encoding="utf-8")
    rows_p.write_text("".join(json.dumps(r, default=str) + "\n" for r in out), encoding="utf-8")
    postprocess.postprocess(dir_)


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dirs", nargs="+")
    args = ap.parse_args(argv)
    for d in args.dirs:
        rescore(Path(d))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
