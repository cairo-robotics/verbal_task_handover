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
    eval_model: str = None,
) -> None:
    os.environ["USE_EVALUATION_DIRS"] = "1"
    env = {**os.environ, "DATA_DIR": data_dir, "USE_EVALUATION_DIRS": "1"}
    repo_root = Path(__file__).resolve().parent.parent.parent
    
    telemetry_kg = Path(data_dir) / "processed_output" / "kg" / f"{pid}_telemetry_to_kg.json"
    if not telemetry_kg.exists():
        print(f"Warning: Telemetry KG not found at {telemetry_kg}. Attempting to generate...")
        _run_step(python_exe, repo_root / "src/core/transforms/telemetry_to_graph.py", [pid], env)
    
    report_types = ["task_aware_raw_ablation"]

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
            
            suffix = f"_{model}" if model else ""
            reconciled_kg = Path(data_dir) / "processed_output" / "kg" / f"{pid}_reconciled_kg{suffix}.json"

            # 1. Identify/Generate KG
            if r_type == "user_report":
                if use_human_dsl:
                    dsl_path = Path(data_dir) / "annotations" / "dsl" / f"kb_annotated_{pid}_user_report.txt"
                    if not dsl_path.exists():
                        print(f"    Error: {dsl_path} not found. Skipping user_report.")
                        continue
                    
                    if os.environ.get("USE_EVALUATION_DIRS") == "1":
                        kg_path = Path(data_dir) / "analysis" / "kg" / f"{pid}_user_report_dsl_to_kg.json"
                    else:
                        kg_path = Path(data_dir) / "processed_output" / "kg" / f"{pid}_user_report_dsl_to_kg.json"
                    _run_step(python_exe, repo_root / "src/core/transforms/dsl_to_graph.py", 
                              [str(dsl_path.relative_to(data_dir)), "--output", str(kg_path)], env)
                else:
                    report_file = f"{pid}_user_report.txt"
                    if not (Path(data_dir) / "reports" / report_file).exists():
                        print(f"    Error: {report_file} not found. Skipping user_report.")
                        continue
                    
                    provider = "gpt"
                    if model:
                        if "claude" in model:
                            provider = "claude"
                        elif "gemini" in model:
                            provider = "gemini"
                    dsl_args = [report_file, "--model-provider", provider]
                    if model:
                        dsl_args.extend(["--model", model])
                    if eval_model:
                        dsl_args.extend(["--eval-model", eval_model])

                    # Generate DSL
                    _run_step(python_exe, repo_root / "src/core/transforms/report_to_dsl.py", 
                              dsl_args, env)
                    # Generate KG
                    from src.core.utils.extraction_paths import dsl_output_path_for_report_arg, fact_extraction_json_path_for_dsl_path
                    dsl_path = dsl_output_path_for_report_arg(data_dir, report_file, model=model)
                    kg_path = fact_extraction_json_path_for_dsl_path(dsl_path)
                    _run_step(python_exe, repo_root / "src/core/transforms/dsl_to_graph.py", 
                              [str(dsl_path.relative_to(data_dir)), "--output", str(kg_path)], env)
            else:
                # AI reports: full_realization, task_aware
                report_file = f"{pid}_{r_type}_report{suffix}.txt"
                if not (Path(data_dir) / "reports" / report_file).exists():
                    print(f"    Warning: {report_file} not found. Skipping {r_type}.")
                    continue
                
                # Generate DSL
                provider = "gpt"
                if model:
                    if "claude" in model:
                        provider = "claude"
                    elif "gemini" in model:
                        provider = "gemini"
                dsl_args = [report_file, "--model-provider", provider]
                if model:
                    dsl_args.extend(["--model", model])
                if eval_model:
                    dsl_args.extend(["--eval-model", eval_model])
                _run_step(python_exe, repo_root / "src/core/transforms/report_to_dsl.py", 
                          dsl_args, env)
                
                # Generate KG
                from src.core.utils.extraction_paths import dsl_output_path_for_report_arg, fact_extraction_json_path_for_dsl_path
                dsl_path = dsl_output_path_for_report_arg(data_dir, report_file, model=model)
                kg_path = fact_extraction_json_path_for_dsl_path(dsl_path)
                _run_step(python_exe, repo_root / "src/core/transforms/dsl_to_graph.py", 
                          [str(dsl_path.relative_to(data_dir)), "--output", str(kg_path)], env)

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
        default=["gpt"],
        help="Models to evaluate (choices: gpt, claude, gemini, all, or specific model versions like gpt5-6-terra. Default: gpt).",
    )
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Process remaining pids after a failure; exit non-zero if any pid failed.",
    )
    parser.add_argument(
        "--eval-model",
        default=None,
        help="Model version to use for evaluation DSL extraction (e.g. gpt-4.1-mini).",
    )
    parser.add_argument(
        "--use-human-dsl",
        action="store_true",
        help="Use human-written DSL from $DATA_DIR/annotations instead of generating it.",
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
        print(f"\n=== Evaluation Pipeline: {pid} ===", flush=True)
        try:
            run_evaluation_for_pid(
                pid,
                data_dir=data_dir,
                python_exe=python_exe,
                models=models,
                use_human_dsl=args.use_human_dsl,
                eval_model=args.eval_model,
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
