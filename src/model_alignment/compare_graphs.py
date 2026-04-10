from __future__ import annotations

import os
from typing import Dict, Any, Tuple, FrozenSet, List

import dotenv
from openai import OpenAI

from pydantic_schema import (
    KnowledgeGraphExtraction,
    Event,
    StateRelation,
    SpatialRelation,
    ConfidenceLevel,
    Entity,
    Participants,
)


dotenv.load_dotenv()


def _event_signature(event: Event) -> Tuple[str, FrozenSet[Tuple[str, str]]]:
    """
    Minimal event signature for comparison:
    (event_type, frozenset(participants.items()))
    Timestamps and locations are intentionally ignored.
    """
    participants_dict = event.participants.model_dump(exclude_none=True)
    return (
        event.event_type.value,
        frozenset(participants_dict.items()),
    )


def _state_relation_key(rel: StateRelation) -> Tuple[str, str, str]:
    """
    State relations are identical iff (subject, relation, object) match.
    """
    return rel.subject, rel.relation.value, rel.object


def _spatial_relation_key(rel: SpatialRelation) -> Tuple[str, str, str]:
    """
    Spatial relations are identical iff (subject, relation, object) match.
    """
    return rel.subject, rel.relation.value, rel.object


def _normalize_entity_id(entity_id: str) -> str:
    """
    Canonical form for matching ids: lowercase, strip, then remove all
    underscores and whitespace so e.g. room1, room_1, and "room 1" align,
    and red_room matches red room.
    """
    s = entity_id.strip().lower()
    return "".join(ch for ch in s if ch not in "_ \t\n\r\f\v")

def _build_entity_mapping(
    base_entities: List[Entity],
    candidate_entities: List[Entity],
) -> Dict[str, str]:
    """
    Build a mapping from candidate entity ids -> base entity ids,
    using both exact id matches, normalization (case/underscore/space-insensitivity), 
    and an LLM to resolve ambiguous cases.
    """
    mapping: Dict[str, str] = {}

    # Build normalization mapping for base entity ids
    base_ids = {e.id for e in base_entities}
    base_by_type: Dict[str, List[str]] = {}
    normal_to_base_ids: Dict[str, str] = {}

    for e in base_entities:
        base_by_type.setdefault(e.type.value, []).append(e.id)
        normal_to_base_ids[_normalize_entity_id(e.id)] = e.id

    # Exact id matches first
    for e in candidate_entities:
        if e.id in base_ids:
            mapping[e.id] = e.id

    # Normalized id matches (skip exacts)
    for e in candidate_entities:
        if e.id in mapping:
            continue
        normalized = _normalize_entity_id(e.id)
        if normalized in normal_to_base_ids:
            mapping[e.id] = normal_to_base_ids[normalized]


    # Use LLM for ambiguous cases
    client: OpenAI | None = None
    model = "gpt-4o-mini"
    temperature = 0

    for e in candidate_entities:
        if e.id in mapping:
            continue

        candidate_type = e.type.value
        base_candidates = base_by_type.get(candidate_type, [])
        if not base_candidates:
            continue

        options_str = ", ".join(base_candidates)
        prompt = (
            f'Does "{e.id}" refer to one of these entities?\n'
            f"[{options_str}]\n\n"
            "Respond with exactly one of the listed entity names, or NONE if there is no match."
        )

        if client is None:
            client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

        try:
            response = client.responses.create(
                model=model,
                input=[{"role": "user", "content": prompt}],
                temperature=temperature,
            )
        except Exception:
            # If the LLM call fails, skip this entity
            print(f"Failed to resolve entity id {e.id} using LLM -- exception raised: {e}")
            continue

        try:
            text = response.output[0].content[0].text.strip()
        except Exception:
            continue

        cleaned = text.strip().strip('"').strip("'")
        if cleaned.upper() == "NONE":
            continue

        if cleaned in base_candidates:
            mapping[e.id] = cleaned
        else:
            print(f"Failed to resolve entity id {e.id} using LLM -- response: {text}")

    return mapping


def _map_entity_id(entity_id: str, mapping: Dict[str, str]) -> str:
    return mapping.get(entity_id, entity_id)


def _event_with_mapped_entities(ev: Event, mapping: Dict[str, str]) -> Event:
    p = ev.participants
    return ev.model_copy(
        update={
            "participants": Participants(
                actor=_map_entity_id(p.actor, mapping) if p.actor is not None else None,
                object=_map_entity_id(p.object, mapping) if p.object is not None else None,
                target=_map_entity_id(p.target, mapping) if p.target is not None else None,
            ),
            "location": (
                _map_entity_id(ev.location, mapping)
                if ev.location is not None
                else None
            ),
        }
    )


def _state_relation_with_mapped_entities(
    rel: StateRelation, mapping: Dict[str, str]
) -> StateRelation:
    return rel.model_copy(
        update={
            "subject": _map_entity_id(rel.subject, mapping),
            "object": _map_entity_id(rel.object, mapping),
        }
    )


