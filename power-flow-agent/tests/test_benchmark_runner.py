import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from benchmarks.evaluate_llms import (
    DEFAULT_REQUEST_TEXT,
    ModelSpec,
    UsageStats,
    _aggregate_group,
    _build_baseline_messages,
    _estimate_cost_usd,
    _flatten_scoreboard,
    build_items,
    main,
    parse_method,
    perturbed_case,
    run_benchmark,
)
from llm.engine import LLMClient
from solver import case_loader
from solver.power_flow import SolverConfig, run_power_flow

FAKE_MODEL = ModelSpec(provider="fake", model="scripted")
PRICING = {"fake:scripted": {"input": 1.0, "output": 2.0}}


# ----------------------------------------------------------------------------- pre-R1 tests (unchanged)


def test_estimate_cost_usd_uses_prompt_and_completion_tokens():
    pricing = {"openai:gpt-4o-mini": {"input": 0.15, "output": 0.60}}
    usage = UsageStats(prompt_tokens=1000, completion_tokens=500, total_tokens=1500)
    cost = _estimate_cost_usd("openai:gpt-4o-mini", usage, pricing)
    assert cost == pytest.approx(0.00045)


def test_aggregate_group_includes_token_and_core_metrics():
    rows = [
        {
            "ok": True,
            "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
            "cost_usd": 0.001,
            "metrics": {
                "voltage_mae": 0.01,
                "flow_mae": 1.0,
                "loading_rmse": 2.0,
                "voltage_f1": 0.8,
                "thermal_f1": 0.5,
                "convergence_match": True,
            },
        },
        {
            "ok": False,
            "usage": {"prompt_tokens": 120, "completion_tokens": 30, "total_tokens": 150},
            "cost_usd": 0.002,
            "metrics": None,
        },
    ]
    agg = _aggregate_group(rows)
    assert agg["success_rate"] == pytest.approx(0.5)
    assert agg["voltage_mae_mean"] == pytest.approx(0.01)
    assert agg["prompt_tokens_mean"] == pytest.approx(110.0)
    assert agg["completion_tokens_mean"] == pytest.approx(40.0)
    assert agg["total_tokens_mean"] == pytest.approx(150.0)
    assert agg["cost_usd_total"] == pytest.approx(0.003)


def test_flatten_scoreboard_keeps_core_fields():
    flat = _flatten_scoreboard([
        {
            "model": "openai:gpt-4o-mini",
            "task": "baseline_pf",
            "success_rate": 1.0,
            "voltage_mae_mean": 0.01,
            "flow_mae_mean": 1.0,
            "loading_rmse_mean": 2.0,
            "voltage_f1_mean": 0.8,
            "thermal_f1_mean": 0.7,
            "convergence_match_rate": 1.0,
            "prompt_tokens_mean": 100.0,
            "completion_tokens_mean": 50.0,
            "total_tokens_mean": 150.0,
            "cost_usd_mean": 0.001,
            "cost_usd_total": 0.002,
        }
    ])
    assert flat[0]["model"] == "openai:gpt-4o-mini"
    assert flat[0]["task"] == "baseline_pf"
    assert flat[0]["cost_usd_total"] == pytest.approx(0.002)


# ----------------------------------------------------------------------------- fakes


