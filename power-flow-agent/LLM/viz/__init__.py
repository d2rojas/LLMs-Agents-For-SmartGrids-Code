"""viz package.

提供 Plotly 可视化：
- network_plot: 基础拓扑与越限概览
- voltage_heatmap: 电压热力图
- flow_diagram: 潮流分布图
- comparison: 修改前后对比图
"""

from viz.network_plot import make_base_network_figure, make_violation_overview
from viz.voltage_heatmap import make_voltage_heatmap
from viz.flow_diagram import make_flow_diagram
from viz.comparison import make_comparison
from viz.n1 import make_n1_ranking
from viz.remedial import make_remedial_ranking
from viz.benchmark import make_benchmark_figure, compute_benchmark_cards

__all__ = [
    "make_base_network_figure",
    "make_violation_overview",
    "make_voltage_heatmap",
    "make_flow_diagram",
    "make_comparison",
    "make_n1_ranking",
    "make_remedial_ranking",
    "make_benchmark_figure",
    "compute_benchmark_cards",
]
