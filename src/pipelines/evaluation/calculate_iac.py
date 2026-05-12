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
from src.pipelines.evaluation.costs import CostConfig, PATIENT_DATA
from src.pipelines.evaluation.map_graph import load_transitions
from src.pipelines.evaluation.report_iac import IACResult, EntityScore, ComponentScore, CreditType
from src.core.utils.spatial_reasoning import is_location_satisfying_constraint, ConnectionFact

from treasure_hunt.src.game_mdp import GameState

DIAGNOSIS_COST = 5.0

def _load_game_state(pid: str) -> GameState:
    """Loads the GameState for a given player ID."""
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

def _calculate_location_score(target_name: str, fact_set: list[Fact], ground_truth: GameState, map_graph: KnowledgeGraph, cost_config: CostConfig) -> ComponentScore:
    """
    Core logic for scoring the Information Access Cost (IAC) of a specific entity's location.
    """
    # 1. Pre-calculate entity rooms for existential resolution
    entity_rooms = {}
    for room, objs in ground_truth._objects.items():
        for name in objs:
            entity_rooms[name] = room
            
    true_room = entity_rooms.get(target_name)
    
    # 2. Get all rooms for max_cost and normalization
    all_rooms = _get_all_rooms(map_graph)
    if not all_rooms:
        # Fallback to current room if graph is empty (shouldn't happen with valid map_graph)
        all_rooms = {true_room} if true_room else {"room 0"}
    
    num_rooms = len(all_rooms)
    max_cost = num_rooms / 2.0

    # 3. Filter facts about this entity
    entity_facts = []
    
    def resolves_to(arg: Argument, candidate_name: str) -> bool:
        if arg.type == "named":
            return arg.value == candidate_name
        elif arg.type == "existential":
            if not arg.location:
                return True # Unconstrained existential matches everything
            cand_room = entity_rooms.get(candidate_name)
            if not cand_room:
                return False
            return is_location_satisfying_constraint(cand_room, arg.location, map_graph, "room 0")
        return False

    for fact in fact_set:
        if isinstance(fact, LocationFact):
            if fact.entity.type == "named" and fact.entity.value == target_name:
                entity_facts.append(fact)
        elif isinstance(fact, SpatialFact):
            if fact.subject.type == "named" and fact.subject.value == target_name:
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
        return ComponentScore(credit_type=CreditType.NONE, max_cost=max_cost, partial_credit=0.0)

    # 4. Selection Logic: Absolute > Directional
    # Sort facts: LocationFact (room) > LocationFact (directional) > SpatialFact
    def fact_priority(f):
        if isinstance(f, LocationFact):
            return 0 if f.location.type == "room" else 1
        return 2

    entity_facts.sort(key=fact_priority)
    
    # Take the most specific (first in sorted list)
    best_fact = entity_facts[0]
    
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
    if true_room in satisfying_rooms:
        if len(satisfying_rooms) == 1:
            return ComponentScore(credit_type=CreditType.FULL, max_cost=max_cost, partial_credit=1.0)
        else:
            # Factor by which search space was reduced
            reduction_factor = 1.0 - (len(satisfying_rooms) / num_rooms)
            return ComponentScore(credit_type=CreditType.PARTIAL, max_cost=max_cost, partial_credit=reduction_factor)
    else:
        # Correct room not in satisfying set -> Misinformation
        return ComponentScore(credit_type=CreditType.CONTRADICTED, max_cost=max_cost, partial_credit=0.0)

