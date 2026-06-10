import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))


from solver import case_loader
from solver.power_flow import run_power_flow, modify_bus_load

from viz import (
    make_comparison,
    make_flow_diagram,
    make_voltage_heatmap,
    make_violation_overview,
)

from llm.tools import ToolContext, build_default_dispatcher


@pytest.mark.parametrize("case_name", ["case14", "case30", "case57"])
def test_voltage_heatmap_returns_figure(case_name: str):
    net, _ = case_loader.load(case_name)
    res = run_power_flow(net)
    fig = make_voltage_heatmap(net, res)
    assert fig is not None
    assert hasattr(fig, "data")
    assert len(fig.data) >= 1
    assert case_name in fig.layout.title.text
    assert any(getattr(t, "showlegend", False) for t in fig.data)
    assert fig.layout.yaxis.scaleanchor == "x"


def test_voltage_heatmap_colors_apply_to_bus_trace_only():
    net, _ = case_loader.load("case14")
    res = run_power_flow(net)
    fig = make_voltage_heatmap(net, res)

    bus_trace = next((t for t in fig.data if getattr(t, "name", "") == "bus"), None)
    assert bus_trace is not None
    assert len(bus_trace.x or []) == len(net.bus)
    assert len(bus_trace.marker.color or []) == len(net.bus)

    hover_trace = next(
        (t for t in fig.data if getattr(t, "mode", None) == "markers" and str(getattr(t, "name", "")) == ""),
        None,
    )
    if hover_trace is not None:
        assert str(hover_trace.marker.color) == "rgba(0,0,0,0)"


@pytest.mark.parametrize("case_name", ["case14", "case30"])
def test_flow_diagram_returns_figure(case_name: str):
    net, _ = case_loader.load(case_name)
    res = run_power_flow(net)
    fig = make_flow_diagram(net, res)
    assert fig is not None
    assert len(fig.data) >= 1
    assert case_name in (fig.layout.title.text or "")


def test_violation_overview_returns_figure():
    net, _ = case_loader.load("case14")
    res = run_power_flow(net)
    fig = make_violation_overview(net, res)
    assert fig is not None
    assert "case14" in (fig.layout.title.text or "")


def test_violation_overview_uses_pf_like_layout_case14():
    net, _ = case_loader.load("case14")
    res = run_power_flow(net)
    fig = make_violation_overview(net, res)

    assert fig.layout.yaxis.scaleanchor == "x"
    assert fig.layout.legend.orientation == "h"

    xr = list(fig.layout.xaxis.range or [])
    yr = list(fig.layout.yaxis.range or [])
    assert len(xr) == 2
    assert len(yr) == 2
    assert xr[0] == pytest.approx(-1.9, abs=1e-6)
    assert xr[1] == pytest.approx(10.9, abs=1e-6)
    assert yr[0] == pytest.approx(-0.8, abs=1e-6)
    assert yr[1] == pytest.approx(8.8, abs=1e-6)


def test_comparison_returns_figure_with_table():
    net, _ = case_loader.load("case14")
    before = run_power_flow(net)

    # make a change
    load_idx = int(net.load.index[0])
    bus_internal = int(net.load.at[load_idx, "bus"])
    bus_name = int(net.bus.at[bus_internal, "name"])
    old_p = float(net.load.loc[net.load["bus"] == bus_internal, "p_mw"].sum())
    after = modify_bus_load(net, bus_id=bus_name, p_mw=old_p + 5.0)

    fig = make_comparison(net, before, after)
    assert fig is not None
    assert "case14" in (fig.layout.title.text or "")
    # last trace should be table
    assert any(t.type == "table" for t in fig.data)
    assert fig.layout.yaxis.scaleanchor == "x"
    assert fig.layout.yaxis2.scaleanchor == "x2"
    xr1 = list(fig.layout.xaxis.range or [])
    yr1 = list(fig.layout.yaxis.range or [])
    xr2 = list(fig.layout.xaxis2.range or [])
    yr2 = list(fig.layout.yaxis2.range or [])
    assert xr1 == pytest.approx([-1.9, 10.9], abs=1e-6)
    assert yr1 == pytest.approx([-0.8, 8.8], abs=1e-6)
    assert xr2 == pytest.approx([-1.9, 10.9], abs=1e-6)
    assert yr2 == pytest.approx([-0.8, 8.8], abs=1e-6)


def test_generate_plot_tool_outputs_json():
    ctx = ToolContext()
    dispatcher = build_default_dispatcher(ctx)

    # load and run
    out1 = dispatcher.dispatch("load_case", {"case_name": "case14"})
    assert "case14" in out1
    out2 = dispatcher.dispatch("run_powerflow", {})
    assert "\"converged\"" in out2

    out3 = dispatcher.dispatch("generate_plot", {"plot_type": "voltage_heatmap"})
    assert "figure_json" in out3
    assert "voltage_heatmap" in out3
