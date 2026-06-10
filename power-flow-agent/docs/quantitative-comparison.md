# Quantitative Comparison View — Implementation Notes

> 4-panel 量化对比视图：在 Remedial 页面的 "修改前后对比" 拓扑图下方，提供数值层面的全面比较。

---

## 1. 整体架构

```
用户触发 Remedial
       │
       ├── _run_remedial_direct()      生成候选方案时附加预览
       │        │
       │        └── make_quantitative_comparison(before, best_preview)
       │
       └── _apply_remedial_action_ui() 实际应用动作后生成对比
                │
                └── make_quantitative_comparison(before, after)
                         │
                         ▼
               ┌─────────────────────────────┐
               │   2×2 Plotly make_subplots   │
               │ ┌───────────┬─────────────┐  │
               │ │ Panel 1   │ Panel 2     │  │
               │ │ V 幅值对比 │ ΔV 柱状图   │  │
               │ ├───────────┼─────────────┤  │
               │ │ Panel 3   │ Panel 4     │  │
               │ │ 负载率Top15│ 指标对比表  │  │
               │ └───────────┴─────────────┘  │
               └─────────────────────────────┘
                         │
                         ▼
               ┌─────────────────────────────┐
               │  st.columns Summary Row     │
               │ [电压越限] [热稳越限] [总损耗]│
               └─────────────────────────────┘
```

### 文件变更清单

| 文件 | 变更类型 | 内容 |
|------|---------|------|
| `viz/comparison.py` | 新增函数 | `make_quantitative_comparison()`, `compute_comparison_summary()` |
| `app.py` | 新增导入 | `from viz.comparison import ...` |
| `app.py` | 新增函数 | `_render_qc_summary_row()` |
| `app.py` | 修改 | `_run_remedial_direct()` 追加 `quantitative_comparison` extra_plot |
| `app.py` | 修改 | `_apply_remedial_action_ui()` 追加 `quantitative_comparison` extra_plot |
| `app.py` | 修改 | chat 渲染循环增加 `quantitative_comparison` 分支 |

---

## 2. 数据流

### 2.1 数据来源

- **before_data**: `session.last_result`（当前网络潮流结果，`PowerFlowResult`）
- **after_data**: `plan.actions[0].preview_result`（候选方案预览）或 `apply_remedial_action_inplace()` 返回值

两者均为 `PowerFlowResult`，包含：
- `bus_voltages: list[BusVoltage]` — 每个 bus 的 `bus_id`, `vm_pu`, `is_violation`
- `line_flows: list[LineFlow]` — 每条线路的 `line_id`, `from_bus`, `to_bus`, `loading_percent`, `is_violation`
- `voltage_violations`, `thermal_violations` — 已过滤的越限列表
- `total_loss_mw`, `total_generation_mw` — 标量

### 2.2 Top 15 线路选取

```python
bl_series = pd.Series({lid: loading_before ...})
al_series = pd.Series({lid: loading_after  ...})
max_loading_series = pd.concat([bl_series, al_series], axis=1).max(axis=1)
top15_idx = max_loading_series.nlargest(15).index.tolist()
```

取 before/after 两组 loading 的 **逐行最大值**，然后取最大的 15 条。这确保：
- 改善前很高的线路会被选中（即使改善后降低了）
- 改善后新出现高负载的线路也会被选中

### 2.3 序列化传递

```python
extra_plots.append({
    "plot_type": "quantitative_comparison",
    "figure_json": pio.to_json(qc_fig),
    "before_result": before.model_dump(),   # ← 原始数据随消息存储
    "after_result":  after.model_dump(),
})
```

`before_result` / `after_result` 嵌入到 `extra_plots` dict 中，随 `st.session_state.messages` 持久化。渲染时由 `_render_qc_summary_row()` 反序列化回 `PowerFlowResult` 来计算 summary metrics。

---

## 3. 四个 Panel 的设计细节

### Panel 1 — 电压幅值对比（左上）

