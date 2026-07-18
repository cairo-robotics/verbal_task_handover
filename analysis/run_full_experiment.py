import dotenv
dotenv.load_dotenv()

import argparse
import subprocess
import sys
import os
import datetime
import threading
import pandas as pd
from scipy.stats import wilcoxon

# Parse arguments
parser = argparse.ArgumentParser(description="Run the full experiment pipeline.")
parser.add_argument("--dry-run", action="store_true", help="Perform a dry run with mock API calls.")
parser.add_argument("--eval-model", default=None, help="The model version to use for evaluation DSL extraction.")
args = parser.parse_args()

# pids = [str(x) for x in range(501, 514)]
pids = [str(x) for x in range(501, 514)]
data_dir = "/media/kaleb/T7/handover_project/participant_data"
python_exe = sys.executable

# 1. Establish logging environment variable first
timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
log_dir = os.path.join(data_dir, "logs")
os.makedirs(log_dir, exist_ok=True)
log_file_path = os.path.join(log_dir, f"experiment_run_{timestamp}.log")
os.environ["EXPERIMENT_LOG_FILE"] = log_file_path

if args.dry_run:
    os.environ["DRY_RUN"] = "1"

# Add the project root to sys.path to ensure src can be imported directly
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import logging utilities after setting env var
from src.core.utils.experiment_logging import log_message

log_message("================================================================================")
log_message(f"EXPERIMENT RUN START: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
log_message(f"Log File: {log_file_path}")
log_message(f"Python Executable: {python_exe}")
log_message(f"Model Version (GPT_MODEL): {os.environ.get('GPT_MODEL', 'gpt-5.6-sol')}")
log_message(f"Evaluation Model (EVAL_MODEL): {args.eval_model}")
log_message(f"Dry Run: {args.dry_run}")
log_message("================================================================================")

print(f"Running pipeline and evaluation for all participants... Log: {log_file_path}")
env = {**os.environ, "PYTHONPATH": ".", "DATA_DIR": data_dir}

def run_logged_command(cmd, env):
    cmd_str = " ".join(cmd)
    log_message(f"[PARENT] Running command: {cmd_str}")
    start_time = datetime.datetime.now()
    
    # We pipe stdout and stderr to capture them and print them in real-time
    process = subprocess.Popen(
        cmd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1
    )
    
    stdout_lines = []
    stderr_lines = []
    
    def read_stream(stream, buffer, dest):
        for line in stream:
            dest.write(line)
            dest.flush()
            buffer.append(line)
            
    t1 = threading.Thread(target=read_stream, args=(process.stdout, stdout_lines, sys.stdout))
    t2 = threading.Thread(target=read_stream, args=(process.stderr, stderr_lines, sys.stderr))
    t1.start()
    t2.start()
    
    exit_code = process.wait()
    t1.join()
    t2.join()
    
    end_time = datetime.datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    if exit_code == 0:
        log_message(f"[PARENT] Success: {cmd_str} (duration: {duration:.2f}s)")
    else:
        stdout_str = "".join(stdout_lines)
        stderr_str = "".join(stderr_lines)
        error_msg = (
            f"[PARENT] Failure: {cmd_str} (duration: {duration:.2f}s, exit code: {exit_code})\n"
            f"--- STDOUT ---\n{stdout_str}\n"
            f"--- STDERR ---\n{stderr_str}\n"
        )
        log_message(error_msg)
        raise subprocess.CalledProcessError(exit_code, cmd, output=stdout_str, stderr=stderr_str)

for pid in pids:
    print(f"\n=== Running participant {pid} ===")
    
    # 1. Run full pipeline for standard (both task_aware and full_realization)
    cmd1 = [python_exe, "src/experiments/run_full_pipeline_for_pids.py", pid, "--prompt-set", "both"]
    if args.eval_model:
        cmd1.extend(["--eval-model", args.eval_model])
    run_logged_command(cmd1, env=env)
    
    # 2. Run full pipeline for no-report ablation
    cmd2 = [python_exe, "src/experiments/run_full_pipeline_for_pids.py", pid, "--prompt-set", "task_aware", "--no-user-report"]
    if args.eval_model:
        cmd2.extend(["--eval-model", args.eval_model])
    run_logged_command(cmd2, env=env)
    
    # 3. Run raw ablation (end-to-end task-aware version)
    run_logged_command([
        python_exe, "src/experiments/generate_reports_raw_ablation.py", pid
    ], env=env)
    
    # 4. Run evaluation for standard (user_report, full_realization, task_aware)
    cmd4 = [python_exe, "src/experiments/run_evaluation_pipeline.py", pid]
    if args.eval_model:
        cmd4.extend(["--eval-model", args.eval_model])
    run_logged_command(cmd4, env=env)
    
    # 5. Run evaluation for no-report ablation
    cmd5 = [python_exe, "src/experiments/run_evaluation_pipeline.py", pid, "--no-user-report"]
    if args.eval_model:
        cmd5.extend(["--eval-model", args.eval_model])
    run_logged_command(cmd5, env=env)

    # 6. Run evaluation for raw ablation
    cmd6 = [python_exe, "src/experiments/run_evaluation_pipeline.py", pid, "--raw-ablation"]
    if args.eval_model:
        cmd6.extend(["--eval-model", args.eval_model])
    run_logged_command(cmd6, env=env)

print("\nPipeline runs complete! Re-aggregating metrics...")

# Run the metrics aggregation script
run_logged_command([
    python_exe, "analysis/aggregate_metrics.py"
], env=env)

# Load the aggregated metrics CSV and calculate statistics
csv_path = "/media/kaleb/T7/handover_project/participant_data/analysis/metrics_output/aggregated_metrics.csv"
df = pd.read_csv(csv_path)
df["communicative_compression"] = df["iac_cost_saved"] / df["token_count"]

from src.core.utils.extraction_paths import format_model_name

print("\n=================== DESCRIPTIVE STATISTICS ===================")
conditions_to_print = ["user_report", "task_aware", "no_report_task_aware", "full_realization", "task_aware_raw_ablation"]
selected_model_raw = os.environ.get("GPT_MODEL") or os.environ.get("MODEL") or "gpt"
selected_model = format_model_name(selected_model_raw)

for metric in ["iac_cost_saved", "token_count", "communicative_compression"]:
    print(f"\nMetric: {metric}")
    for cond in conditions_to_print:
        if cond == "user_report":
            sub_df = df[(df["condition"] == cond) & (df["model"] == "human")][metric].dropna()
            model_filter = "human"
        else:
            sub_df = df[(df["condition"] == cond) & (df["model"].str.startswith(selected_model) | (df["model"] == selected_model))][metric].dropna()
            model_filter = selected_model
        if not sub_df.empty:
            print(f"  {cond:<25} (model: {model_filter:<5}) - Mean: {sub_df.mean():.4f}, Median: {sub_df.median():.4f}, Count: {len(sub_df)}")
        else:
            print(f"  {cond:<25} (model: {model_filter:<5}) - No data")

target_conditions = ["task_aware", "no_report_task_aware"]
filtered_df = df[(df["condition"].isin(target_conditions)) & (df["model"].str.startswith(selected_model) | (df["model"] == selected_model))]
filtered_df = filtered_df.drop_duplicates(subset=["participant_id", "condition"])
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

log_message(f"EXPERIMENT RUN COMPLETE: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
log_message("================================================================================")
