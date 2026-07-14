# LLM Support for Verbal Task Handover

Code for a research project studying whether LLMs can improve *verbal task handover* performance in human-to-human handoffs.

## Goals

This project asks:

- **RQ1:** Can LLM-assisted systems reduce information loss at task handover compared to unaided human reporting?
- **RQ2:** Does task-aware filtering in report generation improve the efficiency of information transfer relative to exhaustive reporting?

To support this, we use:

- Handover reports written by humans and by LLMs for equivalent simulated task states (in a pygame-based multi-room task environment).
- Annotations of these reports to convert them to a consistent structured format (via the extraction metrics pipeline).
- A pipeline that converts (a) telemetry from the simulated task and (b) user-written reports into a shared structured representation ("knowledge graph").
- Diffing/merging logic to identify what the report adds, contradicts, or misses, and to produce an LLM-friendly "narrative view" for final report generation.

## Repository Layout

- `evaluation/` : code used to run the user study and the simulated task.
  - `evaluation/treasure_hunt_py/` : the pygame-based task + telemetry.
  - `evaluation/user_study/` : GUIs/scripts used during participant sessions (chat/report capture).
- `src/core/` : fundamental data models (Pydantic schemas) and transformation logic (telemetry/report to graph).
- `src/experiments/` : high-level scripts for running the full task-handover pipeline and ablation studies.
- `src/pipelines/` : multi-stage workflows for report generation (model alignment) and evaluation (metrics).
- `analysis/` : post-experiment statistics, metrics aggregation, notebooks, and agreement scripts.
- `visualisation/` : tools for visualizing knowledge graphs and evaluation metrics (IAC).
- `scripts/` : helper scripts for working with participant telemetry/report files.

## Tech Stack (dev/run-time)

- Python: Python 3.11+ (see `requirements.txt`)
- Key dependencies: OpenAI API (`openai`), Pydantic (`pydantic`), pandas, scipy, scikit-learn
- Pygame task environment: `pygame`

## Evaluation Task: `evaluation/treasure_hunt_py/`

The evaluation task uses a pygame-based simulated multi-room "treasure hunt / hospital-floor" environment (`treasure_hunt`).

For details on the task, its architecture, and instructions on how to install and run the game, see the package [README](evaluation/treasure_hunt_py/README.md).

---

## Report generation pipeline: `src/pipelines/model_alignment/`

The `src/pipelines/model_alignment/` pipeline (supported by `src/core/transforms/`) converts:

- telemetry logs from the game (`evaluation/treasure_hunt_py`)
- and user-written handover reports

into a shared knowledge graph representation, then computes diffs/conflicts and prepares a "narrative view" for report generation.

### Shared schema: `src/core/representations/pydantic_schema.py`

Defines the Pydantic models and enums used throughout the pipeline:

- `KnowledgeGraph` : `{ facts: List[Fact], conflicts: List[Conflict] }`
- `NarrativeView` (defined in `src/pipelines/model_alignment/craft_narrative_view.py`) : `{ player_state, world_state (rooms + items + present character views), unresolved_conflicts, unanchored_facts }`

### Pipeline steps

The scripts assume a `DATA_DIR` environment variable and a directory layout like:

- `$DATA_DIR/telemetry/<id>.txt` (input telemetry log)
- `$DATA_DIR/reports/<id>_user_report.txt` (input user-written report)
- `$DATA_DIR/processed_output/dsl/` (intermediate DSL output)
- `$DATA_DIR/processed_output/kg/` (output Knowledge Graph JSON files)

Key scripts:

1. `src/core/transforms/telemetry_to_graph.py`
  - Deterministic conversion from telemetry text to `KnowledgeGraph`.
  - Current parsing focuses on patterns like:
    - `room entered: <direction> to <location>`
    - `item obtained: <item>`
    - `npc interact: <npc>` and `npc interact: <npc> about <topic>`
    - `gave item to npc: <item> <npc>`
  - Output: `processed_output/kg/<id>_telemetry_to_kg.json`
2. `src/core/transforms/report_to_dsl.py` & `src/core/transforms/dsl_to_graph.py`
  - `report_to_dsl.py` uses the OpenAI API (`gpt-4o-mini`) to convert a user report text file to an intermediate DSL.
  - `dsl_to_graph.py` parses the DSL into the `KnowledgeGraph` schema.
  - Output: `processed_output/dsl/<id>_user_report_dsl.txt` and `processed_output/kg/<id>_dsl_to_kg.json`
