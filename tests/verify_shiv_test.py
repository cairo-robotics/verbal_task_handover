import pickle
import json
import os
import sys

# Ensure project root is in path
sys.path.append(os.getcwd())

from src.pipelines.evaluation.calculate_iac import get_patient_status_facts
from src.pipelines.evaluation.costs import PATIENT_DATA
from src.core.representations.pydantic_schema import KnowledgeGraph, RelationFact

def main():
    pkl_path = "tests/shiv_test.pkl"
    json_path = "tests/shiv_test_telemetry_to_kg_output.json"
    
    if not os.path.exists(pkl_path):
        print(f"Error: {pkl_path} not found.")
        return
    if not os.path.exists(json_path):
        print(f"Error: {json_path} not found.")
        return

    # 1. Load GameState
    with open(pkl_path, "rb") as f:
        gs = pickle.load(f)
    
    # 2. Load expected KnowledgeGraph
    with open(json_path, "r") as f:
        kg_data = json.load(f)
    kg = KnowledgeGraph.model_validate(kg_data)
    
    # Extract only RelationFacts from the KG
    expected_relation_facts = [f for f in kg.facts if isinstance(f, RelationFact)]
    
    print("--- Calculated Patient Status (from get_patient_status_facts) ---")
    for p_id, info in PATIENT_DATA.items():
        name = info["name"]
        npc = next((obj for room in gs._objects.values() for obj_name, obj in room.items() if obj_name == name), None)
        if npc:
            print(f"DEBUG: {name} held_item_complete={npc.held_item_interact_complete}, counts={npc.conditional_interact_counts}")
        
        # Also check targets
        targets = [info.get("npc_target"), info.get("npc_target_1"), info.get("npc_target_2")]
        targets = [t for t in targets if t]
        for t_name in targets:
            t_npc = next((obj for room in gs._objects.values() for obj_name, obj in room.items() if obj_name == t_name), None)
            if t_npc:
                print(f"  DEBUG: Target {t_name} held_item_complete={t_npc.held_item_interact_complete}, counts={t_npc.conditional_interact_counts}")

        facts = get_patient_status_facts(name, gs)
        status = ", ".join([f"{f.predicate.value} (subj: {f.subject.value}, target/obj: {f.target.value if f.target else f.object.value})" for f in facts]) or "DONE"
        print(f"{name}: {status}")

    print("\n--- RelationFacts found in JSON ---")
    for f in expected_relation_facts:
        subj = f.subject.value or "existential"
        obj = f.object.value if f.object else None
        target = f.target.value if f.target else None
        print(f"[{f.predicate.value}] {subj} -> {target or obj or ''}")

if __name__ == "__main__":
    main()
