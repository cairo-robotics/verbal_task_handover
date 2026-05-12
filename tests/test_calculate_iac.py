
import pytest
from unittest.mock import MagicMock
from src.pipelines.evaluation.calculate_iac import _score_location
from src.core.representations.pydantic_schema import (
    KnowledgeGraph, LocationFact, SpatialFact, Argument, Location, Direction, SpatialRelationType, ConnectionFact
)
from src.pipelines.evaluation.report_iac import CreditType
from src.pipelines.evaluation.costs import CostConfig

# Mock GameState
class MockGameState:
    def __init__(self, objects):
        self._objects = objects

def test_score_location_full_credit():
    # Setup
    entity = "lily"
    gs = MockGameState({"room 1": {"lily": MagicMock()}})
    
    # Map: room 0 --EAST--> room 1
    map_kg = KnowledgeGraph(facts=[
        ConnectionFact(location_a=Location(type="room", room="room 0"), 
                       location_b=Location(type="room", room="room 1"), 
                       direction=Direction.EAST)
    ])
    
    # NPC says: lily is in room 1
    fact_set = [
        LocationFact(entity=Argument(type="named", value="lily"), 
                     location=Location(type="room", room="room 1"))
    ]
    
    score = _score_location(entity, fact_set, gs, map_kg, CostConfig())
    
    assert score.credit_type == CreditType.FULL
    assert score.partial_credit == 1.0

def test_score_location_partial_credit():
    # Setup
    entity = "lily"
    gs = MockGameState({"room 1": {"lily": MagicMock()}})
    
    # Map: room 0 --EAST--> room 1, room 0 --WEST--> room 2, room 1 --EAST--> room 3
    # All rooms: room 0, room 1, room 2, room 3 (Total 4)
    map_kg = KnowledgeGraph(facts=[
        ConnectionFact(location_a=Location(type="room", room="room 0"), 
                       location_b=Location(type="room", room="room 1"), 
                       direction=Direction.EAST),
        ConnectionFact(location_a=Location(type="room", room="room 0"), 
                       location_b=Location(type="room", room="room 2"), 
                       direction=Direction.WEST),
        ConnectionFact(location_a=Location(type="room", room="room 1"), 
                       location_b=Location(type="room", room="room 3"), 
                       direction=Direction.EAST)
    ])
    
    # NPC says: lily is to the east (relative to room 0)
    # Rooms east of room 0: room 1, room 3 (Total 2)
    fact_set = [
        SpatialFact(type=SpatialRelationType.RELATIVE, 
                    subject=Argument(type="named", value="lily"), 
                    direction=Direction.EAST, 
                    reference=Argument(type="named", value="room 0"))
    ]
    
    score = _score_location(entity, fact_set, gs, map_kg, CostConfig())
    
    assert score.credit_type == CreditType.PARTIAL
    # reduction_factor = 1 - (2/5) = 0.6 (relative to patient baseline)
    assert score.partial_credit == 0.6
    assert score.max_cost == 83.20

def test_score_location_contradicted():
    entity = "lily"
    gs = MockGameState({"room 1": {"lily": MagicMock()}})
    map_kg = KnowledgeGraph(facts=[
        ConnectionFact(location_a=Location(type="room", room="room 0"), 
                       location_b=Location(type="room", room="room 1"), 
                       direction=Direction.EAST)
    ])
    
    # NPC says: lily is in room 0
    fact_set = [
        LocationFact(entity=Argument(type="named", value="lily"), 
                     location=Location(type="room", room="room 0"))
    ]
    
    score = _score_location(entity, fact_set, gs, map_kg, CostConfig())
    assert score.credit_type == CreditType.CONTRADICTED

def test_score_location_none():
    entity = "lily"
    gs = MockGameState({"room 1": {"lily": MagicMock()}})
    map_kg = KnowledgeGraph(facts=[])
    fact_set = []
    
    score = _score_location(entity, fact_set, gs, map_kg, CostConfig())
    assert score.credit_type == CreditType.NONE

def test_score_location_priority():
    # NPC provides both correct directional and incorrect absolute.
    # Priority: Absolute wins.
    entity = "lily"
    gs = MockGameState({"room 1": {"lily": MagicMock()}})
    map_kg = KnowledgeGraph(facts=[
        ConnectionFact(location_a=Location(type="room", room="room 0"), 
                       location_b=Location(type="room", room="room 1"), 
                       direction=Direction.EAST)
    ])
    
    fact_set = [
        SpatialFact(type=SpatialRelationType.RELATIVE, 
                    subject=Argument(type="named", value="lily"), 
                    direction=Direction.EAST, 
                    reference=Argument(type="named", value="room 0")), # Correct Directional
        LocationFact(entity=Argument(type="named", value="lily"), 
                     location=Location(type="room", room="room 0")) # Incorrect Absolute
    ]
    
    score = _score_location(entity, fact_set, gs, map_kg, CostConfig())
    # Absolute wins, so it's CONTRADICTED because room 0 != room 1
    assert score.credit_type == CreditType.CONTRADICTED

if __name__ == "__main__":
    pytest.main([__file__])
