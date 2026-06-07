"""Academic-style flow distribution diagram."""

from __future__ import annotations

from typing import Any, Literal, Optional
import math

import pandas as pd
import plotly.graph_objects as go

from models.schemas import LineFlow, PowerFlowResult
from viz.network_plot import Theme, bus_display_id, build_graph, classify_bus_sets, compute_layout


ColorScheme = Literal["light", "dark", "print"]


def _line_id(kind: str, element_id: int) -> int:
    return int(element_id) if kind == "line" else 100000 + int(element_id)


def _ieee14_display_positions() -> dict[int, tuple[float, float]]:
    # Textbook-style layout (Bus1 upper-left, Bus8 right-end).
    return {
        1: (0.0, 8.0),
        2: (2.5, 8.0),
        3: (8.0, 0.5),
        4: (6.0, 4.0),
        5: (3.5, 5.0),
        6: (2.0, 5.0),
        7: (7.0, 3.0),
        8: (9.0, 2.0),
        9: (5.5, 3.0),
        10: (3.5, 3.0),
        11: (2.0, 3.5),
        12: (0.5, 4.0),
        13: (1.0, 3.0),
        14: (3.5, 1.5),
    }


def _internal_positions_from_display(net: Any, disp_pos: dict[int, tuple[float, float]]) -> dict[int, tuple[float, float]]:
    out: dict[int, tuple[float, float]] = {}
    for bi in net.bus.index.tolist():
        bid = int(bus_display_id(net, int(bi)))
        if bid in disp_pos:
            out[int(bi)] = disp_pos[bid]
    return out


def _palette(scheme: ColorScheme, theme: Theme) -> dict[str, str]:
    if scheme == "dark" or theme == "dark":
        return {
            "paper_bg": "#0f172a",
            "plot_bg": "#0f172a",
            "text": "#e5e7eb",
            "light": "#3182CE",
            "heavy": "#DD6B20",
            "over": "#E53E3E",
            "slack_edge": "#E53E3E",
            "slack_fill": "#3b0f14",
            "pv_edge": "#3182CE",
            "pv_fill": "#0b2545",
            "pq_fill": "#6b7280",
            "pq_edge": "#9ca3af",
            "label_bg": "rgba(17,24,39,0.72)",
            "label_border": "rgba(229,231,235,0.70)",
        }
    if scheme == "print":
        return {
            "paper_bg": "#FFFFFF",
            "plot_bg": "#FFFFFF",
            "text": "#111827",
            "light": "#3182CE",
            "heavy": "#DD6B20",
            "over": "#E53E3E",
            "slack_edge": "#C53030",
            "slack_fill": "#FFFFFF",
            "pv_edge": "#2B6CB0",
            "pv_fill": "#FFFFFF",
            "pq_fill": "#4B5563",
            "pq_edge": "#374151",
            "label_bg": "rgba(255,255,255,0.95)",
            "label_border": "rgba(203,213,225,1.0)",
        }
    return {
        "paper_bg": "#FAFBFE",
        "plot_bg": "#FAFBFE",
        "text": "#111827",
        "light": "#3182CE",
        "heavy": "#DD6B20",
        "over": "#E53E3E",
        "slack_edge": "#C53030",
        "slack_fill": "#FFF5F5",
        "pv_edge": "#2B6CB0",
        "pv_fill": "#EBF4FF",
        "pq_fill": "#9CA3AF",
        "pq_edge": "#6B7280",
        "label_bg": "rgba(255,255,255,0.88)",
        "label_border": "rgba(226,232,240,0.95)",
    }


def _load_level_key(loading: float, heavy_th: float, over_th: float) -> str:
    if loading >= over_th:
        return "over"
    if loading >= heavy_th:
        return "heavy"
    return "light"


def _load_level_label(level_key: str, lang: str) -> str:
    if lang == "zh":
        return {
            "light": "轻载",
            "heavy": "重载",
            "over": "过载",
        }.get(level_key, level_key)
    return {
        "light": "Light load",
        "heavy": "Heavy load",
        "over": "Overloaded",
    }.get(level_key, level_key)


def _line_color(loading: float, heavy_th: float, over_th: float, pal: dict[str, str]) -> str:
    if loading >= over_th:
        return pal["over"]
    if loading >= heavy_th:
        return pal["heavy"]
    return pal["light"]


