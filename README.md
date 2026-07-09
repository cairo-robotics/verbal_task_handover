# LLM Support for Verbal Task Handover

Code for a research project studying whether LLMs can improve *verbal task handover* performance in human-to-human handoffs.

## Goals

This project asks:

- **RQ1:** Can LLM-assisted systems reduce information loss at task handover compared to unaided human reporting?
- **RQ2:** Does task-aware filtering in report generation improve the efficiency of information transfer relative to exhaustive reporting?

To support this, we use:

- Handover reports written by humans and by LLMs for equivalent simulated task states (in a game environment that is loosely based on a hospital floor task).
- Annotations of these reports to convert them to a consistent structured format (via the extraction metrics pipeline — WIP).
- A pipeline that converts (a) telemetry from the simulated task and (b) user-written reports into a shared structured representation ("knowledge graph").
- Diffing/merging logic to identify what the report adds, contradicts, or misses, and to produce an LLM-friendly "narrative view" for final report generation.

## Repository Layout

- `evaluation/` : code used to run the user study and the simulated task.
  - `evaluation/treasure_hunt_py/` : the pygame-based task + telemetry.
  - `evaluation/user_study/` : GUIs/scripts used during participant sessions (chat/report capture).
- `src/core/` : fundamental data models (Pydantic schemas) and transformation logic (telemetry/report to graph).
- `src/experiments/` : high-level scripts for running the full task-handover pipeline and ablation studies.
- `src/pipelines/` : multi-stage workflows for report generation (model alignment) and evaluation (metrics).
- `visualisation/` : tools for visualizing knowledge graphs and evaluation metrics (IAC).
- `scripts/` : helper scripts for working with participant telemetry/report files.

## Tech Stack (dev/run-time)

- Python: Python 3.11+ (see `requirements.txt`)
- Key dependencies: OpenAI API (`openai`), Pydantic (`pydantic`)
- Pygame task environment: `pygame`

## Evaluation: `evaluation/treasure_hunt_py/`

`evaluation/treasure_hunt_py` contains a self-contained python package (`treasure_hunt`) implementing the simulated multi-room "treasure hunt / hospital-floor" task.

### What the game does

Participants navigate a grid-based floor, interact with NPCs, collect items (e.g., "potions", "keys", "gems"), unlock/pass through doors, and may encounter small in-game "modules" (minigames / dialogue / input panels).

The game logs participant actions as *telemetry events* to a text file, which is later consumed by `src/core/transforms/telemetry_to_graph.py`.

### Key components

Inside `evaluation/treasure_hunt_py/treasure_hunt/`:

- `src/core.py`
  - `GameMap`: loads room layout (`*.txt`), texture maps (optional), and room transition rules (`transitions.json`).
  - Movement/transition checks: `is_valid_move(...)`, `check_transition(...)`.
- `src/game_mdp.py`
  - `GameState`: current state of the game (player, objects/NPCs, room name, score, on-screen text queue, module state).
  - `Player`: position + direction + held item + flags (used for conditional dialogues).
  - `NPC`: NPC interaction logic (dialogue flows, conditional interactions, held-item interactions).
  - `start_state(...)` / `update_start_state(...)`: initializes and updates room objects from `objects.json` files.
- `src/modules.py`
  - Defines interactive "modules" used in the task (for example wire/password modules and dialogue-like interactive UI).
  - These modules are rendered in `visualization/` and updated through `GameState`.
- `src/telemetry.py`
  - `Telemetry.log_event(event_type, details)`: appends lines in the format:
    - `<timestamp> - <event_type>: <details>`

### Task data (maps, assets, saves)

The task uses package data files under:

- `maps/`
  - `room*.txt` : grid layouts for rooms.
  - `objects.json` : objects/NPC definitions per map.
  - `transitions.json` : how to move between rooms via door/transition tiles.
  - `texture_maps/` : optional texture configuration per room.
- `assets/`
  - sprite/graphics configuration loaded by the renderer.