def _spatial_relation_with_mapped_entities(
    rel: SpatialRelation, mapping: Dict[str, str]
) -> SpatialRelation:
    return rel.model_copy(
        update={
            "subject": _map_entity_id(rel.subject, mapping),
            "object": _map_entity_id(rel.object, mapping),
        }
    )


def _diff_item(
    kind: str, value: Event | StateRelation | SpatialRelation
) -> Dict[str, Any]:
    return {"kind": kind, "value": value.model_dump()}


def compare_graphs(
    base: KnowledgeGraphExtraction,
    candidate: KnowledgeGraphExtraction,
) -> Dict[str, Any]:
    """
    Compute a diff between two knowledge graphs.

    The `base` graph is treated as the reference; `candidate` is compared to it.
    Before comparison, we align entity ids between graphs (normalization + LLM).
    Serialized fact payloads (already_present, novel_*, conflicts, uncertain) use
    those mapped ids so consumers such as merge_graphs stay consistent with base.

    Returns a JSON-serialisable dict with keys:
      - already_present: events or state/spatial relations that also appear in `base`
      - novel_events: events only present in `candidate`
      - novel_state_relations: state relations only present in `candidate`
      - novel_spatial_relations: spatial relations only present in `candidate`
      - novel_entities: entity ids referenced in `candidate` (after mapping) not in `base.entities`
      - entity_conflicts: same entity id in both graphs with different type
      - conflicts: items in `candidate` that contradict `base`
      - uncertain: low-confidence items in `candidate` that are neither present nor conflicting
    """
    result: Dict[str, Any] = {
        "already_present": [],
        "novel_events": [],
        "novel_state_relations": [],
        "novel_spatial_relations": [],
        "novel_entities": [],
        "entity_conflicts": [],
        "conflicts": [],
        "uncertain": [],
    }

    # ----------------------------------------
    # Resolve entity ids across graphs (LLM)
    # ----------------------------------------
    entity_mapping = _build_entity_mapping(base.entities, candidate.entities)

    base_entity_ids = {e.id for e in base.entities}
    base_entity_type_by_id = {e.id: e.type.value for e in base.entities}

    # ----------------------------------------
    # Novel entities: referenced in candidate but not in base (after mapping)
    # ----------------------------------------
    def _candidate_referenced_ids() -> set:
        ids = set()
        for e in candidate.entities:
            ids.add(e.id)
        for ev in candidate.events:
            p = ev.participants.model_dump(exclude_none=True)
            for v in p.values():
                ids.add(v)
            if ev.location is not None:
                ids.add(ev.location)
        for rel in candidate.state_relations:
            ids.add(rel.subject)
            ids.add(rel.object)
        for rel in candidate.spatial_relations:
            ids.add(rel.subject)
            ids.add(rel.object)
        return ids

    for cid in _candidate_referenced_ids():
        resolved_id = _map_entity_id(cid, entity_mapping)
        if resolved_id not in base_entity_ids:
            if resolved_id not in result["novel_entities"]:
                result["novel_entities"].append(resolved_id)

    # ----------------------------------------
    # Entity conflicts: same id in both, different type
    # ----------------------------------------
    for e in candidate.entities:
        resolved_id = _map_entity_id(e.id, entity_mapping)
        if resolved_id in base_entity_ids and base_entity_type_by_id.get(resolved_id) != e.type.value:
            result["entity_conflicts"].append({
                "entity_id": resolved_id,
                "base_type": base_entity_type_by_id[resolved_id],
                "candidate_type": e.type.value,
            })

    # ----------------------------------------
    # Precompute indices for the base graph
    # ----------------------------------------

    # Events
    base_event_sigs = {_event_signature(e) for e in base.events}

    # Map participant sets to event types for conflict detection
    base_participants_to_types: Dict[FrozenSet[Tuple[str, str]], FrozenSet[str]] = {}
    for e in base.events:
        sig_type, participants = _event_signature(e)
        existing = base_participants_to_types.get(participants, frozenset())
        base_participants_to_types[participants] = existing.union({sig_type})

    # State relations
    base_state_keys = {_state_relation_key(r) for r in base.state_relations}

    # Map (subject, relation) to objects for conflict detection
    base_state_by_subj_rel: Dict[Tuple[str, str], FrozenSet[str]] = {}
    for r in base.state_relations:
        key = (r.subject, r.relation.value)
        existing_objs = base_state_by_subj_rel.get(key, frozenset())
        base_state_by_subj_rel[key] = existing_objs.union({r.object})

    # Spatial relations
    base_spatial_keys = {_spatial_relation_key(r) for r in base.spatial_relations}
    base_spatial_by_subj_rel: Dict[Tuple[str, str], FrozenSet[str]] = {}
    for r in base.spatial_relations:
        key = (r.subject, r.relation.value)
        existing_objs = base_spatial_by_subj_rel.get(key, frozenset())
        base_spatial_by_subj_rel[key] = existing_objs.union({r.object})

    # ----------------------------------------
    # Compare events (with mapped entity ids)
    # ----------------------------------------
    for ev in candidate.events:
        participants_dict = ev.participants.model_dump(exclude_none=True)
        mapped_participants = {
            role: _map_entity_id(ent_id, entity_mapping)
            for role, ent_id in participants_dict.items()
        }
        participants_frozen: FrozenSet[Tuple[str, str]] = frozenset(
            mapped_participants.items()
        )
        sig_type = ev.event_type.value
        sig = (sig_type, participants_frozen)

        ev_out = _event_with_mapped_entities(ev, entity_mapping)

        if sig in base_event_sigs:
            result["already_present"].append(_diff_item("event", ev_out))
            continue

        # Possible conflict: same participants but different event type
        base_types_for_participants = base_participants_to_types.get(
            participants_frozen
        )
        if base_types_for_participants and sig_type not in base_types_for_participants:
            result["conflicts"].append(_diff_item("event", ev_out))
            continue

        # Uncertain: low/medium confidence, not present, not conflicting
        if ev.confidence != ConfidenceLevel.HIGH:
            result["uncertain"].append(_diff_item("event", ev_out))
            continue

        # Otherwise, this is a genuinely novel event
        result["novel_events"].append(_diff_item("event", ev_out))

    # ----------------------------------------
    # Compare state relations (with mapped entity ids)
    # ----------------------------------------
    for rel in candidate.state_relations:
        mapped_subject = _map_entity_id(rel.subject, entity_mapping)
        mapped_object = _map_entity_id(rel.object, entity_mapping)
        key = (mapped_subject, rel.relation.value, mapped_object)
        rel_out = _state_relation_with_mapped_entities(rel, entity_mapping)

        if key in base_state_keys:
            result["already_present"].append(_diff_item("state_relation", rel_out))
            continue

        subj_rel_key = (mapped_subject, rel.relation.value)
        base_objs_for_subj_rel = base_state_by_subj_rel.get(subj_rel_key, frozenset())

        # Conflict: same subject+relation, different object
        if base_objs_for_subj_rel and mapped_object not in base_objs_for_subj_rel:
            result["conflicts"].append(_diff_item("state_relation", rel_out))
            continue

        # Uncertain: low/medium confidence, not present, not conflicting
        if rel.confidence != ConfidenceLevel.HIGH:
            result["uncertain"].append(_diff_item("state_relation", rel_out))
            continue

        # Otherwise, this is a genuinely novel state relation
        result["novel_state_relations"].append(
            _diff_item("state_relation", rel_out)
        )

    # ----------------------------------------
    # Compare spatial relations (with mapped entity ids)
    # ----------------------------------------
    for rel in candidate.spatial_relations:
        mapped_subject = _map_entity_id(rel.subject, entity_mapping)
        mapped_object = _map_entity_id(rel.object, entity_mapping)
        key = (mapped_subject, rel.relation.value, mapped_object)
        rel_out = _spatial_relation_with_mapped_entities(rel, entity_mapping)

        if key in base_spatial_keys:
            result["already_present"].append(_diff_item("spatial_relation", rel_out))
            continue

        subj_rel_key = (mapped_subject, rel.relation.value)
        base_objs_for_subj_rel = base_spatial_by_subj_rel.get(subj_rel_key, frozenset())

        # Conflict: same subject+relation, different object
        if base_objs_for_subj_rel and mapped_object not in base_objs_for_subj_rel:
            result["conflicts"].append(_diff_item("spatial_relation", rel_out))
            continue

        # Uncertain: low/medium confidence, not present, not conflicting
        if rel.confidence != ConfidenceLevel.HIGH:
            result["uncertain"].append(_diff_item("spatial_relation", rel_out))
            continue

        # Otherwise, this is a genuinely novel spatial relation
        result["novel_spatial_relations"].append(
            _diff_item("spatial_relation", rel_out)
        )

    return result


__all__ = ["compare_graphs"]

if __name__ == "__main__":
    import sys
    import json
    data_dir = os.environ.get("DATA_DIR")

    # condition = "_user_report"
    condition = ""
    candidate_filename = os.path.join(data_dir, "processed_output", sys.argv[1] + condition + "_text_to_kg_output.json")
    base_filename = os.path.join(data_dir, "processed_output", sys.argv[1] + "_telemetry_to_kg_output.json")


    with open(base_filename, "r") as f:
        base = KnowledgeGraphExtraction.model_validate_json(f.read())
    with open(candidate_filename, "r") as f:
        candidate = KnowledgeGraphExtraction.model_validate_json(f.read())

    result = compare_graphs(base, candidate) 
    with open(os.path.join(data_dir, "processed_output", sys.argv[1] + "_compare_graphs_output.json"), "w") as f:
        json.dump(result, f, indent=2)
