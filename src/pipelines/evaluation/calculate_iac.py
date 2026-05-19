import argparse
import json
import os
from dataclasses import asdict
from typing import Dict

from src.core.representations.pydantic_schema import (
    KnowledgeGraph, 
    Fact, 
    LocationFact, 
    SpatialFact, 
    SpatialRelationType, 
    Location,
    Direction,
    RelationFact,
    RelationPredicate,
    Argument
)
from src.pipelines.evaluation.costs import (
    CostConfig, 
    PATIENT_DATA, 
    EXPECTED_SEARCH_COSTS_PER_ROOM_TYPE,
    SEARCH_ROOMS_PER_ENTITY_TYPE
)
from src.pipelines.evaluation.map_graph import load_transitions
from src.pipelines.evaluation.report_iac import IACResult, EntityScore, ComponentScore, CreditType
from src.core.utils.spatial_reasoning import is_location_satisfying_constraint, ConnectionFact
from src.core.utils.normalization import normalize_entity_name

from treasure_hunt.src.game_mdp import GameState

DIAGNOSIS_COST = 5.0

def _load_game_state(pid: str) -> GameState:
    """Loads the GameState for a given player ID."""
    # Try current directory first
    if os.path.exists(f"{pid}.pkl"):
        return GameState.load(pid)
    
    # Try DATA_DIR
    data_dir = os.environ.get("DATA_DIR")
    if data_dir:
        path = os.path.join(data_dir, pid)
        if os.path.exists(f"{path}.pkl"):
            return GameState.load(path)
            
    return GameState.load(pid)

def _load_map_data(map_directory: str) -> Dict:
    transitions = load_transitions(os.path.join(map_directory, "transitions.json"))
    return transitions

def _get_all_rooms(map_graph: KnowledgeGraph) -> set[str]:
    """Extracts all unique room names from the knowledge graph."""
    rooms = set()
    for fact in map_graph.facts:
        if isinstance(fact, LocationFact):
            if fact.location.type == "room" and fact.location.room:
                rooms.add(fact.location.room)
        elif isinstance(fact, ConnectionFact):
            if fact.location_a.type == "room" and fact.location_a.room:
                rooms.add(fact.location_a.room)
            if fact.location_b.type == "room" and fact.location_b.room:
                rooms.add(fact.location_b.room)
    return rooms

def _normalize_room(room: str) -> str:
    """Robustly normalizes room names for consistency."""
    return normalize_entity_name(room)

def _describe_fact(fact: Fact) -> str:
    """Returns a compact, human-readable string for a Fact."""
    if isinstance(fact, LocationFact):
        entity_str = fact.entity.value if fact.entity.type == "named" else f"?({fact.entity.location})"
        loc = fact.location
        if loc.type == "room":
            return f"LocationFact: {entity_str} in {loc.room}"
        elif loc.type == "directional":
            dirs = ", ".join(str(d) for d in loc.directions)
            return f"LocationFact: {entity_str} direction [{dirs}]"
        return f"LocationFact: {entity_str} @ {loc}"
    elif isinstance(fact, SpatialFact):
        subj = fact.subject.value if fact.subject.type == "named" else "?"
        ref = fact.reference.value if fact.reference and fact.reference.type == "named" else "origin"
        return f"SpatialFact: {subj} {fact.direction} of {ref}"
    elif isinstance(fact, RelationFact):
        subj = fact.subject.value if fact.subject.type == "named" else f"?({fact.subject.location})"
        obj_part = ""
        if hasattr(fact, 'object') and fact.object:
            obj_part = f" -> {fact.object.value}"
        tgt_part = ""
        if fact.target:
            tgt_val = fact.target.value if fact.target.type == "named" else f"?({fact.target.location})"
            tgt_part = f" -> {tgt_val}"
        return f"RelationFact: {subj} {fact.predicate}{obj_part}{tgt_part}"
    return repr(fact)

def _get_entity_type(name: str) -> str:
    """Determines the search category for a given entity name."""
    # Check if it's a patient
    patient_names = [p["name"].lower() for p in PATIENT_DATA.values()]
    if name.lower() in patient_names:
        return "patients"
    
    # Check if it's a potion
    if "potion" in name.lower():
        return "potions"
    
    # Default to NPCs (e.g. eliza, lola)
    return "npcs"

