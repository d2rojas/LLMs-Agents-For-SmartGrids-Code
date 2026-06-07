# Visualization

Implemented in `plots.py` (Phase A). Used by Phase A script; will be used by baseline/agent runs.

- **`plot_schedule(schedule, day, save_path=None)`**: 2D heatmap — rows = sessions, columns = time step, color = power (kW). Saves PNG if `save_path` is set.
- **`plot_load_profile(schedule, day, save_path=None, title=None)`**: Line plot of total facility load (∑_i p_i(t)) vs time step. Optional title (e.g. cost/unmet summary).

Figures are closed after save to avoid memory growth. For reports and qualitative examples.
