"""Unit tests for llm/engine.py::verify_final_answer (V(x,c,z,y)) with synthetic traces.

No LLM, no solver: every trace is a hand-built dict shaped like ``LLMEngine.run_with_trace``'s
output. One test per failing condition, plus the all-pass case and the abstention/retry
machinery inside ``_run_react``.
"""

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from llm.engine import (  # noqa: E402
    EngineConfig,
    LLMEngine,
    verify_final_answer,
    _verification_abstention_text,
    _verification_retry_message,
)
from benchmarks import scoring as bs  # noqa: E402


def _pf_json(*, converged=True, gen=100.0, load=95.0, loss=5.0, bus_voltages=None, line_flows=None):
    return json.dumps(
        {
            "converged": converged,
            "bus_voltages": bus_voltages if bus_voltages is not None else [{"bus_id": 1, "vm_pu": 1.06, "va_deg": 0.0}],
            "line_flows": line_flows if line_flows is not None else [{"line_id": 0, "p_from_mw": 10.0, "loading_percent": 20.0}],
            "total_generation_mw": gen,
            "total_load_mw": load,
            "total_loss_mw": loss,
            # Always present on a real solver payload (baselines.requests._answer's
            # powerflow_summary branch reads them); an empty fixture default matches
            # every existing case here, which never actually flags a violation.
            "voltage_violations": [],
            "thermal_violations": [],
        }
    )


def _round(*tool_records):
    return {"round": 1, "tools": list(tool_records)}


def _tool(name, output, arguments=None):
    return {"name": name, "arguments": arguments or {}, "output": output, "gate": None}


def _trace(*rounds):
    return {"rounds": list(rounds)}


def test_all_conditions_pass():
    pf = _pf_json()
    trace = _trace(_round(_tool("load_case", json.dumps({"case_name": "case14"})), _tool("run_powerflow", pf)))
    text = "The network converged. Bus 1 is at 1.06 pu. The line carries 10.0 MW (20.0% loading)."
    verdict = verify_final_answer(trace, text)
    assert verdict["passed"] is True
    assert all(c["passed"] for c in verdict["conditions"].values())


def test_not_converged_fails():
    pf = _pf_json(converged=False, gen=0.0, load=0.0, loss=0.0)
    trace = _trace(_round(_tool("run_powerflow", pf)))
    verdict = verify_final_answer(trace, "The network did not converge.")
    assert verdict["passed"] is False
    assert verdict["conditions"]["converged"]["passed"] is False
    assert verdict["conditions"]["converged"]["residual"] == 1


def test_balance_mismatch_fails():
    pf = _pf_json(gen=200.0, load=95.0, loss=5.0)  # 100 MW off
    trace = _trace(_round(_tool("run_powerflow", pf)))
    verdict = verify_final_answer(trace, "Generation is 200 MW.")
    assert verdict["passed"] is False
    bal = verdict["conditions"]["balance"]
    assert bal["passed"] is False and bal["residual"] == 100.0


def test_isolated_bus_fails():
    pf = _pf_json(bus_voltages=[{"bus_id": 1, "vm_pu": 1.06, "va_deg": 0.0}, {"bus_id": 8, "vm_pu": None, "va_deg": None}])
    trace = _trace(_round(_tool("run_powerflow", pf)))
    verdict = verify_final_answer(trace, "Voltages look normal.")
    assert verdict["passed"] is False
    iso = verdict["conditions"]["no_isolated_buses"]
    assert iso["passed"] is False and iso["residual"] == 1


def test_faithfulness_fails_on_invented_number():
    pf = _pf_json()
    trace = _trace(_round(_tool("run_powerflow", pf)))
    # 0.873 pu appears nowhere in the tool output or the request.
    verdict = verify_final_answer(trace, "The lowest voltage is 0.873 pu.", request_text="Report the lowest voltage.")
    assert verdict["passed"] is False
    faith = verdict["conditions"]["faithfulness"]
    assert faith["passed"] is False and faith["residual"] == 1.0


