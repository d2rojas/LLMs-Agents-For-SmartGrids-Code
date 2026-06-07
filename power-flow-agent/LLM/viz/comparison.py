"""Before/after what-if comparison plot."""

from __future__ import annotations

from typing import Any, Literal, Optional

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from models.schemas import LineFlow, PowerFlowResult
from viz.network_plot import Theme, build_graph, bus_display_id
from viz.voltage_heatmap import _voltage_colorscale


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


def _bus_vm_map(result: PowerFlowResult) -> dict[int, float]:
    return {int(b.bus_id): float(b.vm_pu) for b in result.bus_voltages}


def _bus_violation_set(result: PowerFlowResult) -> set[int]:
    return {int(b.bus_id) for b in result.voltage_violations}


def _line_flow_map(result: PowerFlowResult) -> dict[int, LineFlow]:
    return {int(l.line_id): l for l in result.line_flows}


def _line_id(kind: str, element_id: int) -> int:
    return int(element_id) if kind == "line" else 100000 + int(element_id)


def make_comparison(
    net: Any,
    before: PowerFlowResult,
    after: PowerFlowResult,
    *,
    positions: Optional[dict[int, tuple[float, float]]] = None,
    theme: Theme = "light",
    lang: Literal["zh", "en"] = "zh",
    topk: int = 5,
    vmin: float = 0.90,
    vmax: float = 1.10,
) -> go.Figure:
    """Side-by-side comparison with explicit change highlighting."""
    # Local import avoids module-level cycles (flow_diagram imports network_plot).
    from viz.flow_diagram import resolve_flow_positions

    g = build_graph(net)
    positions = resolve_flow_positions(
        net,
        after,
        positions=positions,
        use_ieee14_fixed_layout=True,
        graph=g,
    )
    force_ieee14 = str(getattr(after, "case_name", "") or "").lower() == "case14"
    xr, yr = _axis_ranges_like_pf(positions, force_ieee14=force_ieee14)

    bus_idxs = list(net.bus.index.tolist())
    bus_ids = [int(bus_display_id(net, int(i))) for i in bus_idxs]
    bus_pos = {int(bid): (positions[int(i)][0], positions[int(i)][1]) for i, bid in zip(bus_idxs, bus_ids)}

    vm_before = _bus_vm_map(before)
    vm_after = _bus_vm_map(after)
    viol_before = _bus_violation_set(before)
    viol_after = _bus_violation_set(after)

    xs = [bus_pos[bid][0] for bid in bus_ids]
    ys = [bus_pos[bid][1] for bid in bus_ids]
    vb = [float(vm_before.get(bid, 1.0)) for bid in bus_ids]
    va = [float(vm_after.get(bid, 1.0)) for bid in bus_ids]

    bus_delta_v: dict[int, float] = {bid: float(vm_after.get(bid, 1.0) - vm_before.get(bid, 1.0)) for bid in bus_ids}
    changed_bus_ids = {
        bid
        for bid in bus_ids
        if abs(bus_delta_v[bid]) >= 0.005 or ((bid in viol_before) != (bid in viol_after))
    }

    line_before = _line_flow_map(before)
    line_after = _line_flow_map(after)

    changed_edges: list[dict[str, Any]] = []
    edge_delta_candidates: list[dict[str, Any]] = []
    edge_x: list[float] = []
    edge_y: list[float] = []
    for u, v, data in g.edges(data=True):
        x0, y0 = positions[int(u)]
        x1, y1 = positions[int(v)]
        edge_x += [x0, x1, None]
        edge_y += [y0, y1, None]

        kind = str(data.get("kind", "line"))
        eid = int(data.get("element_id", -1))
        lid = _line_id(kind, eid)
        bf = line_before.get(lid)
        af = line_after.get(lid)
        if bf is None and af is None:
            continue

        b_p = float(bf.p_from_mw) if bf is not None else 0.0
        a_p = float(af.p_from_mw) if af is not None else 0.0
        b_loading = float(bf.loading_percent) if bf is not None else 0.0
        a_loading = float(af.loading_percent) if af is not None else 0.0
        b_vi = bool(bf.is_violation) if bf is not None else False
        a_vi = bool(af.is_violation) if af is not None else False

        delta_p = a_p - b_p
        delta_loading = a_loading - b_loading
        edge_info = {
            "kind": kind,
            "eid": eid,
            "lid": lid,
            "from_bus": int(bus_display_id(net, int(u))),
            "to_bus": int(bus_display_id(net, int(v))),
            "x0": x0,
            "y0": y0,
            "x1": x1,
            "y1": y1,
            "before_p": b_p,
            "after_p": a_p,
            "delta_p": delta_p,
            "before_loading": b_loading,
            "after_loading": a_loading,
            "delta_loading": delta_loading,
            "before_violation": b_vi,
            "after_violation": a_vi,
        }
        edge_delta_candidates.append(edge_info)

        changed = abs(delta_p) >= 1.0 or abs(delta_loading) >= 2.0 or (a_vi != b_vi)
        if not changed:
            continue

        changed_edges.append(edge_info)

    changed_edges.sort(
        key=lambda e: max(abs(float(e["delta_loading"])), abs(float(e["delta_p"]))),
        reverse=True,
    )

    fig = make_subplots(
        rows=3,
        cols=1,
        specs=[[{"type": "xy"}], [{"type": "xy"}], [{"type": "table"}]],
        subplot_titles=(
            "Before" if lang == "en" else "修改前",
            "After" if lang == "en" else "修改后",
            "Top Changes" if lang == "en" else "关键变化",
        ),
        row_heights=[0.42, 0.42, 0.16],
        vertical_spacing=0.08,
    )

    # Base network context in both panels.
    base_edge = go.Scatter(
        x=edge_x,
        y=edge_y,
        mode="lines",
        line=dict(color="rgba(160,160,160,0.45)", width=1.8),
        hoverinfo="skip",
        showlegend=False,
    )
    fig.add_trace(base_edge, row=1, col=1)
    fig.add_trace(base_edge, row=2, col=1)

    # Highlight changed branches: subtle in "before", strong in "after".
    highlight_edges = list(changed_edges)
    if not highlight_edges:
        fallback_edges = [e for e in edge_delta_candidates if abs(float(e["delta_p"])) > 1e-9]
        fallback_edges.sort(key=lambda e: abs(float(e["delta_p"])), reverse=True)
        highlight_edges = fallback_edges[: max(1, int(topk))]

    for e in highlight_edges:
        fig.add_trace(
            go.Scatter(
                x=[e["x0"], e["x1"]],
                y=[e["y0"], e["y1"]],
                mode="lines",
                line=dict(color="#DD6B20", width=3, dash="dot"),
                hovertemplate=(
                    f"{e['kind']}#{e['eid']} {e['from_bus']}->{e['to_bus']}<br>"
                    f"P={e['before_p']:.2f} MW, loading={e['before_loading']:.1f}%"
                    "<extra></extra>"
                ),
                showlegend=False,
            ),
            row=1,
            col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=[e["x0"], e["x1"]],
                y=[e["y0"], e["y1"]],
                mode="lines",
                line=dict(color="#d62728", width=4, dash="dash"),
                hovertemplate=(
                    f"{e['kind']}#{e['eid']} {e['from_bus']}->{e['to_bus']}<br>"
                    f"P={e['after_p']:.2f} MW, loading={e['after_loading']:.1f}%<br>"
                    f"Delta P={e['delta_p']:+.2f} MW, Delta loading={e['delta_loading']:+.1f}%"
                    "<extra></extra>"
                ),
                showlegend=False,
            ),
            row=2,
            col=1,
        )

    # Node traces (voltage color) + change highlight.
    node_line_before = ["#d62728" if bid in changed_bus_ids else "rgba(0,0,0,0.3)" for bid in bus_ids]
    node_line_after = ["#d62728" if bid in changed_bus_ids else "rgba(0,0,0,0.3)" for bid in bus_ids]
    node_line_w_before = [3 if bid in changed_bus_ids else 1 for bid in bus_ids]
    node_line_w_after = [3 if bid in changed_bus_ids else 1 for bid in bus_ids]

    fig.add_trace(
        go.Scatter(
            x=xs,
            y=ys,
            mode="markers+text",
            text=[str(bid) for bid in bus_ids],
            textposition="top center",
            marker=dict(
                color=vb,
                colorscale=_voltage_colorscale(),
                cmin=vmin,
                cmax=vmax,
                size=14,
                line=dict(color=node_line_before, width=node_line_w_before),
            ),
            hovertemplate="bus %{text}<br>V(before)=%{marker.color:.4f} pu<extra></extra>",
            showlegend=False,
        ),
        row=1,
        col=1,
    )

    fig.add_trace(
        go.Scatter(
            x=xs,
            y=ys,
            mode="markers+text",
            text=[str(bid) for bid in bus_ids],
            textposition="top center",
            customdata=[[float(bus_delta_v.get(bid, 0.0))] for bid in bus_ids],
            marker=dict(
                color=va,
                colorscale=_voltage_colorscale(),
                cmin=vmin,
                cmax=vmax,
                size=14,
                line=dict(color=node_line_after, width=node_line_w_after),
                colorbar=dict(title="V (p.u.)"),
            ),
            hovertemplate=(
                "bus %{text}<br>"
                "V(after)=%{marker.color:.4f} pu<br>"
                "Delta V=%{customdata[0]:+.4f} pu"
                "<extra></extra>"
            ),
            showlegend=False,
        ),
        row=2,
        col=1,
    )

    # In-plot numeric annotations for key changes.
    n_bus = int(len(bus_ids))
    bus_anno_n = max(3, int(topk))
    edge_anno_n = max(4, int(topk))
    if n_bus > 20:
        bus_anno_n = min(bus_anno_n, 4)
        edge_anno_n = min(edge_anno_n, 2)
    if n_bus > 60:
        bus_anno_n = min(bus_anno_n, 2)
        edge_anno_n = 0

    bus_rank = sorted(changed_bus_ids, key=lambda bid: abs(bus_delta_v[bid]), reverse=True)
    for idx, bid in enumerate(bus_rank[:bus_anno_n]):
        x, y = bus_pos[bid]
        dv = bus_delta_v[bid]
        fig.add_annotation(
            x=x,
            y=y,
            row=2,
            col=1,
            text=f"Delta V={dv:+.3f}" if lang == "en" else f"变化 ΔV={dv:+.3f}",
            showarrow=True,
            arrowhead=0,
            ay=(-18 if idx % 2 == 0 else -28),
            font=dict(size=10, color="#d62728"),
            bgcolor="rgba(255,245,245,0.85)",
            bordercolor="#d62728",
            borderwidth=1,
        )

    edge_anno_source = changed_edges
    if not edge_anno_source:
        edge_anno_source = [e for e in edge_delta_candidates if abs(float(e["delta_p"])) > 1e-9]
        edge_anno_source.sort(key=lambda e: abs(float(e["delta_p"])), reverse=True)

    for idx, e in enumerate(edge_anno_source[:edge_anno_n]):
        fig.add_annotation(
            x=(float(e["x0"]) + float(e["x1"])) / 2.0,
            y=(float(e["y0"]) + float(e["y1"])) / 2.0,
            row=2,
            col=1,
            text=f"Delta P {float(e['delta_p']):+.1f} MW" if lang == "en" else f"变化 ΔP {float(e['delta_p']):+.1f} MW",
            showarrow=True,
            arrowhead=0,
            ax=0,
            ay=(-12 if idx % 2 == 0 else 12),
            font=dict(size=9, color="#d62728"),
            bgcolor="rgba(255,245,245,0.8)",
            borderpad=1,
        )

    table_rows: list[list[str]] = []
    top_n = max(1, int(topk))
    for bid in bus_rank[:top_n]:
        v_before = float(vm_before.get(bid, 1.0))
        v_after = float(vm_after.get(bid, 1.0))
        vchg = (
            f"{'Y' if bid in viol_before else 'N'}→{'Y' if bid in viol_after else 'N'}"
            if lang == "en"
            else f"{'是' if bid in viol_before else '否'}→{'是' if bid in viol_after else '否'}"
        )
        table_rows.append(
            [
                "Bus",
                str(bid),
                f"{v_before:.4f} p.u.",
                f"{v_after:.4f} p.u.",
                f"{(v_after - v_before):+.4f}",
                vchg,
            ]
        )

    for e in changed_edges[:top_n]:
        vchg = (
            f"{'Y' if e['before_violation'] else 'N'}→{'Y' if e['after_violation'] else 'N'}"
            if lang == "en"
            else f"{'是' if e['before_violation'] else '否'}→{'是' if e['after_violation'] else '否'}"
        )
        table_rows.append(
            [
                "Branch",
                f"{e['from_bus']}->{e['to_bus']}",
                f"P={float(e['before_p']):.2f}MW / {float(e['before_loading']):.1f}%",
                f"P={float(e['after_p']):.2f}MW / {float(e['after_loading']):.1f}%",
                f"ΔP={float(e['delta_p']):+.2f}MW, ΔL={float(e['delta_loading']):+.1f}%",
                vchg,
            ]
        )

    if not table_rows:
        table_rows = [["-", "-", "-", "-", "-", "-"]]

    headers = (
        ["Type", "Element", "Before", "After", "Delta", "Violation"]
        if lang == "en"
        else ["类型", "元件", "修改前", "修改后", "变化量", "越限变化"]
    )
    fig.add_trace(
        go.Table(
            header=dict(values=headers, align="left"),
            cells=dict(values=[[r[i] for r in table_rows] for i in range(len(headers))], align="left"),
        ),
        row=3,
        col=1,
    )

    fig.update_layout(
        title=(f"What-if Comparison - {after.case_name}" if lang == "en" else f"修改前后对比 - {after.case_name}"),
        template="plotly_dark" if theme == "dark" else "plotly_white",
        height=1600,
        margin=dict(l=10, r=10, t=80, b=10),
    )

    for r, c in [(1, 1), (2, 1)]:
        fig.update_xaxes(showgrid=False, zeroline=False, visible=False, row=r, col=c)
        fig.update_yaxes(showgrid=False, zeroline=False, visible=False, row=r, col=c)
    fig.update_xaxes(range=xr, row=1, col=1)
    fig.update_yaxes(range=yr, scaleanchor="x", row=1, col=1)
    fig.update_xaxes(range=xr, row=2, col=1)
    fig.update_yaxes(range=yr, scaleanchor="x2", row=2, col=1)

    return fig


