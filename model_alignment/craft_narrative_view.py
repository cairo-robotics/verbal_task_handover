from collections import defaultdict
from typing import Dict, List

from pydantic import BaseModel, Field

from pydantic_schema import (
    ConflictRecord,
    Entity,
    EntityType,
    Event,
    EventType,
    KnowledgeGraphExtraction,
    RelationType,
    SpatialRelation,
    SpatialRelationType,
    StateRelation,
)

class PlayerState(BaseModel):
    inventory: List[str]
    current_location: str

class RoomConnection(BaseModel):
    direction: SpatialRelationType
    room: str

class CharacterView(BaseModel):
    name: str
    interaction_history: List[str]
    requirements: List[str]

class RoomView(BaseModel):
    name: str
    connected_to: List[RoomConnection]
    characters_present: List[CharacterView]
    items_present: List[str]

class WorldState(BaseModel):
    rooms: List[RoomView]

class ConflictSummary(BaseModel):
    description: str
    involved_entities: List[str]

class NarrativeView(BaseModel):
    player_state: PlayerState
    world_state: WorldState
    unresolved_conflicts: List[ConflictSummary]


def _get_player_entity(entities: List[Entity]) -> Entity:
    """Choose a player entity, defaulting to the first Agent if available."""
    for entity in entities:
        if entity.type == EntityType.AGENT and "player" in entity.id.lower():
            return entity
    # Fallback: just return the first entity; caller should handle None if list is empty
    return entities[0]


def _build_inventory(
    player_id: str, state_relations: List[StateRelation]
) -> List[str]:
    inventory_items: List[str] = []
    for rel in state_relations:
        if (
            rel.relation == RelationType.IN_INVENTORY_OF
            and rel.object == player_id
        ):
            inventory_items.append(rel.subject)
    return inventory_items


def _get_player_location(
    player_id: str, state_relations: List[StateRelation]
) -> str:
    for rel in state_relations:
        if (
            rel.relation == RelationType.LOCATED_IN
            and rel.subject == player_id
        ):
            return rel.object
    return ""


def _build_requirements_by_character(
    state_relations: List[StateRelation],
) -> Dict[str, List[str]]:
    requirements: Dict[str, List[str]] = defaultdict(list)
    for rel in state_relations:
        if rel.relation == RelationType.REQUIRES:
            requirements[rel.subject].append(rel.object)
    return requirements


def _build_characters_by_room(
    entities_by_id: Dict[str, Entity],
    state_relations: List[StateRelation],
) -> Dict[str, List[str]]:
    characters_by_room: Dict[str, List[str]] = defaultdict(list)
    for rel in state_relations:
        if rel.relation != RelationType.LOCATED_IN:
            continue
        entity = entities_by_id.get(rel.subject)
        if entity is None or entity.type != EntityType.AGENT:
            continue
        characters_by_room[rel.object].append(rel.subject)
    return characters_by_room


def _build_items_by_room(
    entities_by_id: Dict[str, Entity],
    state_relations: List[StateRelation],
) -> Dict[str, List[str]]:
    items_by_room: Dict[str, List[str]] = defaultdict(list)
    item_ids = {
        entity_id
        for entity_id, entity in entities_by_id.items()
        if entity.type == EntityType.ITEM
    }

    items_in_any_inventory = {
        rel.subject
        for rel in state_relations
        if rel.relation == RelationType.IN_INVENTORY_OF
    }

    for rel in state_relations:
        if rel.relation != RelationType.LOCATED_IN:
            continue
        if rel.subject not in item_ids:
            continue
        if rel.subject in items_in_any_inventory:
            # Items in an inventory should not also show as present in a room
            continue
        items_by_room[rel.object].append(rel.subject)

    return items_by_room


def _build_interaction_history_by_character(
    events: List[Event],
) -> Dict[str, List[str]]:
    """Map character (agent) id -> list of interaction summary strings."""
    history: Dict[str, List[str]] = defaultdict(list)

    for event in events:
        participant_ids = [
            pid
            for pid in [
                event.participants.actor,
                event.participants.object,
                event.participants.target,
            ]
            if pid is not None
        ]
        if not participant_ids:
            continue

        unique_ids = list(dict.fromkeys(participant_ids))

        for pid in unique_ids:
            other_participants = [x for x in unique_ids if x != pid]
            if other_participants:
                # summary = (
                #     f"{event.event_type.value} with "
                #     # f"{', '.join(other_participants)}"
                #     f"{event.participants.}"
                # )
                if event.participants.object:
                    summary = f"{event.event_type.value} {event.participants.object} by {event.participants.actor}"
                else:
                    summary = f"{event.event_type.value} {event.participants.actor}"
            else:
                summary = event.event_type.value

            history[pid].append(summary)

    return history


