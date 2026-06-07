"""
Generate evaluation figures comparing agentic pipeline performance across IEEE test networks.
All figures show all networks side-by-side for easy comparison.
"""
import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

plt.style.use('seaborn-v0_8-whitegrid')
plt.rcParams.update({
    'font.family': 'sans-serif',
    'font.size': 11,
    'axes.labelsize': 12,
    'axes.titlesize': 13,
    'xtick.labelsize': 10,
    'ytick.labelsize': 10,
    'legend.fontsize': 10,
    'figure.dpi': 150,
    'savefig.dpi': 300,
    'savefig.bbox': 'tight',
    'figure.facecolor': 'white',
})

COLORS = ['#4C72B0', '#55A868', '#C44E52']
NETWORK_LABELS = {'case14': 'IEEE 14-bus', 'case30': 'IEEE 30-bus', 'case57': 'IEEE 57-bus'}


def load_all_results(networks):
    """Load evaluation results for all networks."""
    results = {}
    for network in networks:
        path = Path(__file__).parent / "results" / f"full_eval_{network}.json"
        if path.exists():
            with open(path) as f:
                results[network] = json.load(f)
    return results


def fig1_repair_rate_by_category(all_data, output_dir):
    """
    Grouped bar chart: Repair rate by failure category, comparing all networks.
    Shows how well the agentic pipeline fixes different types of failures.
    """
    category_map = {
        'normal_operation': 'Normal',
        'extreme_load_scaling': 'Non-convergence',
        'all_generators_removed': 'Non-convergence',
        'near_zero_impedance': 'Non-convergence',
        'disconnected_subnetwork': 'Non-convergence',
        'heavy_loading_undervoltage': 'Voltage',
        'excess_generation_overvoltage': 'Voltage',
        'reactive_imbalance': 'Voltage',
        'concentrated_loading': 'Thermal',
        'reduced_thermal_limits': 'Thermal',
        'topology_redirection': 'Thermal',
        'line_contingency_overload': 'Contingency',
        'trafo_contingency_voltage': 'Contingency',
    }

    categories = ['Normal', 'Non-convergence', 'Voltage', 'Thermal', 'Contingency']
    networks = list(all_data.keys())

    fig, ax = plt.subplots(figsize=(10, 6))

    x = np.arange(len(categories))
    width = 0.25

    for i, (network, color) in enumerate(zip(networks, COLORS[:len(networks)])):
        data = all_data[network]
        cat_results = {c: {'total': 0, 'success': 0} for c in categories}

        for s in data['scenarios']:
            cat = category_map.get(s['scenario_id'], 'Normal')
            cat_results[cat]['total'] += 1
            if s.get('agentic', {}).get('fix_success', False):
                cat_results[cat]['success'] += 1

        rates = []
        for cat in categories:
            if cat_results[cat]['total'] > 0:
                rates.append(cat_results[cat]['success'] / cat_results[cat]['total'] * 100)
            else:
                rates.append(0)

        bars = ax.bar(x + i * width, rates, width, label=NETWORK_LABELS[network],
                      color=color, edgecolor='black', linewidth=0.5)

        for bar, rate in zip(bars, rates):
            if rate > 0:
                ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
                        f'{rate:.0f}%', ha='center', va='bottom', fontsize=8)

    ax.set_xlabel('Failure Category')
    ax.set_ylabel('Repair Rate (%)')
    ax.set_title('Agentic Pipeline: Repair Rate by Failure Category\n(Higher is better. Repair = network converges AND violations do not increase)')
    ax.set_xticks(x + width * (len(networks) - 1) / 2)
    ax.set_xticklabels(categories)
    ax.set_ylim(0, 115)
    ax.legend(title='Network', loc='upper right')
    ax.axhline(y=100, color='gray', linestyle='--', alpha=0.3, linewidth=1)

    plt.tight_layout()
    plt.savefig(output_dir / 'fig1_repair_by_category.png')
    plt.close()
    print("Generated: fig1_repair_by_category.png")


