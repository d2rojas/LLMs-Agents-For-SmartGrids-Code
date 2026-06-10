"""N-1 ranking visualization."""

from __future__ import annotations

from typing import Literal

import plotly.graph_objects as go

from models.schemas import N1Report


Lang = Literal["zh", "en"]


def make_n1_ranking(
    report: N1Report,
    *,
    theme: str = "light",
    lang: Lang = "en",
) -> go.Figure:
    case_digits = "".join(ch for ch in str(report.case_name or "") if ch.isdigit())
    case_subtitle = f"IEEE {case_digits}-Bus System" if case_digits else str(report.case_name or "System")

    labels = [f"Line {r.from_bus}\u2192{r.to_bus}" for r in report.results]
    worst_loading = [
        float(r.worst_loading_percent) if r.worst_loading_percent is not None else 0.0
        for r in report.results
    ]
    delta_total_violations = [
        int(r.delta_voltage_violations) + int(r.delta_thermal_violations) for r in report.results
    ]

    if lang == "zh":
        title_main = f"N-1 Top-{report.top_k}（按最大越限排序）"
        x_title = "故障线路"
        y_left = "最大负载率 (%)"
        y_right = "新增越限数 Δ(相对Base)"
        h = [
            (
                f"<b>断开</b>: {r.from_bus}-{r.to_bus} ({r.branch_type})<br>"
                f"<b>收敛</b>: {r.converged}<br>"
                f"<b>电压越限</b>: {r.n_voltage_violations} (Δ{r.delta_voltage_violations})<br>"
                f"<b>热越限</b>: {r.n_thermal_violations} (Δ{r.delta_thermal_violations})<br>"
                f"<b>最差电压</b>: {r.worst_vm_pu if r.worst_vm_pu is not None else 'NA'}<br>"
                f"<b>最大负载率</b>: {r.worst_loading_percent if r.worst_loading_percent is not None else 'NA'}<br>"
                f"<b>排序分</b>: {r.score:.4f}"
            )
            for r in report.results
        ]
    else:
        title_main = f"N-1 Top-{report.top_k} (sorted by max violations)"
        x_title = "Outaged Line"
        y_left = "Worst loading (%)"
        y_right = "Delta violations (vs base)"
        h = [
            (
                f"<b>Outage</b>: {r.from_bus}-{r.to_bus} ({r.branch_type})<br>"
                f"<b>Converged</b>: {r.converged}<br>"
                f"<b>Voltage violations</b>: {r.n_voltage_violations} (delta {r.delta_voltage_violations})<br>"
                f"<b>Thermal violations</b>: {r.n_thermal_violations} (delta {r.delta_thermal_violations})<br>"
                f"<b>Worst Vm</b>: {r.worst_vm_pu if r.worst_vm_pu is not None else 'NA'}<br>"
                f"<b>Worst loading</b>: {r.worst_loading_percent if r.worst_loading_percent is not None else 'NA'}<br>"
                f"<b>Ranking score</b>: {r.score:.4f}"
            )
            for r in report.results
        ]

    p = {
        "bar_blue": "#3182CE",
        "bar_orange": "#ED8936",
        "bar_red": "#E53E3E",
        "line_purple": "#805AD5",
        "paper": "#FAFBFE",
        "plot": "#FAFBFE",
        "grid": "#EDF2F7",
        "txt": "#111827",
        "insight_bg": "rgba(66, 153, 225, 0.12)",
        "insight_border": "rgba(66, 153, 225, 0.35)",
    }

    def _bar_color(v: float) -> str:
        if v > 130.0:
            return p["bar_red"]
        if v > 100.0:
            return p["bar_orange"]
        return p["bar_blue"]

    bar_colors = [_bar_color(v) for v in worst_loading]
    bar_text = [f"{v:.1f}%" for v in worst_loading]

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            name=(f"{y_left}\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0\u00A0" if lang == "en" else y_left),
            x=labels,
            y=worst_loading,
            width=0.45,
            text=bar_text,
            textposition="outside",
            textfont=dict(size=11, family="Source Sans 3, sans-serif", color=p["txt"]),
            cliponaxis=False,
            hovertext=h,
            hoverinfo="text",
            marker=dict(color=bar_colors, line=dict(color=bar_colors, width=0.5)),
            opacity=0.95,
        )
    )
    fig.add_trace(
        go.Scatter(
            name=("Δ violations" if lang == "en" else "新增越限 Δ"),
            x=labels,
            y=delta_total_violations,
            mode="lines+markers",
            yaxis="y2",
            line=dict(color=p["line_purple"], width=2.4),
            marker=dict(color=p["line_purple"], size=9, symbol="diamond", line=dict(color="#FFFFFF", width=2)),
            hovertext=h,
            hoverinfo="text",
        )
    )

    fig.update_layout(
        title=dict(
            text=(
                f"<span style='font-family:Crimson Pro, serif; font-size:18px'>{title_main}</span><br>"
                f"<span style='font-family:Source Sans 3, sans-serif; font-size:12px; color:#718096'>{case_subtitle}</span>"
            ),
            x=0.01,
            xanchor="left",
            y=0.96,
            yanchor="top",
        ),
        paper_bgcolor=p["paper"],
        plot_bgcolor=p["plot"],
        margin=dict(l=24, r=65, t=124, b=122),
        bargap=0.4,
        xaxis=dict(
            title=x_title,
            showgrid=False,
            tickfont=dict(size=11, family="Source Sans 3, sans-serif", color=p["txt"]),
            title_font=dict(size=13, family="Source Sans 3, sans-serif", color=p["txt"]),
        ),
        yaxis=dict(
            title=y_left,
            showgrid=True,
            gridcolor=p["grid"],
            zeroline=False,
            tickfont=dict(size=11, family="Source Sans 3, sans-serif", color=p["txt"]),
            title_font=dict(size=13, family="Source Sans 3, sans-serif", color=p["txt"]),
        ),
        yaxis2=dict(
            title=y_right,
            overlaying="y",
            side="right",
            showgrid=False,
            dtick=1,
            tick0=0,
            tickfont=dict(size=11, family="Source Sans 3, sans-serif", color=p["txt"]),
            title_font=dict(size=13, family="Source Sans 3, sans-serif", color=p["txt"]),
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.08,
            xanchor="right",
            x=0.98,
            valign="middle",
            font=dict(size=12, family="Source Sans 3, sans-serif", color=p["txt"]),
            bgcolor="rgba(250,251,254,0.88)",
        ),
        font=dict(family="Source Sans 3, sans-serif", color=p["txt"]),
    )

    fig.add_hline(y=100.0, line_dash="dot", line_color=p["bar_red"], opacity=0.9)
    fig.add_annotation(
        x=1.006,
        xref="paper",
        xanchor="right",
        y=100.0,
        yref="y",
        yanchor="middle",
        text="Thermal Limit",
        showarrow=True,
        arrowhead=0,
        arrowsize=1,
        arrowwidth=1.4,
        arrowcolor=p["bar_red"],
        ax=-22,
        ay=0,
        font=dict(size=11, family="Source Sans 3, sans-serif", color=p["bar_red"]),
        bgcolor="#FFF5F5",
        bordercolor=p["bar_red"],
        borderwidth=2.6,
        borderpad=10,
    )

    if report.results:
        w = report.results[0]
        outage_txt = f"Line {w.from_bus}\u2192{w.to_bus}"
        if lang == "zh":
            insight = (
                f"<b>Insight</b>：最严重故障 {outage_txt} | "
                f"worst loading={float(w.worst_loading_percent or 0.0):.1f}% | "
                f"\u0394V越限={int(w.delta_voltage_violations)} | \u0394热越限={int(w.delta_thermal_violations)}"
            )
        else:
            insight = (
                f"<b>Insight</b>: Worst outage {outage_txt} | "
                f"worst loading={float(w.worst_loading_percent or 0.0):.1f}% | "
                f"\u0394V violations={int(w.delta_voltage_violations)} | "
                f"\u0394thermal violations={int(w.delta_thermal_violations)}"
            )
        fig.add_shape(
            type="rect",
            xref="paper",
            yref="paper",
            x0=0.0,
            x1=1.0,
            y0=-0.34,
            y1=-0.22,
            line=dict(color="#FFF5F5", width=0),
            fillcolor="#FFF5F5",
        )
        fig.add_shape(
            type="line",
            xref="paper",
            yref="paper",
            x0=0.0,
            x1=0.0,
            y0=-0.34,
            y1=-0.22,
            line=dict(color="#E53E3E", width=3),
        )
        fig.add_annotation(
            x=0.01,
            y=-0.28,
            xref="paper",
            yref="paper",
            xanchor="left",
            yanchor="middle",
            text=insight,
            showarrow=False,
            align="left",
            bgcolor="#FFF5F5",
            bordercolor="#FFF5F5",
            borderwidth=0,
            borderpad=4,
            font=dict(size=13, family="Source Sans 3, sans-serif", color=p["txt"]),
        )
    return fig