```
            1.06 ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─  ← Vmax 橙色 dash
   ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  ← 浅红色越限区
            1.05 ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─

         ─ ─ ─ ─ blue dash (before)
         ●─●─●─● red solid+marker (after)

            0.95 ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─  ← Vmin 橙色 dash
   ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  ← 浅红色越限区
            0.92 ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─
```

**小巧思**：
- **越限区域用 `xref="x domain"` 而不是 `xref="x"` 数值坐标**。Category 轴上用数值坐标 (-0.5, N-0.5) 在某些 Plotly 版本中不可靠；`x domain` 用 0~1 比例坐标，永远覆盖整个 x 轴宽度。
- **Y 轴范围 `[min(vm)-0.03, max(vm)+0.03]`**：在 vm 的实际范围基础上留 0.03 p.u. 的呼吸空间，确保越限阈值线和数据点都不会贴边。
- **Limit annotation 用 `xref="x domain", x=1.0`**：标注锚定在 x 轴最右端，不随 bus 数量变化偏移。

### Panel 2 — ΔV 电压变化量（右上）

**小巧思**：
- **正值绿色 `#38A169`，负值红色 `#E53E3E`**：颜色语义 = 电压升高（朝标称值改善）= 绿，降低 = 红。
- **零线加粗** (`line_width=1.5`)：在有正有负的情况下提供清晰基准。
- **ΔV=0 的 bar 着绿色**：delta 恰好为零意味着没有变化，不是恶化，所以归入 `>=0` 的绿色分支。

### Panel 3 — 线路负载率对比 Top 15（左下）

**小巧思**：
- **Grouped bar 用 `barmode="group"`** 全局设置，让 Plotly 自动管理并排偏移，而不是手动指定 `offset`。手动 `offset` + `barmode="group"` 会导致双重偏移 bug。
- **只标注 >80% 的柱顶百分比**：避免标注过密。用 `yshift=10` 让标签浮在柱顶上方不遮挡柱体。
- **X 轴标签用 `from→to` 格式**（Unicode `\u2192` 箭头）：比纯数字 line_id 更直观。`tickangle=-45` 防止长标签重叠。
- **100% 阈值红色虚线**：明确区分安全/越限区域。

### Panel 4 — 关键指标对比表（右下）

```
┌──────────────┬────────┬────────┬────────┐
│ 指标         │ 修改前  │ 修改后  │ 变化   │
├──────────────┼────────┼────────┼────────┤
│ 最低电压     │ 0.9812 │ 0.9934 │ +0.0122│ ← 绿色
│ 电压越限节点 │ 13     │ 10     │ -3     │ ← 绿色
│ 最大负载率   │ 83.2%  │ 85.1%  │ +1.90  │ ← 红色
│ ...          │        │        │        │
└──────────────┴────────┴────────┴────────┘
```

**小巧思**：
- **"变化"列的颜色语义**：每个指标有独立的"改善方向"判断：
  - 最低电压升高 = 改善（`higher_is_better=True`）
  - 越限节点减少 = 改善（`higher_is_better=False`）
  - 总发电变化 = 中性（`higher_is_better=None`，灰色）
- **`go.Table` 的 `font.color` 必须是单个 dict，不能是 list[dict]**。为了实现逐列不同颜色，用嵌套 list-of-lists：`font=dict(color=[[col1_colors], [col2_colors], ...])`。初版用了 `font=[dict(...), dict(...)]` 导致 Plotly 抛 `ValueError`，已修复。
- **交替行背景** `#F7FAFC` / `#FFFFFF`：提高可读性。"变化"列额外用浅绿 `#F0FFF4` 或浅红 `#FFF5F5` 底色增强语义。
- **Header 深蓝 `#2B6CB0` + 白字**：与平台整体 UI 配色一致。

---

## 4. Legend 联动机制

**问题**：Panel 1（Scatter）和 Panel 3（Bar）都有 "Before" / "After" 两组 trace，如果各自 `showlegend=True`，legend 会出现 4 个条目。

**解决**：用 `legendgroup` 将同名 trace 绑定：
```python
# Panel 1 — Scatter
go.Scatter(name=before_label, legendgroup="before", showlegend=True)
go.Scatter(name=after_label,  legendgroup="after",  showlegend=True)

# Panel 3 — Bar (同组, 不重复显示 legend)
go.Bar(name=before_label, legendgroup="before", showlegend=False)
go.Bar(name=after_label,  legendgroup="after",  showlegend=False)
```