def _tool_call(call_id, name, args):
    return {"id": call_id, "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}


def _resp(content=None, tool_calls=None):
    msg = {"role": "assistant", "content": content}
    if tool_calls:
        msg["tool_calls"] = tool_calls
    return {"choices": [{"message": msg}], "usage": {"prompt_tokens": 100, "completion_tokens": 10}}


def _last_pf(messages):
    """The last tool message that carries a power-flow payload."""
    for m in reversed(messages):
        if m.get("role") == "tool":
            try:
                obj = json.loads(m["content"])
            except Exception:
                continue
            if isinstance(obj, dict) and "total_load_mw" in obj:
                return obj
    return None


class FakeAgentClient(LLMClient):
    """Scripted LLM: loads the case, runs the flow, then echoes tool numbers.

    Works for react (tool calls then answer), single_call (tool calls, then a
    final call without tools) and plan_act (JSON plan, then answer). ``modify``
    optionally injects a wrong bus id to exercise the formulation metric.
    """

    def __init__(self, *, wrong_bus=False, hallucinate=False):
        self.calls = []
        self.wrong_bus = wrong_bus
        self.hallucinate = hallucinate

    def _plan_for(self, messages):
        user = [m for m in messages if m["role"] == "user"][0]["content"]
        preloaded = "is loaded" in user or "Single-call mode" in "".join(m["content"] or "" for m in messages if m["role"] == "system")
        steps = [] if preloaded else [("load_case", {"case_name": "case14"})]
        if "set the active load at bus" in user:
            import re

            m = re.search(r"bus (\d+) to ([\d.]+)", user)
            bus, p = int(m.group(1)), float(m.group(2))
            steps.append(("modify_load", {"bus_id": bus + (1 if self.wrong_bus else 0), "p_mw": p}))
        steps.append(("run_powerflow", {}))
        return steps

    def create(self, **kwargs):
        messages = kwargs["messages"]
        self.calls.append({"messages": [dict(m) for m in messages], "tools": kwargs.get("tools")})
        system = "".join(m["content"] or "" for m in messages if m["role"] == "system")
        has_tool_msgs = any(m.get("role") == "tool" for m in messages)

        if "planner" in system and not has_tool_msgs:  # plan_act planning call
            plan = [{"tool": t, "args": a} for t, a in self._plan_for(messages)]
            return _resp(content=json.dumps({"plan": plan}))
        if not has_tool_msgs:  # first react / single_call round
            calls = [_tool_call(f"c{i}", t, a) for i, (t, a) in enumerate(self._plan_for(messages))]
            return _resp(tool_calls=calls)

        pf = _last_pf(messages)
        if pf is None or not pf.get("converged"):
            return _resp(content="The power flow did not converge; no verified numbers are available.")
        if self.hallucinate:
            return _resp(content="Power flow converged. Total load 999.000 MW, losses 77.7 MW.")
        return _resp(
            content=(
                f"Power flow converged. Total load {pf['total_load_mw']:.3f} MW, generation "
                f"{pf['total_generation_mw']:.3f} MW, losses {pf['total_loss_mw']:.3f} MW."
            )
        )


class FakeLLMOnlyClient(LLMClient):
    """Returns a schema-valid baseline JSON (numbers are made up) and records the prompt."""

    def __init__(self):
        self.prompts = []

    def create(self, **kwargs):
        self.prompts.append(kwargs["messages"][1]["content"])
        payload = {
            "converged": True,
            "bus_voltages": [{"bus_id": 1, "vm_pu": 1.06, "va_deg": 0.0}, {"bus_id": 2, "vm_pu": 1.045, "va_deg": -4.98}],
            "line_flows": [{"line_id": 0, "p_from_mw": 156.9, "loading_percent": 60.0}],
            "total_generation_mw": 272.4,
            "total_load_mw": 259.0,
            "total_loss_mw": 13.4,
        }
        return _resp(content=json.dumps(payload))


def _run(methods, client, **kw):
    params = dict(
        models=[FAKE_MODEL],
        methods=methods,
        cases=["case14"],
        runs=1,
        temperature=0.0,
        timeout_s=10.0,
        pricing=PRICING,
        solver_config=SolverConfig(),
        client_factory=lambda spec: client,
        verbose=False,
    )
    params.update(kw)
    return run_benchmark(**params)


# ----------------------------------------------------------------------------- perturbation & seeds


def test_perturbation_differs_across_seeds_and_repeats_for_same_seed():
    base, _ = case_loader.load("case14")
    a = perturbed_case("case14", seed=1, k=1)
    b = perturbed_case("case14", seed=2, k=1)
    a_again = perturbed_case("case14", seed=1, k=1)
    assert a.load["p_mw"].tolist() != b.load["p_mw"].tolist()
    assert a.load["p_mw"].tolist() == a_again.load["p_mw"].tolist()
    assert a.load["p_mw"].tolist() != base.load["p_mw"].tolist()
    # +/-10 % for k=1
    ratio = a.load["p_mw"] / base.load["p_mw"]
    assert ratio.between(0.9, 1.1).all()


def test_k0_reproduces_unperturbed_base_case_exactly():
    base, _ = case_loader.load("case14")
    for seed in (0, 7):
        net = perturbed_case("case14", seed=seed, k=0)
        assert net.load["p_mw"].tolist() == base.load["p_mw"].tolist()
        assert net.load["q_mvar"].tolist() == base.load["q_mvar"].tolist()
        assert net.gen["p_mw"].tolist() == base.gen["p_mw"].tolist()

    items = build_items("case14", seed=0, k=0, solver_config=SolverConfig())
    assert len(items) == 1 and items[0].seed == 0 and items[0].k == 0
    truth_base = run_power_flow(base, config=SolverConfig())
    assert items[0].truth.total_load_mw == pytest.approx(truth_base.total_load_mw)
    assert [b.vm_pu for b in items[0].truth.bus_voltages] == pytest.approx([b.vm_pu for b in truth_base.bus_voltages])


def test_ground_truth_and_method_see_the_same_perturbed_net():
    client = FakeAgentClient()
    report = _run(["react"], client, k=1, seeds=[3])
    row = report["runs"][0]
    assert row["ok"] and row["k"] == 1 and row["seed"] == 3
    # the agent's final state equals the truth on the perturbed case: zero error
    assert row["metrics"]["voltage_mae"] == pytest.approx(0.0, abs=1e-9)
    assert row["metrics"]["flow_mae"] == pytest.approx(0.0, abs=1e-9)
    # ...and that truth is not the base case
    base_truth = run_power_flow(case_loader.load("case14")[0], config=SolverConfig())
    pf = _last_pf(client.calls[-1]["messages"])
    assert pf["total_load_mw"] != pytest.approx(base_truth.total_load_mw)
    assert report["config"]["k"] == 1 and report["config"]["seeds"] == [3]


# ----------------------------------------------------------------------------- legacy path


def test_k0_seed0_legacy_task_reproduces_old_prompt_and_row_shape():
    client = FakeLLMOnlyClient()
    report = _run(["baseline_pf"], client, tasks=None, k=0, seeds=[0])
    _, old_prompt = _build_baseline_messages("case14")  # pre-R1 builder (fresh base case)
    assert client.prompts == [old_prompt]
    row = report["runs"][0]
    for key in ("model", "provider", "task", "case_name", "run", "ok", "error", "latency_s", "usage", "cost_usd", "metrics", "raw_response"):
        assert key in row
    assert row["task"] == "baseline_pf" and row["ok"] is True and row["k"] == 0 and row["seed"] == 0
    assert row["metrics"]["voltage_mae"] is not None
    assert row["cost_usd"] == pytest.approx(100 / 1e6 * 1.0 + 10 / 1e6 * 2.0)
    assert report["config"]["tasks"] == ["baseline_pf"] and report["scoreboard"][0]["task"] == "baseline_pf"
    # legacy keyword still accepted
    again = run_benchmark(
        models=[FAKE_MODEL], tasks=["baseline_pf"], cases=["case14"], runs=1, temperature=0.0, timeout_s=10.0,
        pricing=PRICING, solver_config=SolverConfig(), client_factory=lambda spec: client, verbose=False,
    )
    assert again["runs"][0]["task"] == "baseline_pf"


def test_k1_changes_the_llm_only_prompt():
    client = FakeLLMOnlyClient()
    _run(["baseline_pf"], client, k=1, seeds=[0])
    _, base_prompt = _build_baseline_messages("case14")
    assert client.prompts[0] != base_prompt


def test_blueprint_pf_refuses_perturbation():
    with pytest.raises(SystemExit):
        main(["--task", "blueprint_pf", "--k", "1", "--case", "case14", "--out-dir", "/nonexistent"])


# ----------------------------------------------------------------------------- methods


def test_parse_method_covers_all_families():
    assert parse_method("baseline_pf").kind == "task"
    assert parse_method("rule_based").uses_llm is False
    sc = parse_method("single_call:rag")
    assert sc.kind == "engine" and sc.architecture == "single_call" and sc.preload_case and sc.strategy == "rag"
    lo = parse_method("llm_only:cot")
    assert lo.kind == "llm_only" and lo.strategy == "cot"
    assert parse_method("react_nogate").gate is False
    assert parse_method("pfagent").memory is True and parse_method("pfagent").gate is False
    assert parse_method("pfagent").final_gate is True
    assert parse_method("pfagent_obsgate").gate is True and parse_method("pfagent_obsgate").final_gate is False
    assert parse_method("plan_act").architecture == "plan_act"
    with pytest.raises(ValueError):
        parse_method("single_call:zero_shot")
    with pytest.raises(ValueError):
        parse_method("swarm")


@pytest.mark.parametrize("method", ["react", "react_nogate", "pfagent", "plan_act", "single_call:structured", "single_call:rag"])
def test_agent_methods_run_end_to_end_with_scripted_client(method):
    client = FakeAgentClient()
    report = _run([method], client, k=1, seeds=[0], max_rounds=4)
    row = report["runs"][0]
    assert row["method"] == method and row["ok"] is True, row["error"]
    assert row["formulation_exact"] is True and row["formulation_error_type"] == "ok"
    assert row["faithful_numbers"] == 1.0 and row["n_untraceable_numbers"] == 0
    assert row["final_converged"] is True and row["safe_failure"] is None
    assert row["n_llm_calls"] >= 1 and row["n_tool_calls"] >= 1
    assert row["usage"]["prompt_tokens"] == 100 * row["n_llm_calls"]
    assert row["trace"]["max_rounds"] == 4
    if method.startswith("single_call"):
        assert "tools" in client.calls[0] and client.calls[0]["tools"]
        assert row["executed_calls"][0]["tool"] != "load_case"  # preloaded
    if method == "plan_act":
        assert row["trace"]["plan"] is not None
    agg = report["scoreboard"][0]
    assert agg["formulation_exact_rate"] == 1.0 and agg["formulation_exact_count"] == 1
    assert agg["n_llm_calls_mean"] == row["n_llm_calls"]


def test_wrong_bus_id_is_a_formulation_error_not_a_solve_error():
    from benchmarks.requests import Request

    # A modify_load request; the fake agent shifts the bus id by one.
    intended = [
        {"tool": "load_case", "args": {"case_name": "case14"}},
        {"tool": "modify_load", "args": {"bus_id": 9, "p_mw": 29.5}},
    ]
    req = Request(id="r1", case_name="case14", seed=5, difficulty="parameterized",
                  text="Load case14 and set the active load at bus 9 to 29.5 MW.", intended_calls=intended)
    items = build_items("case14", seed=0, k=1, solver_config=SolverConfig(), requests=[req])
    assert len(items) == 1 and items[0].seed == 5 and items[0].request_id == "r1"

    from benchmarks.evaluate_llms import evaluate_item

    row = evaluate_item(method=parse_method("react"), model_spec=FAKE_MODEL, client=FakeAgentClient(wrong_bus=True), item=items[0],
                        run_idx=0, temperature=0.0, timeout_s=10.0, pricing=PRICING, solver_config=SolverConfig())
    assert row["formulation_exact"] is False and row["formulation_error_type"] == "wrong_id"
    assert row["ok"] is True  # it did solve something, just not the intended state
    assert row["metrics"]["voltage_mae"] > 0.0  # ...and the numbers differ from the intended truth
    assert row["faithful_numbers"] == 1.0  # numbers reported faithfully from its own tool outputs

    good = evaluate_item(method=parse_method("react"), model_spec=FAKE_MODEL, client=FakeAgentClient(), item=items[0],
                         run_idx=0, temperature=0.0, timeout_s=10.0, pricing=PRICING, solver_config=SolverConfig())
    assert good["formulation_exact"] is True and good["metrics"]["voltage_mae"] == pytest.approx(0.0, abs=1e-9)


def test_hallucinated_numbers_lower_faithfulness():
    report = _run(["react"], FakeAgentClient(hallucinate=True), k=0, seeds=[0])
    row = report["runs"][0]
    assert row["formulation_exact"] is True
    assert row["faithful_numbers"] == 0.0 and row["n_untraceable_numbers"] == 2
    assert report["scoreboard"][0]["faithful_numbers_mean"] == 0.0


def test_llm_only_strategy_methods_use_prompt_variants():
    client = FakeLLMOnlyClient()
    report = _run(["llm_only:structured", "llm_only:rag"], client, k=0, seeds=[0])
    rows = {r["method"]: r for r in report["runs"]}
    assert set(rows) == {"llm_only:structured", "llm_only:rag"}
    assert all(r["ok"] for r in rows.values())
    assert all(r["formulation_exact"] is None for r in rows.values())  # no tool stage
    assert all(r["n_tool_calls"] == 0 and r["n_llm_calls"] == 1 for r in rows.values())
    assert DEFAULT_REQUEST_TEXT.format(case_name="case14") in client.prompts[0]
    assert len(client.prompts[1]) < len(client.prompts[0])  # rag context is shorter


# ----------------------------------------------------------------------------- rule-based end to end + CLI


def test_rule_based_end_to_end_on_generated_case14_requests(tmp_path):
    out_dir = tmp_path / "rb"
    rc = main(["--method", "rule_based", "--case", "case14", "--gen-requests", "2", "--seeds", "1",
               "--out-dir", str(out_dir), "--quiet"])
    assert rc == 0
    report = json.loads((out_dir / "report.json").read_text(encoding="utf-8"))
    assert report["config"]["k"] == 1 and report["config"]["seeds"] == [0] and report["config"]["methods"] == ["rule_based"]
    assert report["config"]["requests"]["n_per_case_seed"] == 2
    rows = report["runs"]
    assert len(rows) == 2
    for row in rows:
        assert row["model"] == "none:rule_based" and row["k"] == 1 and row["request_id"].startswith("case14-")
        assert row["seed"] == int(row["seed"]) and row["gen_seed"] == 0
        assert row["n_llm_calls"] == 0 and row["cost_usd"] == 0.0
        assert row["formulation_error_type"] in ("ok", "wrong_id", "wrong_unit_or_value", "missed_step", "extra_step", "unparsed")
        assert row["intended_calls"][0]["tool"] == "load_case"
    sb = report["scoreboard"][0]
    assert sb["n_items"] == 2 and sb["formulation_exact_total"] == 2
    assert sum(sb["formulation_error_counts"].values()) == 2
    for name in ("scoreboard.md", "scoreboard_per_case.md", "scoreboard.csv", "scoreboard.json"):
        assert (out_dir / name).exists()
    md = (out_dir / "scoreboard.md").read_text(encoding="utf-8")
    assert "formulation_exact" in md and "rule_based" in md

    # the comparison script still reads the new report (and picks up the new columns)
    from scripts.compare_reports import DEFAULT_FIELDS, main as compare_main

    cmp_out = tmp_path / "cmp"
    assert compare_main(["--dir", str(out_dir), "--out-dir", str(cmp_out), "--out-json", str(cmp_out / "c.json")]) == 0
    cmp_rows = json.loads((cmp_out / "c.json").read_text(encoding="utf-8"))
    assert cmp_rows[0]["task"] == "rule_based" and "success_rate" in cmp_rows[0]
    assert "formulation_exact_rate" in DEFAULT_FIELDS and cmp_rows[0]["k"] == 1


def test_compare_reports_still_reads_committed_pre_r1_report(tmp_path):
    from scripts.compare_reports import main as compare_main

    old_dir = PROJECT_ROOT / "benchmarks" / "results_gpt_4o_mini"
    if not (old_dir / "report.json").exists():
        pytest.skip("committed report not present")
    out = tmp_path / "cmp_old"
    assert compare_main(["--dir", str(old_dir), "--out-dir", str(out), "--out-json", str(out / "c.json")]) == 0
    rows = json.loads((out / "c.json").read_text(encoding="utf-8"))
    assert rows and rows[0]["success_rate"] is not None and rows[0]["formulation_exact_rate"] is None