def _calculate_location_score(target_name: str, fact_set: list[Fact], ground_truth: GameState, map_graph: KnowledgeGraph, cost_config: CostConfig, entity_type: str = None) -> ComponentScore:
    """
    Core logic for scoring the Information Access Cost (IAC) of a specific entity's location.
    """
    if entity_type is None:
        entity_type = _get_entity_type(target_name)

    # 1. Pre-calculate entity rooms for existential resolution
    # Note: _objects stores potions with underscore names (e.g. "gold_potion") per objects.json,
    # but KG facts and gold facts use space-separated names (e.g. "gold potion").
    # We normalize by inserting both forms so lookups succeed either way.
    entity_rooms = {}
    for room, objs in ground_truth._objects.items():
        for name in objs:
            entity_rooms[name] = room
            # Also register the normalized form (removing underscores/spaces)
            normalized = normalize_entity_name(name)
            if normalized != name:
                entity_rooms[normalized] = room
            
    true_room = entity_rooms.get(target_name) or entity_rooms.get(normalize_entity_name(target_name))
    gt_fact_str = f"LocationFact: {target_name} in {true_room}" if true_room else f"(no ground truth room found for {target_name})"

    # 2. Get all rooms for max_cost and normalization
    all_rooms = _get_all_rooms(map_graph)
    if not all_rooms:
        # Fallback to current room if graph is empty (shouldn't happen with valid map_graph)
        all_rooms = {true_room} if true_room else {"room0"}
    
    # Nuanced cost calculation
    max_cost = EXPECTED_SEARCH_COSTS_PER_ROOM_TYPE.get(entity_type, len(all_rooms) / 2.0)
    baseline_rooms = set(_normalize_room(r) for r in SEARCH_ROOMS_PER_ENTITY_TYPE.get(entity_type, []))
    num_rooms = len(baseline_rooms) if baseline_rooms else len(all_rooms)

    # 3. Filter facts about this entity
    entity_facts = []
    
    def resolves_to(arg: Argument, candidate_name: str, explicit_location: Location = None, ref_room: str = "room 0") -> bool:
        if arg.type == "named":
            return arg.value == candidate_name
        elif arg.type == "existential":
            loc_constraint = arg.location or explicit_location
            if not loc_constraint:
                return True # Unconstrained existential matches everything
            cand_room = entity_rooms.get(candidate_name) or entity_rooms.get(normalize_entity_name(candidate_name))
            if not cand_room:
                return False
            return is_location_satisfying_constraint(cand_room, loc_constraint, map_graph, ref_room)
        return False

    for fact in fact_set:
        if isinstance(fact, LocationFact):
            if resolves_to(fact.entity, target_name, explicit_location=fact.location):
                entity_facts.append(fact)
        elif isinstance(fact, SpatialFact):
            spatial_loc = Location(
                type="directional",
                directions=[fact.direction],
                mode="path"
            )
            ref_room = "room 0"
            if fact.type == SpatialRelationType.RELATIVE and fact.reference and fact.reference.type == "named":
                ref_room = fact.reference.value
                
            if resolves_to(fact.subject, target_name, explicit_location=spatial_loc, ref_room=ref_room):
                entity_facts.append(fact)
        elif isinstance(fact, RelationFact):
            # Check if subject or target refers to our entity and has a location constraint
            if resolves_to(fact.subject, target_name) and fact.subject.location:
                # Treat as a location fact for the target_name
                entity_facts.append(LocationFact(
                    id=fact.id,
                    entity=Argument(type="named", value=target_name),
                    location=fact.subject.location
                ))
            elif fact.target and resolves_to(fact.target, target_name) and fact.target.location:
                entity_facts.append(LocationFact(
                    id=fact.id,
                    entity=Argument(type="named", value=target_name),
                    location=fact.target.location
                ))

    if not entity_facts:
        return ComponentScore(credit_type=CreditType.NONE, max_cost=max_cost, partial_credit=0.0,
                              evaluated_fact="(no matching location fact found)",
                              ground_truth_fact=gt_fact_str)

    # 4. Selection Logic: Absolute > Directional
    # Sort facts: LocationFact (room) > LocationFact (directional) > SpatialFact
    def fact_priority(f):
        if isinstance(f, LocationFact):
            return 0 if f.location.type == "room" else 1
        return 2

    entity_facts.sort(key=fact_priority)
    
    # Take the most specific (first in sorted list)
    best_fact = entity_facts[0]
    evaluated_fact_str = _describe_fact(best_fact)
    
    # 5. Resolve fact against map
    constraint_loc = None
    reference_room = "room 0"
    
    if isinstance(best_fact, LocationFact):
        constraint_loc = best_fact.location
    elif isinstance(best_fact, SpatialFact):
        constraint_loc = Location(
            type="directional",
            directions=[best_fact.direction],
            mode="path"
        )
        if best_fact.type == SpatialRelationType.RELATIVE and best_fact.reference and best_fact.reference.type == "named":
            reference_room = best_fact.reference.value

    # Find set of rooms satisfying the constraint
    satisfying_rooms = set()
    for room in all_rooms:
        if is_location_satisfying_constraint(room, constraint_loc, map_graph, reference_room):
            satisfying_rooms.add(room)

    # 6. Final Score Calculation
    if true_room:
        true_room_norm = _normalize_room(true_room)
        satisfying_rooms_norm = set(_normalize_room(r) for r in satisfying_rooms)

        if true_room_norm in satisfying_rooms_norm:
            # Intersection with baseline to find relevant satisfying rooms
            effective_satisfying = satisfying_rooms_norm
            if baseline_rooms:
                # Only count satisfying rooms that are in the baseline for this entity type
                effective_satisfying = satisfying_rooms_norm.intersection(baseline_rooms)
            
            if len(effective_satisfying) == 1:
                return ComponentScore(credit_type=CreditType.FULL, max_cost=max_cost, partial_credit=1.0,
                                      evaluated_fact=evaluated_fact_str, ground_truth_fact=gt_fact_str)
            else:
                # Factor by which search space was reduced relative to baseline
                reduction_factor = 1.0 - (len(effective_satisfying) / num_rooms)
                # Clamp to [0, 1]
                reduction_factor = max(0.0, min(1.0, reduction_factor))
                return ComponentScore(credit_type=CreditType.PARTIAL, max_cost=max_cost, partial_credit=reduction_factor,
                                      evaluated_fact=evaluated_fact_str, ground_truth_fact=gt_fact_str)
        else:
            # Correct room not in satisfying set -> Misinformation
            return ComponentScore(credit_type=CreditType.CONTRADICTED, max_cost=max_cost, partial_credit=0.0,
                                  evaluated_fact=evaluated_fact_str, ground_truth_fact=gt_fact_str)
    else:
        # No true room found for entity
        return ComponentScore(credit_type=CreditType.NONE, max_cost=max_cost, partial_credit=0.0,
                              evaluated_fact=evaluated_fact_str, ground_truth_fact=gt_fact_str)

