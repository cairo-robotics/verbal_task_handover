"""
Run evaluation metrics (precision_recall and IAC) on existing Knowledge Graph files.
This script skips DSL extraction and graph transformation, assuming .json KGs already exist.

Outputs go under $DATA_DIR/analysis/metrics_output/.
"""

try:
    import dotenv
    dotenv.load_dotenv()
except ImportError:
    pass

import argparse
import os
import subprocess
import sys
from pathlib import Path


def _collect_pids(args: argparse.Namespace) -> list[str]:
    from_file: list[str] = []
    if args.pids_file is not None:
        text = args.pids_file.read_text(encoding="utf-8")
        for line in text.splitlines():
            s = line.strip()
            if s and not s.startswith("#"):
                from_file.append(s)
    combined = list(dict.fromkeys(from_file + args.pids))  # stable dedupe
    if not combined:
        raise SystemExit("No participant IDs: pass pids as arguments and/or use --pids-file.")
    return combined


def _run_step(
    python: str,
    script: Path,
    args: list[str],
    env: dict[str, str],
) -> None:
    cmd = [python, str(script)] + args
    print(f"  {' '.join(cmd)}", flush=True)
    subprocess.run(cmd, check=True, env=env)


def run_metrics_for_pid(
    pid: str,
    *,
    data_dir: str,
    python_exe: str,
    models: list[str],
    no_user_report: bool = False,
) -> None:
    repo_root = Path(__file__).resolve().parent.parent.parent
    env = {**os.environ, "DATA_DIR": data_dir, "PYTHONPATH": str(repo_root)}
    
    kg_dir = Path(data_dir) / "processed_output" / "kg"
    telemetry_kg = kg_dir / f"{pid}_telemetry_to_kg.json"
    
    if not telemetry_kg.exists():
        print(f"Error: Telemetry KG not found at {telemetry_kg}. Skipping metrics for {pid}.")
        return
 
    if no_user_report:
        report_types = ["no_report_task_aware"]
    else:
        report_types = ["user_report", "full_realization", "task_aware", "task_aware_raw_ablation", "no_report_task_aware"]
    
    # Metrics output dirs
    metrics_root = Path(data_dir) / "analysis" / "metrics_output"
    pr_dir = metrics_root / "precision_recall"
    iac_dir = metrics_root / "iac"
    pr_dir.mkdir(parents=True, exist_ok=True)
    iac_dir.mkdir(parents=True, exist_ok=True)
 
    for r_type in report_types:
        print(f"\n  --- Report Type: {r_type} ---")
        
        for model in models:
            model_str = f" ({model})"
            print(f"    --- Model: {model} ---")
            
            suffix = f"_{model}" if model else ""
            if "no_report" in r_type:
                reconciled_kg = kg_dir / f"{pid}_no_report_reconciled_kg{suffix}.json"
            else:
                reconciled_kg = kg_dir / f"{pid}_reconciled_kg{suffix}.json"
            
            # 1. Identify Existing KG
            kg_path = None
            if r_type == "user_report":
                report_file = f"{pid}_user_report.txt"
            else:
                report_file = f"{pid}_{r_type}_report{suffix}.txt"
                
            from src.core.utils.extraction_paths import dsl_output_path_for_report_arg, fact_extraction_json_path_for_dsl_path
            
            # Save original USE_EVALUATION_DIRS value
            orig_use_eval = os.environ.get("USE_EVALUATION_DIRS")
            
            try:
                # 1a. Try with USE_EVALUATION_DIRS="1"
                os.environ["USE_EVALUATION_DIRS"] = "1"
                eval_dsl = dsl_output_path_for_report_arg(data_dir, report_file, model=model)
                eval_kg = fact_extraction_json_path_for_dsl_path(eval_dsl)
                if eval_kg.exists():
                    kg_path = eval_kg
                
                # 1b. Try with USE_EVALUATION_DIRS="0"
                if not kg_path:
                    os.environ["USE_EVALUATION_DIRS"] = "0"
                    prod_dsl = dsl_output_path_for_report_arg(data_dir, report_file, model=model)
                    prod_kg = fact_extraction_json_path_for_dsl_path(prod_dsl)
                    if prod_kg.exists():
                        kg_path = prod_kg
            finally:
                # Restore original USE_EVALUATION_DIRS
                if orig_use_eval is not None:
                    os.environ["USE_EVALUATION_DIRS"] = orig_use_eval
                elif "USE_EVALUATION_DIRS" in os.environ:
                    del os.environ["USE_EVALUATION_DIRS"]

            # 1c. Fallback to candidate list lookup if the above didn't find anything
            if not kg_path:
                if r_type == "user_report":
                    kg_candidates = [
                        kg_dir / f"{pid}_user_report_dsl_to_kg{suffix}.json",
                        kg_dir / f"{pid}_user_report_{model}_dsl_to_kg.json",
                        kg_dir / f"{pid}_user_report_dsl_to_kg.json",
                        kg_dir / f"{pid}_dsl_to_kg.json"
                    ]
                else:
                    kg_candidates = [
                        kg_dir / f"{pid}_{r_type}_report_dsl_to_kg{suffix}.json",
                        kg_dir / f"{pid}_{r_type}_report_{model}_dsl_to_kg.json",
                        kg_dir / f"{pid}_{r_type}_report_dsl_to_kg.json"
                    ]
                kg_path = next((cand for cand in kg_candidates if cand.exists()), None)
 
            if not kg_path or not kg_path.exists():
                print(f"    Warning: KG not found for {r_type} model {model}. Skipping.")
                continue
 
            # 2. Run Precision/Recall
            pr_output = pr_dir / f"{pid}_{r_type}{suffix}_pr.json"
            
            # Ground Truth for P/R: 
            # - User report is compared against telemetry (reporting accuracy)
            # - AI reports are compared against reconciled graph (information survival)
            gt_kg = telemetry_kg if r_type == "user_report" else reconciled_kg
            
            if not gt_kg.exists():
                print(f"    Error: Ground truth KG {gt_kg} missing. Skipping P/R for {r_type}{model_str}.")
            else:
                _run_step(python_exe, repo_root / "src/pipelines/evaluation/precision_recall.py", 
                          [str(kg_path), str(gt_kg), "--output-path", str(pr_output)], env)
            
            # 3. Run IAC
            iac_output = iac_dir / f"{pid}_{r_type}{suffix}_iac.json"
            _run_step(python_exe, repo_root / "src/pipelines/evaluation/calculate_iac.py", 
                      ["--kg-file", str(kg_path), "--pid", pid, "--output-file", str(iac_output), "--map-graph", str(telemetry_kg)], env)
 
 
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run evaluation metrics for each participant ID using existing KG files."
    )
    parser.add_argument(
        "pids",
        nargs="*",
        help="Participant IDs (e.g. 302 303). Combine with --pids-file.",
    )
    parser.add_argument(
        "--pids-file",
        type=Path,
        metavar="FILE",
        help="Text file with one pid per line (# comments and blank lines ignored).",
    )
    parser.add_argument(
        "--data-dir",
        metavar="DIR",
        help="Override DATA_DIR for this run (otherwise uses env DATA_DIR).",
    )
    parser.add_argument(
        "--models",
        nargs="+",
        default=["gpt"],
        help="Models to evaluate (choices: gpt, claude, gemini, all, or specific model versions like gpt5-6-terra. Default: gpt).",
    )
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Process remaining pids after a failure; exit non-zero if any pid failed.",
    )
    parser.add_argument(
        "--no-user-report",
        action="store_true",
        help="Run evaluations on only the no_report (ablation) reports.",
    )
    args = parser.parse_args()
 
    data_dir = args.data_dir or os.environ.get("DATA_DIR")
    if not data_dir:
        raise SystemExit("Set DATA_DIR or pass --data-dir.")
 
    pids = _collect_pids(args)
    python_exe = sys.executable
    
    models = args.models
    if "all" in models:
        models = ["gpt", "claude", "gemini"]
    else:
        from src.core.utils.extraction_paths import format_model_name
        # If default ["gpt"] is used but environment has a specific model, use the environment model
        if models == ["gpt"]:
            env_model = os.environ.get("GPT_MODEL") or os.environ.get("MODEL")
            if env_model:
                models = [env_model]
        models = [format_model_name(m) for m in models]
 
    failed: list[tuple[str, BaseException]] = []
    for pid in pids:
        print(f"\n=== Running Metrics: {pid} ===", flush=True)
        try:
            run_metrics_for_pid(
                pid,
                data_dir=data_dir,
                python_exe=python_exe,
                models=models,
                no_user_report=args.no_user_report
            )
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            print(f"Error for pid {pid}: {e}", file=sys.stderr, flush=True)
            failed.append((pid, e))
            if not args.continue_on_error:
                raise SystemExit(1) from e
 
    if failed:
        print(
            f"\nFinished with {len(failed)} failure(s): "
            + ", ".join(p for p, _ in failed),
            file=sys.stderr,
        )
        raise SystemExit(1)
 
 
if __name__ == "__main__":
    main()
