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

- Language/runtime: Python 3.11+ (use this repo's venv: `./venv/bin/python3`)
- Key libraries: OpenAI API, Pydantic

## Architecture Overview
- `evaluation/` - code/packages used for user study data collection, including the video game task (`treasure_hunt_py`)
- `src/model_alignment` - code for the study-data-to-final-report LLM pipeline, which consists of:
    1a. `telemetry_to_graph.py`: Converting telemetry data to a "ground truth" Pydantic representation.
    1b. `text_to_graph.py`: Converting user notes into the same Pydantic representation.
    2. `compare_graphs.py`: Comparing the knowledge graphs from 1a and 1b to find differences and contradictions
    3. `merge_graphs.py`: Using the diff produced in step 2 to produce a merged graph.
    4. `reconcile_state.py`: Replaying event-driven state effects (OBTAIN/DELIVER/GIVE) on the merged graph to ensure inventory state is consistent with the event log.
    5. `craft_narrative_view.py`: Converting the merged graph into a structured NarrativeView (player state, per-room layout, conflicts) used as input for report generation.
    6. `generate_reports.py`: Generating a final report from the NarrativeView using the OpenAI API (`full_realization` or `task_aware` prompt sets, or both).
    - `generate_reports_raw_ablation.py`: Ablation variant — bypasses the graph/NarrativeView pipeline and sends raw telemetry + user report directly to the model.
    
- `src/extraction_metrics` - code to evaluate the report pipeline -- WIP
    1. `report_to_dsl.py`: Report → line-based DSL facts via LLM (e.g. `emily needs red potion`). A human annotator also runs this step for ~20% of reports to verify inter-rater reliability via Cohen's Kappa. Output is a text file.
    2. `dsl_to_fact_extraction.py`: DSL text → structured `FactExtraction` JSON via LLM. Output is a JSON file.
    3. `fact_extraction.py`: Single-stage alternative — extracts `FactExtraction` JSON directly from a report (no DSL intermediate step).
    4. `narrative_view_to_fact_extraction.py`: Deterministically converts a NarrativeView JSON to `FactExtraction` JSON, used to produce the ground truth fact set.
    5. `precision_recall.py`: Computes precision, recall, F1, and error breakdown by comparing two `FactExtraction` JSON files.


## Current focus / Active work
1. Moving to metrics -- creating an evaluation pipeline to compare report creation methods

## Known constraints / don'ts
- Don't worry about anything in `unused/` -- that's just in case we need to recover anything from older versions of the project
