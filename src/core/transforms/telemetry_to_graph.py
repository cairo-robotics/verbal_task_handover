import json
import os
import re
import sys
from dataclasses import dataclass
from typing import List, Optional, Tuple

try:
    from src.core.representations.pydantic_schema import (
        Argument,
        ConnectionFact,
        Fact,
        KnowledgeGraph,
        Location,
        LocationFact,
        RelationFact,
        RelationPredicate,
        Direction,
    )
except ImportError:
    from pydantic_schema import (
        Argument,
        ConnectionFact,
        Fact,
        KnowledgeGraph,
        Location,
        LocationFact,
        RelationFact,
        RelationPredicate,
        Direction,
    )

try:
    import dotenv
except ModuleNotFoundError:  # pragma: no cover - optional runtime dependency
    dotenv = None

if dotenv is not None:
    dotenv.load_dotenv()


PATIENTS_BY_ROOM = ["lily", "oliver", "nick", "marie", "guy"]


def _parse_line(line: str) -> Optional[Tuple[str, str]]:
    if not line.strip():
        return None
    if " - " not in line:
        return None
    timestamp, event_text = line.split(" - ", 1)
    return timestamp.strip(), event_text.strip()


def _normalize_name(value: str) -> str:
    value = value.strip().lower().replace("_", " ")
    value = re.sub(r"\s+", " ", value)
    return value


def _normalize_item(value: str) -> str:
    item = _normalize_name(value)
    if "potion" in item and not item.endswith("potion"):
        item = f"{item} potion"
    return item


def _normalize_location_name(room: str) -> str:
    """Map telemetry tokens (room1, hallway_5) to DSL-style labels (room 1, hallway 5)."""
    s = _normalize_name(room)
    m = re.match(r"^(room|hallway|lounge|storage)(\d+)$", s.replace(" ", ""))
    if m:
        return f"{m.group(1)} {m.group(2)}"
    return s


_DIRECTION_INVERSES = {
    Direction.NORTH: Direction.SOUTH,
    Direction.SOUTH: Direction.NORTH,
    Direction.EAST: Direction.WEST,
    Direction.WEST: Direction.EAST,
    Direction.NORTHEAST: Direction.SOUTHWEST,
    Direction.SOUTHWEST: Direction.NORTHEAST,
    Direction.NORTHWEST: Direction.SOUTHEAST,
    Direction.SOUTHEAST: Direction.NORTHWEST,
}


def _invert_direction(direction: Direction) -> Direction:
    return _DIRECTION_INVERSES[direction]


def _named(value: str) -> Argument:
    return Argument(type="named", value=_normalize_name(value))


def _room_location(room: str) -> Location:
    return Location(type="room", room=_normalize_location_name(room))


def _arg_key(arg: Optional[Argument]) -> Tuple:
    if arg is None:
        return ("none",)
    loc = arg.location
    if loc is None:
        loc_key = None
    else:
        loc_key = (
            loc.type,
            loc.room,
            tuple(d.value for d in loc.directions) if loc.directions else None,
            loc.mode,
        )
    return (arg.type, arg.value, loc_key)


def _location_key(loc: Location) -> Tuple:
    return (
        loc.type,
        loc.room,
        tuple(d.value for d in loc.directions) if loc.directions else None,
        loc.mode,
    )


def _is_partial(*args: Optional[Argument]) -> bool:
    return any(arg is not None and arg.type == "existential" for arg in args)


@dataclass
class TelemetryInferenceState:
    """Tracks the player room and last NPC interaction for inferring missing telemetry fields."""

    player_room: str
    last_interacted_npc: Optional[str] = None

    def record_room(self, destination_normalized: str) -> None:
        self.player_room = destination_normalized

    def record_npc_interaction(self, npc_normalized_value: Optional[str]) -> None:
        if npc_normalized_value is not None:
            self.last_interacted_npc = npc_normalized_value


