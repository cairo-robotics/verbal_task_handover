from collections import defaultdict
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from src.core.representations.pydantic_schema import (
    KnowledgeGraph,
    Fact,
    RelationFact,
    LocationFact,
    SpatialFact,
    ConnectionFact,
    Argument,
    Location,
    Conflict,
    RelationPredicate,
)

class PlayerState(BaseModel):
    inventory: List[str]
    current_location: str

class RoomConnection(BaseModel):
    direction: str
    room: str

class CharacterView(BaseModel):
    name: str
    interaction_history: List[str]
    requirements: List[str]
    miscellaneous_state_relations: List[str] = Field(default_factory=list)

class RoomView(BaseModel):
    name: str
    connected_to: List[RoomConnection]
    characters_present: List[CharacterView]
    items_present: List[str]
    miscellaneous_state_relations: List[str] = Field(default_factory=list)

class WorldState(BaseModel):
    rooms: List[RoomView]

class ConflictSummary(BaseModel):
    description: str
    involved_entities: List[str]

class NarrativeView(BaseModel):
    player_state: PlayerState
    world_state: WorldState
    unresolved_conflicts: List[ConflictSummary]


# ---------------------------------------------------------------------------
# Entity type heuristics (from entity_alignment.py)
# ---------------------------------------------------------------------------
_ITEM_KEYWORDS = ("potion", "key", "chest", "scroll", "gem", "coin", "sword")
_LOCATION_KEYWORDS = ("room", "corridor", "hall", "vault", "chamber", "area")

def _infer_entity_type(value: str) -> str:
    """Heuristic entity type from a surface-form string: 'item', 'location', or 'agent'."""
    lower = value.lower()
    if any(kw in lower for kw in _ITEM_KEYWORDS):
        return "item"
    if any(kw in lower for kw in _LOCATION_KEYWORDS):
        return "location"
    return "agent"

def _get_all_entities(facts: List[Fact]) -> Dict[str, str]:
    """Collect all unique entities and infer their types."""
    entities: Dict[str, str] = {}
    
    def add_arg(arg: Optional[Argument]):
        if arg and arg.type == "named" and arg.value:
            if arg.value not in entities:
                entities[arg.value] = _infer_entity_type(arg.value)
                
    def add_loc(loc: Optional[Location]):
        if loc and loc.type == "room" and loc.room:
            if loc.room not in entities:
                entities[loc.room] = "location"

    for fact in facts:
        if isinstance(fact, RelationFact):
            add_arg(fact.subject)
            add_arg(fact.object)
            add_arg(fact.target)
        elif isinstance(fact, LocationFact):
            add_arg(fact.entity)
            add_loc(fact.location)
        elif isinstance(fact, SpatialFact):
            add_arg(fact.subject)
            add_arg(fact.reference)
        elif isinstance(fact, ConnectionFact):
            add_loc(fact.location_a)
            add_loc(fact.location_b)
            
    return entities

def _get_player_id(entities: Dict[str, str]) -> str:
    """Find the player entity ID."""
    for entity_id in entities:
        if "player" in entity_id.lower():
            return entity_id
    # Fallback to first agent if no "player" found
    for entity_id, etype in entities.items():
        if etype == "agent":
            return entity_id
    return list(entities.keys())[0] if entities else ""

def _build_inventory(
    player_id: str, facts: List[Fact]
) -> List[str]:
    inventory_items: List[str] = []
    for fact in facts:
        if (
            isinstance(fact, RelationFact)
            and fact.predicate == RelationPredicate.HAS_ITEM
            and fact.subject.value == player_id
            and fact.object and fact.object.value
            and "potion" not in fact.object.value.lower()
        ):
            inventory_items.append(fact.object.value)
    return inventory_items

def _get_player_location(
    player_id: str, facts: List[Fact]
) -> str:
    for fact in facts:
        if (
            isinstance(fact, LocationFact)
            and fact.entity.value == player_id
            and fact.location.type == "room"
        ):
            return fact.location.room or ""
    return ""

def _build_requirements_by_character(
    facts: List[Fact],
) -> Dict[str, List[str]]:
    requirements: Dict[str, List[str]] = defaultdict(list)
    for fact in facts:
        if not isinstance(fact, RelationFact):
            continue
            
        if fact.predicate == RelationPredicate.NEEDS_POTION:
            if fact.subject.value and fact.object and fact.object.value:
                requirements[fact.subject.value].append(fact.object.value)
        elif fact.predicate == RelationPredicate.HAS_MESSAGE_FOR:
            # Message/request entity is subject; recipient agent is target
            if fact.target and fact.target.value and fact.subject.value:
                requirements[fact.target.value].append(fact.subject.value)
    return requirements

