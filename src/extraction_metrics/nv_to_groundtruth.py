"""
nv_to_groundtruth.py

Convert a NarrativeView into a FactExtraction (ground-truth factbase).

Room-to-room spatial connections (e.g. room4 north-of room5) are omitted.
All other information is preserved with minimal loss.
"""

import re
import sys
import os
from pathlib import Path
from typing import List, Set

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "model_alignment"))

from craft_narrative_view import NarrativeView  # noqa: E402
from state_ontology import Argument, CanonicalFact, FactExtraction, Location  # noqa: E402

import dotenv
dotenv.load_dotenv()


# ---------------------------------------------------------------------------
# Argument / Location helpers
# ---------------------------------------------------------------------------

def _entity(value: str) -> Argument:
    return Argument(type="entity", value=value)


def _entity_in_room(value: str, room: str) -> Argument:
    return Argument(
        type="entity",
        value=value,
        location=Location(type="room", room=room),
    )


def _existential_in_room(room: str) -> Argument:
    return Argument(
        type="existential",
        value="someone",
        location=Location(type="room", room=room),
    )


# ---------------------------------------------------------------------------
# interaction_history parsing
#
# Strings are produced by craft_narrative_view._build_interaction_history_by_character:
#   • "was {event_type}: {object_id} by {actor_id}"  (when participants.object is set)
#   • "{actor_id} {event_type}"                       (when participants.object is None)
# ---------------------------------------------------------------------------

_WAS_PATTERN = re.compile(r"^was (\w+): (.+) by (.+)$")
_ACTOR_PATTERN = re.compile(r"^(.+) (\w+)$")


def _facts_from_interaction_entry(
    character_id: str, entry: str
) -> List[CanonicalFact]:
    facts: List[CanonicalFact] = []

    m = _WAS_PATTERN.match(entry)
    if m:
        event_type, obj_id, actor_id = m.group(1), m.group(2).strip(), m.group(3).strip()
        if event_type in ("given", "obtained"):
            # character received/obtained obj_id (possibly from actor_id)
            facts.append(CanonicalFact(
                predicate="has",
                agent=_entity(character_id),
                object=_entity(obj_id),
                source=_entity(actor_id),
            ))
        elif event_type == "delivered":
            # actor_id delivered obj_id to character_id
            facts.append(CanonicalFact(
                predicate="delivered",
                agent=_entity(actor_id),
                patient=_entity(character_id),
                object=_entity(obj_id),
            ))
        elif event_type == "talked_to":
            # actor_id delivered a message (obj_id) to character_id
            facts.append(CanonicalFact(
                predicate="message_delivered",
                agent=_entity(actor_id),
                target=_entity(character_id),
                object=_entity(obj_id),
            ))
        return facts

    m = _ACTOR_PATTERN.match(entry)
    if m:
        actor_id, event_type = m.group(1).strip(), m.group(2).strip()
        if event_type == "talked_to":
            facts.append(CanonicalFact(
                predicate="message_delivered",
                agent=_entity(actor_id),
                target=_entity(character_id),
            ))
        elif event_type == "delivered":
            facts.append(CanonicalFact(
                predicate="delivered",
                agent=_entity(actor_id),
                target=_entity(character_id),
            ))

    return facts


# ---------------------------------------------------------------------------
# miscellaneous_state_relations parsing
#
# Strings are produced by craft_narrative_view._format_state_relation:
#   "{subject} {relation.value} {object}"
# Known relation values: in_inventory_of, located_in, needs
# ---------------------------------------------------------------------------

_STATE_PATTERN = re.compile(r"^(\S+) (\S+) (\S+)$")


def _facts_from_state_relation_str(rel_str: str) -> List[CanonicalFact]:
    m = _STATE_PATTERN.match(rel_str)
    if not m:
        return []
    subject, relation, obj = m.group(1), m.group(2), m.group(3)

    if relation == "in_inventory_of":
        return [CanonicalFact(
            predicate="has",
            agent=_entity(obj),
            object=_entity(subject),
        )]
    if relation == "located_in":
        return [CanonicalFact(
            predicate="located",
            agent=_entity_in_room(subject, obj),
        )]
    if relation == "needs":
        return [CanonicalFact(
            predicate="needs",
            agent=_entity(subject),
            object=_entity(obj),
        )]
    return []


# ---------------------------------------------------------------------------
# Main conversion
# ---------------------------------------------------------------------------

