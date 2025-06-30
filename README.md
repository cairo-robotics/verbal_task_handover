# LLM support for verbal task handover
better code breakdown incoming

Code for Kaleb's verbal task handover project. Includes `treasure_hunt_py`, a simple pygame environment designed for multi-object search tasks with included telemetry for player actions and game states.

Also in `/evaluation` is code used to generate, process, and score reports for information content.

## System requirements
* Python 3.8
* Python dependencies (see `requirements.txt`)

## game task (treasure_hunt_py)
* `treasure_hunt/`
    * `src/`
        * `core.py`: Contains `GameMap` class, which loads & stores current room map, texture data (if specifies), and collision checking / movement information (e.g. `is_valid_move`, `check_transition`)
        * `game_mdp.py`:
            * `Player` class: stores player's current position, direction, held items and interaction data (`Player.flags`). Also specifics in player 1 or player 2 via `Player.name`.
            * `NPC` class, which handles all the heavy lifting of NPC interaction logic, including controlling player-specific interactions or when to use a menu prompt.
            * `GameState` class: the game state class. Holds all current objects (including NPCs) for the level, current score, elapsed time, the Player class, etc. This is what gets saved + loaded between rounds. Also stores what text is currently being displayed or is queued to display on-screen.
                * `handle_interact` determines what to do when the player hits SPACE if they're facing an NPC or object (this used to do more in the previous version that had more chests, locked doors, etc.)
            * `start_state` function loads the map data from the `objects.json` for the given map. This only runs when starting a new game, not when resuming one.
            * You may see references to `cooldown`'s throughout this file -- these are not currently used by anything
        * `modules.py`:
            * `Object` base class
            * `InteractiveDialogue` class to handle NPC menu interactions -- a new one is spun up when a menu interaction is triggered
        * `telemetry.py`: has the `Event` and `Telemetry` classes which is really just to make it easier for other scripts to dump telemetry info to the textfile

[more detail WIP]

## evaluation code
* *requires*: a configued `.env` file (or manually set environment variable `DATA_DIR`)
* `analytics/`: mostly deprecated, except for
    * `report_statistics.py`: [WIP]: currently compiles easy-to-access information about report data, including word counts, across conditions
* `scripts/`:
    * `aggregate_scores.py`: collects & sorts meta-scores (i.e. how far each participant progressed) into a csv
    * `process_all_states_and_reports.py`: bulk generates processed state (ground truth) data & associated report vector data; current needs updating
    * `report_to_vector.py`: makes an API call to GPT (using the new `response_format` argument) to convert natural language reports into the pydantic JSON schema specified in `vector_schema.py`
    * `telemetry_to_vector`: currently deprecated; objective is to produce a version of the ground truth data consisting of what the LLM could actually deduce from its limited telemetry input
    * `vector_schema.py`: defines a pydantic object `GameState` designed to contain all potential information used to determine a next-best action
