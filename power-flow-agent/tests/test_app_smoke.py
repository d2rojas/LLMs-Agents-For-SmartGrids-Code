import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app_utils import extract_tool_artifacts, pick_last_n1_report, pick_last_plot


def test_extract_plot_artifact_generate_plot():
    history_delta = [
        {"role": "tool", "name": "run_powerflow", "content": json.dumps({"ok": True})},
        {
            "role": "tool",
            "name": "generate_plot",
            "content": json.dumps({"plot_type": "voltage_heatmap", "figure_json": "{...}"}),
        },
    ]

    artifacts = extract_tool_artifacts(history_delta)
    last = pick_last_plot(artifacts)
    assert last is not None
    assert last.plot_type == "voltage_heatmap"
    assert last.figure_json == "{...}"


def test_extract_n1_artifact_and_plot():
    history_delta = [
        {
            "role": "tool",
            "name": "run_n1_contingency",
            "content": json.dumps(
                {
                    "plot_type": "n1_ranking",
                    "figure_json": "{FIG}",
                    "n1_report": {"summary_text": "ok", "results": []},
                }
            ),
        }
    ]

    artifacts = extract_tool_artifacts(history_delta)
    last_plot = pick_last_plot(artifacts)
    assert last_plot is not None
    assert last_plot.plot_type == "n1_ranking"

    last_n1 = pick_last_n1_report(artifacts)
    assert last_n1 is not None
    assert last_n1.n1_report["summary_text"] == "ok"


def test_extract_remedial_artifact_with_extra_figures():
    history_delta = [
        {
            "role": "tool",
            "name": "recommend_remedial_actions",
            "content": json.dumps(
                {
                    "plot_type": "remedial_ranking",
                    "figure_json": "{RANK}",
                    "remedial_plan": {"case_name": "case14", "base_risk": 1.0, "actions": []},
                    "extra_figures": [{"plot_type": "comparison", "figure_json": "{CMP}", "title": "cmp"}],
                }
            ),
        }
    ]

    artifacts = extract_tool_artifacts(history_delta)
    last_plot = pick_last_plot(artifacts)
    assert last_plot is not None
    assert last_plot.plot_type == "remedial_ranking"
    assert last_plot.has_remedial_plan
    assert last_plot.remedial_plan["case_name"] == "case14"
    assert last_plot.extra_figures and last_plot.extra_figures[0]["figure_json"] == "{CMP}"