def _score_location(entity: str, fact_set: list[Fact], ground_truth: GameState, map_graph: KnowledgeGraph, cost_config: CostConfig) -> ComponentScore:
    """Scores the accuracy of information about an entity's own location."""
    return _calculate_location_score(entity, fact_set, ground_truth, map_graph, cost_config)

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
    """
    # 1. Get gold facts
    gold_facts = get_patient_status_facts(entity, ground_truth)
    gold_fact = gold_facts[0] if gold_facts else None
    
    max_cost = DIAGNOSIS_COST
    
    # 2. Pre-calculate entity rooms for existential resolution
    entity_rooms = {}
    for room, objs in ground_truth._objects.items():
        for name in objs:
            entity_rooms[name] = room
            
    def resolves_to(arg: Argument, target_name: str) -> bool:
        if arg.type == "named":
            return arg.value == target_name
        elif arg.type == "existential":
            if not arg.location:
                return True # Unconstrained existential matches everything
            target_room = entity_rooms.get(target_name)
            if not target_room:
                return False
            return is_location_satisfying_constraint(target_room, arg.location, map_graph, "room 0")
        return False

    # 3. Filter candidates for this entity and relevant predicates
    candidates = []
    for f in fact_set:
        if not isinstance(f, RelationFact):
            continue
        if f.predicate not in [RelationPredicate.NEEDS_POTION, RelationPredicate.HAS_MESSAGE_FOR]:
            continue
            
        # Does this fact relate to our entity?
        is_relevant = False
        if resolves_to(f.subject, entity):
            is_relevant = True
        elif f.target and resolves_to(f.target, entity):
            is_relevant = True
            
        if is_relevant:
            candidates.append(f)

    if not gold_fact:
        if candidates:
            # Report says there's a need when there isn't
            return ComponentScore(credit_type=CreditType.CONTRADICTED, max_cost=max_cost, partial_credit=0.0)
        else:
            # Correct omission of need facts (neutral score with 0 max_cost)
            return ComponentScore(credit_type=CreditType.FULL, max_cost=0.0, partial_credit=1.0)

    if not candidates:
        # Ground truth has a need but report has nothing -> Omission
        return ComponentScore(credit_type=CreditType.NONE, max_cost=max_cost, partial_credit=0.0)

    # 4. Evaluate each candidate against the gold fact and take the best
    best_score = None
    
    for f in candidates:
        current_score = None
        
        # Predicate mismatch -> Misinformation (relative to this specific need)
        if f.predicate != gold_fact.predicate:
            current_score = ComponentScore(credit_type=CreditType.CONTRADICTED, max_cost=max_cost, partial_credit=0.0)
        else:
            # Predicate matches!
            # Determine which gold argument is the "other" (the one not necessarily the entity being scored)
            g_other = None
            if gold_fact.predicate == RelationPredicate.NEEDS_POTION:
                g_other = gold_fact.object
            elif gold_fact.predicate == RelationPredicate.HAS_MESSAGE_FOR:
                if gold_fact.subject.value == entity:
                    g_other = gold_fact.target
                else:
                    g_other = gold_fact.subject
            
            # Find the "other" argument in the candidate
            f_other = None
            subj_resolves = resolves_to(f.subject, entity)
            target_resolves = f.target and resolves_to(f.target, entity)
            
            if gold_fact.predicate == RelationPredicate.NEEDS_POTION:
                if subj_resolves:
                    f_other = f.object
                else:
                    current_score = ComponentScore(credit_type=CreditType.CONTRADICTED, max_cost=max_cost, partial_credit=0.0)
            elif gold_fact.predicate == RelationPredicate.HAS_MESSAGE_FOR:
                if gold_fact.subject.value == entity:
                    if subj_resolves:
                        f_other = f.target
                    else:
                        current_score = ComponentScore(credit_type=CreditType.CONTRADICTED, max_cost=max_cost, partial_credit=0.0)
                else:
                    if target_resolves:
                        f_other = f.subject
                    else:
                        current_score = ComponentScore(credit_type=CreditType.CONTRADICTED, max_cost=max_cost, partial_credit=0.0)

            if current_score is None:
                # Now compare f_other with g_other
                if not f_other or not g_other:
                    current_score = ComponentScore(credit_type=CreditType.PARTIAL, max_cost=max_cost, partial_credit=cost_config.partial_need_credit)
                else:
                    # Compare Arguments
                    if f_other.type == "named" and g_other.type == "named":
                        if f_other.value == g_other.value:
                            current_score = ComponentScore(credit_type=CreditType.FULL, max_cost=max_cost, partial_credit=1.0)
                        elif _is_category_match(f_other.value, g_other.value):
                            current_score = ComponentScore(credit_type=CreditType.PARTIAL, max_cost=max_cost, partial_credit=cost_config.partial_need_credit)
                        else:
                            current_score = ComponentScore(credit_type=CreditType.CONTRADICTED, max_cost=max_cost, partial_credit=0.0)
                    elif f_other.type == "existential":
                        target_room = entity_rooms.get(g_other.value)
                        is_satisfied = False
                        if not f_other.location:
                            is_satisfied = True
                        elif target_room:
                            is_satisfied = is_location_satisfying_constraint(target_room, f_other.location, map_graph, "room 0")
                        
                        if is_satisfied:
                            current_score = ComponentScore(credit_type=CreditType.PARTIAL, max_cost=max_cost, partial_credit=cost_config.partial_need_credit)
                        else:
                            current_score = ComponentScore(credit_type=CreditType.CONTRADICTED, max_cost=max_cost, partial_credit=0.0)
                    else:
                        current_score = ComponentScore(credit_type=CreditType.CONTRADICTED, max_cost=max_cost, partial_credit=0.0)

        # Update best score: FULL > PARTIAL > NONE > CONTRADICTED
        priority = {CreditType.FULL: 0, CreditType.PARTIAL: 1, CreditType.NONE: 2, CreditType.CONTRADICTED: 3}
        if best_score is None or priority[current_score.credit_type] < priority[best_score.credit_type]:
            best_score = current_score
            
    return best_score if best_score else ComponentScore(credit_type=CreditType.NONE, max_cost=max_cost, partial_credit=0.0)

def _score_resource(entity: str, fact_set: list[Fact], ground_truth: GameState, map_graph: KnowledgeGraph, cost_config: CostConfig) -> ComponentScore:
    """
    Assesses whether there is a fact providing the location of the resource needed by the entity.
    """
    # 1. Identify what the patient needs
    gold_facts = get_patient_status_facts(entity, ground_truth)
    if not gold_facts:
        # No outstanding needs -> No search cost to save
        return ComponentScore(credit_type=CreditType.FULL, max_cost=0.0, partial_credit=1.0)
    
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
        return ComponentScore(credit_type=CreditType.NONE, max_cost=0.0, partial_credit=0.0)

    # 2. Score the location of THIS resource using the shared scoring logic
    return _calculate_location_score(resource_name, fact_set, ground_truth, map_graph, cost_config)

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
    parser.add_argument("--map-dir", type=str, default="evaluation/map_data", help="Directory containing map transitions.")

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
    map_graph_path = os.path.join(args.map_dir, "map_graph.json")
    if not os.path.exists(map_graph_path):
        # Fallback to creating a KnowledgeGraph from transitions if map_graph.json doesn't exist?
        # For now, we'll assume it exists or the user will provide it.
        print(f"Warning: Map graph file not found: {map_graph_path}")
        map_graph = KnowledgeGraph(facts=[])
    else:
        with open(map_graph_path, "r") as f:
            map_graph_data = json.load(f)
        map_graph = KnowledgeGraph.model_validate(map_graph_data)

    # 4. Compute IAC
    cost_config = CostConfig() # Could eventually take these from args too
    result = compute_iac(pred_facts, true_state, map_graph, cost_config)

    # 4. Save result
    output_dir = os.path.dirname(args.output_file)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)

    with open(args.output_file, "w") as f:
        json.dump(asdict(result), f, indent=4)

    print(f"IAC calculation complete. Result saved to {args.output_file}")

if __name__ == "__main__":
    main()