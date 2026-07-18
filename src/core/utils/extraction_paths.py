"""
Shared path and filename contract for two-stage report → DSL → FactExtraction.

Naming (under ``DATA_DIR``):
  - Report input: ``reports/<any/relative/path>.txt``
  - Stage 1 output: ``processed_output/dsl/<report_stem>_dsl.txt``
  - Stage 2 output: ``processed_output/kg/<report_stem>_dsl_to_kg.json``

``<report_stem>`` is ``Path(relative_report_path).stem`` after stripping an optional
``reports/`` prefix from CLI arguments.
"""

from __future__ import annotations

import os
from pathlib import Path


def format_model_name(model_name: str, provider: str = None) -> str:
    """Format model name into a standard suffix like gpt5-6-terra or gpt4-1-mini."""
    if not model_name:
        return provider or "gpt"
    model_name = model_name.lower().strip()
    
    # Determine provider if not explicitly given
    if not provider:
        if model_name.startswith("gpt"):
            provider = "gpt"
        elif model_name.startswith("claude"):
            provider = "claude"
        elif model_name.startswith("gemini"):
            provider = "gemini"
        else:
            provider = "gpt"  # default fallback
            
    # Strip provider prefixes
    for prefix in ["gpt-", "gpt", "claude-", "claude", "gemini-", "gemini"]:
        if model_name.startswith(prefix):
            model_name = model_name[len(prefix):]
            break
            
    # Remove any leading hyphens/dots
    model_name = model_name.lstrip("-.")
    
    # Convert dot to hyphen
    model_name = model_name.replace(".", "-")
    
    return f"{provider}{model_name}"


def get_current_model_suffix(provider: str = "gpt") -> str:
    """Get the formatted model suffix based on active environment settings."""
    model_name = os.environ.get("GPT_MODEL") or os.environ.get("MODEL")
    if not model_name:
        if provider == "gpt":
            model_name = "gpt-4.1-mini"
        elif provider == "claude":
            model_name = "claude-3-5-sonnet-20241022"
        elif provider == "gemini":
            model_name = "gemini-1.5-pro"
    return format_model_name(model_name, provider)


def normalize_report_arg(name: str) -> str:
    """Strip optional leading ``reports/`` so args can be ``foo.txt`` or ``reports/foo.txt``."""
    raw = name.strip().replace("\\", "/")
    prefix = "reports/"
    if raw.startswith(prefix):
        return raw[len(prefix) :]
    return raw


def reports_file(data_dir: str, filename: str) -> Path:
    """Resolve ``DATA_DIR/reports/<filename>`` and reject path traversal."""
    base = (Path(data_dir) / "reports").resolve()
    candidate = (base / filename).resolve()
    try:
        candidate.relative_to(base)
    except ValueError as exc:
        raise ValueError(f"Report path must stay under {base}") from exc
    return candidate


def analysis_file(data_dir: str, filename: str) -> Path:
    """Resolve ``DATA_DIR/processed_output/dsl/<filename>`` and reject path traversal."""
    if os.environ.get("USE_EVALUATION_DIRS") == "1":
        base = (Path(data_dir) / "analysis" / "dsl").resolve()
    else:
        base = (Path(data_dir) / "processed_output" / "dsl").resolve()
    candidate = (base / filename).resolve()
    try:
        candidate.relative_to(base)
    except ValueError as exc:
        raise ValueError(f"DSL path must stay under {base}") from exc
    return candidate


def dsl_output_path_for_report_arg(data_dir: str, report_arg: str, model: str = None) -> Path:
    """Stage 1 artifact: ``processed_output/dsl/<stem>_dsl.txt`` matching stage 2 resolution."""
    rel = normalize_report_arg(report_arg)
    stem = Path(rel).stem
    if model:
        formatted = format_model_name(model)
        return analysis_file(data_dir, f"{stem}_dsl_{formatted}.txt")
    return analysis_file(data_dir, f"{stem}_dsl.txt")


