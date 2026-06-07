# visualizer.py

import matplotlib.pyplot as plt
import pandapower.plotting as plot


def visualize_results(net, voltage_min=0.95, voltage_max=1.05, line_limit=100):
    fig, ax = plt.subplots(figsize=(8,6))

    # Voltage violation coloring
    bus_colors = []
    for v in net.res_bus.vm_pu:
        if v < voltage_min or v > voltage_max:
            bus_colors.append("red")
        else:
            bus_colors.append("green")

    # Line loading coloring
    line_colors = []
    for loading in net.res_line.loading_percent:
        if loading > line_limit:
            line_colors.append("red")
        else:
            line_colors.append("blue")

    plot.simple_plot(net,
                     bus_color=bus_colors,
                     line_color=line_colors,
                     show_plot=True)