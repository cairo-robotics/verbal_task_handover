from collections import defaultdict
from typing import Dict, List, Optional, Set, Tuple

from pydantic import BaseModel, Field

from pydantic_schema import (
    ConflictRecord,
    ConfidenceLevel,
    Entity,
    EntityType,
    Event,
    KnowledgeGraphExtraction,
    RelationType,
    SpatialRelation,
    SpatialRelationType,
    StateRelation,
)

# --- Output models -----------------------------------------------------------


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


class ItemRoomView(BaseModel):
    """Item located in a room, including any requires edges on that item."""

    id: str
    requirements: List[str] = Field(default_factory=list)


class LocatedOtherView(BaseModel):
    """Non-agent, non-item entity with located_in pointing at this room."""

    id: str
    entity_type: Optional[EntityType] = None
    requirements: List[str] = Field(default_factory=list)


class RoomView(BaseModel):
    name: str
    declared_as_location_entity: bool = True
    connected_to: List[RoomConnection]
    room_requirements: List[str] = Field(default_factory=list)
    characters_present: List[CharacterView]
    items_present: List[ItemRoomView]
    other_entities_present: List[LocatedOtherView] = Field(default_factory=list)


class WorldState(BaseModel):
    rooms: List[RoomView]
    characters_without_room_placement: List[CharacterView] = Field(
        default_factory=list,
        description="Agents with no located_in (or invalid) state relation.",
    )


class ConflictSummary(BaseModel):
    description: str
    involved_entities: List[str]


class StateEdgeOutgoing(BaseModel):
    relation: RelationType
    object: str
    confidence: ConfidenceLevel


class StateEdgeIncoming(BaseModel):
    relation: RelationType
    subject: str
    confidence: ConfidenceLevel


class EntityStateHub(BaseModel):
    """All state relations touching one entity id (as subject or object)."""

    entity_id: str
    entity_type: Optional[EntityType] = None
    outgoing: List[StateEdgeOutgoing] = Field(default_factory=list)
    incoming: List[StateEdgeIncoming] = Field(default_factory=list)


class NarrativeView(BaseModel):
    player_state: PlayerState
    world_state: WorldState
    unresolved_conflicts: List[ConflictSummary]
    # entity_state_index: List[EntityStateHub] = Field(
    #     default_factory=list,
    #     description="Per-entity index of state relations; covers ids only mentioned in relations.",
    # )
    # spatial_relations: List[SpatialRelation] = Field(
    #     default_factory=list,
    #     description="Full spatial relation list from the extraction (no filtering).",
    # )


# --- Helpers -----------------------------------------------------------------


def _get_player_entity(entities: List[Entity]) -> Entity:
    """Choose a player entity, defaulting to the first Agent if available."""
    for entity in entities:
        if entity.type == EntityType.AGENT and "player" in entity.id.lower():
            return entity
    return entities[0]


def _build_entity_state_index(
    entities_by_id: Dict[str, Entity],
    state_relations: List[StateRelation],
) -> List[EntityStateHub]:
    entity_ids: Set[str] = set(entities_by_id.keys())
    for rel in state_relations:
        entity_ids.add(rel.subject)
        entity_ids.add(rel.object)

    outgoing: Dict[str, List[StateEdgeOutgoing]] = defaultdict(list)
    incoming: Dict[str, List[StateEdgeIncoming]] = defaultdict(list)
    for rel in state_relations:
        outgoing[rel.subject].append(
            StateEdgeOutgoing(
                relation=rel.relation,
                object=rel.object,
                confidence=rel.confidence,
            )
        )
        incoming[rel.object].append(
            StateEdgeIncoming(
                relation=rel.relation,
                subject=rel.subject,
                confidence=rel.confidence,
            )
        )

    hubs: List[EntityStateHub] = []
    for eid in sorted(entity_ids):
        ent = entities_by_id.get(eid)
        hubs.append(
            EntityStateHub(
                entity_id=eid,
                entity_type=ent.type if ent else None,
                outgoing=outgoing[eid],
                incoming=incoming[eid],
            )
        )
    return hubs


def _requirements_by_subject(
    state_relations: List[StateRelation],
) -> Dict[str, List[str]]:
    requirements: Dict[str, List[str]] = defaultdict(list)
    for rel in state_relations:
        if rel.relation == RelationType.REQUIRES:
            requirements[rel.subject].append(rel.object)
    return requirements


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