def _build_characters_by_room(
    entities: Dict[str, str],
    facts: List[Fact],
) -> Dict[str, List[str]]:
    characters_by_room: Dict[str, List[str]] = defaultdict(list)
    for fact in facts:
        if not isinstance(fact, LocationFact) or fact.location.type != "room":
            continue
        
        entity_id = fact.entity.value
        room_id = fact.location.room
        if not entity_id or not room_id:
            continue
            
        if entities.get(entity_id) == "agent":
            characters_by_room[room_id].append(entity_id)
    return characters_by_room

def _build_items_by_room(
    entities: Dict[str, str],
    facts: List[Fact],
) -> Dict[str, List[str]]:
    items_by_room: Dict[str, List[str]] = defaultdict(list)
    
    items_in_any_inventory = {
        fact.object.value
        for fact in facts
        if isinstance(fact, RelationFact) and fact.predicate == RelationPredicate.HAS_ITEM and fact.object and fact.object.value
    }

    for fact in facts:
        if not isinstance(fact, LocationFact) or fact.location.type != "room":
            continue
            
        entity_id = fact.entity.value
        room_id = fact.location.room
        if not entity_id or not room_id:
            continue
            
        if entities.get(entity_id) != "item":
            continue
            
        if entity_id in items_in_any_inventory:
            continue
            
        items_by_room[room_id].append(entity_id)

    return items_by_room

def _format_relation_fact(fact: RelationFact) -> str:
    parts = [fact.subject.value or "someone", fact.predicate.value]
    if fact.object:
        parts.append(fact.object.value or "something")
    if fact.target:
        parts.append(f"to {fact.target.value or 'someone'}")
    return " ".join(parts)

def _miscellaneous_state_relations_for_room(
    room_id: str, facts: List[Fact]
) -> List[str]:
    lines: List[str] = []
    for fact in facts:
        if not isinstance(fact, RelationFact):
            continue
        # Check if room is mentioned in subject, object, or target (unlikely for rooms but possible)
        mentions_room = (
            (fact.subject.value == room_id) or 
            (fact.object and fact.object.value == room_id) or 
            (fact.target and fact.target.value == room_id)
        )
        if mentions_room:
            lines.append(_format_relation_fact(fact))
    return sorted(lines)

def _miscellaneous_state_relations_for_character(
    character_id: str,
    player_id: str,
    facts: List[Fact],
    interaction_history: Optional[List[str]] = None,
) -> List[str]:
    lines: List[str] = []
    for fact in facts:
        if not isinstance(fact, RelationFact):
            continue
            
        mentions_char = (
            (fact.subject.value == character_id) or 
            (fact.object and fact.object.value == character_id) or 
            (fact.target and fact.target.value == character_id)
        )
        
        if not mentions_char:
            continue
            
        # Exclude relations already covered by specific fields
        if fact.predicate == RelationPredicate.HAS_ITEM and fact.subject.value == character_id and character_id == player_id:
            continue
        if fact.predicate == RelationPredicate.NEEDS_POTION and fact.subject.value == character_id:
            continue
        if fact.predicate == RelationPredicate.HAS_MESSAGE_FOR and fact.target and fact.target.value == character_id:
            continue
            
        formatted = _format_relation_fact(fact)
        if interaction_history and formatted in interaction_history:
            continue
            
        lines.append(formatted)
    return sorted(lines)

def _build_interaction_history_by_character(
    facts: List[Fact],
) -> Dict[str, List[str]]:
    """Map character (agent) id -> list of interaction summary strings."""
    history: Dict[str, List[str]] = defaultdict(list)

    # Use "delivered" predicates as interaction history
    event_predicates = {
        RelationPredicate.POTION_DELIVERED,
        RelationPredicate.MESSAGE_DELIVERED,
    }

    for fact in facts:
        if not isinstance(fact, RelationFact) or fact.predicate not in event_predicates:
            continue

        participants = []
        if fact.subject.value: participants.append(fact.subject.value)
        if fact.object and fact.object.value: participants.append(fact.object.value)
        if fact.target and fact.target.value: participants.append(fact.target.value)

        summary = _format_relation_fact(fact)
        
        for p_id in set(participants):
            history[p_id].append(summary)

    return history