def _score_location(entity: str, fact_set: list[Fact], ground_truth: GameState, map_graph: KnowledgeGraph, cost_config: CostConfig) -> ComponentScore:
    """Scores the accuracy of information about an entity's own location."""
    return _calculate_location_score(entity, fact_set, ground_truth, map_graph, cost_config, entity_type="patients")

def _find_npc(ground_truth: GameState, name: str):
    """Finds an NPC object by name in the GameState."""
    for room_objs in ground_truth._objects.values():
        if name in room_objs:
            return room_objs[name]
    return None

def get_patient_status_facts(entity: str, ground_truth: GameState) -> list[RelationFact]:
    """
    Determines the current status of a patient NPC based on the ground truth GameState.
    Returns a list of RelationFacts representing outstanding needs, messages, or responses.
    """
    # 1. Find patient info
    patient_info = None
    for p_id, info in PATIENT_DATA.items():
        if info["name"] == entity:
            patient_info = info
            break
    
    if not patient_info:
        return []

    # 2. Find patient NPC object
    patient_npc = _find_npc(ground_truth, entity)
    if not patient_npc:
        return []

    facts = []
    
    # 3. Check potion need
    if not patient_npc.held_item_interact_complete:
        facts.append(RelationFact(
            predicate=RelationPredicate.NEEDS_POTION,
            subject=Argument(type="named", value=entity),
            object=Argument(type="named", value=f"{patient_info['potion']} potion")
        ))
        return facts
    
    # 4. Check targets (messages and responses)
    targets = []
    if "npc_target" in patient_info:
        targets.append(patient_info["npc_target"])
    if "npc_target_1" in patient_info:
        targets.append(patient_info["npc_target_1"])
    if "npc_target_2" in patient_info:
        targets.append(patient_info["npc_target_2"])
    
    for target_name in targets:
        target_npc = _find_npc(ground_truth, target_name)
        if not target_npc:
            continue
            
        # Check if the request message has been delivered to the target
        # Request items are typically "request from room X"
        request_item = f"request from {patient_info['location']}"
        if target_npc.conditional_interact_counts.get(request_item, 0) == 0:
            return [RelationFact(
                predicate=RelationPredicate.HAS_MESSAGE_FOR,
                subject=Argument(type="named", value=entity),
                target=Argument(type="named", value=target_name)
            )]
        else:
            # Target received request, check if patient received response
            # Response items are typically "response from [TargetName]"
            response_item = f"response from {target_name.capitalize()}"
            if patient_npc.conditional_interact_counts.get(response_item, 0) == 0:
                return [RelationFact(
                    predicate=RelationPredicate.HAS_MESSAGE_FOR,
                    subject=Argument(type="named", value=target_name),
                    target=Argument(type="named", value=entity)
                )]
            else:
                return [RelationFact(
                    predicate=RelationPredicate.NEEDS_POTION,
                    subject=Argument(type="named", value=entity),
                    object=Argument(type="named", value=f"{patient_info['potion']} potion")
                )]
    
    return []