def test_faithfulness_treats_request_echo_as_traceable():
    pf = _pf_json()
    trace = _trace(_round(_tool("run_powerflow", pf)))
    text = "Set the load at bus 9 to 40 MW as requested; bus 1 is at 1.06 pu."
    verdict = verify_final_answer(trace, text, request_text="Set the active load at bus 9 to 40 MW.")
    assert verdict["conditions"]["faithfulness"]["passed"] is True


def test_currency_fails_when_mutation_never_resolved():
    trace = _trace(_round(_tool("modify_load", json.dumps({"bus_id": 9, "p_mw": 40.0}), arguments={"bus_id": 9, "p_mw": 40.0})))
    verdict = verify_final_answer(trace, "The new load at bus 9 is 40 MW and voltages are within limits.")
    assert verdict["passed"] is False
    cur = verdict["conditions"]["currency"]
    assert cur["passed"] is False


def test_currency_fails_on_stale_quote_after_resolve():
    before = _pf_json(gen=100.0, load=95.0, loss=5.0, bus_voltages=[{"bus_id": 1, "vm_pu": 1.02, "va_deg": 0.0}])
    after = _pf_json(gen=140.0, load=135.0, loss=5.0, bus_voltages=[{"bus_id": 1, "vm_pu": 1.06, "va_deg": 0.0}])
    trace = _trace(
        _round(
            _tool("run_powerflow", before),
            _tool("modify_load", json.dumps({"bus_id": 9, "p_mw": 40.0}), arguments={"bus_id": 9, "p_mw": 40.0}),
            _tool("run_powerflow", after),
        )
    )
    # Quotes the pre-mutation voltage (1.02) instead of the post-mutation one (1.06).
    verdict = verify_final_answer(trace, "Bus 1 is at 1.02 pu.")
    assert verdict["passed"] is False
    assert verdict["conditions"]["currency"]["passed"] is False


def test_currency_passes_with_no_mutation_in_effect():
    pf = _pf_json()
    trace = _trace(_round(_tool("load_case", json.dumps({"case_name": "case14"})), _tool("run_powerflow", pf)))
    verdict = verify_final_answer(trace, "Bus 1 is at 1.06 pu.")
    assert verdict["conditions"]["currency"]["passed"] is True


def test_abstention_text_is_recognized_as_a_declared_failure_by_scoring():
    """The forced-abstention wording must trip benchmarks.scoring.failure_reporting's
    text-based safe_failure detection, or SFR would undercount pfagent by construction."""
    from benchmarks import scoring

    pf = _pf_json(converged=False, gen=0.0, load=0.0, loss=0.0)
    trace = _trace(_round(_tool("run_powerflow", pf)))
    verdict = verify_final_answer(trace, "irrelevant draft")
    text = _verification_abstention_text(verdict)

    result = scoring.failure_reporting(text, truth_converged=False, final_converged=False, has_tools=True)
    assert result["safe_failure"] is True
    assert result["claimed_success_on_failure"] is False
    # No unit-bearing numbers were silently reported alongside the abstention.
    from benchmarks import metrics as bm

    assert not any(n["kind"] != "unknown" for n in bm.numbers_in_text(text))


def test_abstention_text_names_the_isolated_bus_and_the_disconnect_in_plain_words():
    """The peer-review ask: no internal condition names in the abstention text -- name the
    bus, the cause (which branch was disconnected), and suggest reconnecting it."""
    pf = _pf_json(bus_voltages=[{"bus_id": 7, "vm_pu": 1.06, "va_deg": 0.0}, {"bus_id": 8, "vm_pu": None, "va_deg": None}])
    trace = _trace(
        _round(
            _tool("load_case", json.dumps({"case_name": "case14"})),
            _tool("disconnect_line", pf, arguments={"from_bus": 7, "to_bus": 8}),
        )
    )
    verdict = verify_final_answer(trace, "Voltages are within limits.")
    assert verdict["conditions"]["no_isolated_buses"]["passed"] is False
    text = _verification_abstention_text(verdict)
    assert "no_isolated_buses" not in text and "converged" not in text  # no internal condition keys
    assert "bus 8 has no valid voltage" in text
    assert "disconnecting the branch between bus 7 and bus 8 isolated it" in text
    assert "reconnect the branch between bus 7 and bus 8" in text
    assert "No numerical result is reported" in text


