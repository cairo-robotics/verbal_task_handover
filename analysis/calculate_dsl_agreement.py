import argparse
import os
import sys
import json
import tempfile
from sklearn.metrics import cohen_kappa_score
import dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.representations.pydantic_schema import (
    KnowledgeGraph, LocationFact, SpatialFact, RelationFact, ConnectionFact, Argument, Location, SpatialRelationType, RelationPredicate
)
from src.core.utils.normalization import normalize_entity_name, standardize_room_name
from src.core.utils.spatial_reasoning import resolve_directional_path
from src.pipelines.evaluation.costs import PATIENT_DATA
from src.pipelines.evaluation.calculate_iac import _load_game_state
from src.core.transforms.dsl_to_graph import dsl_to_graph

def get_player_start_room(telemetry_kg: KnowledgeGraph) -> str:
    for fact in telemetry_kg.facts:
        if isinstance(fact, LocationFact) and fact.entity.type == "named" and fact.entity.value == "player":
            if fact.location.type == "room":
                return fact.location.room
    return "room 0"

def get_entity_rooms_gt(game_state) -> dict:
    entity_rooms = {}
    for room, objs in game_state._objects.items():
        for name in objs:
            entity_rooms[normalize_entity_name(name)] = room
    return entity_rooms

def resolve_location_fact(fact, telemetry_kg: KnowledgeGraph, player_start_room: str) -> str:
    if isinstance(fact, LocationFact):
        loc = fact.location
        if loc.type == "room":
            return standardize_room_name(loc.room)
        elif loc.type == "directional":
            start_room = loc.room or player_start_room or "room 0"
            resolved = resolve_directional_path(start_room, loc.directions, telemetry_kg)
            if resolved:
                return standardize_room_name(resolved)
    elif isinstance(fact, SpatialFact):
        if fact.type == SpatialRelationType.ABSOLUTE:
            start_room = player_start_room or "room 0"
            resolved = resolve_directional_path(start_room, [fact.direction], telemetry_kg)
            if resolved:
                return standardize_room_name(resolved)
        elif fact.type == SpatialRelationType.RELATIVE:
            if fact.reference and fact.reference.type == "named":
                start_room = fact.reference.value
                resolved = resolve_directional_path(start_room, [fact.direction], telemetry_kg)
                if resolved:
                    return standardize_room_name(resolved)
    return None

def resolves_to(arg: Argument, target_name: str, entity_rooms_gt=None, telemetry_kg=None, player_start_room=None) -> bool:
    target_norm = normalize_entity_name(target_name)
    if arg.type == "named":
        return normalize_entity_name(arg.value) == target_norm
    elif arg.type == "existential":
        if arg.location:
            if not entity_rooms_gt or not telemetry_kg:
                return False
            true_room = entity_rooms_gt.get(target_norm)
            if not true_room:
                return False
            from src.core.utils.spatial_reasoning import is_location_satisfying_constraint
            ref_room = player_start_room or "room 0"
            return is_location_satisfying_constraint(true_room, arg.location, telemetry_kg, ref_room)
        
        if "potion" in target_norm:
            return arg.value is None or "potion" in normalize_entity_name(arg.value)
        else:
            return arg.value is None or "person" in normalize_entity_name(arg.value) or "someone" in normalize_entity_name(arg.value)
    return False

