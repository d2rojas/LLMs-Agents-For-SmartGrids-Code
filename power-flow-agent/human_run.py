#!/usr/bin/env python3
"""Human with solver: a person answers the benchmark requests through the same tools.

The person takes the LLM's seat. For each request the terminal shows the request, the tools
available, and every tool output as it arrives; the person types the tool calls to make (or the
final answer). The engine, dispatcher, solver, scoring and rendering are the unchanged benchmark
pipeline, so the row is measured with exactly the same metrics as the agents, and the LLM latency
becomes the person's thinking time.

    .venv/bin/python human_run.py --who daniela --sample 12        # 3 requests per difficulty
    .venv/bin/python human_run.py --who daniela                    # all 40 requests
    .venv/bin/python human_run.py --who daniela --sample 12 --seed-sample 1   # a different sample

At the prompt type one of:
    run_powerflow                          a tool call with no arguments
    disconnect_line from_bus=1 to_bus=5    a tool call with arguments (key=value, comma or space separated)
    load_case case14; run_powerflow        several calls in one turn, separated by ';'
    tools                                  print the tool list again
    answer: <text>                         the final answer for the operator, numbers copied from tool outputs
    escalate: <reason>                     hand the request to a person (declared inability), no numbers

Output goes to results/ieee14/<date>/human/human_with_solver/ like any other run.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import random
import subprocess
import sys
import textwrap
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from agent.engine import LLMClient  # noqa: E402

RESULTS = PROJECT_ROOT / "results"
ESCALATION_TEXT = "I cannot complete this request with the available tools. No numerical result is reported. This request needs review by an operator: {reason}"


def _typed(v: str) -> Any:
    s = v.strip().strip('"').strip("'")
    if s.lower() in ("true", "false"):
        return s.lower() == "true"
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        return s


def parse_calls(text: str) -> List[Dict[str, Any]]:
    calls = []
    for part in text.split(";"):
        part = part.strip()
        if not part:
            continue
        tokens = part.replace(",", " ").split()
        name, kv = tokens[0], tokens[1:]
        args: Dict[str, Any] = {}
        for t in kv:
            if "=" in t:
                k, v = t.split("=", 1)
                args[k.strip()] = _typed(v)
            elif name == "load_case" and not args:
                args["case_name"] = t
        calls.append({"name": name, "args": args})
    return calls


def tools_text(tools: List[Dict[str, Any]]) -> str:
    lines = []
    for t in tools or []:
        fn = t.get("function", t)
        params = (fn.get("parameters") or {}).get("properties") or {}
        req = set((fn.get("parameters") or {}).get("required") or [])
        sig = ", ".join(f"{k}{'*' if k in req else ''}" for k in params)
        desc = " ".join(str(fn.get("description") or "").split())[:90]
        lines.append(f"  {fn.get('name')}({sig})  {desc}")
    return "\n".join(lines)


def _summarize_tool_output(content: str, limit: int = 1600) -> str:
    """Solver output as a person wants to read it: totals, violations, then compact bus and line lists."""
    try:
        obj = json.loads(content)
    except Exception:
        return content[:limit]
    if not isinstance(obj, dict):
        return content[:limit]
    out: List[str] = []
    if "error" in obj:
        out.append(f"ERROR: {obj['error']}")
    for k in ("case_name", "converged", "n_buses", "n_lines", "n_generators", "n_loads", "message", "status", "summary_text"):
        if k in obj:
            out.append(f"{k}: {obj[k]}")
    for k in ("total_load_mw", "total_generation_mw", "total_loss_mw", "total_gen_capacity_mw"):
        if k in obj and isinstance(obj[k], (int, float)):
            out.append(f"{k}: {obj[k]:.3f}")
    bv = obj.get("bus_voltages")
    if isinstance(bv, list) and bv:
        out.append("bus voltages (bus: vm p.u. / angle deg):")
        out.append(textwrap.fill("  ".join(f"{b.get('bus_id')}: {b.get('vm_pu', 0):.4f}/{b.get('va_deg', 0):.2f}" + ("!" if b.get("is_violation") else "") for b in bv), 100, initial_indent="  ", subsequent_indent="  "))
    lf = obj.get("line_flows")
    if isinstance(lf, list) and lf:
        out.append("branches (id from-to: P_from MW / loading %):")
        out.append(textwrap.fill("  ".join(f"{l.get('line_id', l.get('id', '?'))} {l.get('from_bus', '?')}-{l.get('to_bus', '?')}: {l.get('p_from_mw', 0):.2f}/{l.get('loading_percent', 0):.1f}" + ("!" if l.get("is_violation") else "") for l in lf), 100, initial_indent="  ", subsequent_indent="  "))
    for k in ("voltage_violations", "thermal_violations", "isolated_buses"):
        v = obj.get(k)
        if isinstance(v, list):
            out.append(f"{k}: {len(v)}" + (f" -> {json.dumps(v, ensure_ascii=False)[:300]}" if v else ""))
    n1 = obj.get("n1_report")
    if isinstance(n1, dict):
        out.append("N-1 report: " + str(n1.get("summary_text", "")))
        for r in (n1.get("results") or [])[:10]:
            out.append(f"  outage {r.get('from_bus')}-{r.get('to_bus')} ({r.get('branch_type')}): converged={r.get('converged')} Vviol={r.get('n_voltage_violations')} thermal={r.get('n_thermal_violations')} worst_vm={r.get('worst_vm_pu')} worst_loading={r.get('worst_loading_percent')}")
    for k in ("suggestions", "remedial_actions", "results"):
        v = obj.get(k)
        if isinstance(v, list) and v and k not in ("results",) or (k == "results" and n1 is None and isinstance(v, list) and v):
            out.append(f"{k}:")
            for item in v[:8]:
                out.append("  " + json.dumps(item, ensure_ascii=False)[:220])
    shown = {"error", "case_name", "converged", "n_buses", "n_lines", "n_generators", "n_loads", "message", "status", "summary_text", "total_load_mw", "total_generation_mw", "total_loss_mw", "total_gen_capacity_mw", "bus_voltages", "line_flows", "voltage_violations", "thermal_violations", "isolated_buses", "n1_report", "suggestions", "remedial_actions", "results", "figure_json", "plot_type"}
    rest = {k: v for k, v in obj.items() if k not in shown}
    if rest:
        out.append("other: " + json.dumps(rest, ensure_ascii=False, default=str)[:400])
    txt = "\n".join(out)
    return txt if len(txt) <= limit * 3 else txt[: limit * 3] + "\n  ..."


class HumanClient(LLMClient):
    """The person answers each 'LLM call' at the terminal."""

    def __init__(self, who: str, echo_system: bool = False):
        self.who = who
        self.echo_system = echo_system
        self._n = 0
        self._shown_tools = False

    def create(self, **kwargs: Any) -> Any:
        self._n += 1
        messages = kwargs.get("messages") or []
        tools = kwargs.get("tools") or []
        print("\n" + "=" * 78)
        # show what is new since the last turn: the request on the first call, then tool outputs
        user_msgs = [m for m in messages if m.get("role") == "user"]
        if user_msgs:
            print("REQUEST:", user_msgs[-1].get("content"))
        last_assistant = max((i for i, m in enumerate(messages) if m.get("role") == "assistant"), default=-1)
        new_tool_msgs = [m for m in messages[last_assistant + 1 :] if m.get("role") == "tool"]
        for m in new_tool_msgs:
            print("-" * 78)
            print(f"TOOL OUTPUT ({m.get('name') or m.get('tool_call_id')}):")
            print(_summarize_tool_output(str(m.get("content"))))
        if tools and not self._shown_tools:
            print("-" * 78)
            print("TOOLS (* = required argument):")
            print(tools_text(tools))
            self._shown_tools = True
        print("-" * 78)
        print("Type tool calls (e.g. `load_case case14; run_powerflow`), `answer: ...`, `escalate: ...`, or `tools`.")
        while True:
            try:
                line = input(f"[{self.who}] > ").strip()
            except EOFError:
                line = "escalate: input ended"
            if not line:
                continue
            if line.lower() == "tools":
                print(tools_text(tools))
                continue
            break
        if line.lower().startswith("answer:"):
            content = line[len("answer:"):].strip()
            return self._response(content, [])
        if line.lower().startswith("escalate:"):
            return self._response(ESCALATION_TEXT.format(reason=line[len("escalate:"):].strip() or "unspecified"), [])
        calls = parse_calls(line)
        tool_calls = [
            {"id": f"human_{self._n}_{i}", "type": "function", "function": {"name": c["name"], "arguments": json.dumps(c["args"])}}
            for i, c in enumerate(calls)
        ]
        return self._response(None, tool_calls)

    @staticmethod
    def _response(content: Optional[str], tool_calls: List[Dict[str, Any]]) -> Dict[str, Any]:
        return {
            "choices": [{"message": {"role": "assistant", "content": content, "tool_calls": tool_calls or None}}],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        }


def make_requests_file(case: str, n: int, seed: int, sample: Optional[int], seed_sample: int, out: Path) -> Path:
    full = out.parent / f"requests_{case}_n{n}_s{seed}_full.jsonl"
    subprocess.run([sys.executable, "-m", "evaluation.requests", "--case", case, "--n", str(n), "--seed", str(seed), "--out", str(full)], cwd=PROJECT_ROOT, check=True, capture_output=True)
    lines = [json.loads(l) for l in full.read_text(encoding="utf-8").splitlines() if l.strip()]
    if sample and sample < len(lines):
        by_diff: Dict[str, List[dict]] = {}
        for r in lines:
            by_diff.setdefault(str(r.get("difficulty")), []).append(r)
        rng = random.Random(seed_sample)
        per = max(1, sample // max(1, len(by_diff)))
        chosen: List[dict] = []
        for d in sorted(by_diff):
            pool = by_diff[d][:]
            rng.shuffle(pool)
            chosen += pool[:per]
        chosen.sort(key=lambda r: str(r.get("id")))
        lines = chosen
    out.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in lines) + "\n", encoding="utf-8")
    return out


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--who", required=True, help="who is answering (goes into the model id, e.g. human:daniela)")
    ap.add_argument("--case", default="case14")
    ap.add_argument("--n", type=int, default=40, help="size of the generated request set (same as the agent runs)")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--sample", type=int, default=None, help="answer only about this many requests, the same number per difficulty (4 difficulties, so 12 gives 3 each)")
    ap.add_argument("--seed-sample", type=int, default=0)
    ap.add_argument("--max-rounds", type=int, default=8)
    ap.add_argument("--tool-variant", default="load_split", choices=["v1", "load_split"])
    ap.add_argument("--date", default=None)
    ap.add_argument("--tag", default=None)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args(argv)

    from evaluation.runner import ModelSpec, run_benchmark, write_report
    from evaluation.postprocess import postprocess
    from run import build_index
    from solver.case_loader import normalize_case_name
    from solver.power_flow import SolverConfig

    case = normalize_case_name(args.case)
    date = args.date or _dt.date.today().isoformat()
    name = "human_with_solver" + (f"__{args.tag}" if args.tag else "")
    out = RESULTS / {"case14": "ieee14", "case30": "ieee30", "case57": "ieee57", "case118": "ieee118"}.get(case, case) / date / "human" / name
    raw = out / "raw"
    if (raw / "report.json").is_file() and not args.force:
        raise SystemExit(f"{out} already has a report; use --force or --tag")
    raw.mkdir(parents=True, exist_ok=True)
    req_file = make_requests_file(case, args.n, args.seed, args.sample, args.seed_sample, raw / "requests_used.jsonl")
    n_items = sum(1 for _ in req_file.open())
    spec = ModelSpec(provider="human", model=args.who)
    config = {
        "kind": "human", "date": date, "model": spec.key, "model_short": f"human ({args.who})", "method": "human_with_solver", "method_runner_name": "react_nogate",
        "case": case, "condition": "normal", "n": n_items, "requests_file": str(req_file.relative_to(PROJECT_ROOT)), "sample_of": args.n, "seeds": [args.seed],
        "k": 1, "max_rounds": args.max_rounds, "tool_variant": args.tool_variant, "who": args.who, "started_at": _dt.datetime.now().isoformat(timespec="seconds"),
        "notes": "A person answers through the same tools, engine and scoring as the agents (human_run.py). LLM latency is the person's time; tokens are zero.",
    }
    (out / "config.json").write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{n_items} request(s) for {args.who} on {case}. Results -> {out.relative_to(PROJECT_ROOT)}")
    print("Take your time; each turn is timed from the moment it is shown until you press Enter.")
    t0 = time.time()
    report = run_benchmark(
        models=[spec], methods=["react_nogate"], cases=[case], runs=1, temperature=0.0, timeout_s=3600.0, pricing={},
        solver_config=SolverConfig(), k=1, seeds=[args.seed], requests_path=str(req_file), max_rounds=args.max_rounds,
        client_factory=lambda s: HumanClient(args.who), verbose=False, full_trace_dir=raw / "traces", condition="normal", tool_variant=args.tool_variant,
    )
    write_report(raw, report)
    config["finished_at"] = _dt.datetime.now().isoformat(timespec="seconds")
    config["total_minutes"] = round((time.time() - t0) / 60, 1)
    (out / "config.json").write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    rs = subprocess.run([sys.executable, "evaluation/rescore.py", str(raw), "--quiet"], cwd=PROJECT_ROOT, capture_output=True, text=True)
    (raw / "rescore.log").write_text(rs.stdout + rs.stderr, encoding="utf-8")
    postprocess(out, method="react_nogate", model=spec.key, case=case)
    build_index()
    print(f"\nDone in {config['total_minutes']} min. Read {out.relative_to(PROJECT_ROOT)}/REPORT.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
