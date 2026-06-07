"""Voltage heatmap on the network topology."""

from __future__ import annotations

from typing import Any, Literal, Optional

import plotly.graph_objects as go

from models.schemas import PowerFlowResult
from viz.flow_diagram import resolve_flow_positions
from viz.network_plot import STYLE, Theme, bus_display_id, make_base_network_figure


def _voltage_colorscale() -> list[list[float | str]]:
    """Continuous scale across [0.90, 1.10]."""
    return [
        [0.00, "#d62728"],  # red
        [0.25, "#ffdd57"],  # yellow
        [0.40, "#1a9850"],  # deep green
        [0.60, "#1a9850"],
        [0.75, "#ffdd57"],
        [1.00, "#d62728"],
    ]


def _voltage_zone_legend_items(lang: str) -> list[dict[str, object]]:
    is_en = str(lang).lower().startswith("en")
    return [
        {
            "name": ("Excellent (0.98-1.02)" if is_en else "优良 (0.98-1.02)"),
            "symbol": "circle",
            "color": "#1a9850",
            "line_color": "rgba(0,0,0,0.35)",
            "line_width": 1,
        },
        {
            "name": (
                "Healthy (0.97-0.98 / 1.02-1.03)"
                if is_en
                else "健康 (0.97-0.98 / 1.02-1.03)"
            ),
            "symbol": "circle",
            "color": "#66bd63",
            "line_color": "rgba(0,0,0,0.35)",
            "line_width": 1,
        },
        {
            "name": (
                "Watch (0.95-0.97 / 1.03-1.05)"
                if is_en
                else "注意 (0.95-0.97 / 1.03-1.05)"
            ),
            "symbol": "circle",
            "color": "#ffdd57",
            "line_color": "rgba(0,0,0,0.35)",
            "line_width": 1,
        },
        {
            "name": ("Violation (<0.95 or >1.05)" if is_en else "越限 (<0.95 或 >1.05)"),
            "symbol": "circle",
            "color": "#d62728",
            "line_color": STYLE.violation_color,
            "line_width": 3,
        },
    ]


def _bus_type_legend_items(lang: str) -> list[dict[str, object]]:
    is_en = str(lang).lower().startswith("en")
    return [
        {
            "name": ("Slack bus (diamond)" if is_en else "平衡母线（菱形）"),
            "symbol": "diamond",
            "color": STYLE.slack_color,
        },
        {
            "name": ("PV bus (square)" if is_en else "PV 母线（方片）"),
            "symbol": "square",
            "color": STYLE.gen_color,
        },
        {
            "name": ("PQ bus (circle)" if is_en else "PQ 母线（圆圈）"),
            "symbol": "circle",
            "color": STYLE.load_color,
        },
    ]


def _pick_node_trace(fig: go.Figure) -> Optional[go.Scatter]:
    trace = next((t for t in fig.data if getattr(t, "name", "") == "bus"), None)
    if trace is not None:
        return trace
    return next((t for t in fig.data if "markers" in str(getattr(t, "mode", ""))), None)


def _axis_ranges_like_pf(
    positions: dict[int, tuple[float, float]],
    *,
    force_ieee14: bool,
) -> tuple[list[float], list[float]]:
    if force_ieee14:
        return [-1.9, 10.9], [-0.8, 8.8]
    xs = [float(v[0]) for v in positions.values()]
    ys = [float(v[1]) for v in positions.values()]
    if not xs or not ys:
        return [-1.0, 1.0], [-1.0, 1.0]
    xmin, xmax = min(xs), max(xs)
    ymin, ymax = min(ys), max(ys)
    dx = max(1e-6, xmax - xmin)
    dy = max(1e-6, ymax - ymin)
    pad_x = 0.12 * dx
    pad_y = 0.12 * dy
    return [xmin - pad_x, xmax + pad_x], [ymin - pad_y, ymax + pad_y]


