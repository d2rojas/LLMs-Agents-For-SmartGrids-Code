import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from solver import case_loader
from solver.power_flow import SolverConfig, run_power_flow
from solver.remedial import apply_remedial_action_inplace, recommend_remedial_actions


def test_recommend_remedial_actions_case14_returns_actions_for_overvoltage():
    net, _ = case_loader.load("case14")
    cfg = SolverConfig(v_min=0.95, v_max=1.05, max_loading=100.0)
    base = run_power_flow(net, config=cfg)
    assert base.converged

    plan = recommend_remedial_actions(net, base, config=cfg, max_actions=5)
    # case14 基准工况通常存在过压（>1.05），应能生成至少 1 条调压类建议
    assert plan.case_name == "case14"
    assert plan.actions
    assert any(a.action in ("adjust_gen_vm", "adjust_ext_grid_vm") for a in plan.actions)
    assert all(a.preview_result is not None for a in plan.actions)


def test_apply_remedial_action_inplace_modifies_net_and_returns_result():
    net, _ = case_loader.load("case14")
    cfg = SolverConfig(v_min=0.95, v_max=1.05, max_loading=100.0)
    base = run_power_flow(net, config=cfg)
    assert base.converged

    plan = recommend_remedial_actions(net, base, config=cfg, max_actions=3)
    assert plan.actions
    act = plan.actions[0]

    # capture before
    params = act.parameters or {}
    bus_id = int(params.get("bus_id"))
    if act.action == "adjust_gen_vm" and len(net.gen) > 0:
        # pick the first gen at the bus
        bus_idx = int(net.bus.index[net.bus["name"].astype(str) == str(bus_id)][0])
        mask = net.gen["bus"] == bus_idx
        before_vm = float(net.gen.loc[mask, "vm_pu"].iloc[0]) if mask.any() else None
        after = apply_remedial_action_inplace(net, act, config=cfg)
        assert after is not None
        assert after.case_name == "case14"
        if before_vm is not None and mask.any():
            after_vm = float(net.gen.loc[mask, "vm_pu"].iloc[0])
            assert after_vm != before_vm

    elif act.action == "adjust_ext_grid_vm" and len(net.ext_grid) > 0:
        bus_idx = int(net.bus.index[net.bus["name"].astype(str) == str(bus_id)][0])
        mask = net.ext_grid["bus"] == bus_idx
        before_vm = float(net.ext_grid.loc[mask, "vm_pu"].iloc[0]) if mask.any() else None
        after = apply_remedial_action_inplace(net, act, config=cfg)
        assert after is not None
        if before_vm is not None and mask.any():
            after_vm = float(net.ext_grid.loc[mask, "vm_pu"].iloc[0])
            assert after_vm != before_vm

    else:
        # fallback: just ensure it runs
        after = apply_remedial_action_inplace(net, act, config=cfg)
        assert after is not None


@pytest.mark.parametrize("case_name", ["case30", "case57"])
def test_recommend_remedial_actions_runs(case_name: str):
    net, _ = case_loader.load(case_name)
    cfg = SolverConfig(v_min=0.95, v_max=1.05, max_loading=100.0)
    base = run_power_flow(net, config=cfg)
    assert base.converged
    plan = recommend_remedial_actions(net, base, config=cfg, max_actions=3)
    assert plan.case_name == case_name
    assert plan.base_risk >= 0.0