- `saves/`
  - serialized game saves (used for resuming rounds).

### Running the game (main telemetry task)

1. Install the package:
  ```bash
   pip install -e evaluation/treasure_hunt_py
  ```
2. Set `SAVE_DIR` (where saves + telemetry logs will be written):
  ```bash
   export SAVE_DIR=/path/to/where/to/write/saves
  ```
3. Run from the repo root:
  ```bash
   python -m treasure_hunt.scripts.main --save 302
  ```

Useful options (as defined in `evaluation/treasure_hunt_py/treasure_hunt/scripts/main.py`):

- `--save <name>`: base filename for the `.pkl` save and corresponding telemetry text file.
- `--load <name>`: resume from an existing save.
- `--is_player2`: switch player identity / initialize player2-specific NPC interactions.
- `--use-distractor`: runs an optional distractor task while the main task is paused.
- `--timeout <minutes>`: ends the task after the given time.

Telemetry output is written under:

- `"$SAVE_DIR/telemetry/<save_name>.txt"`

### Optional distractor task

`--use-distractor` starts `scripts/distractor.py`, which uses Selenium + Firefox to play a memory-match game on the web.

This requires a working local Selenium environment (Firefox + `geckodriver` path in the script).

### Tutorial script

`evaluation/treasure_hunt_py/treasure_hunt/scripts/tutorial.py` runs a simplified tutorial map (`maps/tutorial_v2/`) and can log telemetry when `--telemetry` is enabled.

## Report generation pipeline: `src/pipelines/model_alignment/`

The `src/pipelines/model_alignment/` pipeline (supported by `src/core/transforms/`) converts:

- telemetry logs from the game (`evaluation/treasure_hunt_py`)
- and user-written handover reports

into a shared `KnowledgeGraphExtraction` representation, then computes diffs/conflicts and prepares a "narrative view" for report generation.

### Shared schema: `src/core/representations/pydantic_schema.py`

Defines the Pydantic models and enums used throughout the pipeline:

- `KnowledgeGraphExtraction` : `{ entities, events, state_relations, spatial_relations, conflicts }`
- `NarrativeView` : `{ player_state, world_state (rooms + implicit locations + unplaced agents), unresolved_conflicts }`

### Pipeline steps

The scripts assume a `DATA_DIR` environment variable and a directory layout like:

- `$DATA_DIR/telemetry/<id>.txt`
- `$DATA_DIR/reports/<id>.txt`
- `$DATA_DIR/processed_output/` (output JSON files)

Key scripts:

1. `src/core/transforms/telemetry_to_graph.py`
  - Deterministic conversion from telemetry text to `KnowledgeGraphExtraction`.
  - Current parsing focuses on patterns like:
    - `room entered: <direction> to <location>`
    - `item obtained: <item>`
    - `npc interact: <npc>` and `npc interact: <npc> about <topic>`
    - `gave item to npc: <item> <npc>`
  - Output: `<id>_telemetry_to_kg_output.json`
2. `src/core/transforms/report_to_dsl.py` & `src/core/transforms/dsl_to_graph.py`
  - Replaces old `text_to_graph.py`.
  - `report_to_dsl.py` uses the OpenAI API to convert a user report text file to an intermediate DSL.
  - `dsl_to_graph.py` parses the DSL into the `KnowledgeGraphExtraction` schema.
  - Output: `<id>_dsl_to_kg_output.json`
3. `src/pipelines/model_alignment/merge_graphs.py`
  - Aligns graphs and merges them into a single representation.
  - Internally uses `entity_alignment.py` (LLM-based entity matching) and `fact_alignment.py` (matching events/relations).
  - Identifies:
    - Novel facts (added to the merged graph).
    - Conflicting facts (preserved in `Conflict` records).
  - Output: `<id>_merge_graphs_output.json`