def get_associated_patient(fact, telemetry_kg: KnowledgeGraph, entity_rooms_gt: dict) -> str:
    # 1. If RelationFact, try associating by predicate resource/target first (more specific)
    if isinstance(fact, RelationFact):
        if fact.predicate == RelationPredicate.NEEDS_POTION and fact.object:
            if fact.object.type == "named":
                potion_color = normalize_entity_name(fact.object.value).replace("potion", "")
                for p_id, p_info in PATIENT_DATA.items():
                    if p_info["potion"] == potion_color:
                        return p_info["name"]
        elif fact.predicate == RelationPredicate.HAS_MESSAGE_FOR:
            for arg in [fact.subject, fact.target]:
                if arg and arg.type == "named":
                    val = normalize_entity_name(arg.value)
                    for p_id, p_info in PATIENT_DATA.items():
                        targets = [p_info.get("npc_target"), p_info.get("npc_target_1"), p_info.get("npc_target_2")]
                        if val in [normalize_entity_name(t) for t in targets if t]:
                            return p_info["name"]
                        if val == p_info["name"]:
                            return val

    # 2. Check if subject/entity is named patient or existential with location constraint
    entity_arg = None
    if isinstance(fact, LocationFact):
        entity_arg = fact.entity
    elif isinstance(fact, SpatialFact):
        entity_arg = fact.subject
    elif isinstance(fact, RelationFact):
        entity_arg = fact.subject

    if entity_arg:
        if entity_arg.type == "named":
            name = normalize_entity_name(entity_arg.value)
            if name in ["lily", "oliver", "nick", "marie", "guy"]:
                return name
        elif entity_arg.type == "existential":
            if entity_arg.location:
                player_start_room = get_player_start_room(telemetry_kg)
                ref_room = player_start_room or "room 0"
                for p_name, true_room in entity_rooms_gt.items():
                    if p_name in ["lily", "oliver", "nick", "marie", "guy"]:
                        from src.core.utils.spatial_reasoning import is_location_satisfying_constraint
                        if is_location_satisfying_constraint(true_room, entity_arg.location, telemetry_kg, ref_room):
                            return p_name

    # 3. Fallback check for any named patient in subject/target
    if isinstance(fact, RelationFact):
        for arg in [fact.subject, fact.target]:
            if arg and arg.type == "named":
                name = normalize_entity_name(arg.value)
                if name in ["lily", "oliver", "nick", "marie", "guy"]:
                    return name

    return None

def get_location_of_entity(kg: KnowledgeGraph, entity_name: str, telemetry_kg: KnowledgeGraph, player_start_room: str, entity_rooms_gt: dict) -> str:
    location_facts = []
    spatial_facts = []
    
    for fact in kg.facts:
        if isinstance(fact, LocationFact):
            if resolves_to(fact.entity, entity_name, entity_rooms_gt, telemetry_kg, player_start_room):
                location_facts.append(fact)
        elif isinstance(fact, SpatialFact):
            if resolves_to(fact.subject, entity_name, entity_rooms_gt, telemetry_kg, player_start_room):
                spatial_facts.append(fact)
                
    if location_facts:
        location_facts.sort(key=lambda f: 0 if f.location.type == "room" else 1)
        return resolve_location_fact(location_facts[0], telemetry_kg, player_start_room)
    elif spatial_facts:
        return resolve_location_fact(spatial_facts[0], telemetry_kg, player_start_room)
    return None