def _is_category_match(predicted_val: str, gold_val: str) -> bool:
    """Checks if a predicted value is a generic category for a specific gold value."""
    categories = ["potion", "request", "message", "response"]
    if predicted_val.lower() in categories:
        # Check if the gold value contains the category word
        return predicted_val.lower() in gold_val.lower()
    return False

def _score_need(entity: str, fact_set: list[Fact], ground_truth: GameState, map_graph: KnowledgeGraph, cost_config: CostConfig) -> ComponentScore:
    """
    Scores the accuracy of information about a patient NPC's needs (potions or messages).

    Uses a three-tier resolution strength model for matching facts to this entity:
      - 'definite': named match, or constrained existential resolving exclusively to this entity
      - 'possible':  unconstrained existential (e.g. "someone"), or constrained existential
                     that includes this entity among others
      - 'none':      named different entity, or existential that excludes this entity

    Only 'definite' matches can produce CONTRADICTED scores. 'possible' matches are capped
    at PARTIAL (and only when the resource is an exact match), preventing "oliver HAS_MESSAGE_FOR
    (someone)" from being treated as a contradiction when scoring lily.
    """
    # 1. Get gold facts
    gold_facts = get_patient_status_facts(entity, ground_truth)
    gold_fact = gold_facts[0] if gold_facts else None

    max_cost = DIAGNOSIS_COST
    gt_fact_str = _describe_fact(gold_fact) if gold_fact else "(no outstanding need)"

    # 2. Pre-calculate entity rooms for existential resolution
    # Normalize underscore-named keys (e.g. "gold_potion") to also be accessible
    # with spaces (e.g. "gold potion") to match KG fact naming conventions.
    entity_rooms = {}
    for room, objs in ground_truth._objects.items():
        for name in objs:
            entity_rooms[name] = room
            normalized = normalize_entity_name(name)
            if normalized != name:
                entity_rooms[normalized] = room

    all_patient_names = [p["name"] for p in PATIENT_DATA.values()]

    def resolution_strength(arg, target_name):
        """
        Returns 'definite', 'possible', or 'none' indicating how strongly
        the argument resolves to target_name.
        """
        if arg.type == "named":
            return "definite" if arg.value == target_name else "none"
        elif arg.type == "existential":
            if not arg.location:
                return "possible"  # Unconstrained existential — could be anyone
            target_room = entity_rooms.get(target_name) or entity_rooms.get(normalize_entity_name(target_name))
            if not target_room:
                return "none"
            if not is_location_satisfying_constraint(target_room, arg.location, map_graph, "room 0"):
                return "none"
            def _get_room(name):
                return entity_rooms.get(name) or entity_rooms.get(normalize_entity_name(name))
            
            others_satisfy = any(
                p != target_name
                and _get_room(p)
                and is_location_satisfying_constraint(_get_room(p), arg.location, map_graph, "room 0")
                for p in all_patient_names
            )
            return "possible" if others_satisfy else "definite"
        return "none"

    def score_other_arg(f_other, g_other, f, is_definite):
        """
        Compare the 'other' argument (resource or message partner) of a candidate fact
        against the gold. Returns a ComponentScore or None (meaning: skip this candidate).

        When is_definite=True, full scoring tiers apply (FULL / PARTIAL / CONTRADICTED).
        When is_definite=False (subject is only 'possible'), only an exact resource match
        earns PARTIAL credit; everything else returns None so it doesn't block better matches.
        This prevents "someone needs the red potion" from being a contradiction for lily.
        """
        if not f_other or not g_other:
            if is_definite:
                return ComponentScore(credit_type=CreditType.PARTIAL, max_cost=max_cost,
                                      partial_credit=cost_config.partial_need_credit,
                                      evaluated_fact=_describe_fact(f), ground_truth_fact=gt_fact_str)
            return None

        if f_other.type == "named" and g_other.type == "named":
            if f_other.value == g_other.value:
                # Exact resource match
                return ComponentScore(
                    credit_type=CreditType.FULL if is_definite else CreditType.PARTIAL,
                    max_cost=max_cost,
                    partial_credit=1.0 if is_definite else cost_config.partial_need_credit,
                    evaluated_fact=_describe_fact(f), ground_truth_fact=gt_fact_str)
            elif _is_category_match(f_other.value, g_other.value):
                # Generic category (e.g. "potion" for "gold potion") — only when subject is definite
                # "someone needs_potion potion" is too vague on both axes to earn credit
                if is_definite:
                    return ComponentScore(credit_type=CreditType.PARTIAL, max_cost=max_cost,
                                          partial_credit=cost_config.partial_need_credit,
                                          evaluated_fact=_describe_fact(f), ground_truth_fact=gt_fact_str)
                return None
            else:
                # Definitively wrong resource
                if is_definite:
                    return ComponentScore(credit_type=CreditType.CONTRADICTED, max_cost=max_cost,
                                          partial_credit=0.0,
                                          evaluated_fact=_describe_fact(f), ground_truth_fact=gt_fact_str)
                return None  # Possible subject + wrong resource — can't call it a contradiction

        elif f_other.type == "existential":
            g_other_room = entity_rooms.get(g_other.value) or entity_rooms.get(normalize_entity_name(g_other.value)) if g_other.type == "named" else None
            is_satisfied = not f_other.location  # unconstrained existential always satisfies
            if not is_satisfied and g_other_room:
                is_satisfied = is_location_satisfying_constraint(
                    g_other_room, f_other.location, map_graph, "room 0")
            if is_satisfied:
                if is_definite:
                    return ComponentScore(credit_type=CreditType.PARTIAL, max_cost=max_cost,
                                          partial_credit=cost_config.partial_need_credit,
                                          evaluated_fact=_describe_fact(f), ground_truth_fact=gt_fact_str)
                return None  # Possible subject + vague existential object → too ambiguous
            else:
                if is_definite:
                    return ComponentScore(credit_type=CreditType.CONTRADICTED, max_cost=max_cost,
                                          partial_credit=0.0,
                                          evaluated_fact=_describe_fact(f), ground_truth_fact=gt_fact_str)
                return None
        else:
            if is_definite:
                return ComponentScore(credit_type=CreditType.CONTRADICTED, max_cost=max_cost,
                                      partial_credit=0.0,
                                      evaluated_fact=_describe_fact(f), ground_truth_fact=gt_fact_str)
            return None

    # 3. No outstanding gold need
    if not gold_fact:
        for f in fact_set:
            if not isinstance(f, RelationFact):
                continue
            if f.predicate not in [RelationPredicate.NEEDS_POTION, RelationPredicate.HAS_MESSAGE_FOR]:
                continue
            subj_str = resolution_strength(f.subject, entity)
            tgt_str = resolution_strength(f.target, entity) if f.target else "none"
            if subj_str == "definite" or tgt_str == "definite":
                return ComponentScore(credit_type=CreditType.CONTRADICTED, max_cost=max_cost,
                                      partial_credit=0.0,
                                      evaluated_fact=_describe_fact(f), ground_truth_fact=gt_fact_str)
        # No definite candidates about this entity — correct omission
        return ComponentScore(credit_type=CreditType.FULL, max_cost=0.0, partial_credit=1.0,
                              evaluated_fact="(no outstanding need — correct omission)",
                              ground_truth_fact=gt_fact_str)

    # 4. Evaluate candidates and find the best match
    priority = {CreditType.FULL: 0, CreditType.PARTIAL: 1, CreditType.NONE: 2, CreditType.CONTRADICTED: 3}
    best_score = None

    for f in fact_set:
        if not isinstance(f, RelationFact):
            continue
        if f.predicate not in [RelationPredicate.NEEDS_POTION, RelationPredicate.HAS_MESSAGE_FOR]:
            continue

        current_score = None

        if gold_fact.predicate == RelationPredicate.NEEDS_POTION:
            # Entity is the subject (patient needing a potion)
            subj_str = resolution_strength(f.subject, entity)
            if subj_str == "none":
                continue  # Fact is not about this entity
            is_definite = (subj_str == "definite")

            if f.predicate != gold_fact.predicate:
                if is_definite:
                    current_score = ComponentScore(credit_type=CreditType.CONTRADICTED, max_cost=max_cost,
                                                   partial_credit=0.0,
                                                   evaluated_fact=_describe_fact(f), ground_truth_fact=gt_fact_str)
                else:
                    continue  # Possible subject + wrong predicate → skip
            else:
                current_score = score_other_arg(f.object, gold_fact.object, f, is_definite)
                if current_score is None:
                    continue

        elif gold_fact.predicate == RelationPredicate.HAS_MESSAGE_FOR:
            if gold_fact.subject.value == entity:
                # Entity is the sender — look at candidate's subject
                subj_str = resolution_strength(f.subject, entity)
                if subj_str == "none":
                    continue
                is_definite = (subj_str == "definite")

                if f.predicate != gold_fact.predicate:
                    if is_definite:
                        current_score = ComponentScore(credit_type=CreditType.CONTRADICTED, max_cost=max_cost,
                                                       partial_credit=0.0,
                                                       evaluated_fact=_describe_fact(f), ground_truth_fact=gt_fact_str)
                    else:
                        continue
                else:
                    current_score = score_other_arg(f.target, gold_fact.target, f, is_definite)
                    if current_score is None:
                        continue
            else:
                # Entity is the receiver — look at candidate's target
                tgt_str = resolution_strength(f.target, entity) if f.target else "none"
                if tgt_str == "none":
                    continue
                is_definite = (tgt_str == "definite")

                if f.predicate != gold_fact.predicate:
                    if is_definite:
                        current_score = ComponentScore(credit_type=CreditType.CONTRADICTED, max_cost=max_cost,
                                                       partial_credit=0.0,
                                                       evaluated_fact=_describe_fact(f), ground_truth_fact=gt_fact_str)
                    else:
                        continue
                else:
                    current_score = score_other_arg(f.subject, gold_fact.subject, f, is_definite)
                    if current_score is None:
                        continue

        if current_score is not None:
            if best_score is None or priority[current_score.credit_type] < priority[best_score.credit_type]:
                best_score = current_score

    if best_score is not None:
        return best_score

    # Nothing relevant found
    return ComponentScore(credit_type=CreditType.NONE, max_cost=max_cost, partial_credit=0.0,
                          evaluated_fact="(no matching need fact found)",
                          ground_truth_fact=gt_fact_str)