def test_retry_message_never_suggests_undoing_the_requested_change():
    """Regression test for a real gpt-4o-mini trace: the retry message used to say
    "Suggested next step: reconnect the branch..." and the model took it literally,
    calling reconnect_line and reporting the reconnected (converged) state as the answer
    to a request that asked to disconnect that same branch -- formulation_check correctly
    flagged it as extra_step, but verify_final_answer's own conditions no longer could,
    since the resulting state was genuinely consistent. The retry message must describe
    the failure without suggesting the specific fix; only the (terminal) abstention text
    may suggest it."""
    pf = _pf_json(bus_voltages=[{"bus_id": 7, "vm_pu": 1.06, "va_deg": 0.0}, {"bus_id": 8, "vm_pu": None, "va_deg": None}])
    trace = _trace(
        _round(
            _tool("load_case", json.dumps({"case_name": "case14"})),
            _tool("disconnect_line", pf, arguments={"from_bus": 7, "to_bus": 8}),
        )
    )
    verdict = verify_final_answer(trace, "Voltages are within limits.")
    retry_msg = _verification_retry_message(verdict)
    assert "suggested next step" not in retry_msg.lower()
    assert "reconnect the branch between bus 7 and bus 8" not in retry_msg.lower()
    assert "do not reconnect" in retry_msg.lower()  # the generic warning is fine; the specific hint is not

    abstention = _verification_abstention_text(verdict)
    assert "reconnect the branch between bus 7 and bus 8" in abstention


def test_retry_message_names_failed_conditions_only():
    pf = _pf_json(converged=False, gen=0.0, load=0.0, loss=0.0)
    trace = _trace(_round(_tool("run_powerflow", pf)))
    verdict = verify_final_answer(trace, "x")
    msg = _verification_retry_message(verdict)
    assert "did not converge" in msg
    # A passing condition (e.g. currency, vacuously true with no mutation) must not be listed.
    assert "stale" not in msg.lower()


# ----------------------------------------------------------------------------- engine integration