def extract_slots(kg: KnowledgeGraph, telemetry_kg: KnowledgeGraph, game_state) -> dict:
    player_start_room = get_player_start_room(telemetry_kg)
    entity_rooms_gt = get_entity_rooms_gt(game_state)
    
    slots = {}
    
    # 1. Player location
    player_loc = None
    for fact in kg.facts:
        if isinstance(fact, LocationFact) and fact.entity.type == "named" and normalize_entity_name(fact.entity.value) == "player":
            player_loc = resolve_location_fact(fact, telemetry_kg, player_start_room)
            if player_loc:
                break
    slots["player_location"] = player_loc
    
    # Group facts by patient
    patient_facts = {name: [] for name in ["lily", "oliver", "nick", "marie", "guy"]}
    for fact in kg.facts:
        p_name = get_associated_patient(fact, telemetry_kg, entity_rooms_gt)
        if p_name:
            patient_facts[p_name].append(fact)
            
    # 2. Patient slots
    for p_id, p_info in PATIENT_DATA.items():
        name = p_info["name"]
        facts = patient_facts[name]
        
        # A. Patient Location
        patient_loc = None
        location_facts = []
        spatial_facts = []
        relation_location_facts = []
        
        for fact in facts:
            if isinstance(fact, LocationFact):
                location_facts.append(fact)
            elif isinstance(fact, SpatialFact):
                spatial_facts.append(fact)
            elif isinstance(fact, RelationFact):
                if fact.subject.location:
                    relation_location_facts.append((fact, fact.subject.location))
                elif fact.target and fact.target.location:
                    relation_location_facts.append((fact, fact.target.location))
                    
        if location_facts:
            location_facts.sort(key=lambda f: 0 if f.location.type == "room" else 1)
            patient_loc = resolve_location_fact(location_facts[0], telemetry_kg, player_start_room)
        elif spatial_facts:
            patient_loc = resolve_location_fact(spatial_facts[0], telemetry_kg, player_start_room)
        elif relation_location_facts:
            fact, loc_constraint = relation_location_facts[0]
            dummy_fact = LocationFact(entity=Argument(type="named", value=name), location=loc_constraint)
            patient_loc = resolve_location_fact(dummy_fact, telemetry_kg, player_start_room)
            
        slots[f"{name}_location"] = patient_loc
        
        # B. Patient Need
        patient_need = None
        need_facts = []
        for fact in facts:
            if isinstance(fact, RelationFact) and fact.predicate in [RelationPredicate.NEEDS_POTION, RelationPredicate.HAS_MESSAGE_FOR]:
                need_facts.append(fact)
                
        if need_facts:
            best_fact = need_facts[0]
            if best_fact.predicate == RelationPredicate.NEEDS_POTION:
                if best_fact.object:
                    if best_fact.object.type == "named":
                        patient_need = f"potion:{normalize_entity_name(best_fact.object.value)}"
                    else:
                        patient_need = "potion:potion"
            elif best_fact.predicate == RelationPredicate.HAS_MESSAGE_FOR:
                if best_fact.subject.type == "named" and normalize_entity_name(best_fact.subject.value) == name:
                    tgt_val = normalize_entity_name(best_fact.target.value) if best_fact.target and best_fact.target.type == "named" else "someone"
                    patient_need = f"message_to:{tgt_val}"
                elif best_fact.target and best_fact.target.type == "named" and normalize_entity_name(best_fact.target.value) == name:
                    src_val = normalize_entity_name(best_fact.subject.value) if best_fact.subject.type == "named" else "someone"
                    patient_need = f"message_from:{src_val}"
                else:
                    patient_need = "message_to:someone"
                    
        slots[f"{name}_need"] = patient_need
        
        # C. Patient Resource Location
        resource_loc = None
        resource_name = None
        if patient_need:
            if patient_need.startswith("potion:"):
                resource_name = patient_need[7:]
            elif patient_need.startswith("message_to:"):
                resource_name = patient_need[11:]
            elif patient_need.startswith("message_from:"):
                resource_name = patient_need[13:]
                
        if not resource_name or resource_name in ["potion", "someone"]:
            true_potion = p_info["potion"]
            resource_name = f"{true_potion} potion"
            
        resource_loc = get_location_of_entity(kg, resource_name, telemetry_kg, player_start_room, entity_rooms_gt)
        slots[f"{name}_resource_location"] = resource_loc

    return slots

