import pytest
from unittest.mock import MagicMock
from src.pipelines.evaluation.calculate_iac import get_patient_status_facts
from src.core.representations.pydantic_schema import RelationPredicate

class MockNPC:
    def __init__(self, name, held_item_interact_complete=False, conditional_interact_counts=None):
        self.name = name
        self.held_item_interact_complete = held_item_interact_complete
        self.conditional_interact_counts = conditional_interact_counts or {}

class MockGameState:
    def __init__(self, objects):
        self._objects = objects

def test_needs_potion():
    # Lily needs gold potion
    lily = MockNPC("lily", held_item_interact_complete=False)
    gs = MockGameState({"room 1": {"lily": lily}})
    
    facts = get_patient_status_facts("lily", gs)
    assert len(facts) == 1
    assert facts[0].predicate == RelationPredicate.NEEDS_POTION
    assert facts[0].subject.value == "lily"
    assert facts[0].object.value == "gold potion"

def test_has_message():
    # Lily got potion, needs to talk to Eliza (first in sequence)
    lily = MockNPC("lily", held_item_interact_complete=True)
    eliza = MockNPC("eliza", held_item_interact_complete=False, conditional_interact_counts={"request from room 1": 0})
    lola = MockNPC("lola", held_item_interact_complete=False, conditional_interact_counts={"request from room 1": 0})
    
    gs = MockGameState({"room 1": {"lily": lily}, "lounge_1": {"lola": lola, "eliza": eliza}})
    
    facts = get_patient_status_facts("lily", gs)
    assert len(facts) == 2
    assert facts[0].predicate == RelationPredicate.NEEDS_POTION
    assert facts[1].predicate == RelationPredicate.HAS_MESSAGE_FOR
    assert facts[1].subject.value == "lily"
    assert facts[1].target.value == "eliza"

def test_expecting_response():
    # Lily got potion, Eliza got request, Lola hasn't.
    # Eliza should have message for Lily (response).
    lily = MockNPC("lily", held_item_interact_complete=True, conditional_interact_counts={})
    eliza = MockNPC("eliza", held_item_interact_complete=False, conditional_interact_counts={"request from room 1": 1})
    lola = MockNPC("lola", held_item_interact_complete=False, conditional_interact_counts={"request from room 1": 0})
    
    gs = MockGameState({"room 1": {"lily": lily}, "lounge_1": {"lola": lola, "eliza": eliza}})
    
    facts = get_patient_status_facts("lily", gs)
    assert len(facts) == 2
    assert facts[0].predicate == RelationPredicate.NEEDS_POTION
    assert facts[1].predicate == RelationPredicate.HAS_MESSAGE_FOR
    assert facts[1].subject.value == "eliza"
    assert facts[1].target.value == "lily"

def test_sequence_progression():
    # Lily got response from Eliza, now needs to talk to Lola.
    lily = MockNPC("lily", held_item_interact_complete=True, conditional_interact_counts={"response from Eliza": 1})
    eliza = MockNPC("eliza", held_item_interact_complete=False, conditional_interact_counts={"request from room 1": 1})
    lola = MockNPC("lola", held_item_interact_complete=False, conditional_interact_counts={"request from room 1": 0})
    
    gs = MockGameState({"room 1": {"lily": lily}, "lounge_1": {"lola": lola, "eliza": eliza}})
    
    facts = get_patient_status_facts("lily", gs)
    assert len(facts) == 2
    assert facts[0].predicate == RelationPredicate.NEEDS_POTION
    assert facts[1].predicate == RelationPredicate.HAS_MESSAGE_FOR
    assert facts[1].subject.value == "lily"
    assert facts[1].target.value == "lola"

def test_all_done():
    # Lily got potion, both Lola and Eliza got request, Lily got both responses.
    # Under the handover task design, steps 1-3 being complete means she needs the potion again (step 4).
    lily = MockNPC("lily", held_item_interact_complete=True, 
                   conditional_interact_counts={"response from Eliza": 1, "response from Lola": 1})
    lola = MockNPC("lola", held_item_interact_complete=False, conditional_interact_counts={"request from room 1": 1})
    eliza = MockNPC("eliza", held_item_interact_complete=False, conditional_interact_counts={"request from room 1": 1})
    
    gs = MockGameState({"room 1": {"lily": lily}, "lounge_1": {"lola": lola, "eliza": eliza}})
    
    facts = get_patient_status_facts("lily", gs)
    assert len(facts) == 1
    assert facts[0].predicate == RelationPredicate.NEEDS_POTION
    assert facts[0].subject.value == "lily"
    assert facts[0].object.value == "gold potion"

def test_single_target_patient():
    # Oliver needs blue potion
    oliver = MockNPC("oliver", held_item_interact_complete=False)
    gs = MockGameState({"room 2": {"oliver": oliver}})
    
    facts = get_patient_status_facts("oliver", gs)
    assert len(facts) == 1
    assert facts[0].predicate == RelationPredicate.NEEDS_POTION
    assert facts[0].object.value == "blue potion"

if __name__ == "__main__":
    pytest.main([__file__])