def fig2_latency_boxplot(all_data, output_dir):
    """
    Box plot: Latency distribution for each network.
    Shows how long the agentic pipeline takes to diagnose and fix issues.
    """
    networks = list(all_data.keys())

    fig, ax = plt.subplots(figsize=(8, 6))

    latency_data = []
    labels = []

    for network in networks:
        data = all_data[network]
        latencies = [s['agentic']['latency_ms'] / 1000
                     for s in data['scenarios']
                     if 'agentic' in s and 'error' not in s]
        latency_data.append(latencies)
        labels.append(NETWORK_LABELS[network])

    bp = ax.boxplot(latency_data, tick_labels=labels, patch_artist=True)

    for patch, color in zip(bp['boxes'], COLORS[:len(networks)]):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)

    for i, latencies in enumerate(latency_data):
        median = np.median(latencies)
        ax.text(i + 1.15, median, f'{median:.0f}s', ha='left', va='center', fontsize=9)

    ax.set_xlabel('Network')
    ax.set_ylabel('Latency (seconds)')
    ax.set_title('Agentic Pipeline: Time to Diagnose and Fix\n(Each box shows distribution across 13 test scenarios)')

    plt.tight_layout()
    plt.savefig(output_dir / 'fig2_latency_distribution.png')
    plt.close()
    print("Generated: fig2_latency_distribution.png")


def fig3_scaling_analysis(all_data, output_dir):
    """
    3-panel figure: How performance scales with network size.
    Shows repair rate, latency, and iterations as networks get larger.
    """
    networks = list(all_data.keys())
    labels = [NETWORK_LABELS[n] for n in networks]

    metrics = {'repair': [], 'latency': [], 'iterations': []}

    for network in networks:
        data = all_data[network]
        scenarios = data['scenarios']

        total = len([s for s in scenarios if 'agentic' in s and 'error' not in s])
        success = sum(1 for s in scenarios if s.get('agentic', {}).get('fix_success', False))

        latencies = [s['agentic']['latency_ms'] / 1000
                     for s in scenarios if 'agentic' in s and 'error' not in s]
        # Support both old (iterations_used) and new (tool_calls) field names
        iterations = [s['agentic'].get('tool_calls', s['agentic'].get('iterations_used', 0))
                      for s in scenarios if 'agentic' in s and 'error' not in s]

        metrics['repair'].append(success / total * 100 if total > 0 else 0)
        metrics['latency'].append(sum(latencies) / len(latencies) if latencies else 0)
        metrics['iterations'].append(sum(iterations) / len(iterations) if iterations else 0)

    fig, axes = plt.subplots(1, 3, figsize=(14, 5))
    x = np.arange(len(networks))

    # Repair Rate
    bars = axes[0].bar(x, metrics['repair'], color=COLORS[:len(networks)],
                       edgecolor='black', linewidth=0.5)
    axes[0].set_ylabel('Repair Rate (%)')
    axes[0].set_title('Repair Rate\n(% of scenarios fixed)')
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(labels, rotation=15, ha='right')
    axes[0].set_ylim(0, 115)
    for bar, val in zip(bars, metrics['repair']):
        axes[0].text(bar.get_x() + bar.get_width()/2, bar.get_height() + 2,
                     f'{val:.1f}%', ha='center', fontsize=10)

    # Latency
    bars = axes[1].bar(x, metrics['latency'], color=COLORS[:len(networks)],
                       edgecolor='black', linewidth=0.5)
    axes[1].set_ylabel('Average Latency (seconds)')
    axes[1].set_title('Average Latency\n(time to diagnose + fix)')
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(labels, rotation=15, ha='right')
    for bar, val in zip(bars, metrics['latency']):
        axes[1].text(bar.get_x() + bar.get_width()/2, bar.get_height() + 5,
                     f'{val:.0f}s', ha='center', fontsize=10)

    # Tool Calls
    bars = axes[2].bar(x, metrics['iterations'], color=COLORS[:len(networks)],
                       edgecolor='black', linewidth=0.5)
    axes[2].set_ylabel('Average Tool Calls')
    axes[2].set_title('Average Tool Calls\n(per scenario)')
    axes[2].set_xticks(x)
    axes[2].set_xticklabels(labels, rotation=15, ha='right')
    for bar, val in zip(bars, metrics['iterations']):
        axes[2].text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
                     f'{val:.1f}', ha='center', fontsize=10)

    fig.suptitle('Agentic Pipeline: Scaling with Network Size', fontsize=14, fontweight='bold', y=1.02)
    plt.tight_layout()
    plt.savefig(output_dir / 'fig3_scaling_analysis.png')
    plt.close()
    print("Generated: fig3_scaling_analysis.png")


