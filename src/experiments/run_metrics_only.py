"""
Run evaluation metrics (precision_recall and IAC) on existing Knowledge Graph files.
This script skips DSL extraction and graph transformation, assuming .json KGs already exist.

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


def run_metrics_for_pid(
    pid: str,
    *,
    data_dir: str,
    python_exe: str,
) -> None:
    repo_root = Path(__file__).resolve().parent.parent.parent
    env = {**os.environ, "DATA_DIR": data_dir, "PYTHONPATH": str(repo_root)}
    
    kg_dir = Path(data_dir) / "processed_output" / "kg"
    telemetry_kg = kg_dir / f"{pid}_telemetry_to_kg.json"
    reconciled_kg = kg_dir / f"{pid}_reconciled_kg.json"
    
    if not telemetry_kg.exists():
        print(f"Error: Telemetry KG not found at {telemetry_kg}. Skipping metrics for {pid}.")
        return

    report_types = ["user_report", "full_realization", "task_aware"]
    
    # Metrics output dirs
    metrics_root = Path(data_dir) / "analysis" / "metrics_output"
    pr_dir = metrics_root / "precision_recall"
    iac_dir = metrics_root / "iac"
    pr_dir.mkdir(parents=True, exist_ok=True)
    iac_dir.mkdir(parents=True, exist_ok=True)

    for r_type in report_types:
        print(f"\n  --- Report Type: {r_type} ---")
        
        # 1. Identify Existing KG
        if r_type == "user_report":
            kg_candidates = [
                kg_dir / f"{pid}_dsl_to_kg.json",
                kg_dir / f"{pid}_user_report_dsl_to_kg.json"
            ]
            kg_path = next((cand for cand in kg_candidates if cand.exists()), None)
        else:
            kg_path = kg_dir / f"{pid}_{r_type}_report_dsl_to_kg.json"

        if not kg_path or not kg_path.exists():
            print(f"    Warning: KG not found for {r_type} at {kg_path}. Skipping.")
            continue

        # 2. Run Precision/Recall
        pr_output = pr_dir / f"{pid}_{r_type}_pr.json"
        
        # Ground Truth for P/R: 
        # - User report is compared against telemetry (reporting accuracy)
        # - AI reports are compared against reconciled graph (information survival)
        gt_kg = telemetry_kg if r_type == "user_report" else reconciled_kg
        
        if not gt_kg.exists():
            print(f"    Error: Ground truth KG {gt_kg} missing. Skipping P/R for {r_type}.")
        else:
            _run_step(python_exe, repo_root / "src/pipelines/evaluation/precision_recall.py", 
                      [str(kg_path), str(gt_kg), "--output-path", str(pr_output)], env)
        
        # 3. Run IAC
        iac_output = iac_dir / f"{pid}_{r_type}_iac.json"
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
        "--continue-on-error",
        action="store_true",
        help="Process remaining pids after a failure; exit non-zero if any pid failed.",
    )
    args = parser.parse_args()

    data_dir = args.data_dir or os.environ.get("DATA_DIR")
    if not data_dir:
        raise SystemExit("Set DATA_DIR or pass --data-dir.")

    pids = _collect_pids(args)
    python_exe = sys.executable

    failed: list[tuple[str, BaseException]] = []
    for pid in pids:
        print(f"\n=== Running Metrics: {pid} ===", flush=True)
        try:
            run_metrics_for_pid(
                pid,
                data_dir=data_dir,
                python_exe=python_exe,
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
