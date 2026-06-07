"""Canvas particle overlay for flow diagram (Plotly + HTML component)."""

from __future__ import annotations

from typing import Any, Optional
import json
import math
import uuid

from models.schemas import PowerFlowResult
from viz.network_plot import build_graph, bus_display_id


def _edge_line_id(kind: str, element_id: int) -> int:
    return int(element_id) if kind == "line" else 100000 + int(element_id)


def _segment_color(*, loading: float, heavy_th: float, over_th: float, theme: str) -> str:
    # Red particles for strong flow visibility.
    dark = str(theme).lower().startswith("dark")
    return "rgba(254,178,178,0.86)" if dark else "rgba(248,113,113,0.84)"


def _segment_width(*, p_abs: float, p_max: float, n_bus: int) -> float:
    lo, hi = 1.5, 6.0
    if p_max <= 1e-9:
        w = lo
    else:
        t = math.sqrt(max(0.0, min(1.0, float(p_abs) / float(p_max))))
        w = lo + (hi - lo) * t
    if n_bus > 100:
        w *= 0.7
    return float(w)


def build_particle_segments(
    net: Any,
    result: PowerFlowResult,
    positions: dict[int, tuple[float, float]],
    *,
    theme: str = "light",
    heavy_threshold: float = 60.0,
    over_threshold: float = 100.0,
    max_particles: int = 800,
    use_line_id_mapping: bool = False,
) -> list[dict[str, float | int | str]]:
    """Build particle segments with direction and particle budgets."""
    if not positions or result is None or not result.line_flows:
        return []

    display_to_internal: dict[int, int] = {}
    for bi in positions.keys():
        display_to_internal[int(bus_display_id(net, int(bi)))] = int(bi)

    rows: list[dict[str, float | int | str]] = []
    if use_line_id_mapping:
        flow_map = {int(lf.line_id): lf for lf in result.line_flows}
        g = build_graph(net)
        for u, v, data in g.edges(data=True):
            kind = str(data.get("kind", "line"))
            eid = int(data.get("element_id", -1))
            lf = flow_map.get(_edge_line_id(kind, eid))
            if lf is None:
                continue
            if int(u) not in positions or int(v) not in positions:
                continue

            x0, y0 = positions[int(u)]
            x1, y1 = positions[int(v)]
            p = float(lf.p_from_mw)
            p_abs = abs(p)
            if p_abs <= 1e-9:
                continue

            if p >= 0.0:
                sx, sy, ex, ey = float(x0), float(y0), float(x1), float(y1)
            else:
                sx, sy, ex, ey = float(x1), float(y1), float(x0), float(y0)

            rows.append(
                {
                    "sx": sx,
                    "sy": sy,
                    "ex": ex,
                    "ey": ey,
                    "p_abs": float(p_abs),
                    "loading": float(lf.loading_percent),
                }
            )
    else:
        for lf in result.line_flows:
            fb = int(lf.from_bus)
            tb = int(lf.to_bus)
            if fb not in display_to_internal or tb not in display_to_internal:
                continue

            bi0 = int(display_to_internal[fb])
            bi1 = int(display_to_internal[tb])
            if bi0 not in positions or bi1 not in positions:
                continue

            x0, y0 = positions[bi0]
            x1, y1 = positions[bi1]
            p = float(lf.p_from_mw)
            p_abs = abs(p)
            if p_abs <= 1e-9:
                continue

            if p >= 0.0:
                sx, sy, ex, ey = float(x0), float(y0), float(x1), float(y1)
            else:
                sx, sy, ex, ey = float(x1), float(y1), float(x0), float(y0)

            rows.append(
                {
                    "sx": sx,
                    "sy": sy,
                    "ex": ex,
                    "ey": ey,
                    "p_abs": float(p_abs),
                    "loading": float(lf.loading_percent),
                }
            )

    if not rows:
        return []

    n_bus = int(len(positions))
    if n_bus > 200:
        # Large systems: render only strong-flow branches.
        rows = [r for r in rows if float(r["p_abs"]) >= 50.0]
        max_segments = 80
    elif n_bus > 100:
        max_segments = 30
    else:
        max_segments = 120
    rows = sorted(rows, key=lambda r: float(r["p_abs"]), reverse=True)[:max_segments]

    p_sum = sum(float(r["p_abs"]) for r in rows)
    p_max = max(float(r["p_abs"]) for r in rows)
    if p_sum <= 1e-9 or p_max <= 1e-9:
        return []

    counts: list[int] = []
    per_seg_cap = 36 if n_bus > 100 else 42
    for r in rows:
        frac = float(r["p_abs"]) / p_sum
        c = int(round(frac * int(max_particles)))
        c = max(1, min(per_seg_cap, c))
        counts.append(int(c))

    total = sum(counts)
    if total > int(max_particles):
        over = total - int(max_particles)
        order = sorted(range(len(counts)), key=lambda i: counts[i], reverse=True)
        cursor = 0
        while over > 0 and order:
            idx = order[cursor % len(order)]
            if counts[idx] > 1:
                counts[idx] -= 1
                over -= 1
            cursor += 1

    segments: list[dict[str, float | int | str]] = []
    for r, c in zip(rows, counts):
        if c <= 0:
            continue
        p_abs = float(r["p_abs"])
        width = _segment_width(p_abs=p_abs, p_max=p_max, n_bus=n_bus)
        speed = 0.0022 + 0.0038 * (p_abs / p_max)
        radius = max(1.0, 0.9 + 0.20 * width)
        segments.append(
            {
                "sx": float(r["sx"]),
                "sy": float(r["sy"]),
                "ex": float(r["ex"]),
                "ey": float(r["ey"]),
                "count": int(c),
                "speed": float(speed),
                "radius": float(radius),
                "color": _segment_color(
                    loading=float(r["loading"]),
                    heavy_th=float(heavy_threshold),
                    over_th=float(over_threshold),
                    theme=str(theme),
                ),
            }
        )
    return segments


