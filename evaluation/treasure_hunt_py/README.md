# Treasure Hunt Game (Simulated Task)

This package (`treasure_hunt`) implements the pygame-based simulated multi-room "treasure hunt / hospital-floor" task used to evaluate verbal task handover.

## What the Game Does

Participants navigate a grid-based floor, interact with NPCs, collect items (e.g., "potions", "keys", "gems"), unlock/pass through doors, and may encounter small in-game "modules" (minigames, dialogue, input panels).

The game logs participant actions as *telemetry events* to a text file, which is later consumed by the telemetry-to-graph transform pipeline (`src/core/transforms/telemetry_to_graph.py`).

## Key Components

Inside the `treasure_hunt/` package directory:

- `src/core.py`
  - `GameMap`: loads room layout (`*.txt`), texture maps (optional), and room transition rules (`transitions.json`).
  - Movement/transition checks: `is_valid_move(...)`, `check_transition(...)`.
- `src/game_mdp.py`
  - `GameState`: current state of the game (player, objects/NPCs, room name, score, on-screen text queue, module state).
  - `Player`: position + direction + held item + flags (used for conditional dialogues).
  - `NPC`: NPC interaction logic (dialogue flows, conditional interactions, held-item interactions).
  - `start_state(...)` / `update_start_state(...)`: initializes and updates room objects from `objects.json` files.
- `src/modules.py`
  - Defines interactive "modules" used in the task (for example, wire/password modules and dialogue-like interactive UI).
  - These modules are rendered in `visualization/` and updated through `GameState`.
- `src/telemetry.py`
  - `Telemetry.log_event(event_type, details)`: appends lines in the format:
    - `<timestamp> - <event_type>: <details>`

## Task Data (maps, assets, saves)

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

## Running the Game (main telemetry task)

1. **Install the package**:
   From the repository root:
   ```bash
   pip install -e evaluation/treasure_hunt_py
   ```
   Or from this directory:
   ```bash
   pip install -e .
   ```

2. **Set `SAVE_DIR`** (where saves + telemetry logs will be written):
   ```bash
   export SAVE_DIR=/path/to/where/to/write/saves
   ```

3. **Run from the repository root**:
   ```bash
   python -m treasure_hunt.scripts.main --save 302
   ```

### Useful Command-Line Options

As defined in `treasure_hunt/scripts/main.py`:

- `--save <name>`: base filename for the `.pkl` save and corresponding telemetry text file.
- `--load <name>`: resume from an existing save.
- `--is_player2`: switch player identity / initialize player2-specific NPC interactions.
- `--use-distractor`: runs an optional distractor task while the main task is paused.
- `--timeout <minutes>`: ends the task after the given time.

Telemetry output is written under:
- `"$SAVE_DIR/telemetry/<save_name>.txt"`

### Optional Distractor Task

Running with the `--use-distractor` flag starts `scripts/distractor.py`, which uses Selenium + Firefox to play a memory-match game on the web.

> [!NOTE]
> This requires a working local Selenium environment (Firefox + `geckodriver` path in the script).

### Tutorial Script

`treasure_hunt/scripts/tutorial.py` runs a simplified tutorial map (`maps/tutorial_v2/`) and can log telemetry when `--telemetry` is enabled.
