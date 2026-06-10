"""Network topology plotting helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Optional
import re

import networkx as nx
import plotly.graph_objects as go

from models.schemas import PowerFlowResult


Theme = Literal["light", "dark"]


@dataclass(frozen=True)
class PlotStyle:
    template_light: str = "plotly_white"
    template_dark: str = "plotly_dark"

    node_color_default: str = "#9aa0a6"
    edge_color_default: str = "#c9cdd1"

    gen_color: str = "#1f77b4"
    load_color: str = "#2ca02c"
    slack_color: str = "#9467bd"

    violation_color: str = "#d62728"
    ok_outline: str = "#2ca02c"


STYLE = PlotStyle()


def _template(theme: Theme) -> str:
    return STYLE.template_dark if theme == "dark" else STYLE.template_light


def bus_display_id(net: Any, bus_idx: int) -> int:
    """Internal bus index -> display bus id (prefer net.bus.name)."""
    try:
        name = net.bus.at[bus_idx, "name"]
        s = str(name).strip() if name is not None else ""
        if s and re.fullmatch(r"[-+]?\d+", s):
            return int(s)
    except Exception:
        pass
    # MATPOWER conversion typically uses internal index = MATPOWER bus id - 1.
    return int(bus_idx) + 1


def _in_service_bus_values(table: Any, bus_col: str) -> set[int]:
    if table is None or len(table) == 0 or bus_col not in table.columns:
        return set()
    try:
        if "in_service" in table.columns:
            mask = _in_service_mask(table["in_service"])
            vals = table.loc[mask, bus_col].tolist()
        else:
            vals = table[bus_col].tolist()
        return {int(v) for v in vals}
    except Exception:
        return set()


def _in_service_mask(series: Any) -> Any:
    try:
        return series.astype("boolean").fillna(False).astype(bool)
    except Exception:
        try:
            return series.where(series.notna(), False).astype(bool)
        except Exception:
            return series.apply(lambda x: bool(x) if x is not None else False)


def classify_bus_sets(net: Any) -> tuple[set[int], set[int], set[int], set[int]]:
    """Return (slack, pv, pq, inactive) using strict in-service rules."""
    if not hasattr(net, "bus") or len(net.bus) == 0:
        return set(), set(), set(), set()

    all_buses = {int(i) for i in net.bus.index.tolist()}
    try:
        if "in_service" in net.bus.columns:
            mask = _in_service_mask(net.bus["in_service"])
            active_buses = {int(i) for i in net.bus.index[mask].tolist()}
        else:
            active_buses = set(all_buses)
    except Exception:
        active_buses = set(all_buses)

    ext_grid = getattr(net, "ext_grid", None) if hasattr(net, "ext_grid") else None
    gen = getattr(net, "gen", None) if hasattr(net, "gen") else None

    slack = _in_service_bus_values(ext_grid, "bus") & active_buses
    pv = (_in_service_bus_values(gen, "bus") & active_buses) - slack
    pq = active_buses - slack - pv
    inactive = all_buses - active_buses
    return slack, pv, pq, inactive


def _bus_type(net: Any, bus_idx: int, btype_map: Optional[dict[int, str]] = None) -> str:
    if btype_map is not None:
        return str(btype_map.get(int(bus_idx), "other"))
    slack, pv, pq, _inactive = classify_bus_sets(net)
    b = int(bus_idx)
    if b in slack:
        return "slack"
    if b in pv:
        return "pv"
    if b in pq:
        return "pq"

    try:
        if hasattr(net, "load") and len(net.load) > 0:
            if int(bus_idx) in _in_service_bus_values(net.load, "bus"):
                return "pq"
    except Exception:
        pass
    return "other"


def _physical_bus_set(net: Any, *, include_out_of_service: bool = False) -> set[int]:
    """Collect buses referenced by physical elements."""
    if not hasattr(net, "bus") or len(net.bus) == 0:
        return set()

    all_bus = {int(i) for i in net.bus.index.tolist()}
    refs: set[int] = set()

    def _table_values(table: Any, col: str) -> list[Any]:
        if table is None or len(table) == 0 or col not in table.columns:
            return []
        if include_out_of_service or "in_service" not in table.columns:
            return table[col].tolist()
        mask = _in_service_mask(table["in_service"])
        return table.loc[mask, col].tolist()

    for v in _table_values(getattr(net, "line", None), "from_bus"):
        refs.add(int(v))
    for v in _table_values(getattr(net, "line", None), "to_bus"):
        refs.add(int(v))
    for v in _table_values(getattr(net, "trafo", None), "hv_bus"):
        refs.add(int(v))
    for v in _table_values(getattr(net, "trafo", None), "lv_bus"):
        refs.add(int(v))
    for v in _table_values(getattr(net, "gen", None), "bus"):
        refs.add(int(v))
    for v in _table_values(getattr(net, "load", None), "bus"):
        refs.add(int(v))
    for v in _table_values(getattr(net, "ext_grid", None), "bus"):
        refs.add(int(v))

    refs &= all_bus
    if not include_out_of_service and "in_service" in net.bus.columns:
        try:
            active_bus = {int(i) for i in net.bus.index[_in_service_mask(net.bus["in_service"])].tolist()}
            refs &= active_bus
        except Exception:
            pass

    return refs or set(all_bus)


def build_graph(net: Any, *, include_out_of_service: bool = False) -> nx.Graph:
    """Build undirected topology graph from pandapower net."""
    g = nx.Graph()
    buses = _physical_bus_set(net, include_out_of_service=include_out_of_service)
    for bus_idx in sorted(buses):
        g.add_node(int(bus_idx))

    if hasattr(net, "line") and len(net.line) > 0:
        for idx, row in net.line.iterrows():
            if (not include_out_of_service) and ("in_service" in row) and (not bool(row["in_service"])):
                continue
            fb = int(row["from_bus"])
            tb = int(row["to_bus"])
            if fb in buses and tb in buses:
                g.add_edge(fb, tb, kind="line", element_id=int(idx))

    if hasattr(net, "trafo") and len(net.trafo) > 0:
        for idx, row in net.trafo.iterrows():
            if (not include_out_of_service) and ("in_service" in row) and (not bool(row["in_service"])):
                continue
            hv = int(row["hv_bus"])
            lv = int(row["lv_bus"])
            if hv in buses and lv in buses:
                g.add_edge(hv, lv, kind="trafo", element_id=int(idx))

    return g


def compute_layout(net: Any, g: nx.Graph, *, seed: int = 42) -> dict[int, tuple[float, float]]:
    """Compute layout with geodata priority and case-aware fallback."""

    if hasattr(net, "bus_geodata") and len(net.bus_geodata) > 0:
        pos_geo: dict[int, tuple[float, float]] = {}
        try:
            for b in g.nodes:
                bi = int(b)
                if bi not in net.bus_geodata.index:
                    continue
                row = net.bus_geodata.loc[bi]
                x = float(row["x"])
                y = float(row["y"])
                if not (x == x and y == y):
                    continue
                pos_geo[bi] = (x, y)
        except Exception:
            pos_geo = {}
        if len(pos_geo) >= max(1, int(0.9 * len(g.nodes))):
            xs = [p[0] for p in pos_geo.values()]
            ys = [p[1] for p in pos_geo.values()]
            xmin, xmax = min(xs), max(xs)
            ymin, ymax = min(ys), max(ys)
            dx = max(1e-9, xmax - xmin)
            dy = max(1e-9, ymax - ymin)
            out: dict[int, tuple[float, float]] = {}
            for k, (x, y) in pos_geo.items():
                out[int(k)] = (10.0 * (x - xmin) / dx, 10.0 * (y - ymin) / dy)
            if len(out) == len(g.nodes):
                return out

    n = len(g.nodes)
    case_name = str(getattr(net, "_case_name", "") or getattr(net, "name", "")).lower()
    if case_name in {"case30", "case118", "case300"}:
        pos = nx.kamada_kawai_layout(g)
    elif n <= 14:
        pos = nx.spring_layout(g, seed=seed)
    elif n <= 30:
        pos = nx.spring_layout(g, seed=seed, k=2)
    else:
        pos = nx.kamada_kawai_layout(g)

    xs = [float(v[0]) for v in pos.values()]
    ys = [float(v[1]) for v in pos.values()]
    xmin, xmax = min(xs), max(xs)
    ymin, ymax = min(ys), max(ys)
    dx = max(1e-9, xmax - xmin)
    dy = max(1e-9, ymax - ymin)

    out: dict[int, tuple[float, float]] = {}
    for k, v in pos.items():
        out[int(k)] = (10.0 * (float(v[0]) - xmin) / dx, 10.0 * (float(v[1]) - ymin) / dy)
    return out


def _line_id(kind: str, element_id: int) -> int:
    return int(element_id) if kind == "line" else 100000 + int(element_id)


def _edge_hover(net: Any, u: int, v: int, kind: str, element_id: int, result: Optional[PowerFlowResult]) -> str:
    fb = bus_display_id(net, u)
    tb = bus_display_id(net, v)
    base = f"branch: {kind}#{element_id}<br>bus: {fb} -> {tb}"
    if result is None:
        return base

    target_id = _line_id(kind, element_id)
    lf = next((x for x in result.line_flows if int(x.line_id) == target_id), None)
    if lf is None:
        return base
    return (
        base
        + f"<br>P(from)={lf.p_from_mw:.3f} MW"
        + f"<br>Q(from)={lf.q_from_mvar:.3f} Mvar"
        + f"<br>loading={lf.loading_percent:.1f}%"
    )


def _node_hover(
    net: Any,
    bus_idx: int,
    result: Optional[PowerFlowResult],
    *,
    btype_map: Optional[dict[int, str]] = None,
) -> str:
    bid = bus_display_id(net, bus_idx)
    btype = _bus_type(net, bus_idx, btype_map=btype_map)
    base = f"bus {bid} ({btype})"

    try:
        p_load = 0.0
        q_load = 0.0
        if hasattr(net, "load") and len(net.load) > 0:
            mask = net.load["bus"] == bus_idx
            if mask.any():
                p_load = float(net.load.loc[mask, "p_mw"].sum())
                q_load = float(net.load.loc[mask, "q_mvar"].sum())

        p_gen = 0.0
        if hasattr(net, "gen") and len(net.gen) > 0:
            maskg = net.gen["bus"] == bus_idx
            if maskg.any():
                p_gen = float(net.gen.loc[maskg, "p_mw"].sum())

        base += f"<br>load P/Q={p_load:.2f}/{q_load:.2f}"
        if p_gen != 0.0:
            base += f"<br>gen P(set)={p_gen:.2f}"
    except Exception:
        pass

    if result is None:
        return base

    bv = next((x for x in result.bus_voltages if int(x.bus_id) == int(bid)), None)
    if bv is None:
        return base

    extra = f"<br>V={bv.vm_pu:.4f} pu, angle={bv.va_deg:.2f} deg"
    if bv.is_violation:
        extra += f"<br><b>violation: {bv.violation_type}</b>"
    return base + extra


def make_base_network_figure(
    net: Any,
    result: Optional[PowerFlowResult] = None,
    *,
    positions: Optional[dict[int, tuple[float, float]]] = None,
    theme: Theme = "light",
    title: str = "Network topology",
    show_bus_labels: bool = True,
    node_override: Optional[dict[int, dict[str, Any]]] = None,
) -> tuple[go.Figure, dict[int, tuple[float, float]]]:
    """Build base topology figure and return (fig, positions)."""

    g = build_graph(net)
    if positions is None:
        positions = compute_layout(net, g)
    slack, pv, pq, inactive = classify_bus_sets(net)
    btype_map: dict[int, str] = {int(b): "other" for b in g.nodes}
    for b in inactive:
        btype_map[int(b)] = "inactive"
    for b in pq:
        btype_map[int(b)] = "pq"
    for b in pv:
        btype_map[int(b)] = "pv"
    for b in slack:
        btype_map[int(b)] = "slack"

    # Edge lines
    edge_x: list[float] = []
    edge_y: list[float] = []
    for u, v, _ in g.edges(data=True):
        x0, y0 = positions[int(u)]
        x1, y1 = positions[int(v)]
        edge_x += [x0, x1, None]
        edge_y += [y0, y1, None]

    edge_trace = go.Scatter(
        x=edge_x,
        y=edge_y,
        mode="lines",
        line=dict(color=STYLE.edge_color_default, width=2),
        hoverinfo="skip",
        name="branch",
        showlegend=False,
    )

    # Hover markers at edge midpoints
    hover_x: list[float] = []
    hover_y: list[float] = []
    hover_text: list[str] = []
    for u, v, data in g.edges(data=True):
        x0, y0 = positions[int(u)]
        x1, y1 = positions[int(v)]
        hover_x.append((x0 + x1) / 2.0)
        hover_y.append((y0 + y1) / 2.0)
        hover_text.append(
            _edge_hover(
                net,
                int(u),
                int(v),
                str(data.get("kind", "line")),
                int(data.get("element_id", -1)),
                result,
            )
        )

    edge_hover_trace = go.Scatter(
        x=hover_x,
        y=hover_y,
        mode="markers",
        marker=dict(size=8, color="rgba(0,0,0,0)"),
        hovertemplate="%{text}<extra></extra>",
        text=hover_text,
        name="",
        showlegend=False,
    )

    # Nodes
    node_x: list[float] = []
    node_y: list[float] = []
    hover_texts: list[str] = []
    labels: list[str] = []

    node_color: list[str] = []
    node_symbol: list[str] = []
    node_size: list[int] = []
    node_line_color: list[str] = []
    node_line_width: list[int] = []

    for bus_idx in g.nodes:
        bidx = int(bus_idx)
        x, y = positions[bidx]
        node_x.append(x)
        node_y.append(y)
        hover_texts.append(_node_hover(net, bidx, result, btype_map=btype_map))
        labels.append(str(bus_display_id(net, bidx)) if show_bus_labels else "")

        btype = _bus_type(net, bidx, btype_map=btype_map)
        if btype == "slack":
            c, sym, sz, lc, lw = STYLE.slack_color, "diamond", 18, "#000000", 2
        elif btype == "pv":
            c, sym, sz, lc, lw = STYLE.gen_color, "square", 16, "#000000", 1
        elif btype == "pq":
            c, sym, sz, lc, lw = STYLE.load_color, "circle", 14, "#000000", 1
        elif btype == "inactive":
            c, sym, sz, lc, lw = "#c7ccd1", "circle", 10, "#9aa0a6", 0
        else:
            c, sym, sz, lc, lw = STYLE.node_color_default, "circle", 12, "#000000", 0

        if node_override and bidx in node_override:
            o = node_override[bidx]
            c = o.get("color", c)
            sym = o.get("symbol", sym)
            sz = o.get("size", sz)
            lc = o.get("line_color", lc)
            lw = o.get("line_width", lw)

        node_color.append(c)
        node_symbol.append(sym)
        node_size.append(int(sz))
        node_line_color.append(str(lc))
        node_line_width.append(int(lw))

    node_trace = go.Scatter(
        x=node_x,
        y=node_y,
        mode="markers+text" if show_bus_labels else "markers",
        marker=dict(
            color=node_color,
            symbol=node_symbol,
            size=node_size,
            line=dict(color=node_line_color, width=node_line_width),
        ),
        text=labels if show_bus_labels else None,
        textposition="top center",
        textfont=dict(size=10),
        hovertemplate="%{customdata}<extra></extra>",
        customdata=hover_texts,
        showlegend=False,
        name="bus",
    )

    fig = go.Figure(data=[edge_trace, edge_hover_trace, node_trace])
    fig.update_layout(
        title=title,
        template=_template(theme),
        margin=dict(l=10, r=10, t=60, b=10),
        xaxis=dict(showgrid=False, zeroline=False, visible=False),
        yaxis=dict(showgrid=False, zeroline=False, visible=False),
    )
    return fig, positions


def _axis_ranges_like_pf(
    positions: dict[int, tuple[float, float]],
    *,
    force_ieee14: bool,
) -> tuple[list[float], list[float]]:
    """Axis ranges aligned with PF/voltage-map framing."""
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


def make_violation_overview(
    net: Any,
    result: PowerFlowResult,
    *,
    positions: Optional[dict[int, tuple[float, float]]] = None,
    theme: Theme = "light",
    lang: Literal["zh", "en"] = "zh",
) -> go.Figure:
    """Violation overview with only violating elements strongly emphasized."""

    # Local import avoids module-level circular dependency:
    # flow_diagram -> network_plot, so we import resolver only when needed.
    from viz.flow_diagram import resolve_flow_positions

    g = build_graph(net)
    positions = resolve_flow_positions(
        net,
        result,
        positions=positions,
        use_ieee14_fixed_layout=True,
        graph=g,
    )
    force_ieee14 = str(getattr(result, "case_name", "") or "").lower() == "case14"
    xr, yr = _axis_ranges_like_pf(positions, force_ieee14=force_ieee14)

    slack, pv, pq, inactive = classify_bus_sets(net)
    btype_map: dict[int, str] = {int(b): "other" for b in g.nodes}
    for b in inactive:
        btype_map[int(b)] = "inactive"
    for b in pq:
        btype_map[int(b)] = "pq"
    for b in pv:
        btype_map[int(b)] = "pv"
    for b in slack:
        btype_map[int(b)] = "slack"

    flow_map = {int(lf.line_id): lf for lf in result.line_flows}
    thermal_violation_ids = {int(lf.line_id) for lf in result.thermal_violations}
    voltage_violation_bus_ids = {int(bv.bus_id) for bv in result.voltage_violations}
    bus_voltage_map = {int(bv.bus_id): float(bv.vm_pu) for bv in result.bus_voltages}

    bus_internal_by_display: dict[int, int] = {}
    for bi in net.bus.index.tolist():
        bus_internal_by_display[int(bus_display_id(net, int(bi)))] = int(bi)
    voltage_violation_internal = {
        int(bus_internal_by_display[bid])
        for bid in voltage_violation_bus_ids
        if int(bid) in bus_internal_by_display
    }

    fig = go.Figure()

    # Edge layer: violating branches in red with value labels, others as faint context.
    for u, v, data in g.edges(data=True):
        kind = str(data.get("kind", "line"))
        eid = int(data.get("element_id", -1))
        lid = _line_id(kind, eid)
        lf = flow_map.get(lid)
        loading = float(lf.loading_percent) if lf is not None else 0.0
        p_mw = float(lf.p_from_mw) if lf is not None else 0.0
        is_viol = lid in thermal_violation_ids

        line_color = "#d62728" if is_viol else "rgba(160,160,160,0.20)"
        line_width = 5.0 if is_viol else 1.2
        line_dash = "solid" if is_viol else "dot"

        x0, y0 = positions[int(u)]
        x1, y1 = positions[int(v)]
        fig.add_trace(
            go.Scatter(
                x=[x0, x1],
                y=[y0, y1],
                mode="lines",
                line=dict(color=line_color, width=line_width, dash=line_dash),
                hovertemplate=_edge_hover(net, int(u), int(v), kind, eid, result) + "<extra></extra>",
                showlegend=False,
            )
        )

        if is_viol:
            fig.add_annotation(
                x=(x0 + x1) / 2.0,
                y=(y0 + y1) / 2.0,
                text=f"{p_mw:.1f} MW / {loading:.1f}%",
                showarrow=False,
                font=dict(size=10, color="#d62728"),
                bgcolor="rgba(255,245,245,0.8)" if theme == "light" else "rgba(60,0,0,0.35)",
                borderpad=1,
            )

    # Node layer: only voltage-violating nodes are highlighted and labeled with V.
    node_x: list[float] = []
    node_y: list[float] = []
    node_text: list[str] = []
    hover_text: list[str] = []
    node_color: list[str] = []
    node_size: list[int] = []
    node_line_color: list[str] = []
    node_line_width: list[int] = []
    node_opacity: list[float] = []

    for bi in g.nodes:
        bidx = int(bi)
        x, y = positions[bidx]
        node_x.append(x)
        node_y.append(y)
        hover_text.append(_node_hover(net, bidx, result, btype_map=btype_map))

        is_v = bidx in voltage_violation_internal
        bid = int(bus_display_id(net, bidx))
        vm = float(bus_voltage_map.get(bid, 1.0))
        node_text.append(f"{bid}<br>V={vm:.3f}" if is_v else "")
        node_color.append("#d62728" if is_v else "#aeb4ba")
        node_size.append(19 if is_v else 10)
        node_line_color.append("#d62728" if is_v else "rgba(0,0,0,0)")
        node_line_width.append(3 if is_v else 0)
        node_opacity.append(1.0 if is_v else 0.28)

    fig.add_trace(
        go.Scatter(
            x=node_x,
            y=node_y,
            mode="markers+text",
            text=node_text,
            textposition="top center",
            textfont=dict(size=10),
            marker=dict(
                color=node_color,
                size=node_size,
                line=dict(color=node_line_color, width=node_line_width),
                opacity=node_opacity,
            ),
            hovertemplate="%{customdata}<extra></extra>",
            customdata=hover_text,
            name=("Voltage violation nodes" if lang == "en" else "电压越限节点"),
            showlegend=False,
        )
    )

    fig.add_trace(
        go.Scatter(
            x=[None],
            y=[None],
            mode="lines",
            line=dict(color="#d62728", width=4),
            name=("Overloaded branch" if lang == "en" else "过载支路"),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=[None],
            y=[None],
            mode="markers",
            marker=dict(size=10, color="#d62728"),
            name=("Voltage violation node" if lang == "en" else "电压越限节点"),
        )
    )

    fig.update_layout(
        title=dict(
            text=(f"Violation Overview - {result.case_name}" if lang == "en" else f"越限概览图 - {result.case_name}"),
            x=0.02,
            xanchor="left",
            y=0.98,
            yanchor="top",
        ),
        template=_template(theme),
        height=640,
        margin=dict(l=16, r=24, t=72, b=14),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0.0),
        xaxis=dict(showgrid=False, zeroline=False, visible=False, range=xr),
        yaxis=dict(showgrid=False, zeroline=False, visible=False, range=yr, scaleanchor="x"),
    )
    return fig