def fact_extraction_json_path_for_dsl_path(dsl_path: Path) -> Path:
    """Stage 2 JSON in kg/ folder; strip ``_dsl`` from the stem when present."""
    stem = dsl_path.stem
    if "_dsl_" in stem:
        stem = stem.replace("_dsl_", "_dsl_to_kg_")
    elif stem.endswith("_dsl"):
        stem = stem[:-4] + "_dsl_to_kg"
    else:
        stem = f"{stem}_dsl_to_kg"
    
    # Go up from processed_output/dsl to processed_output, then into kg/
    return dsl_path.parent.parent / "kg" / f"{stem}.json"


def resolve_dsl_input_path(data_dir: str, dsl_or_report: str) -> Path:
    """
    Resolve the stage-1 DSL text file used as stage-2 input.

    - ``analysis/<name>`` — explicit path under analysis (leading ``analysis/`` optional for
      disambiguation when chaining).
    - ``reports/<name>`` — resolve to ``analysis/<stem>_dsl_output.txt`` for that report.
    - Otherwise: if ``analysis/<name>`` exists, use it; else if ``reports/<name>`` exists,
      use ``analysis/<stem>_dsl_output.txt``.
    """
    raw = dsl_or_report.strip().replace("\\", "/")

    if raw.startswith("analysis/"):
        rel = raw[len("analysis/") :]
        try:
            p = analysis_file(data_dir, rel)
        except ValueError as exc:
            raise ValueError(str(exc)) from exc
        if not p.is_file():
            raise FileNotFoundError(f"DSL file not found: {p}")
        return p

    if raw.startswith("reports/"):
        rel = normalize_report_arg(raw)
        stem = Path(rel).stem
        model_suffix = get_current_model_suffix()
        candidates = [
            f"{stem}_dsl_{model_suffix}.txt",
            f"{stem}_dsl.txt",
            f"{stem}_gpt_dsl.txt",
            f"{stem}_{model_suffix}_dsl.txt"
        ]
        p = None
        for cand in candidates:
            try:
                candidate_path = analysis_file(data_dir, cand)
                if candidate_path.is_file():
                    p = candidate_path
                    break
            except ValueError:
                continue
        if p is None:
            p = analysis_file(data_dir, f"{stem}_dsl_{model_suffix}.txt")
            raise FileNotFoundError(
                f"No DSL artifact at {p}; run stage 1 for report {rel!r} first."
            )
        return p

    try:
        analysis_candidate = analysis_file(data_dir, raw)
    except ValueError as exc:
        raise ValueError(str(exc)) from exc
    if analysis_candidate.is_file():
        return analysis_candidate

    report_rel = normalize_report_arg(raw)
    try:
        report_candidate = reports_file(data_dir, report_rel)
    except ValueError:
        report_candidate = None

    if report_candidate is not None and report_candidate.is_file():
        stem = Path(report_rel).stem
        model_suffix = get_current_model_suffix()
        candidates = [
            f"{stem}_dsl_{model_suffix}.txt",
            f"{stem}_dsl.txt",
            f"{stem}_gpt_dsl.txt",
            f"{stem}_{model_suffix}_dsl.txt"
        ]
        p = None
        for cand in candidates:
            try:
                candidate_path = analysis_file(data_dir, cand)
                if candidate_path.is_file():
                    p = candidate_path
                    break
            except ValueError:
                continue
        if p is None:
            p = analysis_file(data_dir, f"{stem}_dsl_{model_suffix}.txt")
            raise FileNotFoundError(
                f"No DSL artifact at {p}; run stage 1 for report {report_rel!r} first."
            )
        return p

    raise FileNotFoundError(
        f"No DSL input found for {dsl_or_report!r}: "
        f"neither {analysis_candidate} nor reports/{report_rel!r} (or missing stage-1 output)."
    )
