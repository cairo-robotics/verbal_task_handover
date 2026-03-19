"""
Run the full model-alignment pipeline for one or more participant IDs.

Steps (per pid): telemetry_to_graph → text_to_graph → compare_graphs →
merge_graphs → craft_narrative_view → generate_reports.

Requires DATA_DIR (or --data-dir) with:
  $DATA_DIR/telemetry/<pid>.txt
  $DATA_DIR/reports/<pid>_user_report.txt

Outputs go under $DATA_DIR/processed_output/ (same as the individual scripts).
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


def _alignment_dir() -> Path:
    return Path(__file__).resolve().parent


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
    pid: str,
    extra_args: list[str],
    env: dict[str, str],
) -> None:
    cmd = [python, str(script), pid, *extra_args]
    print(f"  {' '.join(cmd)}", flush=True)
    subprocess.run(cmd, check=True, env=env)


def run_pipeline_for_pid(
    pid: str,
    *,
    data_dir: str,
    prompt_set: str,
    python_exe: str,
) -> None:
    env = {**os.environ, "DATA_DIR": data_dir}
    root = _alignment_dir()
    scripts = [
        (root / "telemetry_to_graph.py", []),
        (root / "text_to_graph.py", []),
        (root / "compare_graphs.py", []),
        (root / "merge_graphs.py", []),
        (root / "craft_narrative_view.py", []),
        (root / "generate_reports.py", ["--prompt-set", prompt_set]),
    ]
    for path, extra in scripts:
        if not path.is_file():
            raise FileNotFoundError(f"Missing pipeline script: {path}")
        _run_step(python_exe, path, pid, extra, env)


def main() -> None:
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
        default="full_realization",
        help="Forwarded to generate_reports.py (default: full_realization).",
    )
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Process remaining pids after a failure; exit non-zero if any pid failed.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print steps only; do not run subprocesses.",
    )
    args = parser.parse_args()

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
                root = _alignment_dir()
                extra = ["--prompt-set", args.prompt_set]
                for name in (
                    "telemetry_to_graph.py",
                    "text_to_graph.py",
                    "compare_graphs.py",
                    "merge_graphs.py",
                    "craft_narrative_view.py",
                    "generate_reports.py",
                ):
                    cmd = [python_exe, str(root / name), pid] + (
                        extra if name == "generate_reports.py" else []
                    )
                    print(f"  {' '.join(cmd)}", flush=True)
            else:
                run_pipeline_for_pid(
                    pid,
                    data_dir=data_dir,
                    prompt_set=args.prompt_set,
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