def make_flow_particles_html(
    fig_json: str,
    segments: list[dict[str, float | int | str]],
    *,
    height_px: int = 700,
) -> str:
    """Build embeddable HTML: Plotly figure + Canvas particle overlay."""
    fig_obj = json.loads(fig_json)
    payload = {"fig": fig_obj, "segments": segments}
    payload_js = json.dumps(payload, ensure_ascii=False)
    uid = uuid.uuid4().hex[:10]
    plot_id = f"pf_plot_{uid}"
    canvas_id = f"pf_canvas_{uid}"

    wrap_id = f"pf_wrap_{uid}"
    return f"""
<div id="{wrap_id}" style="position:relative;width:100%;height:{int(height_px)}px;">
  <div id="{plot_id}" style="width:100%;height:100%;"></div>
  <canvas id="{canvas_id}" style="position:absolute;left:0;top:0;width:100%;height:100%;pointer-events:none;"></canvas>
</div>
<script>
(function() {{
  const payload = {payload_js};
  const wrapDiv = document.getElementById("{wrap_id}");
  const plotDiv = document.getElementById("{plot_id}");
  const canvas = document.getElementById("{canvas_id}");
  const ctx = canvas.getContext("2d");
  const dpr = Math.max(1, window.devicePixelRatio || 1);
  let particles = [];
  let rafId = null;

  function ensureCanvasRect() {{
    const w = Math.max(1, wrapDiv.clientWidth);
    const h = Math.max(1, wrapDiv.clientHeight);
    canvas.width = Math.max(1, Math.floor(w * dpr));
    canvas.height = Math.max(1, Math.floor(h * dpr));
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }}

  function dataToPixel(x, y) {{
    const fl = plotDiv._fullLayout;
    if (!fl || !fl.xaxis || !fl.yaxis || !fl._size) return null;
    const px = fl._size.l + fl.xaxis.l2p(x);
    const py = fl._size.t + fl.yaxis.l2p(y);
    return [px, py];
  }}

  function rebuildParticles() {{
    particles = [];
    for (const seg of payload.segments || []) {{
      const c = Math.max(1, Number(seg.count || 1));
      for (let i = 0; i < c; i++) {{
        particles.push({{
          seg: seg,
          t: Math.random(),
          phase: Math.random() * Math.PI * 2
        }});
      }}
    }}
  }}

  function drawFrame(ts) {{
    const w = Math.max(1, wrapDiv.clientWidth);
    const h = Math.max(1, wrapDiv.clientHeight);
    ctx.clearRect(0, 0, w, h);
    if (!plotDiv._fullLayout || !particles.length) {{
      rafId = requestAnimationFrame(drawFrame);
      return;
    }}

    for (const p of particles) {{
      p.t += Number(p.seg.speed || 0.003);
      if (p.t > 1) p.t -= 1;
      const x = Number(p.seg.sx) + (Number(p.seg.ex) - Number(p.seg.sx)) * p.t;
      const y = Number(p.seg.sy) + (Number(p.seg.ey) - Number(p.seg.sy)) * p.t;
      const pixel = dataToPixel(x, y);
      if (!pixel) continue;

      const jitter = 0.8 * Math.sin(ts * 0.004 + p.phase);
      ctx.beginPath();
      ctx.globalAlpha = 0.90;
      ctx.fillStyle = String(p.seg.color || "rgba(248,113,113,0.84)");
      ctx.arc(pixel[0], pixel[1] + jitter, Number(p.seg.radius || 2.0), 0, Math.PI * 2);
      ctx.fill();
    }}
    ctx.globalAlpha = 1.0;
    rafId = requestAnimationFrame(drawFrame);
  }}

  function bindPlotEvents() {{
    ensureCanvasRect();
    rebuildParticles();
    if (rafId) cancelAnimationFrame(rafId);
    rafId = requestAnimationFrame(drawFrame);
    plotDiv.on("plotly_relayout", ensureCanvasRect);
    plotDiv.on("plotly_afterplot", ensureCanvasRect);
    window.addEventListener("resize", ensureCanvasRect);
  }}

  function init() {{
    const config = {{ responsive: true, displaylogo: false }};
    Plotly.newPlot(plotDiv, payload.fig.data, payload.fig.layout, config).then(bindPlotEvents);
  }}

  if (window.Plotly) {{
    init();
  }} else {{
    const s = document.createElement("script");
    s.src = "https://cdn.plot.ly/plotly-2.35.2.min.js";
    s.onload = init;
    document.head.appendChild(s);
  }}
}})();
</script>
"""