# ── 4-panel quantitative comparison ───────────────────────────────────────

_FONT_SANS = "Source Sans 3, sans-serif"
_FONT_SERIF = "Crimson Pro, serif"
_BG_COLOR = "#FAFBFE"


def _qc_font(size: int = 11, color: str = "#111827") -> dict:
    return dict(size=size, family=_FONT_SANS, color=color)


def make_quantitative_comparison(
    before: PowerFlowResult,
    after: PowerFlowResult,
    *,
    vmin: float = 0.95,
    vmax: float = 1.05,
    max_loading: float = 100.0,
    lang: Literal["zh", "en"] = "zh",
) -> go.Figure:
    """Build a 2x2 quantitative comparison figure (voltage, delta-V, loading, table)."""

    # ── Data extraction ──────────────────────────────────────────────────
    before_vm = {int(b.bus_id): float(b.vm_pu) for b in before.bus_voltages}
    after_vm = {int(b.bus_id): float(b.vm_pu) for b in after.bus_voltages}
    all_bus_ids = sorted(set(before_vm.keys()) | set(after_vm.keys()))

    bv = [before_vm.get(bid, 1.0) for bid in all_bus_ids]
    av = [after_vm.get(bid, 1.0) for bid in all_bus_ids]
    dv = [after_vm.get(bid, 1.0) - before_vm.get(bid, 1.0) for bid in all_bus_ids]
    bus_labels = [str(bid) for bid in all_bus_ids]

    # Line loading data
    before_loading_map: dict[int, LineFlow] = {int(lf.line_id): lf for lf in before.line_flows}
    after_loading_map: dict[int, LineFlow] = {int(lf.line_id): lf for lf in after.line_flows}
    all_line_ids = sorted(set(before_loading_map.keys()) | set(after_loading_map.keys()))

    if all_line_ids:
        bl_series = pd.Series({lid: float(before_loading_map[lid].loading_percent) if lid in before_loading_map else 0.0 for lid in all_line_ids})
        al_series = pd.Series({lid: float(after_loading_map[lid].loading_percent) if lid in after_loading_map else 0.0 for lid in all_line_ids})
        max_loading_series = pd.concat([bl_series, al_series], axis=1).max(axis=1)
        top15_idx = max_loading_series.nlargest(15).index.tolist()
    else:
        bl_series = pd.Series(dtype=float)
        al_series = pd.Series(dtype=float)
        top15_idx = []

    def _line_label(lid: int) -> str:
        lf = before_loading_map.get(lid) or after_loading_map.get(lid)
        if lf is not None:
            return f"{lf.from_bus}\u2192{lf.to_bus}"
        return str(lid)

    top15_labels = [_line_label(lid) for lid in top15_idx]
    top15_before = [bl_series.get(lid, 0.0) for lid in top15_idx]
    top15_after = [al_series.get(lid, 0.0) for lid in top15_idx]

    # ── Subplot figure ───────────────────────────────────────────────────
    fig = make_subplots(
        rows=2,
        cols=2,
        specs=[
            [{"type": "xy"}, {"type": "xy"}],
            [{"type": "xy"}, {"type": "table"}],
        ],
        vertical_spacing=0.12,
        horizontal_spacing=0.08,
    )

    # ── Panel 1 (top-left): Voltage magnitude comparison ─────────────────
    all_vm = bv + av
    y_lo = (min(all_vm) - 0.03) if all_vm else (vmin - 0.03)
    y_hi = (max(all_vm) + 0.03) if all_vm else (vmax + 0.03)

    # Violation shading: use x domain so rects span full axis regardless of category count
    fig.add_shape(
        type="rect", xref="x domain", yref="y",
        x0=0, x1=1,
        y0=y_lo, y1=vmin,
        fillcolor="rgba(229,62,62,0.08)", line_width=0,
        row=1, col=1,
    )
    fig.add_shape(
        type="rect", xref="x domain", yref="y",
        x0=0, x1=1,
        y0=vmax, y1=y_hi,
        fillcolor="rgba(229,62,62,0.08)", line_width=0,
        row=1, col=1,
    )

    # Before trace — legendgroup links voltage + loading "Before" traces
    before_label = "Before" if lang == "en" else "修改前"
    after_label = "After" if lang == "en" else "修改后"

    fig.add_trace(
        go.Scatter(
            x=bus_labels, y=bv,
            mode="lines",
            name=before_label,
            line=dict(color="#3182CE", width=1.8, dash="dash"),
            legendgroup="before",
            showlegend=True,
        ),
        row=1, col=1,
    )
    # After trace
    fig.add_trace(
        go.Scatter(
            x=bus_labels, y=av,
            mode="lines+markers",
            name=after_label,
            line=dict(color="#E53E3E", width=2),
            marker=dict(symbol="circle", size=6, color="#E53E3E"),
            legendgroup="after",
            showlegend=True,
        ),
        row=1, col=1,
    )
    # Limit lines
    fig.add_hline(
        y=vmin, line_dash="dash", line_color="#DD6B20", line_width=1.5,
        row=1, col=1,
    )
    fig.add_hline(
        y=vmax, line_dash="dash", line_color="#DD6B20", line_width=1.5,
        row=1, col=1,
    )
    # Limit annotations
    fig.add_annotation(
        x=1.0, xref="x domain", xanchor="right",
        y=vmin, yref="y",
        text=f"{vmin} p.u.",
        showarrow=False,
        font=_qc_font(10, "#DD6B20"),
        bgcolor="rgba(255,255,255,0.8)",
        row=1, col=1,
    )
    fig.add_annotation(
        x=1.0, xref="x domain", xanchor="right",
        y=vmax, yref="y",
        text=f"{vmax} p.u.",
        showarrow=False,
        font=_qc_font(10, "#DD6B20"),
        bgcolor="rgba(255,255,255,0.8)",
        row=1, col=1,
    )

    fig.update_xaxes(type="category", tickfont=_qc_font(9), row=1, col=1)
    fig.update_yaxes(
        range=[y_lo, y_hi],
        title_text="V (p.u.)",
        title_font=_qc_font(11),
        tickfont=_qc_font(9),
        gridcolor="#EDF2F7",
        row=1, col=1,
    )

    # ── Panel 2 (top-right): ΔV bar chart ────────────────────────────────
    bar_colors_dv = ["#38A169" if d >= 0 else "#E53E3E" for d in dv]

    fig.add_trace(
        go.Bar(
            x=bus_labels, y=dv,
            marker_color=bar_colors_dv,
            name="\u0394V",
            showlegend=False,
            hovertemplate="Bus %{x}<br>\u0394V = %{y:+.4f} p.u.<extra></extra>",
        ),
        row=1, col=2,
    )
    # Zero line emphasis
    fig.add_hline(y=0, line_color="#2D3748", line_width=1.5, row=1, col=2)

    fig.update_xaxes(type="category", tickfont=_qc_font(9), row=1, col=2)
    fig.update_yaxes(
        title_text=("\u0394V (p.u.)" if lang == "en" else "\u0394V (p.u.)"),
        title_font=_qc_font(11),
        tickfont=_qc_font(9),
        gridcolor="#EDF2F7",
        row=1, col=2,
    )

    # ── Panel 3 (bottom-left): Top 15 line loading comparison ────────────
    # Use same legendgroup as Panel 1 so toggling "Before"/"After" controls both
    fig.add_trace(
        go.Bar(
            x=top15_labels, y=top15_before,
            name=before_label,
            marker_color="#3182CE",
            legendgroup="before",
            showlegend=False,
        ),
        row=2, col=1,
    )
    fig.add_trace(
        go.Bar(
            x=top15_labels, y=top15_after,
            name=after_label,
            marker_color="#E53E3E",
            legendgroup="after",
            showlegend=False,
        ),
        row=2, col=1,
    )
    # 100% threshold
    fig.add_hline(
        y=max_loading, line_dash="dash", line_color="#E53E3E", line_width=1.5,
        row=2, col=1,
    )

    # Top annotations for bars > 80%
    for i, (lb, la) in enumerate(zip(top15_before, top15_after)):
        if lb > 80:
            fig.add_annotation(
                x=top15_labels[i], y=lb,
                text=f"{lb:.0f}%",
                showarrow=False, yshift=10,
                font=_qc_font(8, "#3182CE"),
                row=2, col=1,
            )
        if la > 80:
            fig.add_annotation(
                x=top15_labels[i], y=la,
                text=f"{la:.0f}%",
                showarrow=False, yshift=10,
                font=_qc_font(8, "#E53E3E"),
                row=2, col=1,
            )

    fig.update_xaxes(
        type="category", tickfont=_qc_font(9), tickangle=-45,
        row=2, col=1,
    )
    fig.update_yaxes(
        title_text="Loading (%)",
        title_font=_qc_font(11),
        tickfont=_qc_font(9),
        gridcolor="#EDF2F7",
        row=2, col=1,
    )

    # ── Panel 4 (bottom-right): Key metrics table ────────────────────────
    before_min_v = min((b.vm_pu for b in before.bus_voltages), default=1.0)
    after_min_v = min((b.vm_pu for b in after.bus_voltages), default=1.0)
    before_v_violations = len(before.voltage_violations)
    after_v_violations = len(after.voltage_violations)
    before_max_loading = max((l.loading_percent for l in before.line_flows), default=0.0)
    after_max_loading = max((l.loading_percent for l in after.line_flows), default=0.0)
    before_thermal_violations = len(before.thermal_violations)
    after_thermal_violations = len(after.thermal_violations)
    before_loss = before.total_loss_mw
    after_loss = after.total_loss_mw
    before_gen = before.total_generation_mw
    after_gen = after.total_generation_mw

    if lang == "zh":
        metric_labels = ["最低电压 (p.u.)", "电压越限节点数", "最大负载率 (%)", "热稳越限线路数", "总损耗 (MW)", "总发电 (MW)"]
    else:
        metric_labels = ["Min Voltage (p.u.)", "V Violation Buses", "Max Loading (%)", "Thermal Violations", "Total Loss (MW)", "Total Gen (MW)"]

    before_vals = [
        f"{before_min_v:.4f}",
        str(before_v_violations),
        f"{before_max_loading:.1f}",
        str(before_thermal_violations),
        f"{before_loss:.2f}",
        f"{before_gen:.2f}",
    ]
    after_vals = [
        f"{after_min_v:.4f}",
        str(after_v_violations),
        f"{after_max_loading:.1f}",
        str(after_thermal_violations),
        f"{after_loss:.2f}",
        f"{after_gen:.2f}",
    ]

    # Compute delta and color: improved=green, worsened=red, neutral=gray
    raw_deltas = [
        (after_min_v - before_min_v, True),           # higher min voltage = better
        (after_v_violations - before_v_violations, False),  # fewer violations = better
        (after_max_loading - before_max_loading, False),    # lower max loading = better
        (after_thermal_violations - before_thermal_violations, False),
        (after_loss - before_loss, False),                  # lower loss = better
        (after_gen - before_gen, None),                     # neutral context
    ]

    delta_strs: list[str] = []
    delta_colors: list[str] = []
    for delta_val, higher_is_better in raw_deltas:
        if abs(delta_val) < 1e-6:
            delta_strs.append("-")
            delta_colors.append("#A0AEC0")
        elif higher_is_better is None:
            delta_strs.append(f"{delta_val:+.2f}")
            delta_colors.append("#A0AEC0")
        elif higher_is_better:
            improved = delta_val > 0
            delta_strs.append(f"{delta_val:+.4f}" if abs(delta_val) < 1 else f"{delta_val:+.2f}")
            delta_colors.append("#38A169" if improved else "#E53E3E")
        else:
            improved = delta_val < 0
            # int deltas (violation counts) use compact format; float uses .2f
            if isinstance(delta_val, int):
                delta_strs.append(f"{delta_val:+d}")
            else:
                delta_strs.append(f"{delta_val:+.2f}")
            delta_colors.append("#38A169" if improved else "#E53E3E")

    header_label = (
        [("指标" if lang == "zh" else "Metric"),
         ("修改前" if lang == "zh" else "Before"),
         ("修改后" if lang == "zh" else "After"),
         ("变化" if lang == "zh" else "Change")]
    )

    n_rows = len(metric_labels)
    cell_fills = [["#F7FAFC" if i % 2 == 0 else "#FFFFFF" for i in range(n_rows)] for _ in range(4)]
    # Override the "Change" column with delta colors (lighter background tint)
    cell_fills[3] = [
        "#F0FFF4" if c == "#38A169" else ("#FFF5F5" if c == "#E53E3E" else "#F7FAFC")
        for c in delta_colors
    ]

    # Per-column font colors: first 3 columns use default text, last column uses delta colors
    default_text = "#111827"
    font_colors = [
        [default_text] * n_rows,
        [default_text] * n_rows,
        [default_text] * n_rows,
        delta_colors,
    ]

    fig.add_trace(
        go.Table(
            header=dict(
                values=header_label,
                fill_color="#2B6CB0",
                font=dict(color="white", size=12, family=_FONT_SANS),
                align="center",
                height=30,
            ),
            cells=dict(
                values=[
                    metric_labels,
                    before_vals,
                    after_vals,
                    delta_strs,
                ],
                fill_color=cell_fills,
                font=dict(size=11, family=_FONT_SANS, color=font_colors),
                align=["left", "center", "center", "center"],
                height=26,
            ),
        ),
        row=2, col=2,
    )

    # ── Subplot title annotations ────────────────────────────────────────
    panel_titles = (
        ["电压幅值对比", "\u0394V 电压变化量", "线路负载率对比 (Top 15)", "关键指标对比"]
        if lang == "zh"
        else ["Voltage Magnitude", "\u0394V Change", "Line Loading (Top 15)", "Key Metrics"]
    )

    # x/y positions for subplot title annotations (above each subplot)
    title_positions = [
        (0.22, 1.06),   # top-left
        (0.78, 1.06),   # top-right
        (0.22, 0.46),   # bottom-left
        (0.78, 0.46),   # bottom-right
    ]
    for (tx, ty), ttxt in zip(title_positions, panel_titles):
        fig.add_annotation(
            text=f"<b>{ttxt}</b>",
            x=tx, y=ty,
            xref="paper", yref="paper",
            xanchor="center", yanchor="bottom",
            showarrow=False,
            font=dict(size=14, family=_FONT_SERIF, color="#111827"),
        )

    # ── Global layout ────────────────────────────────────────────────────
    main_title = "量化对比视图" if lang == "zh" else "Quantitative Comparison"
    case_name = after.case_name or before.case_name or ""

    fig.update_layout(
        title=dict(
            text=(
                f"<span style='font-family:{_FONT_SERIF}; font-size:18px'>"
                f"{main_title}</span><br>"
                f"<span style='font-family:{_FONT_SANS}; font-size:12px; color:#718096'>"
                f"{case_name}</span>"
            ),
            x=0.01, xanchor="left", y=0.98, yanchor="top",
        ),
        height=700,
        paper_bgcolor=_BG_COLOR,
        plot_bgcolor=_BG_COLOR,
        template="plotly_white",
        margin=dict(l=50, r=30, t=90, b=60),
        font=_qc_font(),
        legend=dict(
            orientation="h",
            yanchor="bottom", y=1.08,
            xanchor="left", x=0.01,
            font=_qc_font(11),
            bgcolor="rgba(250,251,254,0.88)",
            borderwidth=0,
        ),
        barmode="group",
    )

    return fig


