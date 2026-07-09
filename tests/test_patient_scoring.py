import pytest
from src.pipelines.evaluation.calculate_iac import _score_entity, _score_location, _score_need, _score_resource
from src.core.utils.spatial_reasoning import ConnectionFact
from src.core.representations.pydantic_schema import (
    Fact, 
    LocationFact, 
    SpatialFact,
    RelationFact,
    RelationPredicate,
    Location, 
    Argument, 
    KnowledgeGraph,
    Direction,
    SpatialRelationType
)
from src.pipelines.evaluation.costs import CostConfig, PATIENT_DATA
from src.pipelines.evaluation.report_iac import CreditType, EntityScore, ComponentScore

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
    # Simple map graph
    return KnowledgeGraph(facts=[])

@pytest.fixture
def cost_config():
    return CostConfig()

def test_case_1_full_match(map_graph, cost_config):
    # Case 1: {lily is in room 1, lily needs gold potion, gold potion is in storage 1}
    lily = MockNPC("lily", held_item_interact_complete=False)
    gs = MockGameState({
        "room 1": {"lily": lily},
        "storage_1": {"gold potion": "obj"}
    })
    
    fact_set = [
        LocationFact(id="f1", entity=Argument(type="named", value="lily"), location=Location(type="room", room="room 1")),
        RelationFact(id="f2", predicate=RelationPredicate.NEEDS_POTION, subject=Argument(type="named", value="lily"), object=Argument(type="named", value="gold potion")),
        LocationFact(id="f3", entity=Argument(type="named", value="gold potion"), location=Location(type="room", room="storage_1"))
    ]
    
    score = _score_entity("lily", fact_set, gs, map_graph, cost_config)
    
    assert score.location_score.credit_type == CreditType.FULL
    assert score.need_score.credit_type == CreditType.FULL
    assert score.resource_score.credit_type == CreditType.FULL

def test_case_2_partial_need(map_graph, cost_config):
    # Case 2: {lily is in room 1, lily needs a potion}
    lily = MockNPC("lily", held_item_interact_complete=False)
    gs = MockGameState({
        "room 1": {"lily": lily},
        "storage_1": {"gold potion": "obj"}
    })
    
    fact_set = [
        LocationFact(id="f1", entity=Argument(type="named", value="lily"), location=Location(type="room", room="room 1")),
        RelationFact(id="f2", predicate=RelationPredicate.NEEDS_POTION, subject=Argument(type="named", value="lily"), object=Argument(type="named", value="potion"))
    ]
    
    score = _score_entity("lily", fact_set, gs, map_graph, cost_config)
    
    assert score.location_score.credit_type == CreditType.FULL
    assert score.need_score.credit_type == CreditType.PARTIAL
    assert score.resource_score.credit_type == CreditType.NONE

def test_case_3_existential_room(map_graph, cost_config):
    # Case 3: {someone in room 1 needs gold potion}
    # Location: room 1 is exact and subject can be resolved exactly -> FULL
    # Need: fully specified for matching subject -> FULL
    # Resource: no potion location fact -> NONE
    lily = MockNPC("lily", held_item_interact_complete=False)
    gs = MockGameState({
        "room 1": {"lily": lily},
        "storage_1": {"gold potion": "obj"}
    })
    
    fact_set = [
        RelationFact(
            id="f1", 
            predicate=RelationPredicate.NEEDS_POTION, 
            subject=Argument(type="existential", location=Location(type="room", room="room 1")), 
            object=Argument(type="named", value="gold potion")
        )
    ]
    
    score = _score_entity("lily", fact_set, gs, map_graph, cost_config)
    
    # Note: Currently _score_location will return NONE because it doesn't look at RelationFacts.
    # And _score_need will return FULL (this part works).
    assert score.location_score.credit_type == CreditType.FULL
    assert score.need_score.credit_type == CreditType.FULL
    assert score.resource_score.credit_type == CreditType.NONE