def _agent_ids(entities_by_id: Dict[str, Entity]) -> Set[str]:
    return {
        eid
        for eid, ent in entities_by_id.items()
        if ent.type == EntityType.AGENT
    }


def _item_ids(entities_by_id: Dict[str, Entity]) -> Set[str]:
    return {
        eid
        for eid, ent in entities_by_id.items()
        if ent.type == EntityType.ITEM
    }


def _located_in_targets(state_relations: List[StateRelation]) -> Set[str]:
    return {
        rel.object
        for rel in state_relations
        if rel.relation == RelationType.LOCATED_IN
    }


def _items_in_any_inventory(state_relations: List[StateRelation]) -> Set[str]:
    return {
        rel.subject
        for rel in state_relations
        if rel.relation == RelationType.IN_INVENTORY_OF
    }


def _partition_located_subjects(
    entities_by_id: Dict[str, Entity],
    state_relations: List[StateRelation],
) -> Tuple[Dict[str, List[str]], Dict[str, List[str]], Dict[str, List[str]]]:
    """
    For each room id (located_in object), partition subjects into agents, items,
    and other (unknown id, or known non-agent non-item).
    """
    agent_ids = _agent_ids(entities_by_id)
    item_ids = _item_ids(entities_by_id)
    in_inventory = _items_in_any_inventory(state_relations)

    characters_by_room: Dict[str, List[str]] = defaultdict(list)
    items_by_room: Dict[str, List[str]] = defaultdict(list)
    other_by_room: Dict[str, List[str]] = defaultdict(list)

    for rel in state_relations:
        if rel.relation != RelationType.LOCATED_IN:
            continue
        room_id = rel.object
        sid = rel.subject
        ent = entities_by_id.get(sid)

        if sid in agent_ids:
            characters_by_room[room_id].append(sid)
        elif sid in item_ids:
            if sid in in_inventory:
                continue
            items_by_room[room_id].append(sid)
        else:
            # Unknown id, or Message / other declared type
            other_by_room[room_id].append(sid)

    return characters_by_room, items_by_room, other_by_room


def _character_view(
    char_id: str,
    interaction_history_by_character: Dict[str, List[str]],
    requirements_by_subject: Dict[str, List[str]],
) -> CharacterView:
    return CharacterView(
        name=char_id,
        interaction_history=interaction_history_by_character.get(char_id, []),
        requirements=requirements_by_subject.get(char_id, []),
    )


def _build_room_view(
    room_id: str,
    *,
    declared_as_location_entity: bool,
    entities_by_id: Dict[str, Entity],
    characters_by_room: Dict[str, List[str]],
    items_by_room: Dict[str, List[str]],
    other_by_room: Dict[str, List[str]],
    requirements_by_subject: Dict[str, List[str]],
    connections_by_room: Dict[str, List[RoomConnection]],
    interaction_history_by_character: Dict[str, List[str]],
) -> RoomView:
    character_ids = characters_by_room.get(room_id, [])
    characters_present = [
        _character_view(
            char_id,
            interaction_history_by_character,
            requirements_by_subject,
        )
        for char_id in character_ids
    ]

    items_present = [
        ItemRoomView(
            id=item_id,
            requirements=requirements_by_subject.get(item_id, []),
        )
        for item_id in items_by_room.get(room_id, [])
    ]

    other_entities_present: List[LocatedOtherView] = []
    for oid in other_by_room.get(room_id, []):
        oent = entities_by_id.get(oid)
        other_entities_present.append(
            LocatedOtherView(
                id=oid,
                entity_type=oent.type if oent else None,
                requirements=requirements_by_subject.get(oid, []),
            )
        )

    return RoomView(
        name=room_id,
        declared_as_location_entity=declared_as_location_entity,
        connected_to=connections_by_room.get(room_id, []),
        room_requirements=requirements_by_subject.get(room_id, []),
        characters_present=characters_present,
        items_present=items_present,
        other_entities_present=other_entities_present,
    )


