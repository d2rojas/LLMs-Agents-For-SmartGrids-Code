"""solver/validators.py

结果验证器

检查项目（PRD FR-4）：
1) 收敛性检查：确认求解器成功收敛
2) 功率平衡检查：发电 ≈ 负荷 + 损耗（误差 < tol_mw）
3) 电压越限检查：默认 v_min ≤ V ≤ v_max
4) 热稳定越限检查：线路/变压器负载率 > max_loading

本模块只做“标注与过滤”，不抛出异常（避免 UI 白屏）。
若功率平衡误差偏大，会在 result.summary_text 中追加提示（不包含编造数值）。
"""

from __future__ import annotations

from dataclasses import dataclass

from models.schemas import BusVoltage, LineFlow, PowerFlowResult, ViolationType


@dataclass(frozen=True)
class ValidationConfig:
    """验证阈值配置。"""

    v_min: float = 0.95
    v_max: float = 1.05
    max_loading: float = 100.0
    balance_tol_mw: float = 0.01


def _annotate_voltage_violations(
    bus_voltages: list[BusVoltage], v_min: float, v_max: float
) -> tuple[list[BusVoltage], list[BusVoltage]]:
    all_bv: list[BusVoltage] = []
    viol: list[BusVoltage] = []

    for bv in bus_voltages:
        is_v = False
        vtype = None
        if bv.vm_pu < v_min:
            is_v = True
            vtype = ViolationType.UNDERVOLTAGE
        elif bv.vm_pu > v_max:
            is_v = True
            vtype = ViolationType.OVERVOLTAGE

        new_bv = bv.model_copy(update={"is_violation": is_v, "violation_type": vtype})
        all_bv.append(new_bv)
        if is_v:
            viol.append(new_bv)

    return all_bv, viol


def _annotate_thermal_violations(
    line_flows: list[LineFlow], max_loading: float
) -> tuple[list[LineFlow], list[LineFlow]]:
    all_lf: list[LineFlow] = []
    viol: list[LineFlow] = []

    for lf in line_flows:
        is_v = lf.loading_percent > max_loading
        new_lf = lf.model_copy(update={"is_violation": is_v})
        all_lf.append(new_lf)
        if is_v:
            viol.append(new_lf)

    return all_lf, viol


def validate_result(
    net: object,
    result: PowerFlowResult,
    *,
    v_min: float = 0.95,
    v_max: float = 1.05,
    max_loading: float = 100.0,
    balance_tol_mw: float = 0.01,
) -> PowerFlowResult:
    """校验与标注潮流结果。

    Args:
        net: pandapowerNet（目前仅用于未来扩展；本函数不依赖 net 的内部细节）
        result: 原始 PowerFlowResult
        v_min/v_max: 电压上下限
        max_loading: 热稳定越限阈值
        balance_tol_mw: 功率平衡允许误差

    Returns:
        更新后的 PowerFlowResult（填充越限子集，并在 bus/line 级别标注 is_violation）。
    """

    # 不收敛时，只返回原结果（可选地保留已有 summary_text）。
    if not result.converged:
        return result

    bus_voltages, v_viol = _annotate_voltage_violations(result.bus_voltages, v_min, v_max)
    line_flows, t_viol = _annotate_thermal_violations(result.line_flows, max_loading)

    updated = result.model_copy(
        update={
            "bus_voltages": bus_voltages,
            "line_flows": line_flows,
            "voltage_violations": v_viol,
            "thermal_violations": t_viol,
        }
    )

    # 功率平衡检查（不抛异常，避免 UI 白屏）
    mismatch = abs(updated.total_generation_mw - (updated.total_load_mw + updated.total_loss_mw))
    if mismatch > balance_tol_mw:
        # 注意：不输出 mismatch 数值，避免“看起来像编造”。
        hint = (
            "\n\n[校验提示] 功率平衡误差超过阈值（发电 ≈ 负荷 + 损耗）。"
            "请检查网络是否出现孤岛、未建模元件或求解器设置。"
        )
        if hint not in updated.summary_text:
            updated.summary_text = (updated.summary_text or "") + hint

    return updated