效果：点击 legend 中的 "Before" 会同时隐藏 Panel 1 的蓝色虚线和 Panel 3 的蓝色柱体。

---

## 5. Summary Row（底部指标摘要）

在 Plotly 图表下方，用 `st.columns(3)` 渲染三个指标卡片：

```
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│    电压越限      │  │    热稳越限      │  │     总损耗       │
│ 13 → 10 (↓3)   │  │  0 → 0          │  │ 13.4→13.5 MW(↑) │
│    绿色         │  │    灰色         │  │     红色         │
└─────────────────┘  └─────────────────┘  └─────────────────┘
```

**小巧思**：
- **数据不依赖 figure_json**：`before_result` / `after_result` 原始数据嵌入到消息中，渲染时重建 `PowerFlowResult` 对象重新计算。这确保 summary 始终准确。
- **`compute_comparison_summary()` 返回 `fmt` lambda**：每个指标自带格式化函数，整数和浮点数用不同格式（`{b} → {a}` vs `{b:.1f} → {a:.1f} MW`）。
- **颜色三态**：improved=绿, worsened=红, neutral=灰。即使"没有变化"也给出视觉反馈。

---

## 6. 样式规范

| 属性 | 值 |
|------|-----|
| 正文字体 | Source Sans 3, sans-serif |
| 标题字体 | Crimson Pro, serif |
| 整体背景 | `#FAFBFE` |
| 网格线色 | `#EDF2F7` |
| 图表高度 | 700px |
| subplot 间距 | vertical=0.12, horizontal=0.08 |
| Before 色 | `#3182CE`（蓝） |
| After 色 | `#E53E3E`（红） |
| 改善色 | `#38A169`（绿） |
| 恶化色 | `#E53E3E`（红） |
| 中性色 | `#A0AEC0`（灰） |
| 阈值线 | `#DD6B20`（橙） |
| 白色卡片容器 | `background:#fff; border-radius:12px; box-shadow:0 1px 3px rgba(0,0,0,0.08)` |

---

## 7. 自检发现并修复的 Bug

### Bug 1: `go.Table` cells.font 不接受 list[dict]

**现象**：`ValueError: Invalid value of type 'builtins.list' received for the 'font' property of table.cells`

**原因**：初版写成 `font=[dict(color=...), dict(color=...), ...]`，但 Plotly 的 `cells.font` 只接受一个 `Font` 实例。

**修复**：改为 `font=dict(size=11, family=..., color=[[col1], [col2], [col3], [col4]])` — 用 list-of-lists 实现逐列逐行不同颜色。

### Bug 2: `barmode="group"` 与手动 `offset` 冲突

**现象**：Panel 3 的 grouped bar 位置偏移异常。

**原因**：全局 `barmode="group"` 会自动偏移 bar 位置，加上手动 `offset=-0.18/+0.18` 导致双重偏移。

**修复**：移除 `width=0.35, offset=±0.18`，完全依赖 `barmode="group"` 自动布局。

### Bug 3: Legend 出现 4 个重复条目

**现象**：legend 显示 "Before", "After", "Before", "After"（Panel 1 和 Panel 3 各一组）。

**原因**：Panel 1 (Scatter) 和 Panel 3 (Bar) 各自 `showlegend=True`，且使用不同的 `legendgroup`。

**修复**：统一 `legendgroup="before"/"after"`，Panel 3 的 Bar trace 设为 `showlegend=False`。这样 legend 只显示 2 个条目，且点击时两个 panel 联动。

### Bug 4: delta 格式化死代码

**现象**：两个分支产生完全相同的输出。

```python
# 修复前 — elif 分支永远不会走到不同格式
if isinstance(delta_val, float) and abs(delta_val) >= 1:
    delta_strs.append(f"{delta_val:+.2f}")
elif isinstance(delta_val, float):              # ← 死代码
    delta_strs.append(f"{delta_val:+.2f}")      # ← 与 if 完全相同
else:
    delta_strs.append(f"{delta_val:+g}")
```

