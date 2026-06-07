import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))


from llm.tools import ToolContext, build_default_dispatcher
from models.schemas import SessionState


def test_apply_remedial_action_tool_requires_confirmation_and_updates_log():
    session = SessionState()
    ctx = ToolContext(session=session)
    dispatcher = build_default_dispatcher(ctx)

    # load + run PF
    out = json.loads(dispatcher.dispatch("load_case", {"case_name": "case14"}))
    assert out.get("case_name") == "case14"
    out = json.loads(dispatcher.dispatch("run_powerflow", {}))
    assert out.get("converged") is True

    # generate remedial
    out = json.loads(dispatcher.dispatch("recommend_remedial_actions", {"max_actions": 3}))
    assert "remedial_plan" in out
    assert out["remedial_plan"]["actions"]

    # apply without confirmation
    out2 = json.loads(dispatcher.dispatch("apply_remedial_action", {"action_index": 1}))
    assert out2.get("need_confirmation") is True
    assert session.modification_log == []

    # apply with confirmation
    out3 = json.loads(dispatcher.dispatch("apply_remedial_action", {"action_index": 1, "confirmed": True}))
    assert out3.get("applied") is True
    assert session.modification_log
    assert session.modification_log[-1].action == "apply_remedial_action"
    assert session.last_result is not None
