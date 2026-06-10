"""Remedial action ranking visualization."""

from __future__ import annotations

from typing import Literal
import re

import plotly.graph_objects as go

from models.schemas import RemedialPlan


Lang = Literal["zh", "en"]


# ── Color palettes ──────────────────────────────────────────────────────────

_PALETTE_LIGHT = {
    "shed": "#3182CE",
    "gen_vm": "#38A169",
    "ext_vm": "#DD6B20",
    "fallback": "#805AD5",
    "zero": "#CBD5E0",
    "line_risk": "#E53E3E",
    "paper": "#FAFBFE",
    "plot": "#FAFBFE",
    "grid": "#EDF2F7",
    "txt": "#111827",
    "txt_secondary": "#718096",
    "insight_bg": "#F0FFF4",
    "insight_border": "#38A169",
    "legend_bg": "rgba(250,251,254,0.88)",
    "badge_bg": "rgba(255,255,255,0.82)",
    "marker_outline": "#FFFFFF",
    "base_risk_line": "#A0AEC0",
}

_PALETTE_DARK = {
    "shed": "#63B3ED",
    "gen_vm": "#68D391",
    "ext_vm": "#F6AD55",
    "fallback": "#B794F4",
    "zero": "#4A5568",
    "line_risk": "#FC8181",
    "paper": "#1A202C",
    "plot": "#1A202C",
    "grid": "#2D3748",
    "txt": "#E2E8F0",
    "txt_secondary": "#A0AEC0",
    "insight_bg": "#1C2631",
    "insight_border": "#68D391",
    "legend_bg": "rgba(26,32,44,0.88)",
    "badge_bg": "rgba(45,55,72,0.82)",
    "marker_outline": "#1A202C",
    "base_risk_line": "#4A5568",
}


# ── Helpers ─────────────────────────────────────────────────────────────────

def _action_color(action: str, risk_reduction: float, p: dict) -> str:
    if abs(risk_reduction) < 1e-9:
        return p["zero"]
    if "shed" in action:
        return p["shed"]
    if "gen_vm" in action:
        return p["gen_vm"]
    if "ext" in action:
        return p["ext_vm"]
    return p["fallback"]


def _action_type_label(action: str, *, lang: str = "en") -> str:
    if "shed" in action:
        return "Load shedding" if lang == "en" else "减载"
    if "gen_vm" in action:
        return "Gen Vm control" if lang == "en" else "发电机调压"
    if "ext" in action:
        return "Ext grid Vm" if lang == "en" else "外网调压"
    return action


def _compact_action_label(desc: str, *, max_len: int = 38) -> str:
    s = " ".join(str(desc).split())
    # Prefer a compact readable token when description follows expected pattern.
    m = re.search(r"(shed|decrease|increase)\s+(\d+)%.*bus\s+(\d+)", s, flags=re.IGNORECASE)
    if m:
        action = m.group(1).lower()
        pct = m.group(2)
        bus = m.group(3)
        verb = "Shed" if action == "shed" else ("Dec Vm" if action == "decrease" else "Inc Vm")
        return f"{verb} {pct}% @ bus {bus}"
    # Match voltage adjustment: "Increase/Decrease ... VM at bus N by +X.XX p.u."
    m2 = re.search(r"(increase|decrease)\s+\w+\s+VM\s+at\s+bus\s+(\d+)\s+by\s+([+-]?[\d.]+)", s, flags=re.IGNORECASE)
    if m2:
        action = m2.group(1).lower()
        bus = m2.group(2)
        delta = m2.group(3)
        verb = "Inc Vm" if action == "increase" else "Dec Vm"
        return f"{verb} {delta} @ bus {bus}"
    if len(s) <= max_len:
        return s
    return s[: max_len - 1] + "\u2026"


def _font(size: int = 11, p: dict | None = None) -> dict:
    color = p["txt"] if p else "#111827"
    return dict(size=size, family="Source Sans 3, sans-serif", color=color)


# ── Main chart ──────────────────────────────────────────────────────────────