def _line_width(p_abs: float, p_max: float) -> float:
    lo, hi = 1.5, 6.0
    if p_max <= 1e-9:
        return lo
    # Non-linear scaling improves contrast on medium/low-flow branches.
    t = math.sqrt(max(0.0, min(1.0, float(p_abs) / float(p_max))))
    return float(lo + (hi - lo) * t)


def _perp_offset(x0: float, y0: float, x1: float, y1: float, dist: float) -> tuple[float, float]:
    dx, dy = (x1 - x0), (y1 - y0)
    n = math.hypot(dx, dy)
    if n <= 1e-9:
        return 0.0, 0.0
    return (-dy / n * dist, dx / n * dist)


def _axis_ranges(positions: dict[int, tuple[float, float]], *, force_ieee14: bool) -> tuple[list[float], list[float]]:
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
    # Add symmetric margins and keep equal aspect (y scale anchored to x).
    pad_x = 0.12 * dx
    pad_y = 0.12 * dy
    return [xmin - pad_x, xmax + pad_x], [ymin - pad_y, ymax + pad_y]


def _display_shift(net: Any) -> int:
    ids = [int(bus_display_id(net, int(i))) for i in net.bus.index.tolist()]
    n = len(ids)
    s = set(ids)
    if s == set(range(n)):
        return 1
    return 0


def _display_label_maps(net: Any, disp_shift: int) -> tuple[dict[int, int], dict[int, int], bool]:
    """Return (internal->raw_display, raw_display->identity, use_dense_labels)."""
    internal_raw: dict[int, int] = {}
    for bi in net.bus.index.tolist():
        internal_raw[int(bi)] = int(bus_display_id(net, int(bi))) + int(disp_shift)
    raw_ids = sorted(set(internal_raw.values()))
    raw_to_dense = {rid: rid for rid in raw_ids}
    # Keep real MATPOWER bus ids; do not compress high/non-contiguous ids to 1..N.
    return internal_raw, raw_to_dense, False


def _bus_injection_map(net: Any) -> tuple[dict[int, float], dict[int, float]]:
    p_inj: dict[int, float] = {int(i): 0.0 for i in net.bus.index.tolist()}
    q_inj: dict[int, float] = {int(i): 0.0 for i in net.bus.index.tolist()}

    if hasattr(net, "res_ext_grid") and hasattr(net, "ext_grid") and len(net.res_ext_grid) > 0:
        for idx, row in net.res_ext_grid.iterrows():
            b = int(net.ext_grid.at[idx, "bus"])
            p_inj[b] += float(row.get("p_mw", 0.0))
            q_inj[b] += float(row.get("q_mvar", 0.0))
    if hasattr(net, "res_gen") and hasattr(net, "gen") and len(net.res_gen) > 0:
        for idx, row in net.res_gen.iterrows():
            b = int(net.gen.at[idx, "bus"])
            p_inj[b] += float(row.get("p_mw", 0.0))
            q_inj[b] += float(row.get("q_mvar", 0.0))
    if hasattr(net, "res_sgen") and hasattr(net, "sgen") and len(net.res_sgen) > 0:
        for idx, row in net.res_sgen.iterrows():
            b = int(net.sgen.at[idx, "bus"])
            p_inj[b] += float(row.get("p_mw", 0.0))
            q_inj[b] += float(row.get("q_mvar", 0.0))
    if hasattr(net, "res_load") and hasattr(net, "load") and len(net.res_load) > 0:
        for idx, row in net.res_load.iterrows():
            b = int(net.load.at[idx, "bus"])
            p_inj[b] -= float(row.get("p_mw", 0.0))
            q_inj[b] -= float(row.get("q_mvar", 0.0))
    return p_inj, q_inj


