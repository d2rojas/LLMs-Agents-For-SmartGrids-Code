import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from solver import case_loader
from solver.power_flow import run_power_flow
from viz.flow_particles import build_particle_segments, make_flow_particles_html
from viz.flow_diagram import make_flow_diagram
import plotly.io as pio
from viz.network_plot import build_graph, compute_layout


def test_build_particle_segments_case14_non_empty():
    net, _ = case_loader.load("case14")
    result = run_power_flow(net)
    pos = compute_layout(net, build_graph(net))
    segs = build_particle_segments(net, result, pos, theme="light", heavy_threshold=60, over_threshold=100)
    assert segs
    assert all(float(s["count"]) >= 1 for s in segs)


def test_make_flow_particles_html_contains_canvas_and_events():
    net, _ = case_loader.load("case14")
    result = run_power_flow(net)
    pos = compute_layout(net, build_graph(net))
    fig = make_flow_diagram(net, result, positions=pos, lang="en")
    fig_json = pio.to_json(fig, validate=False)
    segs = build_particle_segments(net, result, pos, theme="light", heavy_threshold=60, over_threshold=100)
    html = make_flow_particles_html(fig_json, segs, height_px=700)
    assert "plotly_relayout" in html
    assert "<canvas" in html
