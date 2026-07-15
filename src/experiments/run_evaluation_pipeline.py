"""
Run the full evaluation pipeline for one or more participant IDs.

Steps (per report type: user_report, full_realization, task_aware):
1. (If needed) report_to_dsl -> dsl_to_graph -> KG
2. precision_recall against telemetry KG
3. calculate_iac using telemetry KG as map graph

Outputs go under $DATA_DIR/analysis/metrics_output/.
"""

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


def run_evaluation_for_pid(
    pid: str,
    *,
    data_dir: str,
    python_exe: str,
    models: list[str],
    use_human_dsl: bool = False,
    no_user_report: bool = False,
    raw_ablation: bool = False,
    ) -> None:
    env = {**os.environ, "DATA_DIR": data_dir}
    repo_root = Path(__file__).resolve().parent.parent.parent
    
    telemetry_kg = Path(data_dir) / "processed_output" / "kg" / f"{pid}_telemetry_to_kg.json"
    if not telemetry_kg.exists():
        print(f"Warning: Telemetry KG not found at {telemetry_kg}. Attempting to generate...")
        _run_step(python_exe, repo_root / "src/core/transforms/telemetry_to_graph.py", [pid], env)
    
    if no_user_report:
        reconciled_kg = Path(data_dir) / "processed_output" / "kg" / f"{pid}_no_report_reconciled_kg.json"
    else:
        reconciled_kg = Path(data_dir) / "processed_output" / "kg" / f"{pid}_reconciled_kg.json"

    if not reconciled_kg.exists():
        print(f"Warning: Reconciled KG not found at {reconciled_kg}. This is required for AI report P/R.")
        # Note: We don't auto-generate this here as it requires the full alignment pipeline.
    
    if no_user_report or raw_ablation:
        report_types = ["task_aware"]
    else:
        # report_types = ["user_report", "full_realization", "task_aware"]
        report_types = ["user_report", "task_aware"]
    
    # Metrics output dirs
    pr_dir = Path(data_dir) / "analysis" / "metrics_output" / "precision_recall"
    iac_dir = Path(data_dir) / "analysis" / "metrics_output" / "iac"
    pr_dir.mkdir(parents=True, exist_ok=True)
    iac_dir.mkdir(parents=True, exist_ok=True)

    for r_type in report_types:
        print(f"\n  --- Report Type: {r_type} ---")
        
        # If use_human_dsl is True, we only evaluate the human annotations once
        current_models = [None] if (r_type == "user_report" and use_human_dsl) else models
        
        for model in current_models:
            model_str = f" ({model})" if model else ""
            print(f"    --- Model: {model if model else 'human'} ---")
            
            # 1. Identify/Generate KG
            if r_type == "user_report":
                if use_human_dsl:
                    dsl_path = Path(data_dir) / "annotations" / "dsl" / f"kb_annotated_{pid}_user_report.txt"
                    if not dsl_path.exists():
                        print(f"    Error: {dsl_path} not found. Skipping user_report.")
                        continue
                    
                    kg_path = Path(data_dir) / "processed_output" / "kg" / f"{pid}_user_report_dsl_to_kg.json"
                    _run_step(python_exe, repo_root / "src/core/transforms/dsl_to_graph.py", 
                              [str(dsl_path.relative_to(data_dir)), "--output", str(kg_path)], env)
                else:
                    report_file = f"{pid}_user_report.txt"
                    if not (Path(data_dir) / "reports" / report_file).exists():
                        print(f"    Error: {report_file} not found. Skipping user_report.")
                        continue
                    
                    # Generate DSL
                    _run_step(python_exe, repo_root / "src/core/transforms/report_to_dsl.py", 
                              [report_file, "--model-provider", model], env)
                    # Generate KG
                    dsl_path = Path(data_dir) / "processed_output" / "dsl" / f"{pid}_user_report_{model}_dsl.txt"
                    kg_path = Path(data_dir) / "processed_output" / "kg" / f"{pid}_user_report_{model}_dsl_to_kg.json"
                    _run_step(python_exe, repo_root / "src/core/transforms/dsl_to_graph.py", 
                              [str(dsl_path.relative_to(data_dir)), "--output", str(kg_path)], env)
            else:
                # AI reports: full_realization, task_aware
                if no_user_report:
                    report_file = f"{pid}_no_report_{r_type}_report.txt"
                elif raw_ablation:
                    report_file = f"{pid}_{r_type}_raw_ablation_report.txt"
                else:
                    report_file = f"{pid}_{r_type}_report.txt"

                if not (Path(data_dir) / "reports" / report_file).exists():
                    print(f"    Warning: {report_file} not found. Skipping {r_type}.")
                    continue
                
                # Generate DSL
                _run_step(python_exe, repo_root / "src/core/transforms/report_to_dsl.py", 
                          [report_file, "--model-provider", model], env)
                
                # Generate KG
                if no_user_report:
                    dsl_path = Path(data_dir) / "processed_output" / "dsl" / f"{pid}_no_report_{r_type}_report_{model}_dsl.txt"
                    kg_path = Path(data_dir) / "processed_output" / "kg" / f"{pid}_no_report_{r_type}_report_{model}_dsl_to_kg.json"
                elif raw_ablation:
                    dsl_path = Path(data_dir) / "processed_output" / "dsl" / f"{pid}_{r_type}_raw_ablation_report_{model}_dsl.txt"
                    kg_path = Path(data_dir) / "processed_output" / "kg" / f"{pid}_{r_type}_raw_ablation_report_{model}_dsl_to_kg.json"
                else:
                    dsl_path = Path(data_dir) / "processed_output" / "dsl" / f"{pid}_{r_type}_report_{model}_dsl.txt"
                    kg_path = Path(data_dir) / "processed_output" / "kg" / f"{pid}_{r_type}_report_{model}_dsl_to_kg.json"

                _run_step(python_exe, repo_root / "src/core/transforms/dsl_to_graph.py", 
                          [str(dsl_path.relative_to(data_dir)), "--output", str(kg_path)], env)

            # 2. Run Precision/Recall
            suffix = f"_{model}" if model else ""
            if no_user_report:
                pr_output = pr_dir / f"{pid}_no_report_{r_type}{suffix}_pr.json"
            elif raw_ablation:
                pr_output = pr_dir / f"{pid}_{r_type}_raw_ablation{suffix}_pr.json"
            else:
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
            if no_user_report:
                iac_output = iac_dir / f"{pid}_no_report_{r_type}{suffix}_iac.json"
            elif raw_ablation:
                iac_output = iac_dir / f"{pid}_{r_type}_raw_ablation{suffix}_iac.json"
            else:
                iac_output = iac_dir / f"{pid}_{r_type}{suffix}_iac.json"

            _run_step(python_exe, repo_root / "src/pipelines/evaluation/calculate_iac.py", 
                      ["--kg-file", str(kg_path), "--pid", pid, "--output-file", str(iac_output), "--map-graph", str(telemetry_kg)], env)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the full evaluation pipeline for each participant ID."
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
        choices=["gpt", "claude", "gemini", "all"],
        default=["gpt"],
        help="Models to evaluate (choices: gpt, claude, gemini, all. Default: gpt).",
    )
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Process remaining pids after a failure; exit non-zero if any pid failed.",
    )
    parser.add_argument(
        "--use-human-dsl",
        action="store_true",
        help="Use human-written DSL from $DATA_DIR/annotations instead of generating it.",
    )
    parser.add_argument(
        "--no-user-report",
        action="store_true",
        help="Run evaluations on only the no_report (ablation) reports.",
    )
    parser.add_argument(
        "--raw-ablation",
        action="store_true",
        help="Run evaluations on only the raw_ablation reports.",
    )
    args = parser.parse_args()

    if args.no_user_report and args.use_human_dsl:
        parser.error("Cannot use both --no-user-report and --use-human-dsl.")

    data_dir = args.data_dir or os.environ.get("DATA_DIR")
    if not data_dir:
        raise SystemExit("Set DATA_DIR or pass --data-dir.")

    pids = _collect_pids(args)
    python_exe = sys.executable

    models = args.models
    if "all" in models:
        models = ["gpt", "claude", "gemini"]

    failed: list[tuple[str, BaseException]] = []
    for pid in pids:
        print(f"\n=== Evaluation Pipeline: {pid} ===", flush=True)
        try:
            run_evaluation_for_pid(
                pid,
                data_dir=data_dir,
                python_exe=python_exe,
                models=models,
                use_human_dsl=args.use_human_dsl,
                no_user_report=args.no_user_report,
                raw_ablation=args.raw_ablation,
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
