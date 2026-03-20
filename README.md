# LLM Support for Verbal Task Handover

Code for a research project studying whether LLMs can improve *verbal task handover* performance in human-to-human handoffs.

## Goals

This project asks:

1. Do LLMs produce handover reports that include more task information?
2. Does the information included in LLM-produced handover reports reduce time-to-complete for the next participant/agent?

To support this, we use:

- Handover reports written by humans and by LLMs for equivalent simulated task states (in a game environment that is loosely based on a hospital floor task).
- A pipeline that converts (a) telemetry from the simulated task and (b) user-written reports into a shared structured representation (“knowledge graph”).
- Diffing/merging logic to identify what the report adds, contradicts, or misses, and to produce an LLM-friendly “narrative view” for final report generation.

## Repository Layout

- `evaluation/` : code used to run the user study and the simulated task.
  - `evaluation/treasure_hunt_py/` : the pygame-based task + telemetry.
  - `evaluation/user_study/` : GUIs/scripts used during participant sessions (chat/report capture).
- `src/model_alignment/` : the study-data-to-final-report pipeline (telemetry/report to graph, graph diff/merge, narrative view, report generation).
- `scripts/` : helper scripts for working with participant telemetry/report files.

## Tech Stack (dev/run-time)

- Python: Python 3.11+ (see `requirements.txt`)
- Key dependencies: OpenAI API (`openai`), Pydantic (`pydantic`)
- Pygame task environment: `pygame`

## Evaluation: `evaluation/treasure_hunt_py/`

`evaluation/treasure_hunt_py` contains a self-contained python package (`treasure_hunt`) implementing the simulated multi-room “treasure hunt / hospital-floor” task.

### What the game does

Participants navigate a grid-based floor, interact with NPCs, collect items (e.g., “potions”, “keys”, “gems”), unlock/pass through doors, and may encounter small in-game “modules” (minigames / dialogue / input panels).

The game logs participant actions as *telemetry events* to a text file, which is later consumed by `src/model_alignment/telemetry_to_graph.py`.

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
  - Defines interactive “modules” used in the task (for example wire/password modules and dialogue-like interactive UI).
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

## Report generation pipeline: `src/model_alignment/`

The `src/model_alignment/` pipeline converts:

- telemetry logs from the game (`evaluation/treasure_hunt_py`)
- and user-written handover reports

into a shared `KnowledgeGraphExtraction` representation, then computes diffs/conflicts and prepares a “narrative view” for report generation.

### Shared schema: `pydantic_schema.py`

Defines the Pydantic models and enums used throughout the pipeline:

- `KnowledgeGraphExtraction` : `{ entities, events, state_relations, spatial_relations, conflicts }`
- `NarrativeView` : `{ player_state, world_state (rooms + implicit locations + unplaced agents), unresolved_conflicts }`

### Pipeline steps

The scripts assume a `DATA_DIR` environment variable and a directory layout like:

- `$DATA_DIR/telemetry/<id>.txt`
- `$DATA_DIR/reports/<id>.txt`
- `$DATA_DIR/processed_output/` (output JSON files)

Key scripts:

1. `telemetry_to_graph.py`
  - Deterministic conversion from telemetry text to `KnowledgeGraphExtraction`.
  - Current parsing focuses on patterns like:
    - `room entered: <direction> to <location>`
    - `item obtained: <item>`
    - `npc interact: <npc>` and `npc interact: <npc> about <topic>`
    - `gave item to npc: <item> <npc>`
  - Output: `<id>_telemetry_to_kg_output.json`
2. `text_to_graph.py`
  - Uses the OpenAI API to convert a user report text file to the same `KnowledgeGraphExtraction` schema.
  - Output: `<id>_text_to_kg_output.json`
3. `compare_graphs.py`
  - Aligns entity IDs across graphs (uses an LLM for ambiguous entity matching).
  - Computes a diff/conflict summary:
    - events: already-present vs novel vs conflicts vs uncertain
    - state relations and spatial relations: already-present vs novel vs conflicts vs uncertain
  - Output: `<id>_compare_graphs_output.json`
4. `merge_graphs.py`
  - Applies the diff to the base graph:
    - adds novel facts directly
    - adds `ConflictRecord` entries for contradictions
    - backfills missing entities referenced by events/relations
  - Output: `<id>_merge_graphs_output.json`
5. `craft_narrative_view.py`
  - Converts the merged knowledge graph into `NarrativeView` (player inventory + per-room layout including room-level `requires`, items with requirements, non-item entities in rooms, implicit rooms from `located_in`, agents without placement, a per-entity state-relation index, full spatial relation copy, and conflict summaries).
  - Each room and each character present in a room also lists `miscellaneous_state_relations`: human-readable state edges involving that id that are not already represented by who is in the room, that character’s `requirements`, or the player’s inventory.
  - Output: `<id>_narrative_view_output.json`
6. `generate_reports.py`
  - Loads `<id>_narrative_view_output.json` (or any path to a `NarrativeView` JSON file) and calls the OpenAI Chat Completions API (`gpt-4o-mini`, temperature 0) to produce handover report text.
  - **Input:** With `DATA_DIR` set, the positional argument is a base id (e.g. `302`); the script reads `$DATA_DIR/processed_output/<id>_narrative_view_output.json`. Without `DATA_DIR`, the argument must be the full path to a narrative-view JSON file.
  - **Prompts:** Two built-in system/user prompt pairs are defined in the script:
    - `full_realization` — structured, exhaustive coverage of the narrative state (default).
    - `task_aware` — emphasizes patient needs, message delivery, and task-relevant inventory/location.
  - `**--prompt-set`:** Choose `full_realization`, `task_aware`, or `both`. With `both`, the model is called twice (full realization first, then task-aware); the two replies are output to separate files.

### Example end-to-end run (participant `302`)

Assuming:

- Telemetry file: `$DATA_DIR/telemetry/302.txt`
- User report file: `$DATA_DIR/reports/302_user_report.txt`

Run:

```bash
export DATA_DIR=/path/to/DATA_DIR

python src/model_alignment/telemetry_to_graph.py 302
python src/model_alignment/text_to_graph.py 302
python src/model_alignment/compare_graphs.py 302
python src/model_alignment/merge_graphs.py 302
python src/model_alignment/reconcile_state.py 302
python src/model_alignment/craft_narrative_view.py 302
python src/model_alignment/generate_reports.py 302
# Optional: task-focused report, or both prompt styles (two API calls)
python src/model_alignment/generate_reports.py 302 --prompt-set task_aware
python src/model_alignment/generate_reports.py 302 --prompt-set both
# Without DATA_DIR, pass the narrative view path explicitly:
# python src/model_alignment/generate_reports.py /path/to/302_narrative_view_output.json
```

Run the full pipeline using:

```
python src/model_alignment/run_full_pipline_for_pids.py {PID1 PID2...}
```

### Configuration

Environment variables used by the pipeline:

- `OPENAI_API_KEY` : required for `text_to_graph.py`, `compare_graphs.py`, and `generate_reports.py`
- `DATA_DIR` : base directory for inputs/outputs as described above

## Notes / Current Limitations

- Telemetry parsing in `telemetry_to_graph.py` only covers a subset of possible in-game events (movement, some interactions, and item/npc give patterns). If you add new telemetry event types, you may need to extend the regex handling.
- LLM report quality in `generate_reports.py` depends on the chosen `--prompt-set` and on edits to the in-script prompts if you need different behavior.
- `distractor.py` requires local Selenium/Firefox setup when enabled.