def main():
    dotenv.load_dotenv()
    
    parser = argparse.ArgumentParser(
        description="Calculate Cohen's Kappa agreement metrics on DSL files using slot-filling."
    )
    parser.add_argument(
        "--data-dir",
        help="Override DATA_DIR (otherwise uses env DATA_DIR)."
    )
    parser.add_argument(
        "--pids",
        nargs="*",
        default=["501", "502", "503", "504", "505", "506", "507", "508", "509", "510", "511", "512", "513"],
        help="Participant IDs to evaluate."
    )
    args = parser.parse_args()
    
    data_dir = args.data_dir or os.environ.get("DATA_DIR")
    if not data_dir:
        print("Error: Please set DATA_DIR in env or pass via --data-dir.")
        sys.exit(1)
        
    y_llm = []
    y_human = []
    
    slot_matches = {}
    
    print("=" * 110)
    print(f"{'PID':<6} | {'Kappa':<8} | {'Matches':<6} | {'Disagreements / Mismatches'}")
    print("-" * 110)
    
    for pid in args.pids:
        # Paths
        telemetry_path = os.path.join(data_dir, "processed_output", "kg", f"{pid}_telemetry_to_kg.json")
        llm_kg_path = os.path.join(data_dir, "processed_output", "kg", f"{pid}_user_report_gpt_dsl_to_kg.json")
        
        # Fallback to f"{pid}_user_report_dsl_to_kg.json"
        if not os.path.exists(llm_kg_path):
            llm_kg_path = os.path.join(data_dir, "processed_output", "kg", f"{pid}_user_report_dsl_to_kg.json")
            
        # Fallback to f"{pid}_dsl_to_kg.json"
        if not os.path.exists(llm_kg_path):
            llm_kg_path = os.path.join(data_dir, "processed_output", "kg", f"{pid}_dsl_to_kg.json")
            
        human_dsl_path = os.path.join(data_dir, "annotations", "dsl", f"kb_annotated_{pid}_user_report.txt")
        
        if not os.path.exists(telemetry_path) or not os.path.exists(llm_kg_path) or not os.path.exists(human_dsl_path):
            print(f"{pid:<6} | {'Skipped':<8} | {'N/A':<6} | Missing telemetry, LLM KG, or human DSL file.")
            continue
            
        # Load telemetry KG
        with open(telemetry_path, "r") as f:
            telemetry_kg = KnowledgeGraph.model_validate(json.load(f))
            
        # Load Game State
        game_state = _load_game_state(pid)
        if not game_state:
            print(f"{pid:<6} | {'Skipped':<8} | {'N/A':<6} | Could not load game state (.pkl).")
            continue
            
        # Load LLM KG
        with open(llm_kg_path, "r") as f:
            llm_kg = KnowledgeGraph.model_validate(json.load(f))
            
        # Parse Human DSL to KG
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tf:
            temp_output = tf.name
        try:
            dsl_to_graph(human_dsl_path, temp_output)
            with open(temp_output, "r") as f:
                human_kg = KnowledgeGraph.model_validate(json.load(f))
        finally:
            if os.path.exists(temp_output):
                os.remove(temp_output)
                
        # Extract slots
        llm_s = extract_slots(llm_kg, telemetry_kg, game_state)
        human_s = extract_slots(human_kg, telemetry_kg, game_state)
        
        # Align slots
        pid_y_llm = []
        pid_y_human = []
        disagreements = []
        matches_count = 0
        total_slots = len(llm_s)
        
        for slot in sorted(llm_s.keys()):
            val_llm = str(llm_s[slot])
            val_human = str(human_s[slot])
            pid_y_llm.append(val_llm)
            pid_y_human.append(val_human)
            
            y_llm.append(val_llm)
            y_human.append(val_human)
            
            if val_llm == val_human:
                matches_count += 1
            else:
                disagreements.append(f"{slot} ({val_llm} vs {val_human})")
                
            slot_matches.setdefault(slot, {"match": 0, "total": 0})
            slot_matches[slot]["total"] += 1
            if val_llm == val_human:
                slot_matches[slot]["match"] += 1
                
        import math
        import warnings
        from sklearn.exceptions import UndefinedMetricWarning
        
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=UndefinedMetricWarning)
            if pid_y_llm == pid_y_human:
                pid_kappa = 1.0
            else:
                pid_kappa = cohen_kappa_score(pid_y_llm, pid_y_human)
                if math.isnan(pid_kappa):
                    pid_kappa = 0.0
                    
        disagree_str = ", ".join(disagreements) if disagreements else "None"
        print(f"{pid:<6} | {pid_kappa:<8.4f} | {f'{matches_count}/{total_slots}':<6} | {disagree_str}")
        
    print("=" * 110)
    
    if not y_llm:
        print("No evaluations were run.")
        return
        
    overall_kappa = cohen_kappa_score(y_llm, y_human)
    total_slots_all = len(y_llm)
    total_matches_all = sum(1 for l, h in zip(y_llm, y_human) if l == h)
    accuracy = total_matches_all / total_slots_all
    
    print(f"Overall Cohen's Kappa across all reports: {overall_kappa:.4f}")
    print(f"Overall Slot Agreement Accuracy: {accuracy:.4f} ({total_matches_all}/{total_slots_all})")
    print("-" * 110)
    
    print(f"{'Slot Name':<30} | {'Match Rate':<12} | {'Matches/Total':<13}")
    print("-" * 110)
    for slot in sorted(slot_matches.keys()):
        stats = slot_matches[slot]
        rate = stats["match"] / stats["total"] if stats["total"] > 0 else 0
        print(f"{slot:<30} | {rate:<12.4f} | {f'{stats['match']}/{stats['total']}':<13}")
    print("=" * 110)

if __name__ == "__main__":
    main()