**修复**：按类型分派 — `int` 用 `+d` 格式（紧凑），`float` 用 `+.2f`：
```python
if isinstance(delta_val, int):
    delta_strs.append(f"{delta_val:+d}")    # "+3", "-2"
else:
    delta_strs.append(f"{delta_val:+.2f}")  # "+0.01", "-1.35"
```

### Bug 5: 空数据 crash

**现象**：`min([])` / `max([])` 抛 `ValueError`。

**原因**：当 `bus_voltages` 或 `line_flows` 为空列表时，`all_vm = bv + av = []`，`min(all_vm)` 崩溃。

**修复**：加兜底：
```python
y_lo = (min(all_vm) - 0.03) if all_vm else (vmin - 0.03)
y_hi = (max(all_vm) + 0.03) if all_vm else (vmax + 0.03)
```
以及 `all_line_ids` 为空时跳过 `pd.concat`。

### Bug 6: violation shading 在 category 轴上用数值坐标不可靠

**现象**：在不同 Plotly 版本中，category 轴上用 `xref="x", x0=-0.5` 的 rect shape 可能不渲染。

**修复**：改为 `xref="x domain", x0=0, x1=1`，使用比例坐标始终覆盖整个 x 轴范围。

---

## 8. 可复现的集成测试

```python
import pandapower.networks as pn
from solver.power_flow import run_power_flow, SolverConfig
from solver.remedial import recommend_remedial_actions
from viz.comparison import make_quantitative_comparison, compute_comparison_summary

# 1. 加载 IEEE 14 节点网络
net = pn.case14()

# 2. 用严格阈值强制产生越限
cfg = SolverConfig(v_min=1.02, v_max=1.04)
before = run_power_flow(net, config=cfg)
assert before.converged
assert len(before.voltage_violations) > 0

# 3. 生成 remedial 方案
plan = recommend_remedial_actions(net, before, config=cfg, max_actions=3)
assert len(plan.actions) > 0

# 4. 取最佳方案的预览结果
after = plan.actions[0].preview_result
assert after is not None

# 5. 生成 4-panel 图表
fig = make_quantitative_comparison(before, after, vmin=1.02, vmax=1.04, lang='zh')
assert fig.layout.height == 700
assert len(fig.data) == 6  # 2 Scatter + 1 Bar(ΔV) + 2 Bar(loading) + 1 Table

# 6. 验证 legend 只有 2 个
legend_items = [t.name for t in fig.data if getattr(t, 'showlegend', False)]
assert len(legend_items) == 2

# 7. 验证 summary
summaries = compute_comparison_summary(before, after)
assert len(summaries) == 3
assert summaries[0]['label_zh'] == '电压越限'

# 8. 空数据边界测试
from models.schemas import PowerFlowResult
empty = PowerFlowResult(
    case_name='empty', converged=True,
    total_generation_mw=0, total_load_mw=0, total_loss_mw=0,
)
fig2 = make_quantitative_comparison(empty, empty, lang='en')
assert len(fig2.data) == 6

print("All assertions passed!")
```

---

## 9. 已知限制 & 未来改进方向

1. **深色主题未适配**：当前写死 light mode 配色（`#FAFBFE` 背景），不响应 `theme` 参数。如需适配 dark mode，应加入 `_PALETTE_LIGHT` / `_PALETTE_DARK` 切换逻辑。
2. **大系统 X 轴密集**：300+ bus 系统的 Panel 1/2 bus 标签会过密。可考虑只标注越限 bus 或每隔 N 个标签显示。
3. **Trafo 与 Line 的混合显示**：Panel 3 的 `from→to` 标签不区分 line 和 trafo。对于含大量 trafo 的系统，可在标签中增加 `(T)` 后缀。
4. **Summary Row 的 lambda 序列化**：`compute_comparison_summary()` 返回的 dict 中含 lambda，无法 JSON 序列化。当前仅在渲染时实时调用，不存储。如需持久化，应改用字符串模板。