3. `src/pipelines/model_alignment/merge_graphs.py`
  - Aligns graphs and merges them into a single representation.
  - Internally uses `entity_alignment.py` (LLM-based entity matching) and `fact_alignment.py` (matching events/relations).
  - Identifies:
    - Novel facts (added to the merged graph).
    - Conflicting facts (preserved in `Conflict` records).
  - Output: `processed_output/kg/<id>_merged_kg.json`
4. `src/pipelines/model_alignment/reconcile_state.py`
  - Replays event-driven state effects (e.g. delivered potions/messages) on the merged graph, ensuring inventory/needs state is consistent with the event log.
  - Output: `processed_output/kg/<id>_reconciled_kg.json`
5. `src/pipelines/model_alignment/craft_narrative_view.py`
  - Converts the reconciled knowledge graph into `NarrativeView` (player inventory/location + per-room layout including characters, items, requirements, and conflict summaries).
  - Output: `processed_output/kg/<id>_narrative_view.json`
6. `src/pipelines/model_alignment/generate_reports.py`
  - Loads `<id>_narrative_view.json` and calls the OpenAI Chat Completions API (`gpt-4o-mini`, temperature 0) to produce final handover report text.
  - **Prompts:** Two built-in system/user prompt pairs are defined:
    - `full_realization` — structured, exhaustive coverage of the narrative state.
    - `task_aware` — emphasizes patient needs, message delivery, and task-relevant inventory/location.
  - **`--prompt-set`:** Choose `full_realization`, `task_aware`, or `both`. With `both`, the model is called twice (full realization first, then task-aware); the two replies are output to separate files.

### Ablation: `src/experiments/generate_reports_raw_ablation.py`

An ablation variant of `generate_reports.py` that bypasses the NarrativeView/graph pipeline entirely. It sends the raw telemetry log and the participant-written report directly to `gpt-4o-mini` and uses equivalent `full_realization` and `task_aware` prompt pairs. Useful for comparing LLM report quality with and without the structured pipeline.

- **Input:** `DATA_DIR/telemetry/<id>.txt` and `DATA_DIR/reports/<id>_user_report.txt` (overridable via `--telemetry` / `--user-report`).
- **Output:** `DATA_DIR/reports/<id>_{full_realization,task_aware}_raw_ablation_report.txt`
- **`--prompt-set`:** `full_realization`, `task_aware`, or `both` (default: `full_realization`).

### Example end-to-end run (participant `501`)

Assuming:

- Telemetry file: `$DATA_DIR/telemetry/501.txt`
- User report file: `$DATA_DIR/reports/501_user_report.txt`

Run:

```bash
export DATA_DIR=/path/to/DATA_DIR

# 1. Telemetry parsing
python src/core/transforms/telemetry_to_graph.py 501

# 2. Report translation to DSL
python src/core/transforms/report_to_dsl.py 501_user_report.txt

# 3. Parse report DSL to KG (explicit output path for alignment merging)
python src/core/transforms/dsl_to_graph.py processed_output/dsl/501_user_report_dsl.txt --output processed_output/kg/501_dsl_to_kg.json

# 4. Merge telemetry and report graphs
python src/pipelines/model_alignment/merge_graphs.py 501

# 5. Temporal state reconciliation
python src/pipelines/model_alignment/reconcile_state.py 501

# 6. Craft NarrativeView format
python src/pipelines/model_alignment/craft_narrative_view.py 501

# 7. Generate reports
python src/pipelines/model_alignment/generate_reports.py 501 --prompt-set both
```

Run the full pipeline for one or more participant IDs using:

```bash
python src/experiments/run_full_pipeline_for_pids.py {PID1 PID2...}
```

Useful options:

- `--pids-file <FILE>`: text file with one pid per line (`#` comments and blank lines ignored); combined with positional pids.
- `--data-dir <DIR>`: override the `DATA_DIR` environment variable for this run.
- `--prompt-set`: forwarded to `generate_reports.py`; choices are `full_realization`, `task_aware`, or `both` (default: `both`).
- `--use-human-dsl`: runs pipeline using human-annotated gold DSL from `$DATA_DIR/annotations/dsl/kb_annotated_<pid>_user_report.txt` instead of calling `report_to_dsl.py`.
- `--no-user-report`: ablation variant that reconciles and generates reports directly from telemetry.

### Configuration

Environment variables used by the pipeline:

