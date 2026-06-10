import sys
from pathlib import Path
import warnings

import pytest

# Ensure project root is on path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

# Silence noisy pandapower FutureWarnings from its internal JSON loader
warnings.filterwarnings("ignore", category=FutureWarning, module=r"pandapower\..*")

from solver import case_loader
from solver.power_flow import (
    SolverConfig,
    _resolve_bus_index,
    disconnect_line,
    modify_bus_load,
    reconnect_line,
    run_power_flow,
)
from viz.flow_diagram import _display_label_maps, _display_shift, make_flow_diagram, resolve_flow_positions
from viz.network_plot import bus_display_id, build_graph, classify_bus_sets, compute_layout


@pytest.mark.parametrize("case_name", ["case14", "case30", "case57"])
def test_load_and_run_power_flow(case_name: str):
    net, info = case_loader.load(case_name)
    assert info.case_name == case_name
    assert info.n_buses > 0

    result = run_power_flow(net)
    assert result.converged is True
    assert result.case_name == case_name

    assert len(result.bus_voltages) == info.n_buses
    assert len(result.line_flows) > 0

    # Basic sanity checks
    assert result.total_load_mw >= 0.0
    assert result.total_generation_mw >= 0.0

    # Violation subsets are consistent
    assert all(bv.is_violation for bv in result.voltage_violations)
    assert all(lf.is_violation for lf in result.thermal_violations)


def test_power_balance_check_case14():
    net, _ = case_loader.load("case14")
    result = run_power_flow(net)
    mismatch = abs(result.total_generation_mw - (result.total_load_mw + result.total_loss_mw))
    assert mismatch < 0.01


def test_modify_bus_load_changes_total_load():
    net, _ = case_loader.load("case14")
    base = run_power_flow(net)

    # Pick an existing load row to avoid ambiguity.
    assert len(net.load) > 0
    load_idx = int(net.load.index[0])
    bus_internal = int(net.load.at[load_idx, "bus"])
    bus_name = int(net.bus.at[bus_internal, "name"])  # IEEE-style 1-based

    # Current total p_mw at that bus
    mask = net.load["bus"] == bus_internal
    old_bus_p = float(net.load.loc[mask, "p_mw"].sum())

    new_bus_p = old_bus_p + 10.0

    new_result = modify_bus_load(net, bus_id=bus_name, p_mw=new_bus_p)
    assert new_result.converged is True

    # New total load should change roughly by +10 MW
    delta = new_result.total_load_mw - base.total_load_mw
    assert pytest.approx(delta, abs=1e-3) == 10.0


def test_disconnect_and_reconnect_line_case14():
    net, _ = case_loader.load("case14")
    base = run_power_flow(net)
    assert base.converged

    # Use the first physical line in net.line
    assert len(net.line) > 0
    line_idx = int(net.line.index[0])
    fb_internal = int(net.line.at[line_idx, "from_bus"])
    tb_internal = int(net.line.at[line_idx, "to_bus"])
    fb_name = int(net.bus.at[fb_internal, "name"])
    tb_name = int(net.bus.at[tb_internal, "name"])

    assert bool(net.line.at[line_idx, "in_service"]) is True

    after_disc = disconnect_line(net, from_bus=fb_name, to_bus=tb_name)
    assert bool(net.line.at[line_idx, "in_service"]) is False
    assert after_disc.converged is True

    after_rec = reconnect_line(net, from_bus=fb_name, to_bus=tb_name)
    assert bool(net.line.at[line_idx, "in_service"]) is True
    assert after_rec.converged is True


def test_case118_bus_ids_preserve_matpower_numbering():
    net, _ = case_loader.load("case118")
    result = run_power_flow(net)

    ids = [int(b.bus_id) for b in result.bus_voltages]
    assert len(ids) == len(net.bus)
    assert len(set(ids)) == len(net.bus)
    assert min(ids) == 1
    assert max(ids) == len(net.bus)

    # bus 69 in MATPOWER maps to internal index 68 in converted net.
    assert _resolve_bus_index(net, 69) == 68


def test_case300_keeps_real_high_bus_ids_without_dense_relabel():
    net, _ = case_loader.load("case300")

    display_ids = {int(bus_display_id(net, int(i))) for i in net.bus.index.tolist()}
    assert 9001 in display_ids
    assert 7049 in display_ids

    disp_shift = _display_shift(net)
    _, raw_to_dense, use_dense = _display_label_maps(net, disp_shift)
    assert use_dense is False
    assert 9001 in raw_to_dense


def test_classify_bus_sets_slack_only_from_ext_grid():
    net, _ = case_loader.load("case118")
    slack, pv, pq, inactive = classify_bus_sets(net)

    ext_in_service = set(
        int(net.ext_grid.loc[i, "bus"])
        for i in net.ext_grid.index
        if ("in_service" not in net.ext_grid.columns) or bool(net.ext_grid.loc[i, "in_service"])
    )
    active_bus = set(
        int(i)
        for i in net.bus.index
        if ("in_service" not in net.bus.columns) or bool(net.bus.loc[i, "in_service"])
    )

    assert slack == ext_in_service
    assert len(slack) == 1
    assert len(slack & pv) == 0
    assert len(slack | pv | pq) == len(active_bus)
    assert len(inactive & active_bus) == 0


def test_classify_bus_sets_excludes_slack_from_pv():
    net, _ = case_loader.load("case14")
    ext_bus = int(net.ext_grid.iloc[0]["bus"])
    if len(net.gen) > 0:
        net.gen.at[int(net.gen.index[0]), "bus"] = int(ext_bus)

    slack, pv, _pq, _inactive = classify_bus_sets(net)
    assert ext_bus in slack
    assert ext_bus not in pv


def test_flow_diagram_phase1_static_no_plotly_frames():
    net, _ = case_loader.load("case14")
    result = run_power_flow(net)
    fig = make_flow_diagram(net, result, lang="en", enable_entrance_animation=True)
    assert not fig.frames


def test_build_graph_skips_unreferenced_aux_bus():
    net, _ = case_loader.load("case14")
    new_idx = int(max(net.bus.index)) + 1000
    net.bus.loc[new_idx, :] = net.bus.loc[int(net.bus.index[0]), :]
    if "in_service" in net.bus.columns:
        net.bus.at[new_idx, "in_service"] = True

    g = build_graph(net)
    assert new_idx not in g.nodes


def test_compute_layout_normalized_to_0_10():
    net, _ = case_loader.load("case30")
    g = build_graph(net)
    pos = compute_layout(net, g)
    xs = [float(v[0]) for v in pos.values()]
    ys = [float(v[1]) for v in pos.values()]

    assert min(xs) >= -1e-9
    assert max(xs) <= 10.0 + 1e-9
    assert min(ys) >= -1e-9
    assert max(ys) <= 10.0 + 1e-9


def test_resolve_flow_positions_case14_uses_textbook_coordinates():
    net, _ = case_loader.load("case14")
    result = run_power_flow(net)
    auto = compute_layout(net, build_graph(net))
    pos = resolve_flow_positions(net, result, positions=auto, use_ieee14_fixed_layout=True)

    bus1_internal = int(next(i for i in net.bus.index if int(net.bus.at[i, "name"]) == 1))
    x, y = pos[bus1_internal]
    assert pytest.approx(float(x), abs=1e-6) == 0.0
    assert pytest.approx(float(y), abs=1e-6) == 8.0