class _TelemetryGraphBuilder:
    """Accumulates KnowledgeGraph facts with tuple-key deduplication (schema-aligned, not legacy event keys)."""

    __slots__ = ("facts", "_seen_relation", "_seen_location", "_seen_connection")

    def __init__(self) -> None:
        self.facts: List[Fact] = []
        self._seen_relation: set[Tuple] = set()
        self._seen_location: set[Tuple] = set()
        self._seen_connection: set[Tuple] = set()

    def add_relation(
        self,
        predicate: RelationPredicate,
        subject: Argument,
        obj: Optional[Argument] = None,
        target: Optional[Argument] = None,
        provenance: Optional[str] = None,
        force_partial: bool = False,
    ) -> None:
        key = (predicate.value, _arg_key(subject), _arg_key(obj), _arg_key(target))
        if key in self._seen_relation:
            return
        self._seen_relation.add(key)
        self.facts.append(
            RelationFact(
                predicate=predicate,
                subject=subject,
                object=obj,
                target=target,
                is_partial=force_partial or _is_partial(subject, obj, target),
                provenance=provenance,
            )
        )

    def add_location(self, entity: Argument, room: str, provenance: Optional[str] = None) -> None:
        loc = _room_location(room)
        key = (_arg_key(entity), _location_key(loc))
        if key in self._seen_location:
            return
        self._seen_location.add(key)
        self.facts.append(
            LocationFact(
                entity=entity,
                location=loc,
                is_partial=_is_partial(entity),
                provenance=provenance,
            )
        )

    def add_connection(
        self,
        room_a: str,
        room_b: str,
        direction: Optional[str] = None,
        provenance: Optional[str] = None,
    ) -> None:
        loc_a = _room_location(room_a)
        loc_b = _room_location(room_b)

        # Decide if we need to swap to normalize the connection
        key_a = _location_key(loc_a)
        key_b = _location_key(loc_b)

        dir_enum = Direction(direction.lower()) if direction else None

        if key_a > key_b:
            loc_a, loc_b = loc_b, loc_a
            if dir_enum:
                dir_enum = _invert_direction(dir_enum)

        key = (key_a, key_b) if key_a < key_b else (key_b, key_a)
        if key in self._seen_connection:
            return
        self._seen_connection.add(key)
        self.facts.append(
            ConnectionFact(
                location_a=loc_a,
                location_b=loc_b,
                direction=dir_enum,
                provenance=provenance,
            )
        )


def _resolve_give_target_npc(
    npc_token: Optional[str],
    state: TelemetryInferenceState,
) -> Tuple[Argument, bool]:
    """
    Resolve the NPC for 'Gave item to NPC' lines.

    Returns (argument, is_partial). If the line omits the NPC token, uses last_interacted_npc;
    if that is also missing, returns an existential argument (deterministic partial fact).
    """
    if npc_token:
        return _named(_normalize_name(npc_token)), False
    if state.last_interacted_npc:
        return _named(state.last_interacted_npc), False
    return Argument(type="existential"), True