def make_remedial_ranking(
    plan: RemedialPlan,
    *,
    theme: str = "light",
    lang: Lang = "en",
) -> go.Figure:
    is_dark = str(theme).lower().startswith("dark")
    p = _PALETTE_DARK if is_dark else _PALETTE_LIGHT

    case_digits = "".join(ch for ch in str(plan.case_name or "") if ch.isdigit())
    case_subtitle = (
        f"IEEE {case_digits}-Bus System" if case_digits else str(plan.case_name or "System")
    )

    actions = list(plan.actions)

    # ── Empty state ──────────────────────────────────────────────────────
    if not actions:
        fig = go.Figure()
        fig.update_layout(
            title=dict(
                text=(
                    f"<span style='font-family:Crimson Pro, serif; font-size:18px'>"
                    f"{'Remedial Action Ranking' if lang == 'en' else '缓解建议排名'}"
                    f"</span><br>"
                    f"<span style='font-family:Source Sans 3, sans-serif; font-size:12px; "
                    f"color:{p['txt_secondary']}'>"
                    f"{'No action generated' if lang == 'en' else '未生成任何建议'}"
                    f"</span>"
                ),
                x=0.01,
                xanchor="left",
                y=0.96,
                yanchor="top",
            ),
            template="plotly_dark" if is_dark else "plotly_white",
            paper_bgcolor=p["paper"],
            plot_bgcolor=p["plot"],
            font=_font(p=p),
        )
        return fig

    # ── Data preparation ─────────────────────────────────────────────────
    labels: list[str] = []
    reductions: list[float] = []
    predicted_risks: list[float] = []
    bar_colors: list[str] = []
    hover_texts: list[str] = []

    for i, a in enumerate(actions):
        labels.append(_compact_action_label(a.description))
        reductions.append(float(a.risk_reduction))
        predicted_risks.append(float(a.predicted_risk))
        bar_colors.append(_action_color(a.action, a.risk_reduction, p))

        reason = (a.parameters or {}).get("reason", "")
        type_label = _action_type_label(a.action, lang=lang)
        if lang == "zh":
            hover_texts.append(
                f"<b>#{i + 1} {a.description}</b><br>"
                f"<b>\u7c7b\u578b</b>: {type_label}<br>"
                f"<b>\u539f\u56e0</b>: {reason}<br>"
                f"<b>\u98ce\u9669\u964d\u4f4e</b>: {float(a.risk_reduction):.2f}<br>"
                f"<b>\u6b8b\u4f59\u98ce\u9669</b>: {float(a.predicted_risk):.2f}<br>"
                f"<b>\u57fa\u51c6\u98ce\u9669</b>: {float(plan.base_risk):.2f}"
            )
        else:
            hover_texts.append(
                f"<b>#{i + 1} {a.description}</b><br>"
                f"<b>Type</b>: {type_label}<br>"
                f"<b>Reason</b>: {reason}<br>"
                f"<b>Risk reduction</b>: {float(a.risk_reduction):.2f}<br>"
                f"<b>Residual risk</b>: {float(a.predicted_risk):.2f}<br>"
                f"<b>Base risk</b>: {float(plan.base_risk):.2f}"
            )

    # ── Bar trace: risk reduction (left y-axis) ──────────────────────────
    bar_text = [f"{v:.1f}" for v in reductions]
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            name=(
                ("Risk reduction" + " " * 8)
                if lang == "en"
                else ("\u98ce\u9669\u964d\u4f4e" + " " * 8)
            ),
            x=labels,
            y=reductions,
            width=0.48,
            text=bar_text,
            textposition="outside",
            textfont=_font(11, p),
            cliponaxis=False,
            hovertext=hover_texts,
            hoverinfo="text",
            marker=dict(
                color=bar_colors,
                line=dict(color=bar_colors, width=0.5),
            ),
            opacity=0.92,
            showlegend=True,
        )
    )

    # ── Scatter trace: residual risk (right y-axis) ──────────────────────
    fig.add_trace(
        go.Scatter(
            name=("Residual risk" if lang == "en" else "\u6b8b\u4f59\u98ce\u9669"),
            x=labels,
            y=predicted_risks,
            mode="lines+markers",
            yaxis="y2",
            line=dict(color=p["line_risk"], width=2.2, dash="dot"),
            marker=dict(
                color=p["line_risk"],
                size=9,
                symbol="diamond",
                line=dict(color=p["marker_outline"], width=1.8),
            ),
            hovertext=hover_texts,
            hoverinfo="text",
            showlegend=True,
        )
    )

    # ── Action type legend proxies ───────────────────────────────────────
    type_color_map = {
        "shed_load": (p["shed"], "Load shedding" if lang == "en" else "\u51cf\u8f7d"),
        "adjust_gen_vm": (p["gen_vm"], "Gen Vm" if lang == "en" else "\u53d1\u7535\u673a\u8c03\u538b"),
        "adjust_ext_grid_vm": (
            p["ext_vm"],
            "Ext grid Vm" if lang == "en" else "\u5916\u7f51\u8c03\u538b",
        ),
    }
    seen_types: set[str] = set()
    for a in actions:
        if a.action in type_color_map and a.action not in seen_types:
            seen_types.add(a.action)
            color, label = type_color_map[a.action]
            fig.add_trace(
                go.Scatter(
                    x=[None],
                    y=[None],
                    mode="markers",
                    marker=dict(size=10, color=color, symbol="square"),
                    name=label,
                    showlegend=False,
                )
            )

    # ── Layout ───────────────────────────────────────────────────────────
    title_main = (
        f"Remedial Action Ranking (Top {len(actions)})"
        if lang == "en"
        else f"\u7f13\u89e3\u5efa\u8bae\u6392\u540d\uff08Top {len(actions)}\uff09"
    )

    fig.update_layout(
        title=dict(
            text=(
                f"<span style='font-family:Crimson Pro, serif; font-size:18px'>"
                f"{title_main}</span><br>"
                f"<span style='font-family:Source Sans 3, sans-serif; font-size:12px; "
                f"color:{p['txt_secondary']}'>{case_subtitle}</span>"
            ),
            x=0.01,
            xanchor="left",
            y=0.96,
            yanchor="top",
        ),
        paper_bgcolor=p["paper"],
        plot_bgcolor=p["plot"],
        margin=dict(l=24, r=70, t=120, b=230),
        bargap=0.36,
        xaxis=dict(
            title=("Action" if lang == "en" else "\u7f13\u89e3\u52a8\u4f5c"),
            showgrid=False,
            tickfont=_font(11, p),
            title_font=_font(13, p),
            tickangle=0,
            automargin=True,
        ),
        yaxis=dict(
            title=(
                "Risk score reduction" if lang == "en" else "\u98ce\u9669\u5206\u6570\u964d\u4f4e"
            ),
            showgrid=True,
            gridcolor=p["grid"],
            zeroline=False,
            tickfont=_font(11, p),
            title_font=_font(13, p),
        ),
        yaxis2=dict(
            title=(
                "Residual risk" if lang == "en" else "\u6b8b\u4f59\u98ce\u9669"
            ),
            overlaying="y",
            side="right",
            showgrid=False,
            tickfont=_font(11, p),
            title_font=_font(13, p),
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.26,
            xanchor="left",
            x=0.01,
            font=_font(12, p),
            bgcolor=p["legend_bg"],
            borderwidth=0,
        ),
        font=_font(p=p),
        template="plotly_dark" if is_dark else "plotly_white",
    )

    # ── Base risk reference line on y2 ───────────────────────────────────
    if plan.base_risk > 0:
        fig.add_hline(
            y=float(plan.base_risk),
            yref="y2",
            line_dash="dash",
            line_color=p["base_risk_line"],
            line_width=1.6,
            opacity=0.7,
        )
        fig.add_annotation(
            x=1.006,
            xref="paper",
            xanchor="right",
            y=float(plan.base_risk),
            yref="y2",
            yanchor="middle",
            text=("Base risk" if lang == "en" else "\u57fa\u51c6\u98ce\u9669"),
            showarrow=True,
            arrowhead=0,
            arrowsize=1,
            arrowwidth=1.2,
            arrowcolor=p["base_risk_line"],
            ax=-18,
            ay=0,
            font=_font(10, p),
            bgcolor=p["badge_bg"],
            bordercolor=p["base_risk_line"],
            borderwidth=1.5,
            borderpad=6,
        )

    # ── Insight box (bottom) ─────────────────────────────────────────────
    best = actions[0]
    pct = (
        (best.risk_reduction / plan.base_risk * 100.0) if plan.base_risk > 0 else 0.0
    )
    type_label = _action_type_label(best.action, lang=lang)

    if lang == "zh":
        insight = (
            f"<b>\u6700\u4f73\u5efa\u8bae</b>\uff1a{best.description} | "
            f"\u7c7b\u578b: {type_label} | "
            f"\u98ce\u9669\u964d\u4f4e {best.risk_reduction:.1f} ({pct:.0f}%) | "
            f"\u6b8b\u4f59\u98ce\u9669 {best.predicted_risk:.1f}"
        )
    else:
        insight = (
            f"<b>Best action</b>: {best.description} | "
            f"Type: {type_label} | "
            f"Reduction {best.risk_reduction:.1f} ({pct:.0f}%) | "
            f"Residual {best.predicted_risk:.1f}"
        )

    fig.add_shape(
        type="rect",
        xref="paper",
        yref="paper",
        x0=0.0,
        x1=1.0,
        y0=-0.82,
        y1=-0.70,
        line=dict(color=p["insight_bg"], width=0),
        fillcolor=p["insight_bg"],
    )
    fig.add_shape(
        type="line",
        xref="paper",
        yref="paper",
        x0=0.0,
        x1=0.0,
        y0=-0.82,
        y1=-0.70,
        line=dict(color=p["insight_border"], width=3),
    )
    fig.add_annotation(
        x=0.01,
        y=-0.76,
        xref="paper",
        yref="paper",
        xanchor="left",
        yanchor="middle",
        text=insight,
        showarrow=False,
        align="left",
        bgcolor=p["insight_bg"],
        bordercolor=p["insight_bg"],
        borderwidth=0,
        borderpad=4,
        font=_font(13, p),
    )

    return fig
