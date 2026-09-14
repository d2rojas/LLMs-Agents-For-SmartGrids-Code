"""Engine architecture / gate / trace tests (no network, no API keys).

Uses a scripted FakeClient and a scripted ToolDispatcher so behaviour of the
react / single_call / plan_act loops and the verification gate can be checked
independently of PandaPower. One test runs plan_act end to end on case14.
"""

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from llm.engine import (
    MAX_ROUNDS_EXCEEDED_TEXT,
    PLAN_UNPARSEABLE_TEXT,
    EngineConfig,
    LLMClient,
    LLMEngine,
    gate_verdict,
    parse_plan,
)
from llm.tools import ToolContext, ToolDispatcher, build_default_dispatcher
from models.schemas import SessionState


# ----------------------------------------------------------------------------- fakes


def _tool_call(call_id: str, name: str, args: dict) -> dict:
    return {"id": call_id, "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}


def _resp(content=None, tool_calls=None, usage=None) -> dict:
    msg = {"role": "assistant", "content": content}
    if tool_calls:
        msg["tool_calls"] = tool_calls
    out = {"choices": [{"message": msg}]}
    if usage:
        out["usage"] = usage
    return out


class ScriptedClient(LLMClient):
    """Returns scripted responses in order; the last one repeats forever."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []  # kwargs of each create() call

    def create(self, **kwargs):
        # snapshot: the engine keeps appending to the same messages list
        kwargs = dict(kwargs, messages=[dict(m) for m in kwargs["messages"]])
        self.calls.append(kwargs)
        idx = min(len(self.calls) - 1, len(self.responses) - 1)
        return self.responses[idx]


def _pf_payload(converged=True, load=259.0, gen=272.0, loss=13.0, vm=0.97) -> dict:
    return {
        "case_name": "fake",
        "converged": converged,
        "bus_voltages": [{"bus_id": 1, "vm_pu": vm, "va_deg": 0.0, "is_violation": False, "violation_type": None}],
        "line_flows": [],
        "total_generation_mw": gen,
        "total_load_mw": load,
        "total_loss_mw": loss,
        "voltage_violations": [],
        "thermal_violations": [],
        "summary_text": "",
        "solver_backend": "fake",
    }


class ScriptedTools:
    """Dispatcher handlers that count calls and return a configurable PF payload."""

    def __init__(self, pf_payload=None):
        self.calls = []
        self.pf_payload = pf_payload or _pf_payload()

    def dispatcher(self) -> ToolDispatcher:
        def load_case(args):
            self.calls.append(("load_case", dict(args)))
            return {"case_name": args.get("case_name"), "n_buses": 14}

        def run_powerflow(args):
            self.calls.append(("run_powerflow", dict(args)))
            return self.pf_payload

        def get_status(args):
            self.calls.append(("get_status", dict(args)))
            return {"active_case": "fake", "has_last_result": True}

        return ToolDispatcher(handlers={"load_case": load_case, "run_powerflow": run_powerflow, "get_status": get_status})


# ----------------------------------------------------------------------------- config


def test_engine_config_defaults_reproduce_previous_behaviour():
    cfg = EngineConfig()
    assert cfg.architecture == "react"
    assert cfg.max_tool_rounds == 8
    assert cfg.max_rounds == 8
    assert cfg.gate is True
    assert cfg.memory is True

    assert EngineConfig(max_rounds=3).max_tool_rounds == 3
    assert EngineConfig(max_tool_rounds=5).max_rounds == 5
    with pytest.raises(ValueError):
        EngineConfig(architecture="swarm")


# ----------------------------------------------------------------------------- react


def test_react_performs_multiple_rounds_and_stops_at_max_rounds():
    tools = ScriptedTools()
    client = ScriptedClient([_resp(tool_calls=[_tool_call("c1", "get_status", {})])])  # always asks for a tool
    engine = LLMEngine(client=client, dispatcher=tools.dispatcher(), config=EngineConfig(model="fake", max_rounds=3))
    session = SessionState()

    text, trace = engine.run_with_trace("loop forever", session)

    assert text == MAX_ROUNDS_EXCEEDED_TEXT
    assert trace["status"] == "max_rounds"
    assert trace["n_tool_rounds"] == 3
    assert trace["n_llm_calls"] == 3
    assert len(tools.calls) == 3
    assert all("tools" in c for c in client.calls)  # react always offers tool definitions
    assert [r["round"] for r in trace["rounds"]] == [1, 2, 3]
    assert trace["rounds"][0]["tools"][0]["name"] == "get_status"
    assert session.conversation_history[-1] == {"role": "assistant", "content": MAX_ROUNDS_EXCEEDED_TEXT}


def test_react_default_history_shape_and_trace_usage():
    tools = ScriptedTools()
    client = ScriptedClient(
        [
            _resp(
                tool_calls=[_tool_call("c1", "load_case", {"case_name": "case14"}), _tool_call("c2", "run_powerflow", {})],
                usage={"prompt_tokens": 100, "completion_tokens": 10},
            ),
            _resp(content="Total load 259.000 MW.", usage={"prompt_tokens": 300, "completion_tokens": 20}),
        ]
    )
    engine = LLMEngine(client=client, dispatcher=tools.dispatcher(), config=EngineConfig(model="fake"))
    session = SessionState()

    text, trace = engine.run_with_trace("run case14", session)

    assert text == "Total load 259.000 MW."
    roles = [m["role"] for m in session.conversation_history]
    # identical to the pre-R1 loop: user, assistant(tool_calls), tool, tool, assistant(final)
    assert roles == ["user", "assistant", "tool", "tool", "assistant"]
    assert trace["prompt_tokens"] == 400 and trace["completion_tokens"] == 30
    assert trace["n_llm_calls"] == 2 and trace["n_tool_calls"] == 2 and trace["n_tool_rounds"] == 1
    assert trace["gate_checked"] == 1 and trace["gate_failed"] == 0 and trace["gate_enforced"] == 0
    assert trace["wall_time_s"] >= 0.0
    assert engine.run("again", SessionState()) == "Total load 259.000 MW."  # run() still returns str


# ----------------------------------------------------------------------------- single_call


def test_single_call_does_one_tool_round_and_one_final_call():
    tools = ScriptedTools()
    # The fake keeps returning tool calls forever; single_call must not obey after round 1.
    client = ScriptedClient(
        [_resp(content="I will run the power flow.", tool_calls=[_tool_call("c1", "run_powerflow", {}), _tool_call("c2", "get_status", {})])]
    )
    engine = LLMEngine(
        client=client, dispatcher=tools.dispatcher(), config=EngineConfig(model="fake", architecture="single_call", max_rounds=8)
    )
    session = SessionState()
    session.conversation_history = [{"role": "user", "content": "old"}, {"role": "assistant", "content": "old answer"}]

    text, trace = engine.run_with_trace("run pf", session)

    assert len(client.calls) == 2
    assert "tools" in client.calls[0] and client.calls[0]["tool_choice"] == "auto"
    assert "tools" not in client.calls[1] and "tool_choice" not in client.calls[1]
    assert len(tools.calls) == 2  # both tool calls of the single round, nothing more
    assert trace["n_tool_rounds"] == 1 and trace["n_llm_calls"] == 2
    # the second response's tool_calls are ignored; its content is the answer
    assert text == "I will run the power flow."
    # no memory: prior history is not sent to the LLM
    sent_roles = [m["role"] for m in client.calls[0]["messages"]]
    assert sent_roles == ["system", "user"]
    assert trace["architecture"] == "single_call"


def test_single_call_direct_answer_needs_no_second_call():
    tools = ScriptedTools()
    client = ScriptedClient([_resp(content="Hello.")])
    engine = LLMEngine(client=client, dispatcher=tools.dispatcher(), config=EngineConfig(model="fake", architecture="single_call"))
    text, trace = engine.run_with_trace("hi", SessionState())
    assert text == "Hello." and trace["n_llm_calls"] == 1 and tools.calls == []


# ----------------------------------------------------------------------------- plan_act


def test_parse_plan_is_tolerant():
    plan = [{"tool": "load_case", "args": {"case_name": "case14"}}, {"tool": "run_powerflow", "args": {}}]
    assert parse_plan(json.dumps({"plan": plan})) == plan
    assert parse_plan(json.dumps(plan)) == plan
    assert parse_plan("Sure! ```json\n" + json.dumps({"steps": plan}) + "\n```") == plan
    assert parse_plan('[{"tool": "run_powerflow"}]') == [{"tool": "run_powerflow", "args": {}}]
    assert parse_plan("I would first load the case and then run the power flow.") is None
    assert parse_plan('{"plan": [{"args": {}}]}') is None
    assert parse_plan("") is None


def test_plan_act_executes_plan_without_intermediate_llm_calls():
    tools = ScriptedTools()
    plan = {"plan": [{"tool": "load_case", "args": {"case_name": "case14"}}, {"tool": "run_powerflow", "args": {}}]}
    client = ScriptedClient([_resp(content=json.dumps(plan)), _resp(content="Done: load 259.000 MW.")])
    engine = LLMEngine(client=client, dispatcher=tools.dispatcher(), config=EngineConfig(model="fake", architecture="plan_act"))
    session = SessionState()

    text, trace = engine.run_with_trace("load case14 and run pf", session)

    assert text == "Done: load 259.000 MW."
    assert len(client.calls) == 2  # plan + answer only
    assert all("tools" not in c for c in client.calls)  # plan_act never sends tool definitions
    assert [c[0] for c in tools.calls] == ["load_case", "run_powerflow"]
    assert trace["plan"] == plan["plan"]
    assert trace["formulation_failure"] is False
    assert [r.get("phase") for r in trace["rounds"]] == ["plan", "act", "answer"]
    assert len(trace["rounds"][1]["tools"]) == 2
    # the final call sees the tool outputs
    final_roles = [m["role"] for m in client.calls[1]["messages"]]
    assert final_roles.count("tool") == 2


def test_plan_act_unparseable_plan_is_a_safe_formulation_failure():
    tools = ScriptedTools()
    client = ScriptedClient([_resp(content="Let me think about which tools to use...")])
    engine = LLMEngine(client=client, dispatcher=tools.dispatcher(), config=EngineConfig(model="fake", architecture="plan_act"))
    session = SessionState()

    text, trace = engine.run_with_trace("do something", session)

    assert text == PLAN_UNPARSEABLE_TEXT
    assert trace["status"] == "plan_unparseable"
    assert trace["formulation_failure"] is True
    assert trace["plan"] is None
    assert tools.calls == []  # nothing executed
    assert len(client.calls) == 1
    assert session.conversation_history[-1]["content"] == PLAN_UNPARSEABLE_TEXT


def test_plan_act_end_to_end_on_case14_with_real_dispatcher():
    session = SessionState()
    ctx = ToolContext(session=session)
    plan = {"plan": [{"tool": "load_case", "args": {"case_name": "case14"}}, {"tool": "run_powerflow", "args": {}}]}

    class Client(ScriptedClient):
        def create(self, **kwargs):
            if len(self.calls) == 1:  # final call: read numbers from the tool output
                tool_msgs = [m for m in kwargs["messages"] if m.get("role") == "tool"]
                pf = json.loads(tool_msgs[-1]["content"])
                self.calls.append(dict(kwargs, messages=list(kwargs["messages"])))
                return _resp(content=f"Total load {pf['total_load_mw']:.3f} MW.")
            return super().create(**kwargs)

    client = Client([_resp(content=json.dumps(plan))])
    engine = LLMEngine(client=client, dispatcher=build_default_dispatcher(ctx), config=EngineConfig(model="fake", architecture="plan_act"))
    text, trace = engine.run_with_trace("load case14 and run power flow", session)

    assert session.active_case == "case14" and session.last_result is not None and session.last_result.converged
    assert f"{session.last_result.total_load_mw:.3f}" in text
    assert trace["gate_checked"] == 1 and trace["gate_failed"] == 0


# ----------------------------------------------------------------------------- gate


def test_gate_verdict_shapes():
    assert gate_verdict(json.dumps({"case_name": "case14", "n_buses": 14})) is None
    assert gate_verdict("not json") is None
    ok = gate_verdict(json.dumps(_pf_payload()))
    assert ok["passed"] and ok["converged"] and ok["power_balance_ok"] and ok["reasons"] == []
    bad = gate_verdict(json.dumps(_pf_payload(converged=False)))
    assert not bad["passed"] and "not_converged" in bad["reasons"] and bad["carries_numbers"]
    imbalanced = gate_verdict(json.dumps(_pf_payload(gen=300.0)))
    assert not imbalanced["passed"] and "power_balance_mismatch" in imbalanced["reasons"]
    nested = gate_verdict(json.dumps({"applied": True, "result": _pf_payload(converged=False)}))
    assert nested is not None and not nested["passed"]


def _final_from_tool(kwargs):
    tool_msgs = [m for m in kwargs["messages"] if m.get("role") == "tool"]
    pf = json.loads(tool_msgs[-1]["content"])
    return _resp(content=f"converged={pf['converged']}; vm={pf['bus_voltages'][0]['vm_pu'] if pf['bus_voltages'] else 'n/a'}; load={pf['total_load_mw']}")


class EchoClient(ScriptedClient):
    """Round 1 asks for run_powerflow; round 2 echoes numbers found in the tool output."""

    def create(self, **kwargs):
        kwargs = dict(kwargs, messages=[dict(m) for m in kwargs["messages"]])
        self.calls.append(kwargs)
        if len(self.calls) == 1:
            return _resp(tool_calls=[_tool_call("c1", "run_powerflow", {})])
        return _final_from_tool(kwargs)


def test_gate_off_lets_non_converged_numbers_reach_the_answer_but_records_verdict():
    tools = ScriptedTools(pf_payload=_pf_payload(converged=False, vm=0.5, load=999.0))
    engine = LLMEngine(client=EchoClient([]), dispatcher=tools.dispatcher(), config=EngineConfig(model="fake", gate=False))

    text, trace = engine.run_with_trace("run pf", SessionState())

    assert "vm=0.5" in text and "load=999.0" in text  # unverified numbers reached the user
    assert trace["gate"] is False
    assert trace["gate_checked"] == 1 and trace["gate_failed"] == 1 and trace["gate_enforced"] == 0
    verdict = trace["rounds"][0]["tools"][0]["gate"]
    assert verdict["passed"] is False and verdict["converged"] is False
    assert trace["rounds"][0]["tools"][0]["enforced"] is False


def test_gate_on_withholds_non_converged_numbers():
    tools = ScriptedTools(pf_payload=_pf_payload(converged=False, vm=0.5, load=999.0))
    engine = LLMEngine(client=EchoClient([]), dispatcher=tools.dispatcher(), config=EngineConfig(model="fake"))  # gate=True default

    text, trace = engine.run_with_trace("run pf", SessionState())

    assert "vm=n/a" in text and "load=0.0" in text
    assert "0.5" not in text and "999" not in text
    assert trace["gate_checked"] == 1 and trace["gate_failed"] == 1 and trace["gate_enforced"] == 1
    assert trace["rounds"][0]["tools"][0]["enforced"] is True
    tool_msgs = [m for m in engine.client.calls[1]["messages"] if m["role"] == "tool"]
    forwarded = json.loads(tool_msgs[-1]["content"])
    assert forwarded["bus_voltages"] == [] and forwarded["gate"]["passed"] is False


def test_gate_on_is_a_no_op_for_converged_or_already_blank_payloads():
    blank = _pf_payload(converged=False, load=0.0, gen=0.0, loss=0.0)
    blank["bus_voltages"] = []
    for payload in (_pf_payload(), blank):
        tools = ScriptedTools(pf_payload=payload)
        engine = LLMEngine(client=EchoClient([]), dispatcher=tools.dispatcher(), config=EngineConfig(model="fake"))
        _, trace = engine.run_with_trace("run pf", SessionState())
        tool_msgs = [m for m in engine.client.calls[1]["messages"] if m["role"] == "tool"]
        forwarded = json.loads(tool_msgs[-1]["content"])
        assert forwarded == payload  # forwarded verbatim, exactly as before R1
        assert trace["gate_enforced"] == 0


def test_gate_fails_on_isolated_bus_nan_voltage():
    """A converged solve with a NaN bus voltage (islanded bus) must not pass the gate."""
    import json as _json
    from llm.engine import gate_verdict, _withhold_numbers
    payload = {
        "case_name": "case30", "converged": True,
        "bus_voltages": [{"bus_id": 1, "vm_pu": 1.0, "va_deg": 0.0}, {"bus_id": 11, "vm_pu": float("nan"), "va_deg": float("nan")}],
        "line_flows": [{"line_id": 0, "p_from_mw": 10.0, "loading_percent": 20.0}],
        "total_generation_mw": 100.0, "total_load_mw": 98.0, "total_loss_mw": 2.0,
    }
    out = _json.dumps(payload)
    v = gate_verdict(out)
    assert v is not None and v["converged"] is True
    assert v["topology_ok"] is False and v["isolated_buses"] == [11]
    assert v["passed"] is False and "isolated_or_unsolved_buses" in v["reasons"]
    withheld = _json.loads(_withhold_numbers(out, v))
    assert withheld["converged"] is False and withheld["bus_voltages"] == []
    assert withheld["gate"]["isolated_buses"] == [11]


def test_gate_passes_when_all_voltages_finite():
    import json as _json
    from llm.engine import gate_verdict
    payload = {"converged": True, "bus_voltages": [{"bus_id": 1, "vm_pu": 1.0, "va_deg": 0.0}], "line_flows": [],
               "total_generation_mw": 10.0, "total_load_mw": 9.5, "total_loss_mw": 0.5}
    v = gate_verdict(_json.dumps(payload))
    assert v["passed"] is True and v["topology_ok"] is True and v["isolated_buses"] == []


def test_gate_enforces_on_islanded_payload_not_only_nonconverged():
    """An islanded (converged but NaN-bus) payload must be withheld when gate=True and forwarded when gate=False."""
    import json as _json
    from llm.engine import _withhold_numbers, gate_verdict
    payload = {"converged": True,
               "bus_voltages": [{"bus_id": 1, "vm_pu": 1.0, "va_deg": 0.0}, {"bus_id": 8, "vm_pu": float("nan"), "va_deg": float("nan")}],
               "line_flows": [{"line_id": 0, "p_from_mw": 5.0, "loading_percent": 10.0}],
               "total_generation_mw": 50.0, "total_load_mw": 49.0, "total_loss_mw": 1.0}
    out = _json.dumps(payload); v = gate_verdict(out)
    assert v["converged"] is True and v["passed"] is False and v["carries_numbers"] is True
    # the engine condition is `gate and not passed and carries_numbers`; mirror it here
    assert (True and not v["passed"] and v["carries_numbers"]) is True
    withheld = _json.loads(_withhold_numbers(out, v))
    assert withheld["bus_voltages"] == [] and withheld["gate"]["isolated_buses"] == [8]


def test_gate_balance_tolerance_is_relative_for_large_systems():
    """case118-sized totals with a 0.18 MW mismatch (0.004 percent) must pass; 1 percent must fail."""
    import json as _json
    from llm.engine import gate_verdict
    base = {"converged": True, "bus_voltages": [{"bus_id": 1, "vm_pu": 1.0, "va_deg": 0.0}], "line_flows": [],
            "total_load_mw": 4242.0, "total_loss_mw": 132.684}
    ok = dict(base, total_generation_mw=4242.0 + 132.684 + 0.179)
    bad = dict(base, total_generation_mw=4242.0 + 132.684 + 42.0)
    assert gate_verdict(_json.dumps(ok))["passed"] is True
    assert gate_verdict(_json.dumps(bad))["passed"] is False