def make_voltage_heatmap(
    net: Any,
    result: PowerFlowResult,
    *,
    positions: Optional[dict[int, tuple[float, float]]] = None,
    theme: Theme = "light",
    lang: Literal["zh", "en"] = "en",
    vmin: float = 0.90,
    vmax: float = 1.10,
) -> go.Figure:
    """Build voltage heatmap on network topology."""

    resolved_positions = resolve_flow_positions(
        net,
        result,
        positions=positions,
        use_ieee14_fixed_layout=True,
    )
    force_ieee14 = str(getattr(result, "case_name", "") or "").lower() == "case14"
    xr, yr = _axis_ranges_like_pf(resolved_positions, force_ieee14=force_ieee14)

    title = (
        f"Voltage Heatmap - {result.case_name}"
        if str(lang).lower().startswith("en")
        else f"电压热力图 - {result.case_name}"
    )
    fig, _ = make_base_network_figure(
        net,
        result,
        positions=resolved_positions,
        theme=theme,
        title=title,
        show_bus_labels=True,
    )

    is_dark = str(theme).lower().startswith("dark")

    # Soften branch context to emphasize bus voltage colors.
    branch_trace = next((t for t in fig.data if getattr(t, "name", "") == "branch"), None)
    if branch_trace is not None and hasattr(branch_trace, "line"):
        branch_trace.line.color = "rgba(148,163,184,0.52)" if is_dark else "rgba(148,163,184,0.38)"
        branch_trace.line.width = 2

    # Keep edge-hover anchors fully transparent.
    hover_trace = next(
        (t for t in fig.data if getattr(t, "mode", None) == "markers" and str(getattr(t, "name", "")) == ""),
        None,
    )
    if hover_trace is not None and hasattr(hover_trace, "marker"):
        hover_trace.marker.color = "rgba(0,0,0,0)"
        hover_trace.marker.line = dict(width=0)

    node_trace = _pick_node_trace(fig)
    if node_trace is None:
        return fig

    bus_idxs = list(net.bus.index.tolist())
    vm_map = {int(b.bus_id): float(b.vm_pu) for b in result.bus_voltages}
    violation_bus_ids = {int(v.bus_id) for v in result.voltage_violations}

    vm_vals: list[float] = []
    is_violation: list[bool] = []
    for bi in bus_idxs:
        bid = int(bus_display_id(net, int(bi)))
        vm_vals.append(float(vm_map.get(bid, 1.0)))
        is_violation.append(bid in violation_bus_ids)

    node_trace.marker.color = vm_vals
    node_trace.marker.colorscale = _voltage_colorscale()
    node_trace.marker.cmin = vmin
    node_trace.marker.cmax = vmax
    node_trace.marker.opacity = 0.97
    node_trace.marker.colorbar = dict(
        title="V (p.u.)",
        len=0.82,
        y=0.50,
        yanchor="middle",
        thickness=18,
        x=1.01,
    )
    node_trace.marker.showscale = True
    node_trace.marker.line.color = [STYLE.violation_color if v else "rgba(31,41,55,0.35)" for v in is_violation]
    node_trace.marker.line.width = [3 if v else 1 for v in is_violation]
    node_trace.textfont = dict(size=10, color=("#d1d5db" if is_dark else "#4b5563"))

    # Discrete legend: voltage zones.
    for item in _voltage_zone_legend_items(lang):
        fig.add_trace(
            go.Scatter(
                x=[None],
                y=[None],
                mode="markers",
                marker=dict(
                    size=10,
                    symbol=str(item["symbol"]),
                    color=item["color"],
                    line=dict(color=item["line_color"], width=item["line_width"]),
                ),
                name=str(item["name"]),
                hoverinfo="skip",
                showlegend=True,
            )
        )

    # Discrete legend: bus type symbols.
    for item in _bus_type_legend_items(lang):
        fig.add_trace(
            go.Scatter(
                x=[None],
                y=[None],
                mode="markers",
                marker=dict(
                    size=10,
                    symbol=str(item["symbol"]),
                    color=item["color"],
                    line=dict(color="rgba(31,41,55,0.75)", width=1),
                ),
                name=str(item["name"]),
                hoverinfo="skip",
                showlegend=True,
            )
        )

    fig.update_layout(
        title=dict(text=title, x=0.02, xanchor="left"),
        showlegend=True,
        legend=dict(
            orientation="v",
            yanchor="top",
            y=0.99,
            xanchor="left",
            x=0.01,
            bgcolor=("rgba(26,32,44,0.82)" if is_dark else "rgba(255,255,255,0.82)"),
            bordercolor=("rgba(160,174,192,0.55)" if is_dark else "rgba(148,163,184,0.55)"),
            borderwidth=1,
            font=dict(size=10, color=("#e5e7eb" if is_dark else "#334155")),
        ),
        height=640,
        xaxis=dict(showgrid=False, zeroline=False, visible=False, range=xr),
        yaxis=dict(showgrid=False, zeroline=False, visible=False, range=yr, scaleanchor="x"),
        margin=dict(l=16, r=24, t=72, b=14),
    )

    return fig
