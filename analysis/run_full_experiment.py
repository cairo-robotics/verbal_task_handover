import subprocess
import sys
import os
import pandas as pd
from scipy.stats import wilcoxon

pids = [str(x) for x in range(501, 514)]
data_dir = "/media/kaleb/T7/handover_project/participant_data"
python_exe = sys.executable

print("Running pipeline and evaluation for all participants...")
env = {**os.environ, "PYTHONPATH": ".", "DATA_DIR": data_dir}

for pid in pids:
    print(f"\n=== Running participant {pid} ===")
    
    # 1. Run full pipeline for standard task_aware
    subprocess.run([
        python_exe, "src/experiments/run_full_pipeline_for_pids.py", pid, "--prompt-set", "task_aware"
    ], env=env, check=True)
    
    # 2. Run full pipeline for no-report ablation
    subprocess.run([
        python_exe, "src/experiments/run_full_pipeline_for_pids.py", pid, "--prompt-set", "task_aware", "--no-user-report"
    ], env=env, check=True)
    
    # 3. Run evaluation for standard task_aware
    subprocess.run([
        python_exe, "src/experiments/run_evaluation_pipeline.py", pid
    ], env=env, check=True)
    
    # 4. Run evaluation for no-report ablation
    subprocess.run([
        python_exe, "src/experiments/run_evaluation_pipeline.py", pid, "--no-user-report"
    ], env=env, check=True)

print("\nPipeline runs complete! Re-aggregating metrics...")

# Run the metrics aggregation script
subprocess.run([
    python_exe, "analysis/aggregate_metrics.py"
], env=env, check=True)

# Load the aggregated metrics CSV and calculate statistics
csv_path = "/media/kaleb/T7/handover_project/participant_data/analysis/metrics_output/aggregated_metrics.csv"
df = pd.read_csv(csv_path)
df["communicative_compression"] = df["iac_cost_saved"] / df["token_count"]

target_conditions = ["task_aware", "no_report_task_aware"]
filtered_df = df[(df["condition"].isin(target_conditions)) & (df["model"] == "gpt")]
pivoted = filtered_df.pivot(index="participant_id", columns="condition", values=["iac_cost_saved", "token_count", "communicative_compression"])
pivoted = pivoted.dropna()

print("\n=================== NEW AGGREGATED STATS ===================")
for metric in ["iac_cost_saved", "communicative_compression"]:
    ta = pivoted[(metric, "task_aware")]
    nr = pivoted[(metric, "no_report_task_aware")]
    
    stat, p_val = wilcoxon(ta, nr)
    print(f"\nMetric: {metric}")
    print(f"  Task-Aware mean: {ta.mean():.4f}, No-Report mean: {nr.mean():.4f} (diff = {ta.mean() - nr.mean():.4f})")
    print(f"  Task-Aware median: {ta.median():.4f}, No-Report median: {nr.median():.4f}")
    print(f"  Wilcoxon W: {stat}, p-value: {p_val:.6f}")
    if p_val < 0.05:
        print("  *** STATISTICALLY SIGNIFICANT (p < 0.05) ***")
    else:
        print("  Not statistically significant")
