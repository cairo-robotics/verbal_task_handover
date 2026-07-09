
import pytest
from unittest.mock import MagicMock
from src.pipelines.evaluation.calculate_iac import _score_location, _score_resource
from src.core.representations.pydantic_schema import (
    KnowledgeGraph, LocationFact, RelationFact, Argument, Location, Direction, RelationPredicate
)
from src.pipelines.evaluation.report_iac import CreditType
from src.pipelines.evaluation.costs import CostConfig, EXPECTED_SEARCH_COSTS_PER_ROOM_TYPE

# Mock GameState
class MockGameState:
    def __init__(self, objects):
        self._objects = objects

def test_patient_max_cost():
    # Setup
    entity = "lily"
    gs = MockGameState({"room 1": {"lily": MagicMock()}})
    map_kg = KnowledgeGraph(facts=[]) # Empty map
    
    # NPC says nothing
    fact_set = []
    
    score = _score_location(entity, fact_set, gs, map_kg, CostConfig())
    
    assert score.max_cost == EXPECTED_SEARCH_COSTS_PER_ROOM_TYPE["patients"] # 83.20
    assert score.credit_type == CreditType.NONE

def test_npc_max_cost():
    # Setup - scoring the resource for a patient who needs a message delivered to Eliza
    entity = "lily" # Lily is the patient being scored
    gs = MockGameState({
        "room 1": {"lily": MagicMock()},
        "lounge_1": {"eliza": MagicMock()}
    })
    
    # Mock status: Lily has a message for Eliza
    # Note: calculate_iac._score_resource calls get_patient_status_facts
    # We need to mock get_patient_status_facts or just the objects it uses.
    
    # Actually, let's just test _score_resource directly by mocking its dependencies
    # or just trust the type detection for now.
    
    # Better: test _calculate_location_score with explicit type
    from src.pipelines.evaluation.calculate_iac import _calculate_location_score
    
    score = _calculate_location_score("eliza", [], gs, KnowledgeGraph(facts=[]), CostConfig(), entity_type="npcs")
    assert score.max_cost == EXPECTED_SEARCH_COSTS_PER_ROOM_TYPE["npcs"] # 45.67

def test_potion_max_cost():
    gs = MockGameState({"storage_1": {"gold potion": MagicMock()}})
    from src.pipelines.evaluation.calculate_iac import _calculate_location_score
    
    score = _calculate_location_score("gold potion", [], gs, KnowledgeGraph(facts=[]), CostConfig(), entity_type="potions")
    assert score.max_cost == EXPECTED_SEARCH_COSTS_PER_ROOM_TYPE["potions"] # 41.50

def test_patient_partial_credit_relative_to_baseline():
    entity = "lily"
    # Ground truth: Lily is in room 1
    gs = MockGameState({"room 1": {"lily": MagicMock()}})
    
    # Map contains 10 rooms, but baseline for patients is 5 rooms (room1-room5)
    all_rooms = [f"room{i}" for i in range(10)]
    # We don't actually need to put them in the map_kg for _get_all_rooms if we mock it,
    # but _get_all_rooms extracts from LocationFacts/ConnectionFacts.
    facts = []
    for r in all_rooms:
        facts.append(LocationFact(entity=Argument(type="named", value="wall"), location=Location(type="room", room=r)))
    map_kg = KnowledgeGraph(facts=facts)
    
    # Report says: Lily is in room 1 or room 2
    # Satisfying rooms: {room 1, room 2}
    # Baseline rooms: {room1, room2, room3, room4, room5}
    # Effective satisfying: {room1, room2} (Size 2)
    # Num baseline: 5
    # reduction_factor = 1 - (2/5) = 0.6
    
    fact_set = [
        # Using a trick to get multiple satisfying rooms: a directional constraint that matches room 1 and 2
        # But simpler to just use a custom mock if I could.
        # Let's just use LocationFacts and hope the logic handles multiple.
        # Actually, the logic takes the "best" fact. A single fact that resolves to multiple rooms.
        # I'll mock is_location_satisfying_constraint.
    ]
    
    import src.pipelines.evaluation.calculate_iac as calculate_iac
    orig_is_sat = calculate_iac.is_location_satisfying_constraint
    calculate_iac.is_location_satisfying_constraint = lambda r, c, g, ref: r in ["room1", "room2"]
    
    try:
        # Dummy fact to trigger the loop
        fact_set = [LocationFact(entity=Argument(type="named", value="lily"), location=Location(type="room", room="room 1"))]
        # Wait, if type is "room", it only matches one room. 
        # I'll use "directional" to match multiple.
        fact_set = [LocationFact(entity=Argument(type="named", value="lily"), location=Location(type="directional", directions=[Direction.EAST]))]
        
        score = _score_location(entity, fact_set, gs, map_kg, CostConfig())
        
        assert score.credit_type == CreditType.PARTIAL
        assert score.partial_credit == 0.6 # 1 - (2/5)
    finally:
        calculate_iac.is_location_satisfying_constraint = orig_is_sat

if __name__ == "__main__":
    pytest.main([__file__])
