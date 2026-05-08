"""
Unit tests for src/pipelines/model_alignment/fact_alignment.py

Run with:
    pytest tests/test_fact_alignment.py -v
"""

from __future__ import annotations

import pytest
from src.core.representations.pydantic_schema import (
    Argument,
    KnowledgeGraph,
    Location,
    LocationFact,
    RelationFact,
    RelationPredicate,
    SpatialFact,
    SpatialRelationType,
    Direction,
    ConnectionFact,
)
from src.pipelines.model_alignment.entity_alignment import AlignmentResult, ExistentialResolution
from src.pipelines.model_alignment.fact_alignment import align_facts, ConflictRecord


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _named(value: str, location: Location = None) -> Argument:
    return Argument(type="named", value=value, location=location)


def _existential(location: Location = None) -> Argument:
    return Argument(type="existential", location=location)


def _room(name: str) -> Location:
    return Location(type="room", room=name)


def _directional(dirs: list[Direction]) -> Location:
    return Location(type="directional", directions=dirs)


def _kg(*facts) -> KnowledgeGraph:
    return KnowledgeGraph(facts=list(facts))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestFactAlignment:
    def test_confirmed_location_fact(self):
        """Identical facts result in confirmed_fact_ids."""
        loc_f = LocationFact(id="f1", entity=_named("lily"), location=_room("room 1"))
        report = _kg(loc_f)
        telem = _kg(loc_f)
        
        result = align_facts(report, telem, AlignmentResult())
        
        assert "f1" in result.confirmed_fact_ids
        assert not result.novel_fact_ids
        assert not result.conflicts

    def test_confirmed_with_renaming(self):
        """Alignment mapping is respected."""
        rf = LocationFact(id="r1", entity=_named("Lily"), location=_room("room 1"))
        tf = LocationFact(id="t1", entity=_named("lily"), location=_room("room 1"))
        
        alignment = AlignmentResult(named_mapping={"Lily": "lily"})
        result = align_facts(_kg(rf), _kg(tf), alignment)
        
        assert "r1" in result.confirmed_fact_ids
        assert not result.conflicts

    def test_conflict_location(self):
        """Mismatch in location field produces a ConflictRecord."""
        rf = LocationFact(id="r1", entity=_named("lily"), location=_room("room 1"))
        tf = LocationFact(id="t1", entity=_named("lily"), location=_room("room 2"))
        
        result = align_facts(_kg(rf), _kg(tf), AlignmentResult())
        
        assert not result.confirmed_fact_ids
        assert len(result.conflicts) == 1
        conf = result.conflicts[0]
        assert conf.source_fact_id == "r1"
        assert conf.target_fact_id == "t1"
        assert conf.field_name == "location"
        assert conf.expected_value["room"] == "room 2"
        assert conf.actual_value["room"] == "room 1"

    def test_novel_fact(self):
        """Fact with no identity match in telemetry is novel."""
        rf = LocationFact(id="r1", entity=_named("new_npc"), location=_room("room 1"))
        telem = _kg(LocationFact(id="t1", entity=_named("lily"), location=_room("room 1")))
        
        result = align_facts(_kg(rf), telem, AlignmentResult())
        
        assert "r1" in result.novel_fact_ids
        assert not result.confirmed_fact_ids

    def test_existential_resolution_match(self):
        """Resolved existential arguments allow matching."""
        rf = RelationFact(
             id="r1",
             predicate=RelationPredicate.NEEDS_POTION,
             subject=Argument(type="existential")
        )
        tf = RelationFact(
             id="t1",
             predicate=RelationPredicate.NEEDS_POTION,
             subject=_named("lily")
        )
        
        # Resolve 'someone' to 'lily'
        alignment = AlignmentResult(existential_resolutions=[
            ExistentialResolution(source_fact_id="r1", argument_role="subject", outcome="resolved", resolved_value="lily")
        ])
        
        result = align_facts(_kg(rf), _kg(tf), alignment)
        
        assert "r1" in result.confirmed_fact_ids
        assert not result.conflicts

    def test_relation_object_conflict(self):
        """Conflict in the 'object' field of a RelationFact."""
        rf = RelationFact(
            id="r1",
            predicate=RelationPredicate.NEEDS_POTION,
            subject=_named("lily"),
            object=_named("gold_potion")
        )
        tf = RelationFact(
            id="t1",
            predicate=RelationPredicate.NEEDS_POTION,
            subject=_named("lily"),
            object=_named("red_potion")
        )
        
        result = align_facts(_kg(rf), _kg(tf), AlignmentResult())
        
        assert len(result.conflicts) == 1
        assert result.conflicts[0].field_name == "object"
        assert result.conflicts[0].expected_value == "red_potion"
        assert result.conflicts[0].actual_value == "gold_potion"

    def test_spatial_direction_conflict(self):
        """Conflict in 'direction' field of a SpatialFact."""
        rf = SpatialFact(
            id="r1",
            type=SpatialRelationType.ABSOLUTE,
            subject=_named("lily"),
            direction=Direction.NORTH
        )
        tf = SpatialFact(
            id="t1",
            type=SpatialRelationType.ABSOLUTE,
            subject=_named("lily"),
            direction=Direction.SOUTH
        )
        
        result = align_facts(_kg(rf), _kg(tf), AlignmentResult())
        
        assert len(result.conflicts) == 1
        assert result.conflicts[0].field_name == "direction"

    def test_connection_fact_conflict(self):
        """Conflict in 'location_b' of a ConnectionFact."""
        rf = ConnectionFact(id="r1", location_a=_room("room 1"), location_b=_room("room 2"))
        tf = ConnectionFact(id="t1", location_a=_room("room 1"), location_b=_room("room 3"))
        
        result = align_facts(_kg(rf), _kg(tf), AlignmentResult())
        
        assert len(result.conflicts) == 1
        assert result.conflicts[0].field_name == "location_b"

    def test_named_report_matches_existential_telemetry_room(self):
        """Report has specific 'lily', Telemetry has 'someone in room 1'."""
        rf = RelationFact(
            id="r1",
            predicate=RelationPredicate.NEEDS_POTION,
            subject=_named("lily"),
            object=_named("gold_potion")
        )
        report = _kg(rf)

        tf = RelationFact(
            id="t1",
            predicate=RelationPredicate.NEEDS_POTION,
            subject=_existential(location=_room("room 1")),
            object=_named("gold_potion")
        )
        tl_loc = LocationFact(
            id="t2",
            entity=_named("lily"),
            location=_room("room 1")
        )
        telemetry = _kg(tf, tl_loc)

        result = align_facts(report, telemetry, AlignmentResult())

        assert "r1" in result.resolution_confirmed_fact_ids
        assert not result.conflicts

    def test_named_report_matches_existential_telemetry_directional(self):
        """Report has 'lily', Telemetry has 'someone in the west'."""
        rf = RelationFact(
            id="r1",
            predicate=RelationPredicate.NEEDS_POTION,
            subject=_named("lily"),
            object=_named("gold_potion")
        )
        report = _kg(rf)

        tf = RelationFact(
            id="t1",
            predicate=RelationPredicate.NEEDS_POTION,
            subject=_existential(location=_directional([Direction.WEST])),
            object=_named("gold_potion")
        )
        
        tl_loc = LocationFact(id="t2", entity=_named("lily"), location=_room("room 1"))
        tl_conn = ConnectionFact(
            id="t3",
            location_a=_room("room 0"),
            location_b=_room("room 1"),
            direction=Direction.WEST
        )
        telemetry = _kg(tf, tl_loc, tl_conn)

        result = align_facts(report, telemetry, AlignmentResult())

        assert "r1" in result.resolution_confirmed_fact_ids
        assert not result.conflicts

    def test_mismatch_location_constraint(self):
        """Report 'lily' is in room 2, Telemetry 'someone in room 1' needs potion."""
        rf = RelationFact(
            id="r1",
            predicate=RelationPredicate.NEEDS_POTION,
            subject=_named("lily"),
            object=_named("gold_potion")
        )
        report = _kg(rf)

        tf = RelationFact(
            id="t1",
            predicate=RelationPredicate.NEEDS_POTION,
            subject=_existential(location=_room("room 1")),
            object=_named("gold_potion")
        )
        tl_loc = LocationFact(
            id="t2",
            entity=_named("lily"),
            location=_room("room 2") 
        )
        telemetry = _kg(tf, tl_loc)

        result = align_facts(report, telemetry, AlignmentResult())

        assert "r1" in result.novel_fact_ids
        assert not result.resolution_confirmed_fact_ids

    def test_directional_reachability_complex(self):
        """Test west -> west path."""
        rf = RelationFact(
            id="r1",
            predicate=RelationPredicate.NEEDS_POTION,
            subject=_named("lily"),
            object=_named("gold_potion")
        )
        report = _kg(rf)

        tf = RelationFact(
            id="t1",
            predicate=RelationPredicate.NEEDS_POTION,
            subject=_existential(location=_directional([Direction.WEST])),
            object=_named("gold_potion")
        )
        
        tl_loc = LocationFact(id="t2", entity=_named("lily"), location=_room("room 2"))
        tl_conn1 = ConnectionFact(id="c1", location_a=_room("room 0"), location_b=_room("room 1"), direction=Direction.WEST)
        tl_conn2 = ConnectionFact(id="c2", location_a=_room("room 1"), location_b=_room("room 2"), direction=Direction.WEST)
        
        telemetry = _kg(tf, tl_loc, tl_conn1, tl_conn2)

        result = align_facts(report, telemetry, AlignmentResult())

        assert "r1" in result.resolution_confirmed_fact_ids
