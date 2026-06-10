"""viz/benchmark.py

Benchmark visualization: 2x2 diagnostic Plotly figure and metric card definitions
for LLM vs Ground Truth comparison.
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from viz.comparison import _FONT_SANS, _FONT_SERIF, _qc_font

# ---------------------------------------------------------------------------
# Color constants
# ---------------------------------------------------------------------------
_GREEN = "#38A169"
_YELLOW = "#D69E2E"
_RED = "#E53E3E"
_GRAY = "#718096"
_BLUE = "#3182CE"
_LIGHT_BLUE = "#63B3ED"
_WHITE = "#FFFFFF"
_GRID = "#E7EDF5"
_AXIS = "#C8D3E1"


def _grade_color(value: Optional[float], thresholds: tuple) -> str:
    """Return green/yellow/red based on (good_below, fair_below) thresholds.

    For metrics where lower is better (RMSE, error).
    """
    if value is None:
        return _GRAY
    good, fair = thresholds
    if value < good:
        return _GREEN
    if value < fair:
        return _YELLOW
    return _RED


def _grade_color_higher_better(value: Optional[float], thresholds: tuple) -> str:
    """Return green/yellow/red for metrics where higher is better (F1, accuracy)."""
    if value is None:
        return _GRAY
    good, fair = thresholds
    if value > good:
        return _GREEN
    if value > fair:
        return _YELLOW
    return _RED


# ---------------------------------------------------------------------------
# make_benchmark_figure
# ---------------------------------------------------------------------------


def make_benchmark_figure(
    metrics: Dict[str, Any],
    *,
    lang: Literal["zh", "en"] = "en",
) -> go.Figure:
    """Build 2x2 diagnostic figure: parity plots, error histogram, confusion matrix."""

    zh = lang == "zh"

    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=[
            "电压奇偶性散点" if zh else "Voltage Parity Plot",
            "潮流奇偶性散点" if zh else "Flow Parity Plot",
            "电压误差分布" if zh else "Voltage Error Distribution",
            "越限混淆矩阵" if zh else "Violation Confusion Matrix",
        ],
        horizontal_spacing=0.10,
        vertical_spacing=0.16,
    )

    # ---- Panel 1: Voltage Parity Plot ----
    vm_pairs = metrics.get("_raw_vm_pairs", [])
    if vm_pairs:
        bus_ids = [p[0] for p in vm_pairs]
        vm_llm = [p[1] for p in vm_pairs]
        vm_true = [p[2] for p in vm_pairs]
        vm_errors = [abs(p[1] - p[2]) for p in vm_pairs]

        # y=x reference line
        all_v = vm_llm + vm_true
        v_lo = min(all_v) - 0.01
        v_hi = max(all_v) + 0.01
        fig.add_trace(
            go.Scatter(
                x=[v_lo, v_hi], y=[v_lo, v_hi],
                mode="lines",
                line=dict(dash="dash", color="#A0AEC0", width=1.5),
                name="y = x",
                showlegend=False,
                hoverinfo="skip",
            ),
            row=1, col=1,
        )

        fig.add_trace(
            go.Scatter(
                x=vm_true, y=vm_llm,
                mode="markers",
                marker=dict(
                    size=8,
                    color=vm_errors,
                    colorscale="YlOrRd",
                    colorbar=dict(
                        title=dict(text="|Error|", font=_qc_font(10)),
                        len=0.30, y=0.83, x=0.445,
                        thickness=10,
                    ),
                    line=dict(width=0.5, color="#fff"),
                ),
                text=[f"Bus {b}<br>LLM: {l:.4f}<br>Truth: {t:.4f}<br>Err: {e:.4f}"
                      for b, l, t, e in zip(bus_ids, vm_llm, vm_true, vm_errors)],
                hoverinfo="text",
                name="Buses",
                showlegend=False,
            ),
            row=1, col=1,
        )

        fig.update_xaxes(title_text="Ground Truth V (p.u.)" if not zh else "真值电压 (p.u.)",
                         row=1, col=1, title_font=_qc_font(11))
        fig.update_yaxes(title_text="LLM Predicted V (p.u.)" if not zh else "LLM预测电压 (p.u.)",
                         row=1, col=1, title_font=_qc_font(11))

    # ---- Panel 2: Flow Parity Plot ----
    p_pairs = metrics.get("_raw_p_pairs", [])
    if p_pairs:
        line_ids = [p[0] for p in p_pairs]
        p_llm = [p[1] for p in p_pairs]
        p_true = [p[2] for p in p_pairs]
        p_errors = [abs(p[1] - p[2]) for p in p_pairs]

        all_p = p_llm + p_true
        p_lo = min(all_p) - 1.0
        p_hi = max(all_p) + 1.0
        fig.add_trace(
            go.Scatter(
                x=[p_lo, p_hi], y=[p_lo, p_hi],
                mode="lines",
                line=dict(dash="dash", color="#A0AEC0", width=1.5),
                showlegend=False,
                hoverinfo="skip",
            ),
            row=1, col=2,
        )

        fig.add_trace(
            go.Scatter(
                x=p_true, y=p_llm,
                mode="markers",
                marker=dict(
                    size=7,
                    color=p_errors,
                    colorscale="YlOrRd",
                    colorbar=dict(
                        title=dict(text="|Error| MW", font=_qc_font(10)),
                        len=0.30, y=0.83, x=1.01,
                        thickness=10,
                    ),
                    line=dict(width=0.5, color="#fff"),
                ),
                text=[f"Line {lid}<br>LLM: {l:.2f} MW<br>Truth: {t:.2f} MW<br>Err: {e:.2f}"
                      for lid, l, t, e in zip(line_ids, p_llm, p_true, p_errors)],
                hoverinfo="text",
                name="Lines",
                showlegend=False,
            ),
            row=1, col=2,
        )

        fig.update_xaxes(title_text="Ground Truth P (MW)" if not zh else "真值有功 (MW)",
                         row=1, col=2, title_font=_qc_font(11))
        fig.update_yaxes(title_text="LLM Predicted P (MW)" if not zh else "LLM预测有功 (MW)",
                         row=1, col=2, title_font=_qc_font(11))

    # ---- Panel 3: Voltage Error Distribution ----
    if vm_pairs:
        v_errs = [p[1] - p[2] for p in vm_pairs]
        err_mean = float(np.mean(v_errs))
        err_std = float(np.std(v_errs))

        fig.add_trace(
            go.Histogram(
                x=v_errs,
                nbinsx=min(25, max(8, len(v_errs) // 2)),
                marker=dict(color="#4C9BE8", line=dict(color="#2F6FAE", width=0.6)),
                opacity=0.88,
                name="ΔV",
                showlegend=False,
                hovertemplate="ΔV: %{x:.4f}<br>Count: %{y}<extra></extra>",
            ),
            row=2, col=1,
        )

        # Mean line
        fig.add_vline(
            x=err_mean, row=2, col=1,
            line=dict(color=_RED, dash="dot", width=1.5),
            annotation_text=f"mean={err_mean:.4f}",
            annotation_position="top right",
            annotation_font=_qc_font(10, _RED),
        )

        fig.update_xaxes(title_text="V_LLM − V_True (p.u.)" if not zh else "电压误差 (p.u.)",
                         row=2, col=1, title_font=_qc_font(11))
        fig.update_yaxes(title_text="Count" if not zh else "计数",
                         row=2, col=1, title_font=_qc_font(11))

        # Stats annotation
        fig.add_annotation(
            text=f"μ = {err_mean:.4f}, σ = {err_std:.4f}",
            xref="x3 domain", yref="y3 domain",
            x=0.98, y=0.95,
            showarrow=False,
            font=_qc_font(10, "#4A5568"),
            xanchor="right",
        )

    # ---- Panel 4: Violation Confusion Matrix ----
    cm = metrics.get("_violation_cm", {"tp": 0, "fp": 0, "fn": 0, "tn": 0})
    tp, fp, fn, tn = cm["tp"], cm["fp"], cm["fn"], cm["tn"]

    z = [[tn, fp], [fn, tp]]
    labels_x = ["No Violation", "Violation"] if not zh else ["无越限", "越限"]
    labels_y = ["No Violation", "Violation"] if not zh else ["无越限", "越限"]

    text_matrix = [[str(tn), str(fp)], [str(fn), str(tp)]]

    fig.add_trace(
        go.Heatmap(
            z=z,
            x=labels_x,
            y=labels_y,
            colorscale=[[0, "#EEF5FB"], [1, "#2F6FAE"]],
            text=text_matrix,
            texttemplate="%{text}",
            textfont=dict(size=18, family=_FONT_SANS),
            showscale=False,
            hovertemplate="Pred: %{y}<br>Truth: %{x}<br>Count: %{z}<extra></extra>",
        ),
        row=2, col=2,
    )

    fig.update_xaxes(title_text="Ground Truth" if not zh else "真值",
                     row=2, col=2, title_font=_qc_font(11))
    fig.update_yaxes(title_text="LLM Predicted" if not zh else "LLM预测",
                     row=2, col=2, title_font=_qc_font(11))

    # F1 annotation
    v_f1 = metrics.get("voltage_f1")
    f1_text = f"Voltage F1 = {v_f1:.3f}" if v_f1 is not None else "Voltage F1 = N/A"
    t_f1 = metrics.get("thermal_f1")
    if t_f1 is not None:
        f1_text += f"  |  Thermal F1 = {t_f1:.3f}"

    fig.add_annotation(
        text=f"<b>{f1_text}</b>",
        xref="x4 domain", yref="y4 domain",
        x=0.5, y=1.03,
        showarrow=False,
        font=_qc_font(11, _BLUE),
        xanchor="center",
    )

    # ---- Global layout ----
    fig.update_layout(
        height=820,
        template="plotly_white",
        paper_bgcolor=_WHITE,
        plot_bgcolor=_WHITE,
        margin=dict(l=48, r=28, t=72, b=44),
        title=dict(
            text="LLM Benchmark vs Ground Truth" if not zh else "LLM 基准测试 vs 真值",
            font=dict(family=_FONT_SERIF, size=18, color="#1A202C"),
            x=0.5,
        ),
        font=dict(family=_FONT_SANS, size=11),
    )

    fig.update_xaxes(showline=True, linewidth=1.0, linecolor=_AXIS, gridcolor=_GRID, zeroline=False)
    fig.update_yaxes(showline=True, linewidth=1.0, linecolor=_AXIS, gridcolor=_GRID, zeroline=False)

    # Style subplot titles only (the first 4 annotations are subplot titles)
    ann_list = list(fig.layout.annotations or [])
    for i in range(min(4, len(ann_list))):
        ann_list[i].font = dict(family=_FONT_SERIF, size=14, color="#2D3748")

    return fig


# ---------------------------------------------------------------------------
# compute_benchmark_cards
# ---------------------------------------------------------------------------


def compute_benchmark_cards(
    metrics: Dict[str, Any],
    *,
    lang: Literal["zh", "en"] = "en",
) -> List[Dict[str, Any]]:
    """Return benchmark metric card definitions for tiered rendering."""

    cards: List[Dict[str, Any]] = []

    def _add(label_en: str, label_zh: str, value: Any, unit: str,
             fmt: str, color: str, tier: int) -> None:
        cards.append({
            "label_en": label_en,
            "label_zh": label_zh,
            "value": value,
            "unit": unit,
            "fmt": fmt,
            "color": color,
            "tier": tier,
        })

    # Tier 1: State Estimation Accuracy
    _add("Voltage RMSE", "电压RMSE",
         metrics.get("voltage_rmse"), "p.u.", ".4f",
         _grade_color(metrics.get("voltage_rmse"), (0.005, 0.02)), 1)

    _add("Voltage MAPE", "电压MAPE",
         metrics.get("voltage_mape"), "%", ".2f",
         _grade_color(metrics.get("voltage_mape"), (1.0, 3.0)), 1)

    _add("Voltage Max Err", "电压最大误差",
         metrics.get("voltage_max_error"), "p.u.", ".4f",
         _grade_color(metrics.get("voltage_max_error"), (0.01, 0.05)), 1)

    _add("Angle RMSE", "角度RMSE",
         metrics.get("angle_rmse"), "°", ".2f",
         _grade_color(metrics.get("angle_rmse"), (1.0, 5.0)), 1)

    # Tier 2: Flow Estimation Accuracy
    _add("Flow RMSE", "潮流RMSE",
         metrics.get("flow_rmse"), "MW", ".2f",
         _grade_color(metrics.get("flow_rmse"), (2.0, 10.0)), 2)

    _add("Flow Max Err", "潮流最大误差",
         metrics.get("flow_max_error"), "MW", ".2f",
         _grade_color(metrics.get("flow_max_error"), (5.0, 20.0)), 2)

    _add("Flow P95 Err", "潮流P95误差",
         metrics.get("flow_p95_error"), "MW", ".2f",
         _grade_color(metrics.get("flow_p95_error"), (3.0, 15.0)), 2)

    _add("Loading RMSE", "负载率RMSE",
         metrics.get("loading_rmse"), "%", ".2f",
         _grade_color(metrics.get("loading_rmse"), (5.0, 20.0)), 2)

    # Tier 3: Physical Consistency
    _add("Balance Error", "功率平衡误差",
         metrics.get("power_balance_error"), "MW", ".3f",
         _grade_color(metrics.get("power_balance_error"), (0.1, 1.0)), 3)

    _add("KCL Self-Viol", "KCL自洽违反率",
         metrics.get("kcl_self_violation_rate"), "%", ".1f",
         _grade_color(metrics.get("kcl_self_violation_rate"), (10.0, 30.0)), 3)

    _add("KCL Max ΔP", "KCL最大偏差",
         metrics.get("kcl_max_mismatch_mw"), "MW", ".2f",
         _grade_color(metrics.get("kcl_max_mismatch_mw"), (2.0, 10.0)), 3)

    _add("Flow Deviation", "潮流偏差率",
         metrics.get("flow_deviation_rate"), "%", ".1f",
         _grade_color(metrics.get("flow_deviation_rate"), (5.0, 20.0)), 3)

    _add("Voltage F1", "电压越限F1",
         metrics.get("voltage_f1"), "", ".3f",
         _grade_color_higher_better(metrics.get("voltage_f1"), (0.8, 0.5)), 3)

    conv_match = metrics.get("convergence_match")
    _add("Conv. Match", "收敛一致",
         conv_match, "", "",
         _GREEN if conv_match else _RED, 3)

    # Tier 4: Advanced
    _add("Flow Dir Acc", "潮流方向准确率",
         metrics.get("flow_direction_accuracy"), "%", ".1f",
         _grade_color_higher_better(metrics.get("flow_direction_accuracy"), (95.0, 80.0)), 4)

    _add("Weak Bus Jaccard", "薄弱母线Jaccard",
         metrics.get("critical_bus_jaccard"), "", ".3f",
         _grade_color_higher_better(metrics.get("critical_bus_jaccard"), (0.6, 0.3)), 4)

    return cards
