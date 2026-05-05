
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

class TestSpatialRobustness:
    def test_prefix_match_west_north(self):
        """Test that ['west'] matches ['west', 'north'] but ['west', 'south'] doesn't match ['west', 'north']."""
        # Telemetry: room0 --WEST--> room2 --NORTH--> room1
        # Lily is in room 1
        tf = RelationFact(id="t1", predicate=RelationPredicate.HAS_MESSAGE_FOR, subject=_named("lily"))
        tl_loc = LocationFact(id="t2", entity=_named("lily"), location=_room("room 1"))
        tl_conn1 = ConnectionFact(id="c1", location_a=_room("room 0"), location_b=_room("room 2"), direction=Direction.WEST)
        tl_conn2 = ConnectionFact(id="c2", location_a=_room("room 2"), location_b=_room("room 1"), direction=Direction.NORTH)
        telemetry = _kg(tf, tl_loc, tl_conn1, tl_conn2)

        # 1. Report: Someone in the west has a message
        rf1 = RelationFact(id="r1", predicate=RelationPredicate.HAS_MESSAGE_FOR, subject=_existential(location=_directional([Direction.WEST])))
        res1 = align_facts(_kg(rf1), telemetry, AlignmentResult())
        assert "r1" in res1.resolution_confirmed_fact_ids

        # 2. Report: Someone in the west then north has a message
        rf2 = RelationFact(id="r2", predicate=RelationPredicate.HAS_MESSAGE_FOR, subject=_existential(location=_directional([Direction.WEST, Direction.NORTH])))
        res2 = align_facts(_kg(rf2), telemetry, AlignmentResult())
        assert "r2" in res2.resolution_confirmed_fact_ids

        # 3. Report: Someone in the west then south has a message
        rf3 = RelationFact(id="r3", predicate=RelationPredicate.HAS_MESSAGE_FOR, subject=_existential(location=_directional([Direction.WEST, Direction.SOUTH])))
        res3 = align_facts(_kg(rf3), telemetry, AlignmentResult())
        assert "r3" in res3.novel_fact_ids # Should not match because [WEST, SOUTH] is not prefix of [WEST, NORTH]

    def test_prefix_match_empty_directions(self):
        """Test that existential without directions matches everything."""
        tf = RelationFact(id="t1", predicate=RelationPredicate.HAS_MESSAGE_FOR, subject=_named("lily"))
        tl_loc = LocationFact(id="t2", entity=_named("lily"), location=_room("room 1"))
        telemetry = _kg(tf, tl_loc)

        rf = RelationFact(id="r1", predicate=RelationPredicate.HAS_MESSAGE_FOR, subject=_existential())
        res = align_facts(_kg(rf), telemetry, AlignmentResult())
        assert "r1" in res.resolution_confirmed_fact_ids

    def test_longest_path_does_not_mask_prefix(self):
        """Test that BFS finds the shortest path, and prefix match works on that."""
        # room0 --WEST--> room1
        # room0 --NORTH--> room2 --WEST--> room3 --SOUTH--> room1
        # Shortest path is [WEST]
        tl_conn1 = ConnectionFact(id="c1", location_a=_room("room 0"), location_b=_room("room 1"), direction=Direction.WEST)
        tl_conn2 = ConnectionFact(id="c2", location_a=_room("room 0"), location_b=_room("room 2"), direction=Direction.NORTH)
        tl_conn3 = ConnectionFact(id="c3", location_a=_room("room 2"), location_b=_room("room 3"), direction=Direction.WEST)
        tl_conn4 = ConnectionFact(id="c4", location_a=_room("room 3"), location_b=_room("room 1"), direction=Direction.SOUTH)
        
        tf = RelationFact(id="t1", predicate=RelationPredicate.HAS_MESSAGE_FOR, subject=_named("lily"))
        tl_loc = LocationFact(id="t2", entity=_named("lily"), location=_room("room 1"))
        telemetry = _kg(tf, tl_loc, tl_conn1, tl_conn2, tl_conn3, tl_conn4)

        # Report: Someone in the west
        rf = RelationFact(id="r1", predicate=RelationPredicate.HAS_MESSAGE_FOR, subject=_existential(location=_directional([Direction.WEST])))
        res = align_facts(_kg(rf), telemetry, AlignmentResult())
        assert "r1" in res.resolution_confirmed_fact_ids

        # Report: Someone in the north then west (this is NOT the shortest path to room 1)
        rf2 = RelationFact(id="r2", predicate=RelationPredicate.HAS_MESSAGE_FOR, subject=_existential(location=_directional([Direction.NORTH, Direction.WEST])))
        res2 = align_facts(_kg(rf2), telemetry, AlignmentResult())
        # Since the shortest path is [WEST], [NORTH, WEST] is NOT a prefix of the shortest path.
        # However, it IS a prefix of a longer path. 
        # The user said "use the first direction of the path ... or better yet, as long as the directions match".
        # Usually we want the shortest path.
        assert "r2" in res2.novel_fact_ids

if __name__ == "__main__":
    pytest.main([__file__])
