"""
Run the full model-alignment pipeline for one or more participant IDs.

Steps (per pid): telemetry_to_graph → report_to_dsl → dsl_to_graph →
merge_graphs → reconcile_state → craft_narrative_view → generate_reports.

Requires DATA_DIR (or --data-dir) with:
  $DATA_DIR/telemetry/<pid>.txt
  $DATA_DIR/reports/<pid>_user_report.txt

Outputs go under $DATA_DIR/processed_output/ (same as the individual scripts).
"""

from __future__ import annotations

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


def _alignment_dir() -> Path:
    return Path(__file__).resolve().parent


from src.core.utils.experiment_logging import log_message, get_log_file


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
    cmd_str = ' '.join(cmd)
    print(f"  {cmd_str}", flush=True)
    log_message(f"  [SUB] Running: {cmd_str}")
    try:
        subprocess.run(cmd, check=True, env=env)
        log_message(f"  [SUB] Success: {cmd_str}")
    except subprocess.CalledProcessError as e:
        log_message(f"  [SUB] Failure: {cmd_str} (exit code: {e.returncode})")
        raise e


def get_pipeline_scripts(
    pid: str,
    data_dir: str,
    prompt_set: str,
    repo_root: Path,
    use_human_dsl: bool,
    no_user_report: bool,
    model_provider: str,
    eval_model: str | None = None,
    force: bool = False,
) -> list[tuple[Path, list[str]]]:
    from src.core.utils.extraction_paths import (
        dsl_output_path_for_report_arg,
        fact_extraction_json_path_for_dsl_path,
        get_current_model_suffix,
    )
    
    model_suffix = get_current_model_suffix(provider=model_provider)
    
    if no_user_report:
        return [
            (repo_root / "src/core/transforms/telemetry_to_graph.py", [pid]),
            (repo_root / "src/pipelines/model_alignment/reconcile_state.py", [
                "-i", str(Path(data_dir) / "processed_output" / "kg" / f"{pid}_telemetry_to_kg.json"),
                "-o", str(Path(data_dir) / "processed_output" / "kg" / f"{pid}_no_report_reconciled_kg_{model_suffix}.json")
            ]),
            (repo_root / "src/pipelines/model_alignment/craft_narrative_view.py", [f"{pid}_no_report"]),
            (repo_root / "src/pipelines/model_alignment/generate_reports.py", [f"{pid}_no_report", "--prompt-set", prompt_set]),
        ]
        
    if use_human_dsl:
        dsl_source_path = Path(data_dir) / "annotations" / "dsl" / f"kb_annotated_{pid}_user_report.txt"
        dsl_kg_path = Path(data_dir) / "processed_output" / "kg" / f"{pid}_user_report_dsl_to_kg.json"
        
        return [
            (repo_root / "src/core/transforms/telemetry_to_graph.py", [pid]),
            (repo_root / "src/core/transforms/dsl_to_graph.py", [str(dsl_source_path.relative_to(data_dir)), "--output", str(dsl_kg_path)]),
            (repo_root / "src/pipelines/model_alignment/merge_graphs.py", [
                str(Path(data_dir) / "processed_output" / "kg" / f"{pid}_telemetry_to_kg.json"),
                str(dsl_kg_path),
                "--output", str(Path(data_dir) / "processed_output" / "kg" / f"{pid}_merged_kg.json")
            ]),
            (repo_root / "src/pipelines/model_alignment/reconcile_state.py", [pid]),
            (repo_root / "src/pipelines/model_alignment/craft_narrative_view.py", [pid]),
            (repo_root / "src/pipelines/model_alignment/generate_reports.py", [pid, "--prompt-set", prompt_set]),
        ]

    # Standard model-specific user report path
    dsl_output_path = dsl_output_path_for_report_arg(data_dir, f"{pid}_user_report.txt", model=model_suffix)
    dsl_kg_path = fact_extraction_json_path_for_dsl_path(dsl_output_path)
    
    scripts = [
        (repo_root / "src/core/transforms/telemetry_to_graph.py", [pid]),
    ]
    
    # If the DSL file does not exist, is a placeholder, or force is True, we must generate it.
    is_placeholder = False
    if dsl_output_path.is_file():
        try:
            with open(dsl_output_path, "r", encoding="utf-8") as f:
                first_line = f.readline()
                if "Placeholder DSL" in first_line:
                    is_placeholder = True
        except Exception:
            pass

    if not dsl_output_path.is_file() or is_placeholder or force:
        model_name = os.environ.get("GPT_MODEL") or os.environ.get("MODEL")
        dsl_args = [f"{pid}_user_report.txt", "--model-provider", model_provider]
        if model_name:
            dsl_args.extend(["--model", model_name])
        if eval_model:
            dsl_args.extend(["--eval-model", eval_model])
        scripts.append(
            (repo_root / "src/core/transforms/report_to_dsl.py", dsl_args)
        )
        
    scripts.extend([
        (repo_root / "src/core/transforms/dsl_to_graph.py", [str(dsl_output_path.relative_to(data_dir)), "--output", str(dsl_kg_path)]),
        (repo_root / "src/pipelines/model_alignment/merge_graphs.py", [
            str(Path(data_dir) / "processed_output" / "kg" / f"{pid}_telemetry_to_kg.json"),
            str(dsl_kg_path),
            "--output", str(Path(data_dir) / "processed_output" / "kg" / f"{pid}_merged_kg_{model_suffix}.json")
        ]),
        (repo_root / "src/pipelines/model_alignment/reconcile_state.py", [pid]),
        (repo_root / "src/pipelines/model_alignment/craft_narrative_view.py", [pid]),
        (repo_root / "src/pipelines/model_alignment/generate_reports.py", [pid, "--prompt-set", prompt_set]),
    ])
    
    return scripts