def _score_resource(entity: str, fact_set: list[Fact], ground_truth: GameState, map_graph: KnowledgeGraph, cost_config: CostConfig) -> ComponentScore:
    """
    Assesses whether there is a fact providing the location of the resource needed by the entity.
    """
    # 1. Identify what the patient needs
    gold_facts = get_patient_status_facts(entity, ground_truth)
    if not gold_facts:
        # No outstanding needs -> No search cost to save
        return ComponentScore(credit_type=CreditType.FULL, max_cost=0.0, partial_credit=1.0,
                              evaluated_fact="(no outstanding need — resource score not applicable)",
                              ground_truth_fact="(no outstanding need — resource score not applicable)")
    
    # We take the first outstanding need as the priority resource
    gold_fact = gold_facts[0]
    resource_name = None
    
    if gold_fact.predicate == RelationPredicate.NEEDS_POTION:
        resource_name = gold_fact.object.value
    elif gold_fact.predicate == RelationPredicate.HAS_MESSAGE_FOR:
        # Resource is the other NPC in the relation
        if gold_fact.subject.value == entity:
            resource_name = gold_fact.target.value
        else:
            resource_name = gold_fact.subject.value
            
    if not resource_name:
        return ComponentScore(credit_type=CreditType.NONE, max_cost=0.0, partial_credit=0.0,
                              evaluated_fact="(could not determine resource name)",
                              ground_truth_fact="(could not determine resource name)")

    # 2. Score the location of THIS resource using the shared scoring logic
    entity_type = "potions" if gold_fact.predicate == RelationPredicate.NEEDS_POTION else "npcs"
    return _calculate_location_score(resource_name, fact_set, ground_truth, map_graph, cost_config, entity_type=entity_type)