def _build_interaction_history_by_character(
    events: List[Event],
) -> Dict[str, List[str]]:
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
        connections_by_room[rel.subject].append(
            RoomConnection(direction=rel.relation, room=rel.object)
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

    State relations are indexed per entity in ``entity_state_index``. Room layouts
    include declared Location entities plus any located_in targets that are not
    declared locations. All spatial relations are copied verbatim to
    ``spatial_relations``.
    """
    unresolved_conflicts = _build_conflict_summaries(extraction.conflicts)
    spatial_relations = list(extraction.spatial_relations)

    if not extraction.entities:
        return NarrativeView(
            player_state=PlayerState(inventory=[], current_location=""),
            world_state=WorldState(rooms=[]),
            unresolved_conflicts=unresolved_conflicts,
            # entity_state_index=_build_entity_state_index({}, extraction.state_relations),
            # spatial_relations=spatial_relations,
        )

    entities_by_id: Dict[str, Entity] = {
        entity.id: entity for entity in extraction.entities
    }

    # entity_state_index = _build_entity_state_index(
    #     entities_by_id, extraction.state_relations
    # )

    player_entity = _get_player_entity(extraction.entities)
    player_id = player_entity.id

    player_state = PlayerState(
        inventory=_build_inventory(player_id, extraction.state_relations),
        current_location=_get_player_location(player_id, extraction.state_relations),
    )

    requirements_by_subject = _requirements_by_subject(extraction.state_relations)
    (
        characters_by_room,
        items_by_room,
        other_by_room,
    ) = _partition_located_subjects(entities_by_id, extraction.state_relations)

    connections_by_room = _build_connections_by_room(extraction.spatial_relations)
    interaction_history_by_character = _build_interaction_history_by_character(
        extraction.events
    )

    location_entity_ids = {
        e.id for e in extraction.entities if e.type == EntityType.LOCATION
    }
    implicit_room_ids = sorted(
        _located_in_targets(extraction.state_relations) - location_entity_ids
    )

    room_views: List[RoomView] = []
    for entity in extraction.entities:
        if entity.type != EntityType.LOCATION:
            continue
        room_views.append(
            _build_room_view(
                entity.id,
                declared_as_location_entity=True,
                entities_by_id=entities_by_id,
                characters_by_room=characters_by_room,
                items_by_room=items_by_room,
                other_by_room=other_by_room,
                requirements_by_subject=requirements_by_subject,
                connections_by_room=connections_by_room,
                interaction_history_by_character=interaction_history_by_character,
            )
        )

    for room_id in implicit_room_ids:
        room_views.append(
            _build_room_view(
                room_id,
                declared_as_location_entity=False,
                entities_by_id=entities_by_id,
                characters_by_room=characters_by_room,
                items_by_room=items_by_room,
                other_by_room=other_by_room,
                requirements_by_subject=requirements_by_subject,
                connections_by_room=connections_by_room,
                interaction_history_by_character=interaction_history_by_character,
            )
        )

    agent_ids = _agent_ids(entities_by_id)
    placed_agents: Set[str] = set()
    for rel in extraction.state_relations:
        if rel.relation == RelationType.LOCATED_IN and rel.subject in agent_ids:
            placed_agents.add(rel.subject)

    characters_without_room_placement: List[CharacterView] = []
    for aid in sorted(agent_ids):
        if "player" not in aid and aid not in placed_agents:
            characters_without_room_placement.append(
                _character_view(
                    aid,
                    interaction_history_by_character,
                    requirements_by_subject,
                )
            )

    world_state = WorldState(
        rooms=room_views,
        characters_without_room_placement=characters_without_room_placement,
    )

    return NarrativeView(
        player_state=player_state,
        world_state=world_state,
        unresolved_conflicts=unresolved_conflicts,
        # entity_state_index=entity_state_index,
        # spatial_relations=spatial_relations,
    )


if __name__ == "__main__":
    import json
    import os
    import sys

    data_dir = os.environ.get("DATA_DIR")

    extraction_filename = os.path.join(
        data_dir, "processed_output", sys.argv[1] + "_merge_graphs_output.json"
    )
    with open(extraction_filename, "r") as f:
        extraction = KnowledgeGraphExtraction.model_validate_json(f.read())
    narrative_view = craft_narrative_view(extraction)
    with open(
        os.path.join(
            data_dir, "processed_output", sys.argv[1] + "_narrative_view_output.json"
        ),
        "w",
    ) as f:
        f.write(narrative_view.model_dump_json())