def run_pipeline_for_pid(
    pid: str,
    *,
    data_dir: str,
    prompt_set: str,
    python_exe: str,
    use_human_dsl: bool = False,
    no_user_report: bool = False,
    model_provider: str = "gpt",
    eval_model: str | None = None,
    force: bool = False,
) -> None:
    env = {**os.environ, "DATA_DIR": data_dir}
    repo_root = Path(__file__).resolve().parent.parent.parent
    
    scripts = get_pipeline_scripts(
        pid,
        data_dir=data_dir,
        prompt_set=prompt_set,
        repo_root=repo_root,
        use_human_dsl=use_human_dsl,
        no_user_report=no_user_report,
        model_provider=model_provider,
        eval_model=eval_model,
        force=force,
    )
    
    for path, args in scripts:
        if not path.is_file():
            raise FileNotFoundError(f"Missing pipeline script: {path}")
        _run_step(python_exe, path, args, env)


def main() -> None:
    get_log_file()
    parser = argparse.ArgumentParser(
        description="Run the full report pipeline for each participant ID."
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
        "--prompt-set",
        choices=("full_realization", "task_aware", "both"),
        default="both",
        help="Forwarded to generate_reports.py (default: both).",
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
        help="Ablation: do not incorporate the user report; reconcile and generate reports directly from telemetry.",
    )
    parser.add_argument(
        "--model-provider",
        default="gpt",
        help="Model provider for parsing the user report to DSL (default: gpt).",
    )
    parser.add_argument(
        "--eval-model",
        default=None,
        help="Model version to use for evaluation DSL extraction (e.g. gpt-4.1-mini).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print steps only; do not run subprocesses.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force regeneration of DSLs and KGs, even if they already exist.",
    )
    args = parser.parse_args()

    if args.no_user_report and args.use_human_dsl:
        parser.error("Cannot use both --no-user-report and --use-human-dsl.")

    data_dir = args.data_dir or os.environ.get("DATA_DIR")
    if not data_dir:
        raise SystemExit("Set DATA_DIR or pass --data-dir.")

    pids = _collect_pids(args)
    python_exe = sys.executable

    failed: list[tuple[str, BaseException]] = []
    for pid in pids:
        print(f"\n=== Pipeline: {pid} ===", flush=True)
        try:
            if args.dry_run:
                repo_root = Path(__file__).resolve().parent.parent.parent
                scripts = get_pipeline_scripts(
                    pid,
                    data_dir=data_dir,
                    prompt_set=args.prompt_set,
                    repo_root=repo_root,
                    use_human_dsl=args.use_human_dsl,
                    no_user_report=args.no_user_report,
                    model_provider=args.model_provider,
                    eval_model=args.eval_model,
                    force=args.force,
                )
                for path, step_args in scripts:
                    cmd = [python_exe, str(path)] + step_args
                    print(f"  (dry-run) {' '.join(cmd)}", flush=True)
            else:
                run_pipeline_for_pid(
                    pid,
                    data_dir=data_dir,
                    prompt_set=args.prompt_set,
                    python_exe=python_exe,
                    use_human_dsl=args.use_human_dsl,
                    no_user_report=args.no_user_report,
                    model_provider=args.model_provider,
                    eval_model=args.eval_model,
                    force=args.force,
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