def _score_entity(entity: str, fact_set: list[Fact], ground_truth: GameState, map_graph: KnowledgeGraph, cost_config: CostConfig) -> EntityScore:
    location_score = _score_location(entity, fact_set, ground_truth, map_graph, cost_config)
    need_score = _score_need(entity, fact_set, ground_truth, map_graph, cost_config)
    resource_score = _score_resource(entity, fact_set, ground_truth, map_graph, cost_config)
    
    # Ensure they are ComponentScore objects (if the stubs returned int/0)
    if isinstance(location_score, int): location_score = ComponentScore(CreditType.NONE, 0.0, 0.0)
    if isinstance(need_score, int): need_score = ComponentScore(CreditType.NONE, 0.0, 0.0)
    if isinstance(resource_score, int): resource_score = ComponentScore(CreditType.NONE, 0.0, 0.0)

    return EntityScore(
        location_score=location_score,
        need_score=need_score,
        resource_score=resource_score
    )

def compute_iac(
    pred_facts: list[Fact],
    true_state: GameState,
    map_graph: KnowledgeGraph,
    cost_config: CostConfig = CostConfig()
) -> IACResult:
    """
    Computes the Information Access Cost (IAC) based on predicted facts and ground truth.
    """
    # 1. Identify patient entities
    patient_npcs = [p["name"] for p in PATIENT_DATA.values()]
    
    # 2. Score each patient entity
    entity_scores = {}
    for entity in patient_npcs:
        entity_scores[entity] = _score_entity(entity, pred_facts, true_state, map_graph, cost_config)

    return IACResult(
        entity_scores=entity_scores,
        misinformation_multiplier=cost_config.misinformation_multiplier
    )