class _ScriptedClient:
    """Returns each scripted message in order; ignores tool schemas."""

    def __init__(self, messages):
        self._messages = list(messages)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        content = self._messages.pop(0)
        return {
            "choices": [{"message": {"role": "assistant", "content": content, "tool_calls": []}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }


class _FakeDispatcher:
    def __init__(self, output):
        self._output = output

    def dispatch(self, name, args):
        return self._output


def test_final_gate_retries_once_then_abstains_on_repeated_failure():
    from models.schemas import SessionState

    bad_pf = _pf_json(converged=False, gen=0.0, load=0.0, loss=0.0)
    # Two LLM turns, neither ever calls a tool: both final answers fail verification
    # (no run_powerflow output exists in the trace at all).
    client = _ScriptedClient(["First answer with a number: 1.05 pu.", "Second answer, still bad: 1.05 pu."])
    engine = LLMEngine(client=client, dispatcher=_FakeDispatcher(bad_pf), config=EngineConfig(model="fake", architecture="react", gate=False, final_gate=True))
    text, trace = engine.run_with_trace("Run the power flow.", SessionState())
    assert trace["verification_outcome"] == "abstained"
    assert trace["verification_attempts"] == 2
    assert "No numerical result is reported" in text
    assert len(client.calls) == 2  # exactly one retry, no third attempt


class _ScriptedToolClient:
    """Returns a scripted (content, tool_calls) pair per turn; ignores tool schemas."""

    def __init__(self, turns):
        self._turns = list(turns)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        content, tool_calls = self._turns.pop(0)
        return {
            "choices": [{"message": {"role": "assistant", "content": content, "tool_calls": tool_calls}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }


class _RecordingDispatcher:
    """Routes by tool name; records every call so the test can assert a tool was never reached."""

    def __init__(self, outputs):
        self._outputs = outputs
        self.calls = []

    def dispatch(self, name, args):
        self.calls.append(name)
        return self._outputs[name]


def test_mutating_tool_during_retry_is_blocked_not_executed():
    """Structural counterpart to the message-wording fix: even if the model tries to call
    reconnect_line during a retry (e.g. ignoring the instruction not to), the dispatcher must
    never see that call -- it is blocked and treated as a verification failure in itself."""
    from models.schemas import SessionState

    isolated_pf = _pf_json(bus_voltages=[{"bus_id": 7, "vm_pu": 1.06, "va_deg": 0.0}, {"bus_id": 8, "vm_pu": None, "va_deg": None}])
    reconnected_pf = _pf_json()  # would "pass" if it were ever allowed to run
    dispatcher = _RecordingDispatcher({"disconnect_line": isolated_pf, "reconnect_line": reconnected_pf})

    def _call(id_, name, args_json):
        return {"id": id_, "type": "function", "function": {"name": name, "arguments": args_json}}

    disconnect_call = [_call("1", "disconnect_line", '{"from_bus": 7, "to_bus": 8}')]
    reconnect_call = [_call("2", "reconnect_line", '{"from_bus": 7, "to_bus": 8}')]
    client = _ScriptedToolClient(
        [
            (None, disconnect_call),
            ("Voltages are within limits.", []),  # fails no_isolated_buses -> retry injected
            (None, reconnect_call),  # attempts to undo the disconnection instead of reporting it
        ]
    )
    engine = LLMEngine(client=client, dispatcher=dispatcher, config=EngineConfig(model="fake", architecture="react", gate=False, final_gate=True))
    text, trace = engine.run_with_trace("Disconnect the branch between bus 7 and bus 8.", SessionState())

    assert "reconnect_line" not in dispatcher.calls  # never executed
    assert dispatcher.calls == ["disconnect_line"]
    assert trace["verification_outcome"] == "abstained_retry_mutation"
    assert "attempted to change the network" in text
    assert "reconnect_line" in text


def test_split_tool_load_mutations_are_blocked_during_retry_too():
    """2026-09-21: _RETRY_BLOCKED_TOOLS was v1-only (modify_load) and predated
    --tool-variant load_split's set_active_load/set_load pair -- an audit of the
    four-row split-tool launch found no PFAgent trace actually exploited the gap
    (every retry-window call was read-only across all 17 windows that occurred, both
    models), but the list itself was wrong regardless of whether anything used it.
    Structural counterpart to test_mutating_tool_during_retry_is_blocked_not_executed,
    same scenario under the split tool set."""
    from models.schemas import SessionState

    isolated_pf = _pf_json(bus_voltages=[{"bus_id": 7, "vm_pu": 1.06, "va_deg": 0.0}, {"bus_id": 8, "vm_pu": None, "va_deg": None}])
    reconnected_pf = _pf_json()
    dispatcher = _RecordingDispatcher({"disconnect_line": isolated_pf, "set_active_load": reconnected_pf})

    def _call(id_, name, args_json):
        return {"id": id_, "type": "function", "function": {"name": name, "arguments": args_json}}

    disconnect_call = [_call("1", "disconnect_line", '{"from_bus": 7, "to_bus": 8}')]
    mutate_call = [_call("2", "set_active_load", '{"bus_id": 9, "p_mw": 70.0}')]
    client = _ScriptedToolClient(
        [
            (None, disconnect_call),
            ("Voltages are within limits.", []),  # fails no_isolated_buses -> retry injected
            (None, mutate_call),  # attempts a load mutation instead of reporting the failure
        ]
    )
    engine = LLMEngine(
        client=client, dispatcher=dispatcher,
        config=EngineConfig(model="fake", architecture="react", gate=False, final_gate=True, tool_variant="load_split"),
    )
    text, trace = engine.run_with_trace("Disconnect the branch between bus 7 and bus 8.", SessionState())

    assert "set_active_load" not in dispatcher.calls  # never executed
    assert dispatcher.calls == ["disconnect_line"]
    assert trace["verification_outcome"] == "abstained_retry_mutation"
    assert "set_active_load" in text


# ----------------------------------------------------------------------------- V6/V7 (2026-09-21, cheap-tier live wiring)


def test_verify_final_answer_checks_v6_v7_only_when_enforced():
    """enforce_v6v7 defaults False: evaluate_llms.py/rescore.py's offline v_pass measurement
    (computed for every method, not just PFAgent) must stay exactly as it read before this
    condition existed. Only a caller that opts in sees an invented argument as a failure."""
    pf = _pf_json()
    trace = _trace(_round(_tool("modify_load", pf, arguments={"bus_id": 1, "p_mw": 100.0, "q_mvar": 5.0})))
    request_text = "Load case14 and set the active load at bus 1 to 100 MW."  # never mentions q_mvar

    default_verdict = verify_final_answer(trace, "Bus 1 is now at 100.0 MW.", request_text=request_text)
    assert default_verdict["passed"] is True
    assert "argument_grounding" not in default_verdict["conditions"]
    assert "claims_from_tools" not in default_verdict["conditions"]

    enforced_verdict = verify_final_answer(trace, "Bus 1 is now at 100.0 MW.", request_text=request_text, enforce_v6v7=True)
    assert enforced_verdict["passed"] is False
    cond = enforced_verdict["conditions"]["argument_grounding"]
    assert cond["passed"] is False and cond["label"] == "V6"
    assert cond["invented_args"] == [{"tool": "modify_load", "arg": "q_mvar", "value": 5.0}]
    msg = _verification_retry_message(enforced_verdict)
    assert "modify_load.q_mvar=5.0" in msg


def test_pfagent_live_gate_abstains_on_a_v6_argument_grounding_failure():
    """End-to-end through _run_react: a mutating call with an argument the request never
    stated (and no prior tool output reported) passes every V1-V5 condition -- the network
    genuinely converges and balances -- but must still trigger the same retry-once,
    abstain-twice machinery as a V1-V5 failure, since the tool call itself is the defect the
    live gate is supposed to catch. The retry cannot fix it (modify_load is blocked once
    retry_active is set, so the invented q_mvar stays in the trace); the second attempt fails
    the same way and the run abstains rather than silently reporting the tainted answer."""
    from models.schemas import SessionState

    pf = _pf_json()  # converged, balanced, no isolated buses, gen=100/load=95/loss=5
    dispatcher = _FakeDispatcher(pf)

    def _call(id_, name, args_json):
        return {"id": id_, "type": "function", "function": {"name": name, "arguments": args_json}}

    modify_call = [_call("1", "modify_load", '{"bus_id": 1, "p_mw": 100.0, "q_mvar": 5.0}')]
    client = _ScriptedToolClient(
        [
            (None, modify_call),
            ("Bus 1 is now at 100.0 MW; generation 100.0 MW, load 95.0 MW, losses 5.0 MW.", []),
            ("Bus 1 is now at 100.0 MW; generation 100.0 MW, load 95.0 MW, losses 5.0 MW.", []),  # retry: same tainted call, nothing to fix
        ]
    )
    engine = LLMEngine(client=client, dispatcher=dispatcher, config=EngineConfig(model="fake", architecture="react", gate=False, final_gate=True))
    text, trace = engine.run_with_trace("Load case14 and set the active load at bus 1 to 100 MW.", SessionState())

    assert trace["verification_outcome"] == "abstained"
    assert trace["verification_attempts"] == 2
    v6_conditions = [v["conditions"]["argument_grounding"] for v in trace["verification"]]
    assert all(c["passed"] is False for c in v6_conditions)  # failed both attempts, as expected
    assert "do not trace to the request" in text


def test_pfagent_live_gate_v7_self_corrects_a_wrong_claim_on_retry():
    """V7 is where the retry path can genuinely fix the answer, unlike V6: the agent
    already has the right state (its own run_powerflow output), it just misreported which
    bus was worst. On retry it does not need to call any tool again -- read-only tools stay
    allowed during retry -- it only needs to restate its own already-computed result
    correctly, and the run passes on the second attempt instead of abstaining."""
    from models.schemas import SessionState

    pf = _pf_json(bus_voltages=[{"bus_id": 1, "vm_pu": 1.06, "va_deg": 0.0}, {"bus_id": 3, "vm_pu": 0.94, "va_deg": 0.0}])
    dispatcher = _FakeDispatcher(pf)

    def _call(id_, name, args_json):
        return {"id": id_, "type": "function", "function": {"name": name, "arguments": args_json}}

    pf_call = [_call("1", "run_powerflow", "{}")]
    client = _ScriptedToolClient(
        [
            (None, pf_call),
            ("The bus with the lowest voltage magnitude is bus 1.", []),  # wrong: bus 3 is actually worst
            ("On review, the bus with the lowest voltage magnitude is bus 3.", []),  # self-corrected, no new tool call
        ]
    )
    engine = LLMEngine(client=client, dispatcher=dispatcher, config=EngineConfig(model="fake", architecture="react", gate=False, final_gate=True))
    text, trace = engine.run_with_trace("Load case14 and report the bus with the lowest voltage magnitude.", SessionState())

    assert trace["verification_outcome"] == "pass_retry"
    assert trace["verification_attempts"] == 2
    assert trace["verification"][0]["conditions"]["claims_from_tools"]["passed"] is False
    assert trace["verification"][1]["conditions"]["claims_from_tools"]["passed"] is True
    assert "bus 3" in text


def test_live_v7_verdict_matches_an_independent_offline_recomputation():
    """2026-09-21 (Daniela's question on case14-multistep-034-s0, gpt-4o-mini PFAgent
    solving one fewer than ReAct): checked whether the live gate's V7 verdict could
    disagree with an offline recomputation on the exact same reconstructed trace and
    candidate text -- the candidate mechanisms were the live in-progress trace shape
    differing from the saved-report shape, the n1_report plot-envelope nesting
    (aadc1b3), truncated tool outputs, or the request-text claim-shape derivation
    reading a compound request differently offline. Audited all 14 real abstentions
    in the split-tool launch (12 mini + 2 sol PFAgent, every verification attempt in
    each): 0 disagreements -- claims_from_tools_check is a pure function of (trace,
    text, request_text), so live and an offline call with the same three inputs agree
    by construction; there is no separate "live path" for V7 to diverge in the first
    place, at least not one exercised by any committed trace. This test pins the
    invariant for a real end-to-end run rather than only auditing the passing_tests set:
    a first-attempt answer that is genuinely correct passes live, and calling
    claims_from_tools_check directly on the same pre-answer trace and text (the
    reconstruction rescore.py/an auditor would do from a saved report) must also pass."""
    from models.schemas import SessionState

    pf = {
        "case_name": "case14",
        "converged": True,
        "bus_voltages": [{"bus_id": 1, "vm_pu": 1.06, "va_deg": 0.0}, {"bus_id": 3, "vm_pu": 0.94, "va_deg": 0.0}],
        "line_flows": [],
        "voltage_violations": [],
        "thermal_violations": [],
    }
    dispatcher = _FakeDispatcher(_pf_json(bus_voltages=pf["bus_voltages"]))
    request_text = "Load case14 and report the bus with the lowest voltage magnitude."
    answer_text = "The bus with the lowest voltage magnitude is bus 3."

    def _call(id_, name, args_json):
        return {"id": id_, "type": "function", "function": {"name": name, "arguments": args_json}}

    client = _ScriptedToolClient([(None, [_call("1", "run_powerflow", "{}")]), (answer_text, [])])
    engine = LLMEngine(client=client, dispatcher=dispatcher, config=EngineConfig(model="fake", architecture="react", gate=False, final_gate=True))
    text, trace = engine.run_with_trace(request_text, SessionState())

    assert trace["verification_outcome"] == "pass_first"
    live_v7 = trace["verification"][0]["conditions"]["claims_from_tools"]
    assert live_v7["passed"] is True

    # reconstruct exactly what a saved report / an auditor would see: the trace up to
    # (not including) the answer round, and the answer text, then call the same
    # function used inside verify_final_answer directly
    pre_answer_trace = {"rounds": trace["rounds"][:1]}
    offline_v7 = bs.claims_from_tools_check(pre_answer_trace, answer_text, request_text)
    assert offline_v7["passed"] is live_v7["passed"] and offline_v7["applicable"] is live_v7["applicable"]