def _build_connections_by_room(
    facts: List[Fact],
) -> Dict[str, List[RoomConnection]]:
    connections_by_room: Dict[str, List[RoomConnection]] = defaultdict(list)

    for fact in facts:
        if isinstance(fact, ConnectionFact):
            room_a = fact.location_a.room
            room_b = fact.location_b.room
            if room_a and room_b:
                # Connections are often bidirectional in these games, but we'll follow the fact
                # If location_a has directions, use them
                direction = "connected"
                if fact.location_a.directions:
                    direction = ", ".join([d.value for d in fact.location_a.directions])
                
                connections_by_room[room_a].append(
                    RoomConnection(direction=direction, room=room_b)
                )
        elif isinstance(fact, SpatialFact):
            # Room-to-room spatial relations also imply connections
            if fact.subject.type == "named" and fact.reference and fact.reference.type == "named":
                room_a = fact.reference.value
                room_b = fact.subject.value
                if room_a and room_b:
                    connections_by_room[room_a].append(
                        RoomConnection(direction=fact.direction.value, room=room_b)
                    )

    return connections_by_room

def _build_conflict_summaries(
    conflicts: List[Conflict],
) -> List[ConflictSummary]:
    summaries: List[ConflictSummary] = []
    for conflict in conflicts:
        description = (
            f"Conflict in {conflict.field_name}: "
            f"Expected {conflict.base_value}, found {conflict.new_value}"
        )
        summaries.append(
            ConflictSummary(
                description=description,
                involved_entities=[
                    conflict.base_fact_id,
                    conflict.new_fact.id,
                ],
            )
        )
    return summaries


def craft_narrative_view(
    graph: KnowledgeGraph,
) -> NarrativeView:
    """
    Transform a KnowledgeGraph into a NarrativeView.
    """
    if not graph.facts:
        player_state = PlayerState(inventory=[], current_location="")
        world_state = WorldState(rooms=[])
        unresolved_conflicts: List[ConflictSummary] = []
        return NarrativeView(
            player_state=player_state,
            world_state=world_state,
            unresolved_conflicts=unresolved_conflicts,
        )

    entities = _get_all_entities(graph.facts)
    player_id = _get_player_id(entities)

    inventory = _build_inventory(player_id, graph.facts)
    current_location = _get_player_location(player_id, graph.facts)
    player_state = PlayerState(
        inventory=inventory,
        current_location=current_location,
    )

    requirements_by_character = _build_requirements_by_character(graph.facts)
    characters_by_room = _build_characters_by_room(entities, graph.facts)
    items_by_room = _build_items_by_room(entities, graph.facts)
    connections_by_room = _build_connections_by_room(graph.facts)
    interaction_history_by_character = _build_interaction_history_by_character(
        graph.facts
    )

    room_views: List[RoomView] = []
    for room_id, etype in entities.items():
        if etype != "location":
            continue

        room_connections = connections_by_room.get(room_id, [])
        character_ids = characters_by_room.get(room_id, [])
        characters_present = [
            CharacterView(
                name=char_id,
                interaction_history=interaction_history_by_character.get(
                    char_id, []
                ),
                requirements=requirements_by_character.get(char_id, []),
                miscellaneous_state_relations=_miscellaneous_state_relations_for_character(
                    char_id, 
                    player_id, 
                    graph.facts,
                    interaction_history=interaction_history_by_character.get(char_id, [])
                ),
            )
            for char_id in character_ids
        ]

        items_present = items_by_room.get(room_id, [])

        room_views.append(
            RoomView(
                name=room_id,
                connected_to=room_connections,
                characters_present=characters_present,
                items_present=items_present,
                miscellaneous_state_relations=_miscellaneous_state_relations_for_room(
                    room_id, graph.facts
                ),
            )
        )

    world_state = WorldState(rooms=room_views)
    unresolved_conflicts = _build_conflict_summaries(graph.conflicts)

    return NarrativeView(
        player_state=player_state,
        world_state=world_state,
        unresolved_conflicts=unresolved_conflicts,
    )


if __name__ == "__main__":
    import sys
    import json
    import os
    import dotenv
    dotenv.load_dotenv()

    data_dir = os.environ.get("DATA_DIR")

    graph_filename = os.path.join(data_dir, "processed_output", sys.argv[1])
    with open(graph_filename, "r") as f:
        graph = KnowledgeGraph.model_validate_json(f.read())
    narrative_view = craft_narrative_view(graph)
    
    output_filename = os.path.join(data_dir, "processed_output", sys.argv[1] + "_narrative_view_output.json")
    with open(output_filename, "w") as f:
        f.write(narrative_view.model_dump_json(indent=2))