def fig4_baseline_detection(all_data, output_dir):
    """
    Two-panel figure: Baseline single-pass detection accuracy.
    Left: Bus detection (voltage violations) for all networks.
    Right: Line detection (thermal violations) for networks with line violations.
    """
    def compute_pr(predicted_set, actual_set):
        if not predicted_set and not actual_set:
            return 1.0, 1.0, 1.0
        tp = len(predicted_set & actual_set)
        fp = len(predicted_set - actual_set)
        fn = len(actual_set - predicted_set)
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
        return precision, recall, f1

    def compute_detection_metrics(all_data, pred_key, actual_key):
        """Compute detection metrics for a component type."""
        results = {}
        for network, data in all_data.items():
            all_p, all_r, all_f1 = [], [], []
            total_actual = 0

            for s in data['scenarios']:
                if 'baseline' not in s or 'initial_state' not in s:
                    continue
                predicted = set(s.get('baseline', {}).get('predicted_components', {}).get(pred_key, []))
                actual = set(s.get('initial_state', {}).get('violations', {}).get(actual_key, []))
                total_actual += len(actual)
                p, r, f1 = compute_pr(predicted, actual)
                all_p.append(p)
                all_r.append(r)
                all_f1.append(f1)

            results[network] = {
                'precision': sum(all_p) / len(all_p) * 100 if all_p else 0,
                'recall': sum(all_r) / len(all_r) * 100 if all_r else 0,
                'f1': sum(all_f1) / len(all_f1) * 100 if all_f1 else 0,
                'total_actual': total_actual
            }
        return results

    networks = list(all_data.keys())
    labels = [NETWORK_LABELS[n] for n in networks]

    # Compute metrics for bus and line detection
    bus_results = compute_detection_metrics(all_data, 'bus', 'buses')
    line_results = compute_detection_metrics(all_data, 'line', 'lines')

    # Filter networks with actual line violations for line detection panel
    line_networks = [n for n in networks if line_results[n]['total_actual'] > 0]
    line_labels = [NETWORK_LABELS[n] for n in line_networks]

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    metric_colors = ['#4C72B0', '#55A868', '#8172B3']
    metric_names = ['Precision', 'Recall', 'F1 Score']

    # Left panel: Bus detection (all networks)
    ax = axes[0]
    x = np.arange(len(networks))
    width = 0.25

    for i, (metric, color, name) in enumerate(zip(['precision', 'recall', 'f1'], metric_colors, metric_names)):
        values = [bus_results[n][metric] for n in networks]
        bars = ax.bar(x + i * width, values, width, label=name, color=color,
                      edgecolor='black', linewidth=0.5)
        for bar, val in zip(bars, values):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
                    f'{val:.0f}%', ha='center', va='bottom', fontsize=9)

    ax.set_xlabel('Network')
    ax.set_ylabel('Score (%)')
    ax.set_title('Bus Detection (Voltage Violations)')
    ax.set_xticks(x + width)
    ax.set_xticklabels(labels)
    ax.set_ylim(0, 110)
    ax.legend(loc='upper right')

    # Right panel: Line detection (only networks with line violations)
    ax = axes[1]
    if line_networks:
        x = np.arange(len(line_networks))
        for i, (metric, color, name) in enumerate(zip(['precision', 'recall', 'f1'], metric_colors, metric_names)):
            values = [line_results[n][metric] for n in line_networks]
            bars = ax.bar(x + i * width, values, width, label=name, color=color,
                          edgecolor='black', linewidth=0.5)
            for bar, val in zip(bars, values):
                ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
                        f'{val:.0f}%', ha='center', va='bottom', fontsize=9)

        ax.set_xlabel('Network')
        ax.set_ylabel('Score (%)')
        ax.set_title('Line Detection (Thermal Violations)')
        ax.set_xticks(x + width)
        ax.set_xticklabels(line_labels)
        ax.set_ylim(0, 110)
        ax.legend(loc='upper right')
    else:
        ax.text(0.5, 0.5, 'No line violations\nin test scenarios', ha='center', va='center',
                transform=ax.transAxes, fontsize=12)
        ax.set_title('Line Detection (Thermal Violations)')

    fig.suptitle('Baseline Pipeline: Component Detection Accuracy\n(Single-pass diagnosis without remediation)',
                 fontsize=14, fontweight='bold', y=1.02)
    plt.tight_layout()
    plt.savefig(output_dir / 'fig4_baseline_detection.png')
    plt.close()
    print("Generated: fig4_baseline_detection.png")


