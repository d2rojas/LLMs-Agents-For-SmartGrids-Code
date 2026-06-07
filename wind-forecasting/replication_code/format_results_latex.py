#!/usr/bin/env python3
"""
Format wind forecasting results into LaTeX tables
"""

import pandas as pd
import numpy as np

# Read existing results
df = pd.read_csv('wind_forecasting_results.csv')

# Calculate Overall Score (MAE + RMSE) / 2
df['Overall'] = (df['MAE'] + df['RMSE']) / 2

# Round to 2 decimal places
df = df.round(2)

print("=" * 80)
print("CURRENT RESULTS")
print("=" * 80)
print(df.to_string(index=False))

# Create pivot table like Table 2 in the report
# Rows: Strategy, Columns: Horizon, Values: MAE, RMSE, Overall
print("\n" + "=" * 80)
print("TABLE 2 FORMAT: Performance Across Horizons")
print("=" * 80)

# Group by Strategy and Horizon
for model in df['Model'].unique():
    model_data = df[df['Model'] == model]
    print(f"\n{model}:")

    pivot = model_data.pivot_table(
        index='Strategy',
        columns='Horizon',
        values=['MAE', 'RMSE', 'Overall'],
        aggfunc='first'
    )
    print(pivot)

# Create Table 3 format (like in the report)
print("\n" + "=" * 80)
print("TABLE 3 FORMAT: Results Across Different Models and Variants")
print("=" * 80)

# Create a summary table
summary = df.groupby(['Model', 'Strategy']).agg({
    'MAE': 'mean',
    'RMSE': 'mean',
    'Overall': 'mean'
}).reset_index()

summary = summary.round(2)
summary['Model / Variant'] = summary['Model'] + ' (' + summary['Strategy'] + ')'
summary_display = summary[['Model / Variant', 'MAE', 'RMSE', 'Overall']].copy()

print(summary_display.to_string(index=False))

# Generate LaTeX Table 2 (Horizons)
print("\n" + "=" * 80)
print("LaTeX CODE: Table 2 (Performance Across Horizons)")
print("=" * 80)

# For each model, create a separate table
for model in df['Model'].unique():
    model_data = df[df['Model'] == model]

    print(f"\n% {model}")
    print("\\begin{table}[h]")
    print("\\centering")
    print("\\caption{" + f"Performance across horizons for {model}" + "}")
    print("\\begin{tabular}{|l|ccc|ccc|ccc|}")
    print("\\hline")
    print("& \\multicolumn{3}{c|}{\\textbf{3h}} & \\multicolumn{3}{c|}{\\textbf{6h}} & \\multicolumn{3}{c|}{\\textbf{48h}} \\\\")
    print("\\textbf{Strategy} & MAE & RMSE & Overall & MAE & RMSE & Overall & MAE & RMSE & Overall \\\\")
    print("\\hline")

    for strategy in model_data['Strategy'].unique():
        strategy_data = model_data[model_data['Strategy'] == strategy]

        row = [strategy]
        for horizon in ['3h', '6h', '48h']:
            horizon_data = strategy_data[strategy_data['Horizon'] == horizon]
            if len(horizon_data) > 0:
                row.append(f"{horizon_data['MAE'].values[0]:.2f}")
                row.append(f"{horizon_data['RMSE'].values[0]:.2f}")
                row.append(f"{horizon_data['Overall'].values[0]:.2f}")
            else:
                row.extend(['-', '-', '-'])

        print(" & ".join(row) + " \\\\")

    print("\\hline")
    print("\\end{tabular}")
    print("\\end{table}")

# Generate LaTeX Table 3 (Model comparison)
print("\n" + "=" * 80)
print("LaTeX CODE: Table 3 (Results Across Different Models)")
print("=" * 80)

print("\\begin{table}[h]")
print("\\centering")
print("\\caption{Wind Power Forecasting: Results Across Different Models and Variants}")
print("\\begin{tabular}{|l|c|c|c|}")
print("\\hline")
print("\\textbf{Model / Variant} & \\textbf{MAE (kW)} & \\textbf{RMSE (kW)} & \\textbf{Overall Score (kW)} \\\\")
print("\\hline")

for _, row in summary_display.iterrows():
    print(f"{row['Model / Variant']} & {row['MAE']:.2f} & {row['RMSE']:.2f} & {row['Overall']:.2f} \\\\")

print("\\hline")
print("\\end{tabular}")
print("\\end{table}")

# Save formatted results
output_file = 'formatted_results.csv'
df.to_csv(output_file, index=False)
print(f"\n💾 Formatted results saved to: {output_file}")

# Also save summary
summary_file = 'summary_results.csv'
summary_display.to_csv(summary_file, index=False)
print(f"💾 Summary saved to: {summary_file}")

# Print comparison with report values
print("\n" + "=" * 80)
print("COMPARISON WITH ORIGINAL REPORT (Table 3, Page 8)")
print("=" * 80)

report_values = {
    'GPT 5.2 (Advanced Prompt)': {'MAE': 367.17, 'RMSE': 439.44, 'Overall': 402.83},
    'GPT 5.2 (Advanced Prompt/Binning)': {'MAE': 485.47, 'RMSE': 536.68, 'Overall': 506.07},
    'Gemini 3-flash (Naive Prompt)': {'MAE': 1030.67, 'RMSE': 1114.29, 'Overall': 1072.48},
    'Gemini 3-flash (Advanced Prompt)': {'MAE': 366.22, 'RMSE': 439.44, 'Overall': 402.83},
    'Gemini 3-flash (Advanced Prompt/Binning)': {'MAE': 384.03, 'RMSE': 464.85, 'Overall': 424.44},
    'Gemini 3-flash (APBF)': {'MAE': 189.79, 'RMSE': 292.34, 'Overall': 241.07},
    'Baseline (GRU normalized)': {'MAE': 351.34, 'RMSE': 280.28, 'Overall': 315.82}
}

print("\nOriginal Report (Best Results):")
for model, scores in report_values.items():
    print(f"{model:45s} | MAE: {scores['MAE']:7.2f} | RMSE: {scores['RMSE']:7.2f} | Overall: {scores['Overall']:7.2f}")

print("\nYour Replication Results (Averaged across horizons):")
for _, row in summary_display.iterrows():
    print(f"{row['Model / Variant']:45s} | MAE: {row['MAE']:7.2f} | RMSE: {row['RMSE']:7.2f} | Overall: {row['Overall']:7.2f}")

print("\n" + "=" * 80)
print("NOTES:")
print("=" * 80)
print("1. Original report used Gemini 3-flash, you have results for Gemini 2.5 Flash/Pro")
print("2. Model versions and prompting may differ slightly")
print("3. Results may vary due to LLM non-determinism")
print("4. Best original result: Gemini 3-flash (APBF) with Overall=241.07 kW")
print("5. Your best result: " + summary_display.loc[summary_display['Overall'].idxmin(), 'Model / Variant'] +
      f" with Overall={summary_display['Overall'].min():.2f} kW")