def compute_comparison_summary(
    before: PowerFlowResult,
    after: PowerFlowResult,
    *,
    max_loading: float = 100.0,
) -> list[dict]:
    """Return summary metrics for the Streamlit bottom row.

    Each dict has: label, before, after, delta, improved (bool).
    """
    bv = len(before.voltage_violations)
    av = len(after.voltage_violations)
    bt = len(before.thermal_violations)
    at_ = len(after.thermal_violations)
    bl = before.total_loss_mw
    al = after.total_loss_mw

    return [
        {
            "label_zh": "电压越限",
            "label_en": "V Violations",
            "before": bv,
            "after": av,
            "delta": av - bv,
            "improved": av < bv,
            "worsened": av > bv,
            "fmt": lambda b, a, d: f"{b} \u2192 {a} (\u2193{abs(d)})" if d < 0 else (f"{b} \u2192 {a} (\u2191{abs(d)})" if d > 0 else f"{b} \u2192 {a}"),
        },
        {
            "label_zh": "热稳越限",
            "label_en": "Thermal Violations",
            "before": bt,
            "after": at_,
            "delta": at_ - bt,
            "improved": at_ < bt,
            "worsened": at_ > bt,
            "fmt": lambda b, a, d: f"{b} \u2192 {a} (\u2193{abs(d)})" if d < 0 else (f"{b} \u2192 {a} (\u2191{abs(d)})" if d > 0 else f"{b} \u2192 {a}"),
        },
        {
            "label_zh": "总损耗",
            "label_en": "Total Loss",
            "before": bl,
            "after": al,
            "delta": al - bl,
            "improved": al < bl,
            "worsened": al > bl,
            "fmt": lambda b, a, d: f"{b:.1f} \u2192 {a:.1f} MW (\u2193{abs(d):.1f})" if d < 0 else (f"{b:.1f} \u2192 {a:.1f} MW (\u2191{abs(d):.1f})" if d > 0 else f"{b:.1f} \u2192 {a:.1f} MW"),
        },
    ]