def test_case_4_existential_direction(map_graph, cost_config):
    # Case 4: {someone to the west needs gold potion} (no potion location)
    # Location: existential that only partially reduces candidates -> PARTIAL
    # Need: exact match for applicable subject -> FULL
    lily = MockNPC("lily", held_item_interact_complete=False)
    # To test PARTIAL, we need multiple rooms.
    # We'll mock map_graph behavior or add facts to it.
    
    # Let's say there are 4 rooms: room 0, room 1, room 2, room 3.
    # Room 1 is West of Room 0.
    # Lily is in Room 1.
    gs = MockGameState({
        "room 1": {"lily": lily},
        "room 0": {},
        "room 2": {},
        "room 3": {}
    })
    
    # We need to populate map_graph with enough info for directional check
    # Or we can just mock is_location_satisfying_constraint if we wanted to be lazy, 
    # but let's use the real one.
    # In src/core/utils/spatial_reasoning.py, it uses ConnectionFacts.
    # Wait, I don't want to overcomplicate the test setup if I can just use a simple map.
    
    fact_set = [
        RelationFact(
            id="f1", 
            predicate=RelationPredicate.NEEDS_POTION, 
            subject=Argument(type="existential", location=Location(type="directional", directions=[Direction.WEST], mode="path")), 
            object=Argument(type="named", value="gold potion")
        )
    ]
    
    # We need to make sure map_graph.facts has some connection facts so num_rooms > 1
    map_graph.facts = [
        LocationFact(id="m1", entity=Argument(type="named", value="room 1"), location=Location(type="room", room="room 1")),
        LocationFact(id="m2", entity=Argument(type="named", value="room 0"), location=Location(type="room", room="room 0")),
        LocationFact(id="m3", entity=Argument(type="named", value="room 2"), location=Location(type="room", room="room 2")),
        ConnectionFact(
            id="c1",
            location_a=Location(type="room", room="room 0"),
            location_b=Location(type="room", room="room 1"),
            direction=Direction.WEST
        ),
        ConnectionFact(
            id="c2",
            location_a=Location(type="room", room="room 0"),
            location_b=Location(type="room", room="room 2"),
            direction=Direction.WEST
        )
    ]
    
    score = _score_entity("lily", fact_set, gs, map_graph, cost_config)
    
    assert score.location_score.credit_type == CreditType.PARTIAL
    assert score.need_score.credit_type == CreditType.FULL

def test_case_5_resource_only(map_graph, cost_config):
    # Case 5: {gold potion is in storage_1} (no info about lily)
    lily = MockNPC("lily", held_item_interact_complete=False)
    gs = MockGameState({
        "room 1": {"lily": lily},
        "storage_1": {"gold potion": "obj"}
    })
    
    fact_set = [
        LocationFact(id="f1", entity=Argument(type="named", value="gold potion"), location=Location(type="room", room="storage_1"))
    ]
    
    score = _score_entity("lily", fact_set, gs, map_graph, cost_config)
    
    assert score.location_score.credit_type == CreditType.NONE
    assert score.need_score.credit_type == CreditType.NONE
    assert score.resource_score.credit_type == CreditType.FULL

def test_case_6_contradicted_location(map_graph, cost_config):
    # Case 6: {lily is in room 3, lily needs gold potion, gold potion is in storage_1} (contradicted location)
    # Lily is in room 1
    lily = MockNPC("lily", held_item_interact_complete=False)
    gs = MockGameState({
        "room 1": {"lily": lily},
        "storage_1": {"gold potion": "obj"}
    })
    
    fact_set = [
        LocationFact(id="f1", entity=Argument(type="named", value="lily"), location=Location(type="room", room="room 3")),
        RelationFact(id="f2", predicate=RelationPredicate.NEEDS_POTION, subject=Argument(type="named", value="lily"), object=Argument(type="named", value="gold potion")),
        LocationFact(id="f3", entity=Argument(type="named", value="gold potion"), location=Location(type="room", room="storage_1"))
    ]
    
    score = _score_entity("lily", fact_set, gs, map_graph, cost_config)
    
    assert score.location_score.credit_type == CreditType.CONTRADICTED
    assert score.need_score.credit_type == CreditType.FULL
    assert score.resource_score.credit_type == CreditType.FULL
