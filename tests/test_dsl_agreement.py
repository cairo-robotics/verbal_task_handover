import pytest
from src.core.representations.pydantic_schema import (
    KnowledgeGraph, LocationFact, SpatialFact, RelationFact, ConnectionFact, Argument, Location, SpatialRelationType, RelationPredicate, Direction
)
from src.core.utils.normalization import normalize_entity_name
from analysis.calculate_dsl_agreement import (
    resolves_to, get_associated_patient, extract_slots, resolve_location_fact
)

# Mock GameState class for testing
class MockGameState:
    def __init__(self, objects):
        self._objects = objects

def test_resolves_to_named():
    arg = Argument(type="named", value="lily")
    assert resolves_to(arg, "lily") is True
    assert resolves_to(arg, "oliver") is False

def test_resolves_to_existential_no_location():
    # Potion check
    arg_pot = Argument(type="existential", value="potion")
    assert resolves_to(arg_pot, "gold potion") is True
    assert resolves_to(arg_pot, "lily") is False

    # Person check
    arg_person = Argument(type="existential", value="someone")
    assert resolves_to(arg_person, "lily") is True
    assert resolves_to(arg_person, "gold potion") is False

def test_resolves_to_existential_with_location():
    # Setup mock telemetry with room connections
    # room 0 connected to room 1 via north
    facts = [
        ConnectionFact(
            location_a=Location(type="room", room="room 0"),
            location_b=Location(type="room", room="room 1"),
            direction=Direction.NORTH
        ),
        # Player location
        LocationFact(
            entity=Argument(type="named", value="player"),
            location=Location(type="room", room="room 0")
        )
    ]
    telemetry_kg = KnowledgeGraph(facts=facts)
    entity_rooms_gt = {"lily": "room 1", "oliver": "room 2"}
    
    # Existential to the north
    arg = Argument(
        type="existential",
        value="someone",
        location=Location(type="directional", directions=[Direction.NORTH])
    )
    
    # Lily is in room 1 (north of room 0), so she should match
    assert resolves_to(arg, "lily", entity_rooms_gt, telemetry_kg, "room 0") is True
    # Oliver is in room 2 (not north), so he should not match
    assert resolves_to(arg, "oliver", entity_rooms_gt, telemetry_kg, "room 0") is False

def test_get_associated_patient():
    # 1. Associated by named subject/target
    fact1 = LocationFact(
        entity=Argument(type="named", value="oliver"),
        location=Location(type="room", room="room 2")
    )
    assert get_associated_patient(fact1, KnowledgeGraph(facts=[]), {}) == "oliver"

    # 2. Associated by relation resource (needs_potion)
    # Lily needs gold potion in ground truth
    fact2 = RelationFact(
        predicate=RelationPredicate.NEEDS_POTION,
        subject=Argument(type="existential", value="someone"),
        object=Argument(type="named", value="gold potion")
    )
    assert get_associated_patient(fact2, KnowledgeGraph(facts=[]), {}) == "lily"

    # 3. Associated by location constraint
    facts = [
        ConnectionFact(
            location_a=Location(type="room", room="room 0"),
            location_b=Location(type="room", room="room 1"),
            direction=Direction.NORTH
        )
    ]
    telemetry_kg = KnowledgeGraph(facts=facts)
    entity_rooms_gt = {"lily": "room 1"}
    fact3 = LocationFact(
        entity=Argument(type="existential", value="someone", location=Location(type="directional", directions=[Direction.NORTH])),
        location=Location(type="room", room="room 1")
    )
    assert get_associated_patient(fact3, telemetry_kg, entity_rooms_gt) == "lily"

def test_extract_slots():
    # Setup telemetry where room 0 connects to room 1 (north) and room 2 (south)
    telemetry_facts = [
        ConnectionFact(
            location_a=Location(type="room", room="room 0"),
            location_b=Location(type="room", room="room 1"),
            direction=Direction.NORTH
        ),
        ConnectionFact(
            location_a=Location(type="room", room="room 0"),
            location_b=Location(type="room", room="room 2"),
            direction=Direction.SOUTH
        ),
        LocationFact(
            entity=Argument(type="named", value="player"),
            location=Location(type="room", room="room 0")
        )
    ]
    telemetry_kg = KnowledgeGraph(facts=telemetry_facts)
    
    # Ground truth: lily is in room 1 (needs gold), oliver is in room 2 (needs blue)
    game_state = MockGameState(
        objects={
            "room 1": ["lily"],
            "room 2": ["oliver"],
            "room 0": ["player"]
        }
    )
    
    # Mock report graph
    report_facts = [
        # Player is in room 0
        LocationFact(
            entity=Argument(type="named", value="player"),
            location=Location(type="room", room="room 0")
        ),
        # Someone to the north needs a gold potion
        RelationFact(
            predicate=RelationPredicate.NEEDS_POTION,
            subject=Argument(type="existential", value="someone", location=Location(type="directional", directions=[Direction.NORTH])),
            object=Argument(type="named", value="gold potion")
        ),
        # Gold potion is to the north
        SpatialFact(
            type=SpatialRelationType.ABSOLUTE,
            subject=Argument(type="named", value="gold potion"),
            direction=Direction.NORTH
        )
    ]
    report_kg = KnowledgeGraph(facts=report_facts)
    
    slots = extract_slots(report_kg, telemetry_kg, game_state)
    
    # Verify player location
    assert slots["player_location"] == "room 0"
    # Verify lily location (lily is north, so she matches the need fact subject location)
    assert slots["lily_location"] == "room 1"
    # Verify lily need
    assert slots["lily_need"] == "potion:goldpotion"
    # Verify lily resource location (gold potion is north -> room 1)
    assert slots["lily_resource_location"] == "room 1"
    
    # Oliver was not mentioned in report, so his slots should be None
    assert slots["oliver_location"] is None
    assert slots["oliver_need"] is None
    assert slots["oliver_resource_location"] is None