- `OPENAI_API_KEY` : required for `src/core/transforms/report_to_dsl.py`, `src/pipelines/model_alignment/merge_graphs.py` (for entity alignment), and `src/pipelines/model_alignment/generate_reports.py`
- `DATA_DIR` : base directory for inputs/outputs as described above

---

## Evaluation pipeline: `src/pipelines/evaluation/`

The `src/pipelines/evaluation/` pipeline evaluates report quality using several metrics:

1. **Extraction Accuracy**: Extracting structured facts from reports and comparing them against a ground truth.
2. **Information Access Cost (IAC)**: Quantifying the "cost" (search time) for a subsequent agent to find required entities based on the information provided in the report.

### Data layout

Scripts read and write under `DATA_DIR`:

- `$DATA_DIR/reports/<report>.txt` — input report files
- `$DATA_DIR/processed_output/kg/<id>_narrative_view.json` — NarrativeView input for ground truth
- `$DATA_DIR/processed_output/dsl/<stem>_dsl.txt` — stage 1 DSL output
- `$DATA_DIR/processed_output/kg/<stem>_dsl_to_kg.json` — stage 2 / direct fact extraction output
- `$DATA_DIR/analysis/metrics_output/precision_recall/<stem>_pr.json` — PR calculation results
- `$DATA_DIR/analysis/metrics_output/iac/<stem>_iac.json` — IAC calculation results

### Key evaluation scripts

1. `src/pipelines/evaluation/precision_recall.py`
  - Computes precision, recall, F1, and an error breakdown (false positives / false negatives) by comparing two `KnowledgeGraph` JSON files.
  - Usage: `python src/pipelines/evaluation/precision_recall.py <pred.json> <gt.json>`
2. `src/pipelines/evaluation/calculate_iac.py`
  - Calculates Information Access Cost (IAC) for a report.
  - It assesses three components per patient: `location_score` (cost to find the patient), `need_score` (identifying the need), and `resource_score` (cost to find the required potion/NPC).
  - Uses `costs.py` for config/patient metadata, `search_costs.py` to model expected search traversals, and `map_graph.py` for room connections/distances.
  - Usage: `python src/pipelines/evaluation/calculate_iac.py --kg-file <pred_kg.json> --pid <pid> --map-graph <map_graph.json> --output-file <output.json>`
3. `src/experiments/run_evaluation_pipeline.py`
  - Orchestrates the full evaluation for a list of PIDs, running extraction and metric calculations across report conditions (`user_report`, `task_aware`, `no_user_report`, or `raw_ablation`).

---

## Post-Experiment Analysis & Notebooks: `analysis/`

The `analysis/` directory contains tools to run full-scale experimental runs, aggregate metrics, evaluate agreement, and run statistical tests:

1. `analysis/run_full_experiment.py`
  - Runs the pipeline (`run_full_pipeline_for_pids.py`) and evaluation (`run_evaluation_pipeline.py`) across all participant IDs (501 to 513) for both standard and no-report conditions, aggregates all metrics, and runs Wilcoxon signed-rank significance tests.
  - Usage: `python analysis/run_full_experiment.py`
2. `analysis/run_fast_experiment.py`
  - Fast variant of the full experiment assuming intermediate pipeline files are already generated.
3. `analysis/aggregate_metrics.py`
  - Aggregates IAC and Precision-Recall outputs into a master CSV (`aggregated_metrics.csv`) and computes report token counts.
4. `analysis/calculate_dsl_agreement.py`
  - Calculates Cohen's Kappa agreement metrics and slot-filling accuracy between human annotations and model-generated extraction DSL.
  - Usage: `python analysis/calculate_dsl_agreement.py`
5. `analysis/statistical_analysis.ipynb`
  - Jupyter notebook performing statistical reporting (mean, median, range, std dev), Wilcoxon signed-rank test statistics, rank-biserial correlations, and producing paper figures.

---

## Visualization: `visualisation/`

We provide several tools to visualize the output of our pipeline:

- `visualisation/vizkg.py`: A terminal-based visualizer for Knowledge Graph JSON files. Supports side-by-side comparison of two graphs.
  - Usage: `python visualisation/vizkg.py <file1.json> [<file2.json>]`
- `visualisation/viziac.py`: A terminal-based visualizer for IAC result JSON files, providing a clear breakdown of scores and costs.
  - Usage: `python visualisation/viziac.py <iac_result.json>`
- `visualisation/dash_graph_vis.py`: An interactive, web-based visualization tool using Dash and Plotly for exploring complex knowledge graphs.
