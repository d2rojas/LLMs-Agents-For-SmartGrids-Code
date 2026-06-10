import json
import sys
from pathlib import Path

import pytest

# Ensure project root is on path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from llm.engine import EngineConfig, LLMClient, LLMEngine
from llm.tools import ToolContext, build_default_dispatcher
from models.schemas import SessionState


class FakeClient(LLMClient):
    """Controllable fake LLM for validating tool-calling loop behavior."""

    def __init__(self, mode: str = "happy"):
        self.calls = 0
        self.mode = mode

    def create(self, **kwargs):
        self.calls += 1

        if self.mode == "happy":
            if self.calls == 1:
                return {
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": None,
                                "tool_calls": [
                                    {
                                        "id": "call_load",
                                        "type": "function",
                                        "function": {
                                            "name": "load_case",
                                            "arguments": json.dumps({"case_name": "case14"}),
                                        },
                                    },
                                    {
                                        "id": "call_pf",
                                        "type": "function",
                                        "function": {
                                            "name": "run_powerflow",
                                            "arguments": "{}",
                                        },
                                    },
                                ],
                            }
                        }
                    ]
                }

            # 2nd round: summarize strictly from tool output values.
            tool_msgs = [m for m in kwargs["messages"] if m.get("role") == "tool"]
            pf = json.loads(tool_msgs[-1]["content"])
            text = (
                f"✅ IEEE 14 潮流计算完成。总负荷 {pf['total_load_mw']:.3f} MW，"
                f"总发电 {pf['total_generation_mw']:.3f} MW，总损耗 {pf['total_loss_mw']:.3f} MW。"
            )
            return {"choices": [{"message": {"role": "assistant", "content": text}}]}

        if self.mode == "no_case":
            if self.calls == 1:
                return {
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": None,
                                "tool_calls": [
                                    {
                                        "id": "call_pf",
                                        "type": "function",
                                        "function": {"name": "run_powerflow", "arguments": "{}"},
                                    }
                                ],
                            }
                        }
                    ]
                }

            tool_msgs = [m for m in kwargs["messages"] if m.get("role") == "tool"]
            err = json.loads(tool_msgs[-1]["content"]).get("error")
            return {
                "choices": [
                    {"message": {"role": "assistant", "content": f"⚠️ {err}"}}
                ]
            }

        raise RuntimeError("Unknown fake mode")


def test_llm_engine_happy_path_runs_tools_and_updates_session():
    session = SessionState()
    ctx = ToolContext(session=session)
    dispatcher = build_default_dispatcher(ctx)
    engine = LLMEngine(
        client=FakeClient(mode="happy"),
        dispatcher=dispatcher,
        config=EngineConfig(model="fake", max_tool_rounds=4),
    )

    out = engine.run("运行IEEE 14节点潮流", session)
    assert "IEEE 14" in out
    assert "总负荷" in out

    assert session.active_case == "case14"
    assert session.last_result is not None
    assert session.last_result.converged is True
    assert session.last_result.total_load_mw > 0
    assert session.last_result.total_generation_mw > 0

    # conversation_history should include user, assistant(tool_calls), tool(s), assistant(final)
    roles = [m.get("role") for m in session.conversation_history]
    assert roles.count("tool") >= 2
    assert roles[0] == "user"
    assert roles[-1] == "assistant"

    # Ensure numeric value comes from tool output.
    expected = f"{session.last_result.total_load_mw:.3f}"
    assert expected in out


def test_llm_engine_handles_run_without_loaded_case():
    session = SessionState()
    ctx = ToolContext(session=session)
    dispatcher = build_default_dispatcher(ctx)
    engine = LLMEngine(
        client=FakeClient(mode="no_case"),
        dispatcher=dispatcher,
        config=EngineConfig(model="fake", max_tool_rounds=2),
    )

    out = engine.run("运行潮流", session)
    assert ("请先加载" in out) or ("Please load a test case first." in out)
    assert session.active_case is None
    assert session.last_result is None
