from __future__ import annotations

from typing import Dict, Any, List, Tuple

from pydantic_schema import (
    KnowledgeGraphExtraction,
    Event,
    StateRelation,
    SpatialRelation,
    ConflictRecord,
    UpdateRecord,
    RelationType,
    EventType,
    Entity,
    EntityType,
)

from telemetry_to_graph import infer_entity_type

import dotenv

dotenv.load_dotenv()


def _state_relation_id(rel: StateRelation) -> str:
    """
    Create a stable string identifier for a state relation.
    """
    return f"state:{rel.subject}|{rel.relation.value}|{rel.object}"


def _spatial_relation_id(rel: SpatialRelation) -> str:
    """
    Create a stable string identifier for a spatial relation.
    """
    return f"spatial:{rel.subject}|{rel.relation.value}|{rel.object}"


def _find_conflicting_events(
    base: KnowledgeGraphExtraction,
    new_event: Event,
) -> List[Event]:
    """
    Find events in the base graph that conflict with `new_event`.
    Conflict definition: same participants, different event_type.
    """
    new_parts = new_event.participants.model_dump(exclude_none=True)
    conflicts: List[Event] = []
    for ev in base.events:
        if ev.event_id == new_event.event_id:
            continue
        if ev.participants.model_dump(exclude_none=True) == new_parts and ev.event_type != new_event.event_type:
            conflicts.append(ev)
    return conflicts


def _find_conflicting_state_relations(
    base: KnowledgeGraphExtraction,
    new_rel: StateRelation,
) -> List[StateRelation]:
    """
    Find state relations in the base graph that conflict with `new_rel`.
    Conflict definition: same subject and relation, different object.
    """
    conflicts: List[StateRelation] = []
    for rel in base.state_relations:
        if rel.subject == new_rel.subject and rel.relation == new_rel.relation and rel.object != new_rel.object:
            conflicts.append(rel)
    return conflicts


def _find_conflicting_spatial_relations(
    base: KnowledgeGraphExtraction,
    new_rel: SpatialRelation,
) -> List[SpatialRelation]:
    """
    Find spatial relations in the base graph that conflict with `new_rel`.
    Conflict definition: same subject and relation, different object.
    """
    conflicts: List[SpatialRelation] = []
    for rel in base.spatial_relations:
        if rel.subject == new_rel.subject and rel.relation == new_rel.relation and rel.object != new_rel.object:
            conflicts.append(rel)
    return conflicts


def _state_exists(
    graph: KnowledgeGraphExtraction,
    subject: str,
    relation: RelationType,
    obj: str,
) -> bool:
    for rel in graph.state_relations:
        if (
            rel.subject == subject
            and rel.relation == relation
            and rel.object == obj
        ):
            return True
    return False


def apply_event_effects(event: Event, graph: KnowledgeGraphExtraction) -> None:
    """
    Apply deterministic effects of an event to keep state consistent.
    Currently:
      - OBTAIN(actor, object) => (object, IN_INVENTORY_OF, actor)
    """
    if event.event_type == EventType.OBTAIN:
        actor = event.participants.actor
        obj = event.participants.object
        if actor is None or obj is None:
            return

        if not _state_exists(graph, obj, RelationType.IN_INVENTORY_OF, actor):
            graph.state_relations.append(
                StateRelation(
                    subject=obj,
                    relation=RelationType.IN_INVENTORY_OF,
                    object=actor,
                    confidence=event.confidence,
                    source=event.source,
                )
            )


def _collect_referenced_entity_ids(graph: KnowledgeGraphExtraction) -> set:
    """
    Collect every entity id referenced in events, state_relations, and spatial_relations.
    """
    ids: set = set()
    for ev in graph.events:
        p = ev.participants
        if p.actor is not None:
            ids.add(p.actor)
        if p.object is not None:
            ids.add(p.object)
        if p.target is not None:
            ids.add(p.target)
        if ev.location is not None:
            ids.add(ev.location)
    for rel in graph.state_relations:
        ids.add(rel.subject)
        ids.add(rel.object)
    for rel in graph.spatial_relations:
        ids.add(rel.subject)
        ids.add(rel.object)
    return ids


def _backfill_entities(graph: KnowledgeGraphExtraction) -> List[str]:
    """
    Ensure every entity id referenced in the graph exists in graph.entities.
    Appends missing entities with inferred type. Returns list of added entity ids.
    """
    existing_ids = {e.id for e in graph.entities}
    referenced = _collect_referenced_entity_ids(graph)
    added: List[str] = []
    for eid in referenced:
        if eid in existing_ids:
            continue
        graph.entities.append(
            Entity(id=eid, type=infer_entity_type(eid))
        )
        existing_ids.add(eid)
        added.append(eid)
    return added


