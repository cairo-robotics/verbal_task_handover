
import pytest
from src.core.representations.pydantic_schema import (
    Argument,
    KnowledgeGraph,
    Location,
    LocationFact,
    RelationFact,
    RelationPredicate,
    Direction,
    ConnectionFact,
)
from src.pipelines.model_alignment.entity_alignment import AlignmentResult
from src.pipelines.model_alignment.fact_alignment import align_facts

def _named(value: str) -> Argument:
    return Argument(type="named", value=value)

def _existential(location: Location = None) -> Argument:
    return Argument(type="existential", location=location)

def _room(name: str) -> Location:
    return Location(type="room", room=name)

def _directional(dirs: list[Direction]) -> Location:
    return Location(type="directional", directions=dirs)

def _kg(*facts) -> KnowledgeGraph:
    return KnowledgeGraph(facts=list(facts))

def test_existential_report_matches_named_telemetry_spatial():
    """
    Reproduce the issue where a general report fact fails to align with a specific telemetry fact,
    especially with a 'west then north' path.
    """
    # 1. Base Graph (Telemetry): Lily has a message, Lily is in room 1, room 1 is West then North of room 0
    tf = RelationFact(
        id="t1",
        predicate=RelationPredicate.HAS_MESSAGE_FOR,
        subject=_named("lily"),
        target=_existential()
    )
    tl_loc = LocationFact(id="t2", entity=_named("lily"), location=_room("room 1"))
    
    # Path: room 0 --WEST--> room 2 --NORTH--> room 1
    # Real telemetry might have it reversed: room 2 --EAST--> room 0
    tl_conn1 = ConnectionFact(id="c1", location_a=_room("room 2"), location_b=_room("room 0"), direction=Direction.EAST)
    tl_conn2 = ConnectionFact(id="c2", location_a=_room("room 2"), location_b=_room("room 1"), direction=Direction.NORTH)
    
    telemetry = _kg(tf, tl_loc, tl_conn1, tl_conn2)

    # 2. New Graph (Report): Someone in the west has a message
    rf = RelationFact(
        id="r1",
        predicate=RelationPredicate.HAS_MESSAGE_FOR,
        subject=_existential(location=_directional([Direction.WEST])),
        target=_existential()
    )
    report = _kg(rf)

    # 3. Align
    result = align_facts(report, telemetry, AlignmentResult())

    # This is expected to fail currently
    assert "r1" in result.resolution_confirmed_fact_ids, f"Fact r1 should be aligned, but got result: {result}"

if __name__ == "__main__":
    try:
        test_existential_report_matches_named_telemetry_spatial()
        print("Test PASSED")
    except AssertionError as e:
        print(f"Test FAILED: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")