def _build_connections_by_room(
    spatial_relations: List[SpatialRelation],
) -> Dict[str, List[RoomConnection]]:
    connections_by_room: Dict[str, List[RoomConnection]] = defaultdict(list)

    for rel in spatial_relations:
        subject_room = rel.subject
        object_room = rel.object
        direction = rel.relation

        connections_by_room[subject_room].append(
            RoomConnection(direction=direction, room=object_room)
        )

    return connections_by_room


def _build_conflict_summaries(
    conflicts: List[ConflictRecord],
) -> List[ConflictSummary]:
    summaries: List[ConflictSummary] = []
    for conflict in conflicts:
        description = (
            f"{conflict.conflict_type}: "
            f"{conflict.new_fact_id} vs {conflict.existing_fact_id}"
        )
        summaries.append(
            ConflictSummary(
                description=description,
                involved_entities=[
                    conflict.new_fact_id,
                    conflict.existing_fact_id,
                ],
            )
        )
    return summaries


def craft_narrative_view(
    extraction: KnowledgeGraphExtraction,
) -> NarrativeView:
    """
    Transform a KnowledgeGraphExtraction into a NarrativeView.

    Assumptions:
    - The "player" is the first Entity with type Agent.
    - Entity IDs are human-readable names for rooms, characters, and items.
    """
    if not extraction.entities:
        player_state = PlayerState(inventory=[], current_location="")
        world_state = WorldState(rooms=[])
        unresolved_conflicts: List[ConflictSummary] = []
        return NarrativeView(
            player_state=player_state,
            world_state=world_state,
            unresolved_conflicts=unresolved_conflicts,
        )

    entities_by_id: Dict[str, Entity] = {
        entity.id: entity for entity in extraction.entities
    }

    player_entity = _get_player_entity(extraction.entities)
    player_id = player_entity.id

    inventory = _build_inventory(player_id, extraction.state_relations)
    current_location = _get_player_location(
        player_id, extraction.state_relations
    )
    player_state = PlayerState(
        inventory=inventory,
        current_location=current_location,
    )

    requirements_by_character = _build_requirements_by_character(
        extraction.state_relations
    )
    characters_by_room = _build_characters_by_room(
        entities_by_id, extraction.state_relations
    )
    items_by_room = _build_items_by_room(
        entities_by_id, extraction.state_relations
    )
    connections_by_room = _build_connections_by_room(
        extraction.spatial_relations
    )
    interaction_history_by_character = _build_interaction_history_by_character(
        extraction.events
    )

    room_views: List[RoomView] = []
    for entity in extraction.entities:
        if entity.type != EntityType.LOCATION:
            continue

        room_id = entity.id

        room_connections = connections_by_room.get(room_id, [])

        character_ids = characters_by_room.get(room_id, [])
        characters_present = [
            CharacterView(
                name=char_id,
                interaction_history=interaction_history_by_character.get(
                    char_id, []
                ),
                requirements=requirements_by_character.get(char_id, []),
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
            )
        )

    world_state = WorldState(rooms=room_views)
    unresolved_conflicts = _build_conflict_summaries(extraction.conflicts)

    return NarrativeView(
        player_state=player_state,
        world_state=world_state,
        unresolved_conflicts=unresolved_conflicts,
    )


if __name__ == "__main__":
    import sys
    import json
    import os
    data_dir = os.environ.get("DATA_DIR")

    extraction_filename = os.path.join(data_dir, "processed_output", sys.argv[1] + "_merge_graphs_output.json")
    with open(extraction_filename, "r") as f:
        extraction = KnowledgeGraphExtraction.model_validate_json(f.read())
    narrative_view = craft_narrative_view(extraction)
    # print(narrative_view.model_dump_json())
    with open(os.path.join(data_dir, "processed_output", sys.argv[1] + "_narrative_view_output.json"), "w") as f:
        f.write(narrative_view.model_dump_json())