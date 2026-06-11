"""Run cross-model LLM benchmarks for power-flow estimation tasks.

This runner evaluates multiple models, tasks, and cases against the PandaPower
ground truth and records both scientific metrics and API usage.

Cost estimation is pricing-table driven. Update PRICE_BOOK_USD_PER_1M or pass
--pricing-file with the rates you want to use before treating cost numbers as authoritative.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import ANTHROPIC_API_KEY, GEMINI_API_KEY, GEMINI_MODEL, OPENAI_API_KEY, OPENAI_MODEL

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
DEFAULT_OUT_DIR = "benchmarks/results"

CORE_SCOREBOARD_FIELDS = [
    "success_rate",
    "voltage_mae_mean",
    "flow_mae_mean",
    "loading_rmse_mean",
    "voltage_f1_mean",
    "thermal_f1_mean",
    "convergence_match_rate",
    "prompt_tokens_mean",
    "completion_tokens_mean",
    "total_tokens_mean",
    "cost_usd_mean",
    "cost_usd_total",
]

CASE_SCOREBOARD_FIELDS = [
    "case_name",
    *CORE_SCOREBOARD_FIELDS,
]

# Update these values or provide --pricing-file before relying on cost numbers.
PRICE_BOOK_USD_PER_1M: dict[str, dict[str, float]] = {}


@dataclass(frozen=True)
class UsageStats:
    prompt_tokens: Optional[int]
    completion_tokens: Optional[int]
    total_tokens: Optional[int]


@dataclass(frozen=True)
class ModelSpec:
    provider: str
    model: str

    @property
    def key(self) -> str:
        return f"{self.provider}:{self.model}"


@dataclass(frozen=True)
class TaskSpec:
    name: str
    prompt_builder: Callable[[str], tuple[str, str]]
    response_parser: Callable[[str, dict[str, Any]], Any]
    context_builder: Optional[Callable[[str], dict[str, Any]]] = None


def _content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        chunks: list[str] = []
        for part in content:
            if isinstance(part, str):
                chunks.append(part)
            elif isinstance(part, dict):
                text = part.get("text")
                if isinstance(text, dict):
                    text = text.get("value")
                if text is None:
                    text = part.get("content")
                if text is not None:
                    chunks.append(str(text))
            else:
                text = getattr(part, "text", None)
                if text is not None:
                    chunks.append(str(text))
        return "\n".join(c for c in chunks if c)
    return str(content or "")


def _extract_response_text(resp: Any) -> str:
    if isinstance(resp, dict):
        msg = resp.get("choices", [{}])[0].get("message", {})
        return _content_to_text(msg.get("content", ""))
    try:
        return _content_to_text(resp.choices[0].message.content)
    except Exception:
        return str(resp)


def _extract_usage(resp: Any) -> UsageStats:
    usage = getattr(resp, "usage", None)
    if usage is None and isinstance(resp, dict):
        usage = resp.get("usage")
    if usage is None:
        return UsageStats(None, None, None)

    def _read(name: str) -> Optional[int]:
        if isinstance(usage, dict):
            val = usage.get(name)
        else:
            val = getattr(usage, name, None)
        return int(val) if val is not None else None

    prompt = _read("prompt_tokens")
    completion = _read("completion_tokens")
    total = _read("total_tokens")
    if total is None and prompt is not None and completion is not None:
        total = prompt + completion
    return UsageStats(prompt, completion, total)


def _safe_mean(values: list[Optional[float]]) -> Optional[float]:
    nums = [float(v) for v in values if v is not None]
    return float(np.mean(nums)) if nums else None


def _safe_sum(values: list[Optional[float]]) -> Optional[float]:
    nums = [float(v) for v in values if v is not None]
    return float(np.sum(nums)) if nums else None


def _load_pricing(path: Optional[str]) -> dict[str, dict[str, float]]:
    pricing = dict(PRICE_BOOK_USD_PER_1M)
    if not path:
        return pricing
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    for key, value in payload.items():
        if not isinstance(value, dict):
            continue
        pricing[key] = {
            "input": float(value["input"]),
            "output": float(value["output"]),
        }
    return pricing


def _estimate_cost_usd(
    model_key: str,
    usage: UsageStats,
    pricing: dict[str, dict[str, float]],
) -> Optional[float]:
    rates = pricing.get(model_key) or pricing.get(model_key.split(":", 1)[1])
    if not rates:
        return None
    if usage.prompt_tokens is None or usage.completion_tokens is None:
        return None
    return (
        float(usage.prompt_tokens) / 1_000_000.0 * float(rates["input"])
        + float(usage.completion_tokens) / 1_000_000.0 * float(rates["output"])
    )


def _extract_first_json_object(text: str) -> Optional[dict[str, Any]]:
    s = str(text or "").strip()
    if not s:
        return None
    try:
        obj = json.loads(s)
        return obj if isinstance(obj, dict) else None
    except Exception:
        pass

    start = s.find("{")
    if start < 0:
        return None

    depth = 0
    in_string = False
    escaped = False
    quote = ""
    for i in range(start, len(s)):
        ch = s[i]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == quote:
                in_string = False
            continue
        if ch in {'"', "'"}:
            in_string = True
            quote = ch
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    obj = json.loads(s[start : i + 1])
                    return obj if isinstance(obj, dict) else None
                except Exception:
                    return None
    return None


def _baseline_parser(raw_text: str, _ctx: dict[str, Any]) -> BaselineParsed:
    from baselines.llm_only import BaselineParsed, parse_llm_baseline_json

    obj, err = parse_llm_baseline_json(raw_text)
    if err:
        raise ValueError(err)
    parsed, err = BaselineParsed.from_json(obj or {})
    if err or parsed is None:
        raise ValueError(err or "baseline_parse_failed")
    return parsed


def _blueprint_parser(raw_text: str, ctx: dict[str, Any]) -> BaselineParsed:
    from baselines.llm_only import BaselineParsed
    from solver.llm_pf import validate_llm_output

    parsed = validate_llm_output(
        raw_text=str(raw_text or ""),
        m_file_path=str(ctx["m_file_path"]),
        case_name=str(ctx["case_name"]),
        debug_mode=bool(ctx.get("debug_mode", False)),
        relax_a2=True,
    )

    return BaselineParsed(
        converged=bool(parsed.converged),
        bus_vm={int(b.bus_id): float(b.vm_pu) for b in parsed.bus_voltages},
        bus_va={int(b.bus_id): float(b.va_deg) for b in parsed.bus_voltages},
        line_p={int(l.line_id): float(l.p_from_mw) for l in parsed.line_flows},
        line_loading={int(l.line_id): float(l.loading_percent or 0.0) for l in parsed.line_flows},
        line_ends={int(l.line_id): (int(l.from_bus), int(l.to_bus)) for l in parsed.line_flows},
        total_generation_mw=float(parsed.totals.total_generation_mw),
        total_load_mw=float(parsed.totals.total_load_mw),
        total_loss_mw=float(parsed.totals.total_loss_mw),
    )


def _build_baseline_messages(case_name: str) -> tuple[str, str]:
    from baselines.llm_only import build_baseline_prompt
    from baselines.prompts_baseline import BASELINE_SYSTEM_PROMPT
    from solver import case_loader

    net, _ = case_loader.load(case_name)
    return BASELINE_SYSTEM_PROMPT, build_baseline_prompt(case_name, net)


def _build_blueprint_messages(case_name: str) -> tuple[str, str]:
    from solver.llm_pf import build_matpower_prompt_messages
    from solver.matpower_text import get_case_m_path, read_case_m_text

    m_path = get_case_m_path(case_name)
    matpower_text = read_case_m_text(case_name)
    return build_matpower_prompt_messages(
        matpower_text=matpower_text,
        case_name=case_name,
        debug_mode=False,
    )


def _build_blueprint_context(case_name: str) -> dict[str, Any]:
    from solver.matpower_text import get_case_m_path

    return {
        "case_name": case_name,
        "m_file_path": str(get_case_m_path(case_name)),
        "debug_mode": False,
    }


TASKS: dict[str, TaskSpec] = {
    "baseline_pf": TaskSpec(
        name="baseline_pf",
        prompt_builder=_build_baseline_messages,
        response_parser=_baseline_parser,
    ),
    "blueprint_pf": TaskSpec(
        name="blueprint_pf",
        prompt_builder=_build_blueprint_messages,
        response_parser=_blueprint_parser,
        context_builder=_build_blueprint_context,
    ),
}


def _resolve_api_key(provider: str) -> str:
    p = str(provider).strip().lower()
    if p == "openai":
        return str(OPENAI_API_KEY or os.getenv("OPENAI_API_KEY") or "").strip()
    if p == "gemini":
        return str(GEMINI_API_KEY or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip()
    if p == "anthropic":
        return str(ANTHROPIC_API_KEY or os.getenv("ANTHROPIC_API_KEY") or "").strip()
    raise ValueError(f"Unsupported provider: {provider}")


def _resolve_base_url(provider: str) -> Optional[str]:
    return GEMINI_BASE_URL if str(provider).strip().lower() == "gemini" else None


def _call_model(
    client: Any,
    *,
    system_prompt: str,
    user_prompt: str,
    model: str,
    temperature: float,
    timeout_s: float,
) -> tuple[str, UsageStats, float]:
    t0 = time.time()
    resp = client.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=float(temperature),
        timeout=float(timeout_s),
    )
    return _extract_response_text(resp), _extract_usage(resp), float(time.time() - t0)


def _build_clients(models: list[ModelSpec]) -> dict[str, Any]:
    from llm.engine import AnthropicChatClient, OpenAIChatClient

    clients: dict[str, Any] = {}
    for spec in models:
        if spec.provider == "anthropic":
            clients[spec.key] = AnthropicChatClient(api_key=_resolve_api_key(spec.provider))
        else:
            clients[spec.key] = OpenAIChatClient(
                api_key=_resolve_api_key(spec.provider),
                base_url=_resolve_base_url(spec.provider),
            )
    return clients


def _aggregate_group(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ok_rows = [r for r in rows if r.get("ok")]
    scoreboard = {
        "success_rate": float(len(ok_rows) / len(rows)) if rows else 0.0,
        "voltage_mae_mean": _safe_mean([r.get("metrics", {}).get("voltage_mae") for r in ok_rows]),
        "flow_mae_mean": _safe_mean([r.get("metrics", {}).get("flow_mae") for r in ok_rows]),
        "loading_rmse_mean": _safe_mean([r.get("metrics", {}).get("loading_rmse") for r in ok_rows]),
        "voltage_f1_mean": _safe_mean([r.get("metrics", {}).get("voltage_f1") for r in ok_rows]),
        "thermal_f1_mean": _safe_mean([r.get("metrics", {}).get("thermal_f1") for r in ok_rows]),
        "convergence_match_rate": _safe_mean([
            1.0 if r.get("metrics", {}).get("convergence_match") else 0.0 for r in ok_rows
        ]),
        "prompt_tokens_mean": _safe_mean([r.get("usage", {}).get("prompt_tokens") for r in rows]),
        "completion_tokens_mean": _safe_mean([r.get("usage", {}).get("completion_tokens") for r in rows]),
        "total_tokens_mean": _safe_mean([r.get("usage", {}).get("total_tokens") for r in rows]),
        "cost_usd_mean": _safe_mean([r.get("cost_usd") for r in rows]),
        "cost_usd_total": _safe_sum([r.get("cost_usd") for r in rows]),
    }
    return scoreboard


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_markdown(path: Path, scoreboard: list[dict[str, Any]]) -> None:
    lines = [
        "# LLM Power-Flow Benchmark\n\n",
        "| model | task | success_rate | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total |\n",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|\n",
    ]
    for row in scoreboard:
        lines.append(
            f"| {row['model']} | {row['task']} | {row.get('success_rate')} | {row.get('voltage_mae_mean')} | "
            f"{row.get('flow_mae_mean')} | {row.get('loading_rmse_mean')} | {row.get('voltage_f1_mean')} | "
            f"{row.get('thermal_f1_mean')} | {row.get('convergence_match_rate')} | {row.get('prompt_tokens_mean')} | "
            f"{row.get('completion_tokens_mean')} | {row.get('total_tokens_mean')} | {row.get('cost_usd_mean')} | "
            f"{row.get('cost_usd_total')} |\n"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(lines), encoding="utf-8")


def _write_case_markdown(path: Path, scoreboard: list[dict[str, Any]]) -> None:
    lines = [
        "# LLM Power-Flow Benchmark (Per Case)\n\n",
        "| model | task | case | success_rate | voltage_mae | flow_mae | loading_rmse | voltage_f1 | thermal_f1 | conv_match | prompt_tokens | completion_tokens | total_tokens | cost_usd_mean | cost_usd_total |\n",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|\n",
    ]
    for row in scoreboard:
        lines.append(
            f"| {row['model']} | {row['task']} | {row['case_name']} | {row.get('success_rate')} | "
            f"{row.get('voltage_mae_mean')} | {row.get('flow_mae_mean')} | {row.get('loading_rmse_mean')} | "
            f"{row.get('voltage_f1_mean')} | {row.get('thermal_f1_mean')} | {row.get('convergence_match_rate')} | "
            f"{row.get('prompt_tokens_mean')} | {row.get('completion_tokens_mean')} | {row.get('total_tokens_mean')} | "
            f"{row.get('cost_usd_mean')} | {row.get('cost_usd_total')} |\n"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(lines), encoding="utf-8")


def run_benchmark(
    *,
    models: list[ModelSpec],
    tasks: list[str],
    cases: list[str],
    runs: int,
    temperature: float,
    timeout_s: float,
    pricing: dict[str, dict[str, float]],
    solver_config: Any,
) -> dict[str, Any]:
    from baselines.llm_only import evaluate_against_truth_extended
    from solver import case_loader
    from solver.power_flow import run_power_flow

    clients = _build_clients(models)
    raw_rows: list[dict[str, Any]] = []

    for model_spec in models:
        client = clients[model_spec.key]
        for task_name in tasks:
            task = TASKS[task_name]
            for case_name in cases:
                net, _ = case_loader.load(case_name)
                truth = run_power_flow(net, config=solver_config)
                if not truth.converged:
                    raise RuntimeError(f"Ground-truth solver did not converge for {case_name}")
                system_prompt, user_prompt = task.prompt_builder(case_name)
                parser_ctx = task.context_builder(case_name) if task.context_builder else {}

                for run_idx in range(runs):
                    print(f"{task_name} {case_name} run ID: {run_idx}")
                    raw_text: Optional[str] = None
                    usage = UsageStats(None, None, None)
                    latency_s: Optional[float] = None
                    try:
                        raw_text, usage, latency_s = _call_model(
                            client,
                            system_prompt=system_prompt,
                            user_prompt=user_prompt,
                            model=model_spec.model,
                            temperature=temperature,
                            timeout_s=timeout_s,
                        )
                        parsed = task.response_parser(raw_text, parser_ctx)
                        metrics = evaluate_against_truth_extended(
                            parsed,
                            truth,
                            net=net,
                            v_min=solver_config.v_min,
                            v_max=solver_config.v_max,
                            max_loading=solver_config.max_loading,
                        )
                        error = None
                        ok = True
                    except Exception as exc:
                        metrics = None
                        error = f"{type(exc).__name__}: {exc}"
                        ok = False

                    cost_usd = _estimate_cost_usd(model_spec.key, usage, pricing)
                    raw_rows.append(
                        {
                            "model": model_spec.key,
                            "provider": model_spec.provider,
                            "task": task.name,
                            "case_name": case_name,
                            "run": int(run_idx),
                            "ok": bool(ok),
                            "error": error,
                            "latency_s": latency_s,
                            "usage": {
                                "prompt_tokens": usage.prompt_tokens,
                                "completion_tokens": usage.completion_tokens,
                                "total_tokens": usage.total_tokens,
                            },
                            "cost_usd": cost_usd,
                            "metrics": metrics,
                            "raw_response": raw_text,
                        }
                    )

    scoreboard_rows: list[dict[str, Any]] = []
    scoreboard_case_rows: list[dict[str, Any]] = []
    by_group: dict[tuple[str, str], list[dict[str, Any]]] = {}
    by_case_group: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for row in raw_rows:
        by_group.setdefault((row["model"], row["task"]), []).append(row)
        by_case_group.setdefault((row["model"], row["task"], row["case_name"]), []).append(row)

    for (model_key, task_name), rows in sorted(by_group.items()):
        agg = _aggregate_group(rows)
        scoreboard_rows.append({"model": model_key, "task": task_name, **agg})

    for (model_key, task_name, case_name), rows in sorted(by_case_group.items()):
        agg = _aggregate_group(rows)
        scoreboard_case_rows.append(
            {"model": model_key, "task": task_name, "case_name": case_name, **agg}
        )

    return {
        "config": {
            "models": [m.key for m in models],
            "tasks": tasks,
            "cases": cases,
            "runs": runs,
            "temperature": temperature,
            "timeout_s": timeout_s,
            "solver_config": {
                "v_min": solver_config.v_min,
                "v_max": solver_config.v_max,
                "max_loading": solver_config.max_loading,
            },
        },
        "core_scoreboard_fields": CORE_SCOREBOARD_FIELDS,
        "scoreboard": scoreboard_rows,
        "scoreboard_per_case": scoreboard_case_rows,
        "runs": raw_rows,
    }


def _flatten_scoreboard(scoreboard: list[dict[str, Any]]) -> list[dict[str, Any]]:
    flat: list[dict[str, Any]] = []
    for row in scoreboard:
        flat.append({k: row.get(k) for k in ["model", "task", *CORE_SCOREBOARD_FIELDS]})
    return flat


def _flatten_case_scoreboard(scoreboard: list[dict[str, Any]]) -> list[dict[str, Any]]:
    flat: list[dict[str, Any]] = []
    for row in scoreboard:
        flat.append({k: row.get(k) for k in ["model", "task", *CASE_SCOREBOARD_FIELDS]})
    return flat


def _parse_model_specs(values: list[str]) -> list[ModelSpec]:
    if not values:
        values = [f"openai:{OPENAI_MODEL}", f"gemini:{GEMINI_MODEL}"]
    specs: list[ModelSpec] = []
    for raw in values:
        provider, sep, model = raw.partition(":")
        if not sep or not model:
            raise ValueError(f"Invalid model spec: {raw}. Expected provider:model")
        specs.append(ModelSpec(provider=provider.strip().lower(), model=model.strip()))
    return specs


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Benchmark multiple LLMs on power-flow tasks.")
    parser.add_argument("--model", dest="models", action="append", default=[], help="provider:model, repeatable")
    parser.add_argument("--task", dest="tasks", action="append", choices=sorted(TASKS.keys()), default=[], help="repeatable")
    parser.add_argument("--case", dest="cases", action="append", default=[], help="repeatable")
    parser.add_argument("--runs", dest="runs", type=int, default=1)
    parser.add_argument("--temperature", dest="temperature", type=float, default=0.0)
    parser.add_argument("--timeout-s", dest="timeout_s", type=float, default=90.0)
    parser.add_argument("--pricing-file", dest="pricing_file", default=None)
    parser.add_argument("--out-dir", dest="out_dir", default=DEFAULT_OUT_DIR)

    args = parser.parse_args(argv)

    models = _parse_model_specs(args.models)
    tasks = args.tasks or ["baseline_pf", "blueprint_pf"]
    cases = args.cases or ["case14", "case30", "case57"]
    pricing = _load_pricing(args.pricing_file)
    from solver.power_flow import SolverConfig

    solver_config = SolverConfig()

    report = run_benchmark(
        models=models,
        tasks=tasks,
        cases=cases,
        runs=int(args.runs),
        temperature=float(args.temperature),
        timeout_s=float(args.timeout_s),
        pricing=pricing,
        solver_config=solver_config,
    )

    out_dir = Path(args.out_dir)
    _write_json(out_dir / "report.json", report)
    _write_json(out_dir / "scoreboard.json", report["scoreboard"])
    _write_csv(out_dir / "scoreboard.csv", _flatten_scoreboard(report["scoreboard"]))
    _write_markdown(out_dir / "scoreboard.md", report["scoreboard"])
    _write_json(out_dir / "scoreboard_per_case.json", report["scoreboard_per_case"])
    _write_csv(out_dir / "scoreboard_per_case.csv", _flatten_case_scoreboard(report["scoreboard_per_case"]))
    _write_case_markdown(out_dir / "scoreboard_per_case.md", report["scoreboard_per_case"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