4. `src/pipelines/model_alignment/reconcile_state.py`
  - Replays event-driven state effects (e.g. OBTAIN/DELIVER/GIVE events) on `state_relations` of the merged graph, ensuring inventory state is consistent with the event log.
  - Output: `<id>_reconcile_state_output.json`
5. `src/pipelines/model_alignment/craft_narrative_view.py`
  - Converts the merged knowledge graph into `NarrativeView` (player inventory + per-room layout including room-level `requires`, items with requirements, non-item entities in rooms, implicit rooms from `located_in`, agents without placement, a per-entity state-relation index, full spatial relation copy, and conflict summaries).
  - Each room and each character present in a room also lists `miscellaneous_state_relations`: human-readable state edges involving that id that are not already represented by who is in the room, that character's `requirements`, or the player's inventory.
  - Output: `<id>_narrative_view_output.json`
6. `src/pipelines/model_alignment/generate_reports.py`
  - Loads `<id>_narrative_view_output.json` (or any path to a `NarrativeView` JSON file) and calls the OpenAI Chat Completions API (`gpt-4o-mini`, temperature 0) to produce handover report text.
  - **Input:** With `DATA_DIR` set, the positional argument is a base id (e.g. `302`); the script reads `$DATA_DIR/processed_output/<id>_narrative_view_output.json`. Without `DATA_DIR`, the argument must be the full path to a narrative-view JSON file.
  - **Prompts:** Two built-in system/user prompt pairs are defined in the script:
    - `full_realization` — structured, exhaustive coverage of the narrative state.
    - `task_aware` — emphasizes patient needs, message delivery, and task-relevant inventory/location.
  - **`--prompt-set`:** Choose `full_realization`, `task_aware`, or `both`. With `both`, the model is called twice (full realization first, then task-aware); the two replies are output to separate files.

### Ablation: `src/experiments/generate_reports_raw_ablation.py`

An ablation variant of `generate_reports.py` that bypasses the NarrativeView/graph pipeline entirely. It sends the raw telemetry log and the participant-written report directly to `gpt-4o-mini` and uses equivalent `full_realization` and `task_aware` prompt pairs. Useful for comparing LLM report quality with and without the structured pipeline.

- **Input:** `DATA_DIR/telemetry/<id>.txt` and `DATA_DIR/reports/<id>_user_report.txt` (overridable via `--telemetry` / `--user-report`).
- **Output:** `DATA_DIR/reports/<id>_{full_realization,task_aware}_raw_ablation_report.txt`
- **`--prompt-set`:** `full_realization`, `task_aware`, or `both` (default: `full_realization`).

### Example end-to-end run (participant `302`)

Assuming:

- Telemetry file: `$DATA_DIR/telemetry/302.txt`
- User report file: `$DATA_DIR/reports/302_user_report.txt`

Run:

```bash
export DATA_DIR=/path/to/DATA_DIR

python src/core/transforms/telemetry_to_graph.py 302
python src/core/transforms/report_to_dsl.py 302
python src/core/transforms/dsl_to_graph.py 302_user
python src/pipelines/model_alignment/merge_graphs.py 302
python src/pipelines/model_alignment/reconcile_state.py 302
python src/pipelines/model_alignment/craft_narrative_view.py 302
python src/pipelines/model_alignment/generate_reports.py 302
# Optional: task-focused report, or both prompt styles (two API calls)
python src/pipelines/model_alignment/generate_reports.py 302 --prompt-set task_aware
python src/pipelines/model_alignment/generate_reports.py 302 --prompt-set both
# Without DATA_DIR, pass the narrative view path explicitly:
# python src/pipelines/model_alignment/generate_reports.py /path/to/302_narrative_view_output.json
```

Run the full pipeline for one or more participant IDs using:

```bash
python src/experiments/run_full_pipeline_for_pids.py {PID1 PID2...}
```

Useful options:

- `--pids-file <FILE>`: text file with one pid per line (`#` comments and blank lines ignored); combined with positional pids.
- `--data-dir <DIR>`: override the `DATA_DIR` environment variable for this run.
- `--prompt-set`: forwarded to `generate_reports.py`; choices are `full_realization`, `task_aware`, or `both` (default: `both`).
- `--continue-on-error`: process remaining pids after a failure; exits non-zero if any pid failed.
- `--dry-run`: print steps only without executing subprocesses.

### Configuration

Environment variables used by the pipeline:

- `OPENAI_API_KEY` : required for `src/core/transforms/report_to_dsl.py`, `src/pipelines/model_alignment/merge_graphs.py` (for entity alignment), and `src/pipelines/model_alignment/generate_reports.py`
- `DATA_DIR` : base directory for inputs/outputs as described above

## Evaluation pipeline: `src/pipelines/evaluation/`

The `src/pipelines/evaluation/` pipeline evaluates report quality using several metrics:

1. **Extraction Accuracy**: Extracting structured facts from reports and comparing them against a ground truth.
2. **Information Access Cost (IAC)**: Quantifying the "cost" (search time) for a subsequent agent to find required entities based on the information provided in the report.

### Data layout

Scripts read and write under `DATA_DIR`:

- `$DATA_DIR/reports/<report>.txt` — input report files
- `$DATA_DIR/processed_output/<id>_narrative_view_output.json` — NarrativeView input for ground truth
- `$DATA_DIR/analysis/<stem>_dsl_output.txt` — stage 1 DSL output
- `$DATA_DIR/analysis/<stem>_fact_extraction_output.json` — stage 2 / direct fact extraction output
- `$DATA_DIR/analysis/<stem>_nv_fact_extraction_output.json` — NarrativeView-derived ground truth facts
- `$DATA_DIR/analysis/<stem>_iac.json` — IAC calculation results

### Key evaluation scripts

1. `src/pipelines/evaluation/precision_recall.py`
  - Computes precision, recall, F1, and an error breakdown (false positives / false negatives) by comparing two `FactExtraction` JSON files.
  - Usage: `python src/pipelines/evaluation/precision_recall.py <pred.json> <gt.json>`
  - Output: `$DATA_DIR/analysis/<pred_stem>_pr.json`
2. `src/pipelines/evaluation/calculate_iac.py`
  - Calculates Information Access Cost (IAC) for a report.
  - It assesses three components per patient: `location_score` (cost to find the patient), `need_score` (identifying the need), and `resource_score` (cost to find the required potion/NPC).
  - Usage: `python src/pipelines/evaluation/calculate_iac.py --kg-file <pred_kg.json> --pid <pid> --map-graph <map_graph.json> --output-file <output.json>`
3. `src/experiments/run_evaluation_pipeline.py`
  - Orchestrates the full evaluation for a list of PIDs, running extraction and metric calculations.

## Visualization: `visualisation/`

We provide several tools to visualize the output of our pipeline:

- `visualisation/vizkg.py`: A terminal-based visualizer for Knowledge Graph JSON files. Supports side-by-side comparison of two graphs.
  - Usage: `python visualisation/vizkg.py <file1.json> [<file2.json>]`
- `visualisation/viziac.py`: A terminal-based visualizer for IAC result JSON files, providing a clear breakdown of scores and costs.
  - Usage: `python visualisation/viziac.py <iac_result.json>`
- `visualisation/dash_graph_vis.py`: An interactive, web-based visualization tool using Dash and Plotly for exploring complex knowledge graphs.

## Current focus

- Creating an evaluation pipeline to compare report creation methods (moving to metrics).

## Notes / Current Limitations

- Telemetry parsing in `src/core/transforms/telemetry_to_graph.py` only covers a subset of possible in-game events (movement, some interactions, and item/npc give patterns). If you add new telemetry event types, you may need to extend the regex handling.
- LLM report quality in `src/pipelines/model_alignment/generate_reports.py` depends on the chosen `--prompt-set` and on edits to the in-script prompts if you need different behavior.
- `distractor.py` requires local Selenium/Firefox setup when enabled.