def _branch_df(
    net: Any,
    result: PowerFlowResult,
    branch_override_df: Optional[pd.DataFrame],
) -> pd.DataFrame:
    rows: list[dict[str, float | int | str]] = []
    g = build_graph(net)
    flow_map: dict[int, LineFlow] = {int(x.line_id): x for x in result.line_flows}
    for u, v, data in g.edges(data=True):
        kind = str(data.get("kind", "line"))
        eid = int(data.get("element_id", -1))
        lf = flow_map.get(_line_id(kind, eid))
        if lf is None:
            continue
        rows.append(
            {
                "kind": kind,
                "element_id": eid,
                "u": int(u),
                "v": int(v),
                "from_bus": int(lf.from_bus),
                "to_bus": int(lf.to_bus),
                "p_from_mw": float(lf.p_from_mw),
                "q_from_mvar": float(lf.q_from_mvar),
                "loading_percent": float(lf.loading_percent),
            }
        )
    df = pd.DataFrame(rows)

    if branch_override_df is None or df.empty:
        return df
    need = {"from_bus", "to_bus", "p_from_mw"}
    if not need.issubset(set(branch_override_df.columns)):
        return df

    ov = branch_override_df.copy()
    for c in ["from_bus", "to_bus"]:
        ov[c] = pd.to_numeric(ov[c], errors="coerce").astype("Int64")
    for c in ["p_from_mw", "q_from_mvar", "loading_percent"]:
        if c in ov.columns:
            ov[c] = pd.to_numeric(ov[c], errors="coerce")
    ov = ov.dropna(subset=["from_bus", "to_bus", "p_from_mw"])

    key = {(int(r["from_bus"]), int(r["to_bus"])): r for _, r in ov.iterrows()}
    key_rev = {(int(r["to_bus"]), int(r["from_bus"])): r for _, r in ov.iterrows()}

    upd_rows: list[dict[str, float | int | str]] = []
    for _, r in df.iterrows():
        fb, tb = int(r["from_bus"]), int(r["to_bus"])
        hit = key.get((fb, tb))
        sign = 1.0
        if hit is None:
            hit = key_rev.get((fb, tb))
            sign = -1.0 if hit is not None else 1.0
        row = dict(r)
        if hit is not None:
            row["p_from_mw"] = float(hit["p_from_mw"]) * sign
            if "q_from_mvar" in hit and pd.notna(hit["q_from_mvar"]):
                row["q_from_mvar"] = float(hit["q_from_mvar"]) * sign
            if "loading_percent" in hit and pd.notna(hit["loading_percent"]):
                row["loading_percent"] = float(hit["loading_percent"])
        upd_rows.append(row)
    return pd.DataFrame(upd_rows)


def resolve_flow_positions(
    net: Any,
    result: PowerFlowResult,
    *,
    positions: Optional[dict[int, tuple[float, float]]] = None,
    use_ieee14_fixed_layout: bool = True,
    graph: Optional[Any] = None,
) -> dict[int, tuple[float, float]]:
    """Resolve the exact bus coordinates used by the flow diagram."""
    g = graph if graph is not None else build_graph(net)
    case_name = str(getattr(result, "case_name", "") or "")

    if use_ieee14_fixed_layout and case_name.lower() == "case14":
        resolved = _internal_positions_from_display(net, _ieee14_display_positions())
        if len(resolved) < len(g.nodes):
            auto = positions if positions is not None else compute_layout(net, g)
            for bi, pos in auto.items():
                resolved.setdefault(int(bi), (float(pos[0]), float(pos[1])))
        return resolved

    if positions is None:
        return compute_layout(net, g)

    return {int(bi): (float(pos[0]), float(pos[1])) for bi, pos in positions.items()}


