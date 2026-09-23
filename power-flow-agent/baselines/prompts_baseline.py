"""baselines/prompts_baseline.py

LLM-Only 基线 Prompt 模板。

目的：
- 不调用任何外部求解器或工具；
- 将 IEEE 用例（以 pandapower 网络表格形式导出）直接塞入 prompt；
- 让 LLM "声称" 给出潮流结果；
- 再与 pandapower 求解器真值对比，量化幻觉与数值误差。

注意：
- 该基线本质上是“反例/下界”，用于对比工具增强版的准确性。
- 由于 token 成本与模型上下文窗口限制，用例规模越大（>57）越不适合该基线。
"""

from __future__ import annotations

from methods import read_text as _read_method_text


# BASELINE_SYSTEM_PROMPT = """你是一个电力系统分析专家。你需要根据用户提供的测试系统数据，计算交流潮流结果。
#
# 重要约束：
# - 你必须严格输出 JSON（不要额外文本，不要 Markdown 代码块）。
# - 不要输出 NaN/Infinity，所有数值必须是有限实数。
# - 如果你无法完成计算，请将 converged 设为 false，并尽量输出你能给出的结构（空数组也可以）。
# """

BASELINE_SYSTEM_PROMPT = _read_method_text("_shared/llm_only_system_prompt.txt")

# BASELINE_PROMPT_TEMPLATE = """你是一个电力系统专家。请根据以下 IEEE {case_name} 测试系统数据，计算交流潮流结果。
#
# ## 系统数据（来自 pandapower 网络表）
#
# ### 节点数据 (Bus Table: net.bus)
# {bus_data_table}
#
# ### 负荷数据 (Load Table: net.load)
# {load_data_table}
#
# ### 发电机数据 (Generator Table: net.gen)
# {gen_data_table}
#
# ### 平衡节点/外部电网 (External Grid Table: net.ext_grid)
# {ext_grid_data_table}
#
# ### 线路数据 (Line Table: net.line)
# {line_data_table}
#
# ### 变压器数据 (Transformer Table: net.trafo)
# {trafo_data_table}
#
# ## 输出要求
# 请计算并返回以下结果（JSON 格式）：
# 1) 每个节点的电压幅值 (p.u.) 与相角 (度)
# 2) 每条支路的首端有功功率 (MW) 与负载率 (%)
#    - 对于线路：line_id 使用 net.line 的行索引
#    - 对于变压器：line_id 使用 100000 + net.trafo 的行索引
# 3) 总发电量 (MW)、总负荷 (MW)、总损耗 (MW)
# 4) 是否有电压越限（<0.95 或 >1.05 p.u.）或线路越限（>100%）
#
# 请严格按以下 JSON schema 输出（字段齐全，类型正确）：
# {{
#   "converged": true/false,
#   "bus_voltages": [{{"bus_id": 1, "vm_pu": 1.0, "va_deg": 0.0}}, ...],
#   "line_flows": [{{"line_id": 0, "p_from_mw": 0.0, "loading_percent": 0.0}}, ...],
#   "total_generation_mw": 0.0,
#   "total_load_mw": 0.0,
#   "total_loss_mw": 0.0
# }}
# """

BASELINE_PROMPT_TEMPLATE = _read_method_text("_shared/llm_only_user_template.txt")
