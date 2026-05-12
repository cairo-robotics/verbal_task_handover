
import os
import json
import pickle
from collections import defaultdict
from src.pipelines.evaluation.calculate_iac import compute_iac
from src.pipelines.evaluation.costs import CostConfig, PATIENT_DATA
from src.core.representations.pydantic_schema import (
    KnowledgeGraph, LocationFact, RelationFact, Argument, Location, RelationPredicate
)
from treasure_hunt.src.game_mdp import GameState, NPC, Object

def test_compute_iac_wiring():
    # 1. Setup mock GameState
    # We need to mock the objects dictionary to have the 5 patients
    objects = defaultdict(dict)
    
    # Let's put lily in room 1
    lily_npc = NPC("lily", (1,1), "NORTH", interact_data=[["hello", None]])
    lily_npc.held_item_interact_complete = False # Needs potion
    objects["room 1"]["lily"] = lily_npc
    
    # Put oliver in room 2
    oliver_npc = NPC("oliver", (2,2), "SOUTH", interact_data=[["hello", None]])
    oliver_npc.held_item_interact_complete = True # Has potion
    # Oliver needs to talk to john
    oliver_npc.conditional_interact_counts = {"request from room 2": 0}
    oliver_npc.conditional_interact_data = {"request from room 2": [["request received", None]]}
    objects["room 2"]["oliver"] = oliver_npc
    
    # Put john in lounge 1 (target for oliver)
    john_npc = NPC("john", (3,3), "EAST", interact_data=[["hello", None]])
    objects["lounge 1"]["john"] = john_npc
    
    # Fill in others as placeholders so they don't crash
    for p_id, p_info in PATIENT_DATA.items():
        name = p_info["name"]
        if name not in ["lily", "oliver"]:
            objects[p_info["location"]][name] = NPC(name, (0,0), "NORTH", [["hello", None]])

    true_state = GameState((0,0), (0,1), "room 0", objects=objects)
    
    # 2. Setup mock KnowledgeGraph (predicted facts)
    # Correct location for lily
    lily_loc = LocationFact(
        id="f1",
        entity=Argument(type="named", value="lily"),
        location=Location(type="room", room="room 1")
    )
    # Incorrect location for oliver (misinformation)
    oliver_loc = LocationFact(
        id="f2",
        entity=Argument(type="named", value="oliver"),
        location=Location(type="room", room="room 1")
    )
    # Correct need for lily
    lily_need = RelationFact(
        id="f3",
        predicate=RelationPredicate.NEEDS_POTION,
        subject=Argument(type="named", value="lily"),
        object=Argument(type="named", value="gold potion")
    )
    
    pred_facts = [lily_loc, oliver_loc, lily_need]
    
    # 3. Setup mock map graph
    map_graph = KnowledgeGraph(facts=[]) # Empty map graph for now, _get_all_rooms will fallback
    
    # 4. Run compute_iac
    cost_config = CostConfig(misinformation_multiplier=2.0)
    result = compute_iac(pred_facts, true_state, map_graph, cost_config)
    
    # 5. Assertions
    assert len(result.entity_scores) == 5
    assert "lily" in result.entity_scores
    assert "oliver" in result.entity_scores
    assert result.misinformation_multiplier == 2.0
    
    # Check lily's scores
    lily_score = result.entity_scores["lily"]
    assert lily_score.location_score.credit_type.name == "FULL"
    assert lily_score.need_score.credit_type.name == "FULL"
    
    # Check oliver's scores
    oliver_score = result.entity_scores["oliver"]
    assert oliver_score.location_score.credit_type.name == "CONTRADICTED"
    
    # Verify aggregate costs are calculated
    assert result.total_cost_saved > 0
    assert result.combined_cost > 0
    
    print("Wiring test passed!")

if __name__ == "__main__":
    test_compute_iac_wiring()