def fig5_violation_reduction(all_data, output_dir):
    """
    Grouped bar chart: Total violations before vs after remediation.
    Shows the aggregate impact of the agentic pipeline.
    """
    networks = list(all_data.keys())
    labels = [NETWORK_LABELS[n] for n in networks]

    before_totals = []
    after_totals = []

    for network in networks:
        data = all_data[network]
        before = 0
        after = 0

        for s in data['scenarios']:
            if 'agentic' not in s or 'initial_state' not in s:
                continue
            before += s.get('initial_state', {}).get('violations', {}).get('total', 0)
            final_v = s.get('agentic', {}).get('final_violations', {})
            if isinstance(final_v, dict):
                after += final_v.get('total', 0)
            else:
                after += final_v if final_v else 0

        before_totals.append(before)
        after_totals.append(after)

    fig, ax = plt.subplots(figsize=(8, 6))

    x = np.arange(len(networks))
    width = 0.35

    bars1 = ax.bar(x - width/2, before_totals, width, label='Before (Initial)',
                   color='#C44E52', edgecolor='black', linewidth=0.5)
    bars2 = ax.bar(x + width/2, after_totals, width, label='After (Remediated)',
                   color='#55A868', edgecolor='black', linewidth=0.5)

    for bar, val in zip(bars1, before_totals):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 3,
                str(val), ha='center', va='bottom', fontsize=10)
    for bar, val in zip(bars2, after_totals):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 3,
                str(val), ha='center', va='bottom', fontsize=10)

    ax.set_xlabel('Network')
    ax.set_ylabel('Total Violations (across 13 scenarios)')
    ax.set_title('Agentic Pipeline: Violation Reduction\n(Sum of voltage + thermal violations before and after remediation)')
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.legend()

    plt.tight_layout()
    plt.savefig(output_dir / 'fig5_violation_reduction.png')
    plt.close()
    print("Generated: fig5_violation_reduction.png")


def generate_all_figures():
    """Generate all consolidated figures."""
    networks = ['case14', 'case30', 'case57']

    # Check which networks have data
    available_networks = []
    for n in networks:
        path = Path(__file__).parent / "results" / f"full_eval_{n}.json"
        if path.exists():
            available_networks.append(n)

    if not available_networks:
        print("No evaluation results found!")
        return

    print(f"Found data for: {', '.join(available_networks)}")

    all_data = load_all_results(available_networks)

    output_dir = Path(__file__).parent / "results" / "figures"
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\nGenerating consolidated figures...")
    print(f"Output directory: {output_dir}\n")

    fig1_repair_rate_by_category(all_data, output_dir)
    fig2_latency_boxplot(all_data, output_dir)
    fig3_scaling_analysis(all_data, output_dir)
    fig4_baseline_detection(all_data, output_dir)
    fig5_violation_reduction(all_data, output_dir)

    print(f"\nDone! Generated 5 figures in {output_dir}")


if __name__ == "__main__":
    generate_all_figures()