def convert_telemetry_to_kg(file_path: str) -> KnowledgeGraph:
    player_arg = _named("player")
    state = TelemetryInferenceState(player_room=_normalize_location_name("room0"))
    builder = _TelemetryGraphBuilder()

    with open(file_path, "r", encoding="utf-8") as f:
        for raw_line in f:
            parsed = _parse_line(raw_line)
            if parsed is None:
                continue
            _, text = parsed
            text_lower = text.lower()

            move_match = re.match(r"room entered:\s*([a-z]+)\s+to\s+([a-z0-9_]+)\s*$", text_lower)
            if move_match:
                direction_str, destination = move_match.groups()
                dest_norm = _normalize_location_name(destination)
                builder.add_connection(
                    state.player_room, dest_norm, direction=direction_str, provenance=text
                )
                state.record_room(dest_norm)
                continue

            item_match = re.match(r"item obtained:\s*(.+)$", text, re.IGNORECASE)
            if item_match:
                raw_item = item_match.group(1).strip()
                raw_item_lower = raw_item.lower()

                request_room_match = re.match(r"request from room\s*([0-9]+)$", raw_item_lower)
                if request_room_match:
                    room_id = f"room {request_room_match.group(1)}"
                    item_arg = _named(f"request from {room_id}")
                    builder.add_relation(
                        RelationPredicate.HAS_ITEM,
                        subject=player_arg,
                        obj=item_arg,
                        provenance=text,
                    )
                    builder.add_relation(
                        RelationPredicate.HAS_MESSAGE_FOR,
                        # subject=Argument(type="existential", location=_room_location(room_id)),
                        subject = _named(PATIENTS_BY_ROOM[int(request_room_match.group(1))-1]),
                        target=Argument(type="existential"),
                        provenance=text,
                        force_partial=True,
                    )
                    continue

                response_match = re.match(r"response from\s+(.+)$", raw_item, re.IGNORECASE)
                if response_match:
                    sender_name = _normalize_name(response_match.group(1))
                    sender = _named(sender_name)
                    response_item = _named(f"response from {sender_name}")
                    builder.add_relation(
                        RelationPredicate.HAS_ITEM,
                        subject=player_arg,
                        obj=response_item,
                        provenance=text,
                    )
                    builder.add_relation(
                        RelationPredicate.HAS_MESSAGE_FOR,
                        subject=sender,
                        target=Argument(type="existential"),
                        provenance=text,
                    )
                    continue

                item_name = _normalize_item(raw_item)
                if "potion" not in item_name:
                    item_arg = _named(item_name)
                    builder.add_relation(
                        RelationPredicate.HAS_ITEM,
                        subject=player_arg,
                        obj=item_arg,
                        provenance=text,
                    )
                continue

            npc_about_match = re.match(
                r"npc interact:\s*([a-z0-9_]+)\s+about\s+(.+)$",
                text,
                re.IGNORECASE,
            )
            if npc_about_match:
                npc_raw, topic_raw = npc_about_match.groups()
                npc = _named(npc_raw)
                topic = topic_raw.strip()
                builder.add_location(npc, state.player_room, provenance=text)
                state.record_npc_interaction(npc.value)

                request_match = re.match(r"request from room\s*([0-9]+)$", topic, re.IGNORECASE)
                if request_match:
                    source_room = f"room {request_match.group(1)}"
                    source_arg = Argument(type="existential", location=_room_location(source_room))
                    builder.add_relation(
                        RelationPredicate.MESSAGE_DELIVERED,
                        subject=source_arg,
                        target=npc,
                        provenance=text,
                        force_partial=True,
                    )
                    # builder.add_relation(
                    #     RelationPredicate.HAS_MESSAGE_FOR,
                    #     subject=npc,
                    #     target=source_arg,
                    #     provenance=text,
                    #     force_partial=True,
                    # )
                    continue

                response_match = re.match(r"response from\s+(.+)$", topic, re.IGNORECASE)
                if response_match:
                    sender = _named(response_match.group(1))
                    builder.add_relation(
                        RelationPredicate.MESSAGE_DELIVERED,
                        subject=sender,
                        target=npc,
                        provenance=text,
                    )
                    continue

                continue

            npc_match = re.match(r"npc interact:\s*([a-z0-9_]+)\s*$", text_lower)
            if npc_match:
                npc_name = npc_match.group(1)
                npc = _named(npc_name)
                builder.add_location(npc, state.player_room, provenance=text)
                state.record_npc_interaction(npc.value)
                continue

            # Item token then optional NPC token (same format as game telemetry).
            gave_match = re.match(
                r"gave item to npc:\s*([a-z0-9_]+)(?:\s+([a-z0-9_]+))?\s*$",
                text_lower,
            )
            if gave_match:
                item_raw, npc_raw = gave_match.groups()
                npc_arg, inferred_partial = _resolve_give_target_npc(npc_raw, state)
                if npc_arg.type == "named" and npc_arg.value is not None:
                    builder.add_location(npc_arg, state.player_room, provenance=text)
                potion_arg = _named(_normalize_item(item_raw))
                builder.add_relation(
                    RelationPredicate.POTION_DELIVERED,
                    subject=npc_arg,
                    obj=potion_arg,
                    provenance=text,
                    force_partial=inferred_partial,
                )
                continue

            if text_lower.startswith("gave wrong item to npc:"):
                continue

            if text_lower.startswith("treasure collected:"):
                continue

    builder.add_location(player_arg, state.player_room, provenance=None)
    return KnowledgeGraph(facts=builder.facts)


def create_kg_json(telemetry_file: str, output_file: str) -> None:
    kg = convert_telemetry_to_kg(telemetry_file)
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(kg.model_dump(), f, indent=2)


if __name__ == "__main__":
    data_dir = os.environ.get("DATA_DIR")
    if not data_dir:
        raise SystemExit("DATA_DIR environment variable is not set")
    if len(sys.argv) < 2:
        raise SystemExit("usage: telemetry_to_graph.py <telemetry_basename>")
    text_filename = os.path.join(data_dir, "telemetry", sys.argv[1] + ".txt")
    output_filename = os.path.join(
        data_dir, "processed_output", sys.argv[1] + "_telemetry_to_kg_output.json"
    )
    create_kg_json(text_filename, output_filename)