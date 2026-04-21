"""
Shared path and filename contract for two-stage report → DSL → FactExtraction.

Naming (under ``DATA_DIR``):
  - Report input: ``reports/<any/relative/path>.txt``
  - Stage 1 output: ``analysis/<report_stem>_dsl_output.txt``
  - Stage 2 output: ``analysis/<report_stem>_fact_extraction_output.json``

``<report_stem>`` is ``Path(relative_report_path).stem`` after stripping an optional
``reports/`` prefix from CLI arguments.
"""

from __future__ import annotations

from pathlib import Path


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
    """Resolve ``DATA_DIR/analysis/<filename>`` and reject path traversal."""
    base = (Path(data_dir) / "analysis").resolve()
    candidate = (base / filename).resolve()
    try:
        candidate.relative_to(base)
    except ValueError as exc:
        raise ValueError(f"Analysis path must stay under {base}") from exc
    return candidate


def dsl_output_path_for_report_arg(data_dir: str, report_arg: str) -> Path:
    """Stage 1 artifact: ``analysis/<stem>_dsl_output.txt`` matching stage 2 resolution."""
    rel = normalize_report_arg(report_arg)
    stem = Path(rel).stem
    return analysis_file(data_dir, f"{stem}_dsl_output.txt")


def fact_extraction_json_path_for_dsl_path(dsl_path: Path) -> Path:
    """Stage 2 JSON next to the DSL file; strip ``_dsl_output`` from the stem when present."""
    stem = dsl_path.stem
    suffix = "_dsl_output"
    if stem.endswith(suffix):
        stem = stem[: -len(suffix)]
    return dsl_path.parent / f"{stem}_fact_extraction_output.json"


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
        try:
            p = analysis_file(data_dir, f"{stem}_dsl_output.txt")
        except ValueError as exc:
            raise ValueError(str(exc)) from exc
        if not p.is_file():
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
        try:
            p = analysis_file(data_dir, f"{stem}_dsl_output.txt")
        except ValueError as exc:
            raise ValueError(str(exc)) from exc
        if not p.is_file():
            raise FileNotFoundError(
                f"No DSL artifact at {p}; run stage 1 for report {report_rel!r} first."
            )
        return p

    raise FileNotFoundError(
        f"No DSL input found for {dsl_or_report!r}: "
        f"neither {analysis_candidate} nor reports/{report_rel!r} (or missing stage-1 output)."
    )