def merge_graphs(
    base: KnowledgeGraphExtraction,
    diff: Dict[str, Any],
) -> Tuple[KnowledgeGraphExtraction, UpdateRecord]:
    """
    Update the base graph using the JSON diff produced by `compare_graphs`.

    - Novel events and state relations are directly added to the base graph.
    - For conflicts, the new fact is added and corresponding ConflictRecord
      objects are appended to `base.conflicts`.

    Returns the updated graph and an UpdateRecord summarising changes.
    """
    added_events: List[str] = []
    added_state_relations: List[str] = []
    added_spatial_relations: List[str] = []
    added_entities: List[str] = []
    conflicts_created: List[str] = []

    # Ensure conflicts list exists
    if base.conflicts is None:
        base.conflicts = []

    conflict_index = len(base.conflicts)

    # ----------------------------------------
    # Add novel events
    # ----------------------------------------
    for item in diff.get("novel_events", []):
        if item.get("kind") != "event":
            continue
        ev = Event.model_validate(item["value"])
        ev.source = "user"
        base.events.append(ev)
        added_events.append(ev.event_id)
        apply_event_effects(ev, base)

    # ----------------------------------------
    # Add novel state relations
    # ----------------------------------------
    for item in diff.get("novel_state_relations", []):
        if item.get("kind") != "state_relation":
            continue
        rel = StateRelation.model_validate(item["value"])
        rel.source = "user"
        base.state_relations.append(rel)
        added_state_relations.append(_state_relation_id(rel))

    # ----------------------------------------
    # Add novel spatial relations
    # ----------------------------------------
    for item in diff.get("novel_spatial_relations", []):
        if item.get("kind") != "spatial_relation":
            continue
        rel = SpatialRelation.model_validate(item["value"])
        rel.source = "user"
        base.spatial_relations.append(rel)
        added_spatial_relations.append(_spatial_relation_id(rel))

    # ----------------------------------------
    # Handle conflicts
    # ----------------------------------------
    for item in diff.get("conflicts", []):
        kind = item.get("kind")
        value = item.get("value", {})

        if kind == "event":
            new_ev = Event.model_validate(value)
            new_ev.source = "user"
            base.events.append(new_ev)
            added_events.append(new_ev.event_id)
            apply_event_effects(new_ev, base)

            existing_events = _find_conflicting_events(base, new_ev)
            for existing in existing_events:
                conflict_id = f"conflict_{conflict_index}"
                conflict_index += 1
                record = ConflictRecord(
                    conflict_id=conflict_id,
                    new_fact_id=new_ev.event_id,
                    existing_fact_id=existing.event_id,
                    conflict_type="event",
                )
                base.conflicts.append(record)
                conflicts_created.append(conflict_id)

        elif kind == "state_relation":
            new_rel = StateRelation.model_validate(value)
            new_rel.source = "user"
            base.state_relations.append(new_rel)
            new_rel_id = _state_relation_id(new_rel)
            added_state_relations.append(new_rel_id)

            existing_rels = _find_conflicting_state_relations(base, new_rel)
            for existing in existing_rels:
                conflict_id = f"conflict_{conflict_index}"
                conflict_index += 1
                record = ConflictRecord(
                    conflict_id=conflict_id,
                    new_fact_id=new_rel_id,
                    existing_fact_id=_state_relation_id(existing),
                    conflict_type="state_relation",
                )
                base.conflicts.append(record)
                conflicts_created.append(conflict_id)

        elif kind == "spatial_relation":
            new_rel = SpatialRelation.model_validate(value)
            new_rel.source = "user"
            base.spatial_relations.append(new_rel)
            new_rel_id = _spatial_relation_id(new_rel)
            added_spatial_relations.append(new_rel_id)

            existing_rels = _find_conflicting_spatial_relations(base, new_rel)
            for existing in existing_rels:
                conflict_id = f"conflict_{conflict_index}"
                conflict_index += 1
                record = ConflictRecord(
                    conflict_id=conflict_id,
                    new_fact_id=new_rel_id,
                    existing_fact_id=_spatial_relation_id(existing),
                    conflict_type="spatial_relation",
                )
                base.conflicts.append(record)
                conflicts_created.append(conflict_id)

    # ----------------------------------------
    # Backfill entities: ensure every referenced id is in base.entities
    # ----------------------------------------
    added_entities = _backfill_entities(base)

    update_log = UpdateRecord(
        added_events=added_events,
        added_state_relations=added_state_relations,
        added_spatial_relations=added_spatial_relations,
        added_entities=added_entities,
        conflicts_created=conflicts_created,
    )

    return base, update_log


__all__ = ["merge_graphs"]

if __name__ == "__main__":
    import sys
    import json
    import os
    data_dir = os.environ.get("DATA_DIR")

    base_filename = os.path.join(data_dir, "processed_output", sys.argv[1] + "_telemetry_to_kg_output.json")
    diff_filename = os.path.join(data_dir, "processed_output", sys.argv[1] + "_compare_graphs_output.json")

    with open(base_filename, "r") as f:
        base = KnowledgeGraphExtraction.model_validate_json(f.read())
    with open(diff_filename, "r") as f:
        diff = json.load(f)

    result, update_log = merge_graphs(base, diff)
    with open(os.path.join(data_dir, "processed_output", sys.argv[1] + "_merge_graphs_output.json"), "w") as f:
        json.dump(result.model_dump(), f, indent=2)
    with open(os.path.join(data_dir, "processed_output", sys.argv[1] + "_merge_graphs_update_log.json"), "w") as f:
        json.dump(update_log.model_dump(), f, indent=2)