def nv_to_groundtruth(nv: NarrativeView) -> FactExtraction:
    """Convert a NarrativeView to a FactExtraction.

    Room-to-room spatial connections are intentionally omitted.
    Duplicate facts (which arise because interaction_history entries are
    shared across all event participants) are deduplicated.
    """
    facts: List[CanonicalFact] = []
    seen: Set[str] = set()

    def add(fact: CanonicalFact) -> None:
        key = fact.model_dump_json()
        if key not in seen:
            seen.add(key)
            facts.append(fact)

    # --- Player state -------------------------------------------------------

    if nv.player_state.current_location:
        add(CanonicalFact(
            predicate="located",
            agent=_entity_in_room("player", nv.player_state.current_location),
        ))

    for item in nv.player_state.inventory:
        add(CanonicalFact(
            predicate="has",
            agent=_entity("player"),
            object=_entity(item),
        ))

    # --- World state --------------------------------------------------------

    for room in nv.world_state.rooms:

        # Room-to-room connections → omit per spec

        for char in room.characters_present:
            add(CanonicalFact(
                predicate="located",
                agent=_entity_in_room(char.name, room.name),
            ))

            for req in char.requirements:
                add(CanonicalFact(
                    predicate="needs",
                    agent=_entity(char.name),
                    object=_entity(req),
                ))

            for entry in char.interaction_history:
                for fact in _facts_from_interaction_entry(char.name, entry):
                    add(fact)

            for rel_str in char.miscellaneous_state_relations:
                for fact in _facts_from_state_relation_str(rel_str):
                    add(fact)

        for item in room.items_present:
            add(CanonicalFact(
                predicate="located",
                agent=_entity_in_room(item, room.name),
            ))

        for rel_str in room.miscellaneous_state_relations:
            for fact in _facts_from_state_relation_str(rel_str):
                add(fact)

    # Unresolved conflicts are meta-information about the knowledge base,
    # not game-world facts, so they are omitted.

    return FactExtraction(facts=facts)


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------

def _run_stem_from_narrative_filename(filename: str) -> str:
    """Stem used for output naming: ``foo`` from ``foo_narrative_view_output.json``."""
    stem = Path(filename).stem
    suffix = "_narrative_view_output"
    if stem.endswith(suffix):
        return stem[: -len(suffix)]
    return stem


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(
            "Usage: DATA_DIR=<dir> nv_to_groundtruth.py <stem_or_filename>",
            file=sys.stderr,
        )
        print(
            "  Reads:   $DATA_DIR/processed_output/<stem>_narrative_view_output.json",
            file=sys.stderr,
        )
        print(
            "  Writes:  $DATA_DIR/analysis/<stem>_groundtruth.json",
            file=sys.stderr,
        )
        sys.exit(1)

    data_dir = os.environ.get("DATA_DIR")
    if not data_dir:
        print("DATA_DIR is not set.", file=sys.stderr)
        sys.exit(1)

    raw = sys.argv[1].strip().replace("\\", "/")
    if raw.startswith("processed_output/"):
        raw = raw[len("processed_output/") :]
    if "/" in raw:
        print(
            "Argument must be a run stem or a single filename (no subpaths).",
            file=sys.stderr,
        )
        sys.exit(1)

    basename = raw
    if not basename:
        print("Empty argument.", file=sys.stderr)
        sys.exit(1)

    if basename.endswith(".json"):
        input_filename = basename
        run_stem = _run_stem_from_narrative_filename(basename)
    else:
        run_stem = basename
        input_filename = f"{run_stem}_narrative_view_output.json"

    processed_base = (Path(data_dir) / "processed_output").resolve()
    analysis_base = (Path(data_dir) / "analysis").resolve()

    input_path = (processed_base / input_filename).resolve()
    try:
        input_path.relative_to(processed_base)
    except ValueError:
        print(f"Invalid path: {input_path}", file=sys.stderr)
        sys.exit(1)

    if not input_path.is_file():
        print(f"Input not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    analysis_base.mkdir(parents=True, exist_ok=True)
    output_path = (analysis_base / f"{run_stem}_groundtruth.json").resolve()
    try:
        output_path.relative_to(analysis_base)
    except ValueError:
        print(f"Invalid output path: {output_path}", file=sys.stderr)
        sys.exit(1)

    with open(input_path) as f:
        nv = NarrativeView.model_validate_json(f.read())

    result = nv_to_groundtruth(nv)
    text = result.model_dump_json(indent=2)
    with open(output_path, "w") as f:
        f.write(text)
    print(output_path)
