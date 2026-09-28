"""The answer parser and the gate's own helpers, on hand-built inputs. No network, no key."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from methods.agent.gate import supported, traceability  # noqa: E402
from methods.answer import declared_failure, parse_answer  # noqa: E402


def test_parse_bare_object():
    a = parse_answer(json.dumps({"diagnosis": {"fault_type": "Line_Outage", "components": {"line": ["9"]}}, "actions": [],
                                 "final_state": {"converged": True, "n_new_violations": 0}, "status": "repaired", "remaining_violations": [], "summary": "ok"}))
    assert a.json_ok and a.fault_type == "line_outage" and a.components == {"line": [9]} and a.claims_repaired


def test_parse_after_reasoning_and_in_fence():
    text = "First I reason.\n\nFINAL ANSWER:\n```json\n" + json.dumps({"status": "not_repaired", "remaining_violations": ["line 5 at 118 %"]}) + "\n```"
    a = parse_answer(text)
    assert a.json_ok and a.declares_failure and a.remaining == ["line 5 at 118 %"]


def test_parse_nothing():
    a = parse_answer("I could not decide.")
    assert not a.json_ok and a.status is None and not a.claims_repaired and not a.declares_failure


def test_declared_failure_carries_no_claim():
    a = parse_answer(json.dumps(declared_failure("budget", ["bus 3 at 0.93 p.u."])))
    assert a.status == "cannot_repair" and a.remaining == ["bus 3 at 0.93 p.u."] and a.actions == []


def test_supported_respects_the_decimals_written():
    pool = {0.9312, 118.44, 5.0}
    assert supported("0.93", pool) and supported("118.4", pool) and supported("5", pool)
    assert not supported("0.95", pool) and not supported("118.6", pool)


def test_traceability_reads_tool_outputs_and_evidence():
    a = parse_answer(json.dumps({"status": "repaired", "final_state": {"converged": True, "n_new_violations": 0},
                                 "summary": "Line 13 was at 624.9 % and is now at 71.2 %.", "remaining_violations": []}))
    log = [{"name": "check_overloads", "output": {"overloaded_lines": [{"line_index": 13, "loading_percent": 624.9}]}, "args": {}}]
    n, bad, which = traceability(a, log, evidence_text="")
    assert n == 3 and bad == 1 and which == ["71.2"]
    n, bad, _ = traceability(a, log + [{"name": "get_loading_profile", "output": {"lines": [{"line_index": 13, "loading_percent": 71.2}]}, "args": {}}], "")
    assert bad == 0
