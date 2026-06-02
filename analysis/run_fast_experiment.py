import subprocess
import sys
import os
import time
import pandas as pd
from scipy.stats import wilcoxon

pids = [str(x) for x in range(501, 514)]
data_dir = "/media/kaleb/T7/handover_project/participant_data"
python_exe = sys.executable
env = {**os.environ, "PYTHONPATH": ".", "DATA_DIR": data_dir}

def run_with_retry(cmd, retries=3, timeout=60):
    for i in range(retries):
        try:
            print(f"  Running: {' '.join(cmd)}")
            subprocess.run(cmd, env=env, check=True, timeout=timeout)
            return
        except subprocess.TimeoutExpired:
            print(f"  [Timeout] Command timed out after {timeout}s. Retrying ({i+1}/{retries})...")
            time.sleep(2)
        except subprocess.CalledProcessError as e:
            print(f"  [Error] Command failed: {e}. Retrying ({i+1}/{retries})...")
            time.sleep(2)
    raise RuntimeError(f"Command failed after {retries} retries: {' '.join(cmd)}")

print("Running fast generation and evaluation for all participants...")

for pid in pids:
    print(f"\n=================== PARTICIPANT {pid} ===================")
    
    # 1. Generate task_aware report
    run_with_retry([
        python_exe, "src/pipelines/model_alignment/generate_reports.py", pid, "--prompt-set", "task_aware"
    ])
    
    # 2. Generate no_report_task_aware report
    run_with_retry([
        python_exe, "src/pipelines/model_alignment/generate_reports.py", f"{pid}_no_report", "--prompt-set", "task_aware"
    ])
    
    # 3. Evaluate task_aware report (automatically runs report_to_dsl and dsl_to_graph)
    run_with_retry([
        python_exe, "src/experiments/run_evaluation_pipeline.py", pid
    ])
    
    # 4. Evaluate no_report_task_aware report
    run_with_retry([
        python_exe, "src/experiments/run_evaluation_pipeline.py", pid, "--no-user-report"
    ])

print("\nAll pipeline and evaluation runs complete! Re-aggregating metrics...")

# Run the metrics aggregation script
run_with_retry([
    python_exe, "analysis/aggregate_metrics.py"
])

# Load the aggregated metrics CSV and calculate statistics
csv_path = "/media/kaleb/T7/handover_project/participant_data/analysis/metrics_output/aggregated_metrics.csv"
df = pd.read_csv(csv_path)
df["communicative_compression"] = df["iac_cost_saved"] / df["token_count"]

target_conditions = ["task_aware", "no_report_task_aware"]
filtered_df = df[df["condition"].isin(target_conditions)]
pivoted = filtered_df.pivot(index="participant_id", columns="condition", values=["iac_cost_saved", "token_count", "communicative_compression"])
pivoted = pivoted.dropna()

print("\n=================== FAST EXPERIMENT AGGREGATED STATS ===================")
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
