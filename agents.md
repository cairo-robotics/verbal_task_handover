# Project: LLM support for task handover
Code for a research paper on LLM's ability to improve task handover performance on human-to-human handoffs.

## Goals & overview

1. This paper asks: 
RQ1: Can LLM-assisted systems reduce information loss at task handover compared to unaided human reporting?
RQ2: Does task-aware filtering in report generation improve the efficiency of information transfer relative to exhaustive reporting?

2. Using data:
    * Handover reports written by both humans and LLMs for equivalent task states in  a simulated hospital floor task
    * Annotations of these reports to convert them to a consistent format [WIP]
    * An estimated minimum completion time (for the next participant/agent) given the data included in these reports [to-do]

## Tech stack

- Language/runtime: Python 3.11+ (IMPORTANT: use this repo's venv: `verbal_task_handover/venv/bin/python3`)
- Key libraries: OpenAI API, Pydantic

- `src/core/` - Fundamental data models and low-level logic.
    - `representations/`
        - `pydantic_schema.py`: Core Knowledge Graph models.
    - `transforms/`
        - `telemetry_to_graph.py`: Game telemetry -> KG.
        - `report_to_dsl.py`: Report text -> intermediate DSL via LLM.
        - `dsl_to_graph.py`: Parser for intermediate DSL -> KG.
    - `utils/`
        - `extraction_paths.py`: Path helpers for evaluation.
        - `spatial_reasoning.py`: Helpers for spatial constraints and relative locations.

- `src/experiments/` - Scripts for running the full pipeline or specific variants.
    - `run_full_pipeline_for_pids.py`: Orchestrates the entire model alignment process.
    - `run_evaluation_pipeline.py`: Orchestrates the full evaluation (extraction + IAC metrics).
    - `generate_reports_raw_ablation.py`: Bypasses graph pipeline for raw LLM comparison.

- `src/pipelines/` - Multi-stage workflows for report generation and evaluation.
    - `model_alignment/`
        - `reconcile_state.py`: Corrects KG state based on event logs.
        - `entity_alignment.py`: Normalizes entities and resolves existentials via LLM.
        - `fact_alignment.py`: Matches facts and identifies conflicts.
        - `merge_graphs.py`: Consolidates alignment and merging.
        - `craft_narrative_view.py`: Preparing KG for report generation (NarrativeView).
        - `generate_reports.py`: Final report generation using OpenAI API.
    - `evaluation/`
        - `calculate_iac.py`: Computes Information Access Cost (IAC) based on game state and map graph.
        - `precision_recall.py`: Compares extracted facts against ground truth.
        - `map_graph.py`: Map graph representation for navigation costs.

- `visualisation/` - Visualization tools for graphs and metrics.
    - `vizkg.py`: CLI visualizer for Knowledge Graphs (with conflict highlighting).
    - `viziac.py`: CLI visualizer for IAC results.
    - `dash_graph_vis.py`: Interactive Dash-based graph visualization.

## Current focus / Active work

Developing and refining the automated evaluation pipeline:
- **IAC Calculation**: Improving the accuracy of cost assessments for different entity types (patients, potions, NPCs).
- **Visualization**: Enhancing `vizkg.py` and `viziac.py` to provide actionable insights into report quality and pipeline performance.
- **Large-scale Evaluation**: Running the full pipeline and evaluation across all participant IDs to generate final metrics for the paper.

## Known constraints / don'ts
- Don't worry about anything in `unused/` -- that's just in case we need to recover anything from older versions of the project