def main():
    parser = argparse.ArgumentParser(description="Calculate Information Access Cost (IAC) for a Knowledge Graph.")
    parser.add_argument("--kg-file", type=str, required=True, help="Path to the KnowledgeGraph JSON file.")
    parser.add_argument("--pid", type=str, required=True, help="Player ID to load the saved GameState.")
    parser.add_argument("--output-file", type=str, required=True, help="Path to save the IACResult JSON.")
    # parser.add_argument("--map-dir", type=str, default="evaluation/map_data", help="Directory containing map transitions.")
    parser.add_argument("--map-graph", type=str, required=True, help="Path to the map graph JSON file.")

    args = parser.parse_args()

    # 1. Load Knowledge Graph
    if not os.path.exists(args.kg_file):
        print(f"Error: Knowledge Graph file not found: {args.kg_file}")
        return

    with open(args.kg_file, "r") as f:
        kg_data = json.load(f)
    
    kg = KnowledgeGraph.model_validate(kg_data)
    pred_facts = kg.facts

    # 2. Load Ground Truth Game State
    true_state = _load_game_state(args.pid)
    if true_state is None:
        print(f"Error: Could not load GameState for PID: {args.pid}")
        return

    # 3. Load Map Graph (Connectivity)
    # map_graph_path = os.path.join(args.map_dir, "map_graph.json")
    if not os.path.exists(args.map_graph):
        # Fallback to creating a KnowledgeGraph from transitions if map_graph.json doesn't exist?
        # For now, we'll assume it exists or the user will provide it.
        print(f"Warning: Map graph file not found: {args.map_graph}")
        map_graph = KnowledgeGraph(facts=[])
    else:
        with open(args.map_graph, "r") as f:
            map_graph_data = json.load(f)
        map_graph = KnowledgeGraph.model_validate(map_graph_data)

    # 4. Compute IAC
    cost_config = CostConfig() # Could eventually take these from args too
    result = compute_iac(pred_facts, true_state, map_graph, cost_config)

    # 5. Save result
    output_dir = os.path.dirname(args.output_file)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)

    with open(args.output_file, "w") as f:
        json.dump(asdict(result), f, indent=4)

    print(f"IAC calculation complete. Result saved to {args.output_file}")

if __name__ == "__main__":
    main()