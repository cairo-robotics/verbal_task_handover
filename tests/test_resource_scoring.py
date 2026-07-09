import pytest
from src.pipelines.evaluation.calculate_iac import _score_resource
from src.core.representations.pydantic_schema import (
    Fact, 
    LocationFact, 
    Location, 
    Argument, 
    KnowledgeGraph
)
from src.pipelines.evaluation.costs import CostConfig, PATIENT_DATA
from src.pipelines.evaluation.report_iac import CreditType

class MockNPC:
    def __init__(self, name, held_item_interact_complete=False, conditional_interact_counts=None):
        self.name = name
        self.held_item_interact_complete = held_item_interact_complete
        self.conditional_interact_counts = conditional_interact_counts or {}

class MockGameState:
    def __init__(self, objects):
        self._objects = objects

@pytest.fixture
def map_graph():
    # Simple map: room 1 -> room 0 (south)
    return KnowledgeGraph(facts=[])

@pytest.fixture
def cost_config():
    return CostConfig()

def test_resource_score_potion_success(map_graph, cost_config):
    # Lily needs gold potion. Gold potion is in storage_1.
    lily = MockNPC("lily", held_item_interact_complete=False)
    # Note: PATIENT_DATA says lily needs gold potion.
    gs = MockGameState({
        "room 1": {"lily": lily},
        "storage_1": {"gold potion": "some_obj"}
    })
    
    # Report says gold potion is in storage_1
    fact_set = [
        LocationFact(
            id="f1",
            entity=Argument(type="named", value="gold potion"),
            location=Location(type="room", room="storage_1")
        )
    ]
    
    score = _score_resource("lily", fact_set, gs, map_graph, cost_config)
    
    assert score.credit_type == CreditType.FULL
    assert score.partial_credit == 1.0
    # max_cost depends on rooms. _get_all_rooms might be empty here.
    # If empty, _get_all_rooms returns set(). 
    # _calculate_location_score uses true_room if available.
    # true_room = storage_1. all_rooms = {storage_1}. num_rooms = 1. max_cost = 0.5.
    assert score.max_cost == 41.5

def test_resource_score_potion_none(map_graph, cost_config):
    lily = MockNPC("lily", held_item_interact_complete=False)
    gs = MockGameState({
        "room 1": {"lily": lily},
        "storage_1": {"gold potion": "some_obj"}
    })
    
    # Report says nothing about gold potion
    fact_set = []
    
    score = _score_resource("lily", fact_set, gs, map_graph, cost_config)
    
    assert score.credit_type == CreditType.NONE
    assert score.partial_credit == 0.0

def test_resource_score_npc_target(map_graph, cost_config):
    # Lily needs to talk to Eliza. Eliza is in lounge_1.
    lily = MockNPC("lily", held_item_interact_complete=True)
    eliza = MockNPC("eliza", conditional_interact_counts={"request from room 1": 0})
    
    gs = MockGameState({
        "room 1": {"lily": lily},
        "lounge_1": {"eliza": eliza}
    })
    
    # Report says Eliza is in lounge_1
    fact_set = [
        LocationFact(
            id="f1",
            entity=Argument(type="named", value="eliza"),
            location=Location(type="room", room="lounge_1")
        )
    ]
    
    score = _score_resource("lily", fact_set, gs, map_graph, cost_config)
    
    assert score.credit_type == CreditType.FULL
    assert score.partial_credit == 1.0

def test_resource_score_no_need(map_graph, cost_config):
    # unknown_patient is not in PATIENT_DATA, so they have no outstanding needs
    gs = MockGameState({
        "room 1": {}
    })
    
    score = _score_resource("unknown_patient", [], gs, map_graph, cost_config)
    
    # No need -> FULL credit for 0 cost
    assert score.credit_type == CreditType.FULL
    assert score.max_cost == 0.0
    assert score.partial_credit == 1.0

if __name__ == "__main__":
    pytest.main([__file__])
