import pytest
from src.core.representations.pydantic_schema import (
    KnowledgeGraph, Location, Argument, RelationFact, 
    RelationPredicate, ConnectionFact, Direction
)
from src.pipelines.evaluation.calculate_iac import _score_need
from src.pipelines.evaluation.costs import CostConfig
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
def cost_config():
    return CostConfig()

@pytest.fixture
def empty_map():
    return KnowledgeGraph(facts=[])

def test_score_need_exact(cost_config, empty_map):
    lily = MockNPC("lily", held_item_interact_complete=False)
    gs = MockGameState({"room 1": {"lily": lily}})
    
    fact_set = [
        RelationFact(
            predicate=RelationPredicate.NEEDS_POTION,
            subject=Argument(type="named", value="lily"),
            object=Argument(type="named", value="gold potion")
        )
    ]
    
    score = _score_need("lily", fact_set, gs, empty_map, cost_config)
    assert score.credit_type == CreditType.FULL
    assert score.partial_credit == 1.0

def test_score_need_existential_subject(cost_config, empty_map):
    lily = MockNPC("lily", held_item_interact_complete=False)
    gs = MockGameState({"room 1": {"lily": lily}})
    
    # Candidate: someone needs gold potion
    fact_set = [
        RelationFact(
            predicate=RelationPredicate.NEEDS_POTION,
            subject=Argument(type="existential"),
            object=Argument(type="named", value="gold potion")
        )
    ]
    
    score = _score_need("lily", fact_set, gs, empty_map, cost_config)
    assert score.credit_type == CreditType.FULL
    assert score.partial_credit == 1.0

def test_score_need_existential_object(cost_config, empty_map):
    lily = MockNPC("lily", held_item_interact_complete=False)
    gs = MockGameState({"room 1": {"lily": lily}})
    
    # Candidate: lily needs a potion
    fact_set = [
        RelationFact(
            predicate=RelationPredicate.NEEDS_POTION,
            subject=Argument(type="named", value="lily"),
            object=Argument(type="existential")
        )
    ]
    
    score = _score_need("lily", fact_set, gs, empty_map, cost_config)
    assert score.credit_type == CreditType.PARTIAL
    assert score.partial_credit == cost_config.partial_need_credit

def test_score_need_misinformation(cost_config, empty_map):
    lily = MockNPC("lily", held_item_interact_complete=False)
    gs = MockGameState({"room 1": {"lily": lily}})
    
    # Candidate: lily needs a red potion (gold is needed)
    fact_set = [
        RelationFact(
            predicate=RelationPredicate.NEEDS_POTION,
            subject=Argument(type="named", value="lily"),
            object=Argument(type="named", value="red potion")
        )
    ]
    
    score = _score_need("lily", fact_set, gs, empty_map, cost_config)
    assert score.credit_type == CreditType.CONTRADICTED
    assert score.partial_credit == 0.0

def test_score_need_spatial_existential(cost_config):
    lily = MockNPC("lily", held_item_interact_complete=False)
    gs = MockGameState({"room 1": {"lily": lily}})
    
    # Map: room 0 --WEST--> room 1
    map_graph = KnowledgeGraph(facts=[
        ConnectionFact(
            location_a=Location(type="room", room="room 0"),
            location_b=Location(type="room", room="room 1"),
            direction=Direction.WEST
        )
    ])
    
    # Case 1: Matching spatial constraint
    fact_set_1 = [
        RelationFact(
            predicate=RelationPredicate.NEEDS_POTION,
            subject=Argument(
                type="existential", 
                location=Location(type="directional", directions=[Direction.WEST], mode="path")
            ),
            object=Argument(type="named", value="gold potion")
        )
    ]
    score_1 = _score_need("lily", fact_set_1, gs, map_graph, cost_config)
    assert score_1.credit_type == CreditType.FULL
    
    # Case 2: Mismatched spatial constraint (lily is west, constraint is east)
    fact_set_2 = [
        RelationFact(
            predicate=RelationPredicate.NEEDS_POTION,
            subject=Argument(
                type="existential", 
                location=Location(type="directional", directions=[Direction.EAST], mode="path")
            ),
            object=Argument(type="named", value="gold potion")
        )
    ]
    score_2 = _score_need("lily", fact_set_2, gs, map_graph, cost_config)
    assert score_2.credit_type == CreditType.NONE # Omission for Lily

def test_score_need_has_message(cost_config, empty_map):
    # Setup Lily needing to talk to Eliza
    lily = MockNPC("lily", held_item_interact_complete=True)
    eliza = MockNPC("eliza", held_item_interact_complete=False, conditional_interact_counts={"request from room 1": 0})
    gs = MockGameState({"room 1": {"lily": lily}, "lounge_1": {"eliza": eliza}})
    
    # Candidate 1: Full match
    fact_set_1 = [
        RelationFact(
            predicate=RelationPredicate.HAS_MESSAGE_FOR,
            subject=Argument(type="named", value="lily"),
            target=Argument(type="named", value="eliza")
        )
    ]
    assert _score_need("lily", fact_set_1, gs, empty_map, cost_config).credit_type == CreditType.FULL
    
    # Candidate 2: Vague recipient
    fact_set_2 = [
        RelationFact(
            predicate=RelationPredicate.HAS_MESSAGE_FOR,
            subject=Argument(type="named", value="lily"),
            target=Argument(type="existential")
        )
    ]
    assert _score_need("lily", fact_set_2, gs, empty_map, cost_config).credit_type == CreditType.PARTIAL
    
    # Candidate 3: Vague subject (someone has message for Eliza)
    fact_set_3 = [
        RelationFact(
            predicate=RelationPredicate.HAS_MESSAGE_FOR,
            subject=Argument(type="existential"),
            target=Argument(type="named", value="eliza")
        )
    ]
    assert _score_need("lily", fact_set_3, gs, empty_map, cost_config).credit_type == CreditType.FULL

def test_score_need_omission(cost_config, empty_map):
    lily = MockNPC("lily", held_item_interact_complete=False)
    gs = MockGameState({"room 1": {"lily": lily}})
    
    fact_set = []
    
    score = _score_need("lily", fact_set, gs, empty_map, cost_config)
    assert score.credit_type == CreditType.NONE
    assert score.max_cost == 5.0

def test_score_need_no_gold_fact(cost_config, empty_map):
    # Lily is all done
    lily = MockNPC("lily", held_item_interact_complete=True, conditional_interact_counts={"response from Eliza": 1, "response from Lola": 1})
    gs = MockGameState({"room 1": {"lily": lily}})
    
    # Candidate 1: No facts (correct)
    assert _score_need("lily", [], gs, empty_map, cost_config).max_cost == 0.0
    
    # Candidate 2: Erroneous fact (misinformation)
    fact_set_2 = [
        RelationFact(
            predicate=RelationPredicate.NEEDS_POTION,
            subject=Argument(type="named", value="lily"),
            object=Argument(type="named", value="gold potion")
        )
    ]
    assert _score_need("lily", fact_set_2, gs, empty_map, cost_config).credit_type == CreditType.CONTRADICTED

if __name__ == "__main__":
    pytest.main([__file__])