def make_flow_diagram(
    net: Any,
    result: PowerFlowResult,
    *,
    positions: Optional[dict[int, tuple[float, float]]] = None,
    theme: Theme = "light",
    lang: Literal["zh", "en"] = "zh",
    label_threshold_mw: float = 0.0,
    max_labels: int = 60,
    heavy_threshold: float = 60.0,
    over_threshold: float = 100.0,
    show_power_labels: bool = True,
    show_flow_arrows: bool = True,
    show_voltage_overlay: bool = False,
    color_scheme: ColorScheme = "light",
    use_ieee14_fixed_layout: bool = True,
    # Kept for API compatibility; Phase 1 uses static rendering only.
    enable_entrance_animation: bool = True,
    branch_override_df: Optional[pd.DataFrame] = None,
) -> go.Figure:
    g = build_graph(net)
    case_name = str(getattr(result, "case_name", "") or "")
    disp_shift = _display_shift(net)
    n_bus = int(len(g.nodes))
    internal_raw, raw_to_dense, use_dense_labels = _display_label_maps(net, disp_shift)
    positions = resolve_flow_positions(
        net,
        result,
        positions=positions,
        use_ieee14_fixed_layout=use_ieee14_fixed_layout,
        graph=g,
    )

    pal = _palette(color_scheme, theme)
    fig = go.Figure()
    px = [float(v[0]) for v in positions.values()] if positions else [0.0]
    py = [float(v[1]) for v in positions.values()] if positions else [0.0]
    span_x = max(px) - min(px) if px else 1.0
    span_y = max(py) - min(py) if py else 1.0
    span = max(1e-6, max(span_x, span_y))
    bus_label_dy = 0.035 * span
    slack_text_dy = 0.038 * span
    gen_text_dy = 0.032 * span
    flow_label_perp = 0.024 * span

    bdf = _branch_df(net, result, branch_override_df)
    if disp_shift != 0 and not bdf.empty:
        bdf = bdf.copy()
        bdf["from_bus"] = bdf["from_bus"].astype(int) + disp_shift
        bdf["to_bus"] = bdf["to_bus"].astype(int) + disp_shift
    if use_dense_labels and not bdf.empty:
        bdf = bdf.copy()
        bdf["from_bus_raw"] = bdf["from_bus"].astype(int)
        bdf["to_bus_raw"] = bdf["to_bus"].astype(int)
        bdf["from_bus"] = bdf["from_bus"].map(lambda x: int(raw_to_dense.get(int(x), int(x))))
        bdf["to_bus"] = bdf["to_bus"].map(lambda x: int(raw_to_dense.get(int(x), int(x))))
    elif not bdf.empty:
        bdf = bdf.copy()
        bdf["from_bus_raw"] = bdf["from_bus"].astype(int)
        bdf["to_bus_raw"] = bdf["to_bus"].astype(int)
    p_max = max(1e-6, float(bdf["p_from_mw"].abs().max())) if not bdf.empty else 1.0
    show_power_labels_eff = bool(show_power_labels) and n_bus <= 50
    show_flow_arrows_eff = bool(show_flow_arrows)
    line_scale = 0.7 if n_bus > 100 else 1.0
    node_scale = 0.6 if n_bus > 100 else 1.0
    is_en = str(lang).lower().startswith("en")
    label_branch = "Branch" if is_en else "支路"
    label_bus = "Bus" if is_en else "母线"
    label_raw = "raw" if is_en else "原始"
    label_angle = "Angle" if is_en else "相角"
    label_p_inj = "P_inj" if is_en else "有功注入"
    label_q_inj = "Q_inj" if is_en else "无功注入"
    label_level = "Level" if is_en else "负载等级"
    legend_light = "Light load" if is_en else "轻载"
    legend_heavy = "Heavy load" if is_en else "重载"
    legend_over = "Overloaded" if is_en else "过载"
    legend_slack = "Slack bus" if is_en else "平衡母线"
    legend_pv = "PV bus" if is_en else "PV 母线"
    legend_pq = "PQ bus" if is_en else "PQ 母线"
    slack_text = "<b>Slack</b>" if is_en else "<b>平衡</b>"
    base_text = "Base: 100 MVA" if is_en else "基准: 100 MVA"

    # Branches + arrows + labels
    for _, br in bdf.iterrows():
        u = int(br["u"])
        v = int(br["v"])
        x0, y0 = positions[u]
        x1, y1 = positions[v]
        p_mw = float(br["p_from_mw"])
        q_mvar = float(br["q_from_mvar"])
        loading = float(br["loading_percent"])
        level_key = _load_level_key(loading, heavy_threshold, over_threshold)
        level = _load_level_label(level_key, "en" if is_en else "zh")
        color = _line_color(loading, heavy_threshold, over_threshold, pal)
        width = _line_width(abs(p_mw), p_max) * line_scale

        fig.add_trace(
            go.Scatter(
                x=[x0, x1],
                y=[y0, y1],
                mode="lines",
                line=dict(color=color, width=width),
                opacity=0.82,
                hovertemplate=(
                    f"{label_branch} {int(br['from_bus'])}->{int(br['to_bus'])}<br>"
                    f"P={p_mw:.2f} MW<br>"
                    f"Q={q_mvar:.2f} Mvar<br>"
                    f"{label_level}={level}<extra></extra>"
                ),
                showlegend=False,
            )
        )

        # Direction marker at midpoint (u->v if P>=0 else reversed)
        if show_flow_arrows_eff:
            if p_mw >= 0.0:
                sx, sy, ex, ey = x0, y0, x1, y1
            else:
                sx, sy, ex, ey = x1, y1, x0, y0
            mx = (sx + ex) / 2.0
            my = (sy + ey) / 2.0
            fig.add_trace(
                go.Scatter(
                    x=[mx],
                    y=[my],
                    mode="markers",
                    marker=dict(
                        symbol="triangle-right",
                        size=max(8.0, 5.0 + 0.55 * width),
                        color=color,
                        angle=0,
                        angleref="previous",
                    ),
                    hoverinfo="skip",
                    showlegend=False,
                )
            )

        if show_power_labels_eff and abs(p_mw) >= float(label_threshold_mw):
            mx, my = (x0 + x1) / 2.0, (y0 + y1) / 2.0
            ox, oy = _perp_offset(x0, y0, x1, y1, flow_label_perp)
            fig.add_annotation(
                x=mx + ox,
                y=my + oy,
                text=f"{abs(p_mw):.1f} MW",
                showarrow=False,
                font=dict(size=10, color=pal["text"], family="Times New Roman, serif"),
                bgcolor=pal["label_bg"],
                bordercolor=pal["label_border"],
                borderwidth=1,
                borderpad=2,
            )

    # Node data
    vm_map = {int(v.bus_id): float(v.vm_pu) for v in result.bus_voltages}
    va_map = {int(v.bus_id): float(v.va_deg) for v in result.bus_voltages}
    if disp_shift != 0:
        vm_map = {int(k) + disp_shift: float(v) for k, v in vm_map.items()}
        va_map = {int(k) + disp_shift: float(v) for k, v in va_map.items()}
    if use_dense_labels:
        vm_map = {int(raw_to_dense.get(int(k), int(k))): float(v) for k, v in vm_map.items()}
        va_map = {int(raw_to_dense.get(int(k), int(k))): float(v) for k, v in va_map.items()}
    p_inj, q_inj = _bus_injection_map(net)

    slack_internal, pv_internal, pq_internal, _inactive_internal = classify_bus_sets(net)

    for bi in g.nodes:
        bidx = int(bi)
        bid_raw = int(internal_raw.get(bidx, int(bus_display_id(net, bidx)) + disp_shift))
        bid = int(raw_to_dense.get(bid_raw, bid_raw))
        x, y = positions[bidx]
        vm = float(vm_map.get(bid, 1.0))
        va = float(va_map.get(bid, 0.0))
        pinj = float(p_inj.get(bidx, 0.0))
        qinj = float(q_inj.get(bidx, 0.0))

        is_slack = bidx in slack_internal
        if is_slack:
            ntype = "slack"
            marker = dict(
                symbol="square",
                size=22 * node_scale,
                color=pal["slack_fill"],
                line=dict(color=pal["slack_edge"], width=max(1.2, 2.5 * node_scale)),
            )
        elif bidx in pv_internal:
            ntype = "pv"
            marker = dict(
                symbol="circle",
                size=18 * node_scale,
                color=pal["pv_fill"],
                line=dict(color=pal["pv_edge"], width=max(1.0, 2.2 * node_scale)),
            )
        elif bidx in pq_internal:
            ntype = "pq"
            node_color = pal["pq_fill"]
            if show_voltage_overlay:
                # Simple voltage tint overlay for PQ nodes only.
                node_color = "#7ec8e3" if vm >= 1.05 else ("#f2b8b5" if vm <= 0.95 else pal["pq_fill"])
            marker = dict(
                symbol="circle",
                size=12 * node_scale,
                color=node_color,
                line=dict(color=pal["pq_edge"], width=max(0.8, 1.2 * node_scale)),
            )
        else:
            ntype = "inactive"
            marker = dict(
                symbol="circle",
                size=10 * node_scale,
                color="#c7ccd1",
                line=dict(color="#9aa0a6", width=max(0.6, 1.0 * node_scale)),
            )

        fig.add_trace(
            go.Scatter(
                x=[x],
                y=[y],
                mode="markers",
                marker=marker,
                hovertemplate=(
                    f"{label_bus} {bid}" + (f" ({label_raw} {bid_raw})" if use_dense_labels else "") + "<br>"
                    f"V={vm:.3f} p.u.<br>"
                    f"{label_angle}={va:.2f} deg<br>"
                    f"{label_p_inj}={pinj:.2f} MW<br>"
                    f"{label_q_inj}={qinj:.2f} Mvar<extra></extra>"
                ),
                showlegend=False,
            )
        )

        # Large systems: show bus number only for slack/PV to reduce clutter.
        show_bus_no = True if n_bus <= 50 else (ntype in {"slack", "pv"})
        if show_bus_no:
            fig.add_annotation(
                x=x,
                y=y + bus_label_dy,
                text=f"<b>{bid}</b>",
                showarrow=False,
                font=dict(size=12 if ntype == "slack" else 11, color=pal["text"], family="Times New Roman, serif"),
            )
        if ntype == "slack":
            fig.add_annotation(
                x=x,
                y=y - slack_text_dy,
                text=slack_text,
                showarrow=False,
                font=dict(size=9, color=pal["slack_edge"], family="Times New Roman, serif"),
            )
        elif ntype == "pv":
            fig.add_annotation(
                x=x,
                y=y - gen_text_dy,
                text="<i>G</i>",
                showarrow=False,
                font=dict(size=10, color=pal["pv_edge"], family="Times New Roman, serif"),
            )

    # Legend (3 line levels + 3 bus types)
    fig.add_trace(go.Scatter(x=[None], y=[None], mode="lines", line=dict(color=pal["light"], width=2.5), name=legend_light, showlegend=True))
    fig.add_trace(go.Scatter(x=[None], y=[None], mode="lines", line=dict(color=pal["heavy"], width=3.5), name=legend_heavy, showlegend=True))
    fig.add_trace(go.Scatter(x=[None], y=[None], mode="lines", line=dict(color=pal["over"], width=4.5), name=legend_over, showlegend=True))
    fig.add_trace(
        go.Scatter(
            x=[None],
            y=[None],
            mode="markers",
            marker=dict(symbol="square", size=12, color=pal["slack_fill"], line=dict(color=pal["slack_edge"], width=2)),
            name=legend_slack,
            showlegend=True,
        )
    )
    fig.add_trace(
        go.Scatter(
            x=[None],
            y=[None],
            mode="markers",
            marker=dict(symbol="circle", size=12, color=pal["pv_fill"], line=dict(color=pal["pv_edge"], width=2)),
            name=legend_pv,
            showlegend=True,
        )
    )
    fig.add_trace(
        go.Scatter(
            x=[None],
            y=[None],
            mode="markers",
            marker=dict(symbol="circle", size=10, color=pal["pq_fill"], line=dict(color=pal["pq_edge"], width=1.5)),
            name=legend_pq,
            showlegend=True,
        )
    )

    force_ieee14 = bool(use_ieee14_fixed_layout and case_name.lower() == "case14")
    xr, yr = _axis_ranges(positions, force_ieee14=force_ieee14)
    if is_en:
        title = (
            f"Power Flow Distribution - {case_name} (IEEE 14-Bus System)"
            if case_name.lower() == "case14"
            else f"Flow Distribution - {case_name}"
        )
    else:
        title = (
            f"\u6f6e\u6d41\u5206\u5e03\u56fe - {case_name} (IEEE 14\u8282\u70b9)"
            if case_name.lower() == "case14"
            else f"\u6f6e\u6d41\u5206\u5e03\u56fe - {case_name}"
        )
    fig.update_layout(
        title=title,
        paper_bgcolor=pal["paper_bg"],
        plot_bgcolor=pal["plot_bg"],
        height=640,
        margin=dict(l=20, r=20, t=70, b=20),
        legend=dict(
            x=0.01,
            y=0.99,
            xanchor="left",
            yanchor="top",
            bgcolor=pal["label_bg"],
            bordercolor=pal["label_border"],
            borderwidth=1,
            font=dict(size=11, family="Times New Roman, serif", color=pal["text"]),
        ),
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False, visible=False, range=xr),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False, visible=False, range=yr, scaleanchor="x"),
        hoverlabel=dict(font=dict(family="Times New Roman, serif", size=12)),
    )
    fig.add_annotation(
        x=0.995,
        y=0.02,
        xref="paper",
        yref="paper",
        xanchor="right",
        yanchor="bottom",
        text=base_text,
        showarrow=False,
        font=dict(size=11, color=pal["text"], family="Times New Roman, serif"),
        bgcolor=pal["label_bg"],
        bordercolor=pal["label_border"],
        borderwidth=1,
        borderpad=2,
    )

    return fig
