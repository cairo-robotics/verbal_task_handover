"""
Fact alignment step for the model-alignment pipeline.

Aligns Facts from report KnowledgeGraph against telemetry KnowledgeGraph,
identifying confirmed facts, novel facts, and conflicts.
"""

from __future__ import annotations

from typing import List, Optional, Any, Union, Set
from pydantic import BaseModel, Field
from src.core.representations.pydantic_schema import (
    KnowledgeGraph,
    Fact,
    RelationFact,
    LocationFact,
    SpatialFact,
    ConnectionFact,
    Argument,
    Location,
)
from src.pipelines.model_alignment.entity_alignment import AlignmentResult, ExistentialResolution


class ConflictRecord(BaseModel):
    """Details about a mismatch between a report fact and a telemetry fact."""
    source_fact_id: str = Field(..., description="ID of the fact in the report graph.")
    target_fact_id: str = Field(..., description="ID of the matching fact in the telemetry graph.")
    field_name: str = Field(..., description="The field that differs (e.g., 'location', 'object').")
    expected_value: Any = Field(..., description="The value found in telemetry.")
    actual_value: Any = Field(..., description="The value found in the report.")


class FactAlignmentResult(BaseModel):
    """The result of aligning report facts against telemetry facts."""
    confirmed_fact_ids: List[str] = Field(default_factory=list, description="IDs of report facts that match telemetry.")
    novel_fact_ids: List[str] = Field(default_factory=list, description="IDs of report facts with no telemetry match.")
    conflicts: List[ConflictRecord] = Field(default_factory=list, description="Records of value mismatches.")


def _get_normalized_argument_value(arg: Argument, fact_id: str, role: str, alignment: AlignmentResult) -> Optional[str]:
    """Get the telemetry-side canonical value for a report Argument."""
    if arg.type == "named":
        # Check if we have a rename mapping; if not, use the original value
        return alignment.named_mapping.get(arg.value, arg.value) if arg.value else None
    
    # Existential resolution
    for res in alignment.existential_resolutions:
        if res.source_fact_id == fact_id and res.argument_role == role:
            if res.outcome == "resolved":
                return res.resolved_value
    return None


def _get_fact_match_key(fact: Fact, alignment: AlignmentResult) -> Optional[tuple]:
    """
    Generate a comparable key for the 'identity' of a fact.
    Identifies the "what" or "who" the fact is about.
    """
    if isinstance(fact, LocationFact):
        entity_val = _get_normalized_argument_value(fact.entity, fact.id, "entity", alignment)
        if entity_val is None: return None
        return ("LocationFact", entity_val)
    
    elif isinstance(fact, RelationFact):
        subject_val = _get_normalized_argument_value(fact.subject, fact.id, "subject", alignment)
        if subject_val is None: return None
        return ("RelationFact", subject_val, fact.predicate)
    
    elif isinstance(fact, SpatialFact):
        subject_val = _get_normalized_argument_value(fact.subject, fact.id, "subject", alignment)
        if subject_val is None: return None
        # Identity includes spatial type (absolute vs relative)
        return ("SpatialFact", subject_val, fact.type)
    
    elif isinstance(fact, ConnectionFact):
        # Identity is the first location. 
        # Note: Connections are often directional or fixed in telemetry.
        return ("ConnectionFact", fact.location_a.model_dump_json())
    
    return None


def _compare_values(report_val: Any, telem_val: Any) -> bool:
    """Deep comparison for complex types like Location or Argument."""
    if isinstance(report_val, (Location, Argument)):
        return report_val.model_dump() == telem_val.model_dump()
    return report_val == telem_val


def _compare_arguments(report_arg: Optional[Argument], telem_arg: Optional[Argument], fact_id: str, role: str, alignment: AlignmentResult) -> bool:
    """Compare two arguments after resolving report-side entities."""
    if (report_arg is None) != (telem_arg is None):
        return False
    if report_arg is None:
        return True
    
    # Normalize report value
    norm_report_val = _get_normalized_argument_value(report_arg, fact_id, role, alignment)
    # Telemetry value is already canonical
    telem_val = telem_arg.value if telem_arg else None
    
    return norm_report_val == telem_val


def align_facts(
    report_graph: KnowledgeGraph,
    telemetry_graph: KnowledgeGraph,
    alignment_result: AlignmentResult,
) -> FactAlignmentResult:
    """
    Align Facts from report against telemetry.
    
    Matches report facts to telemetry facts based on identity key, then
    compares values to establish confirmed/conflict status.
    """
    result = FactAlignmentResult()
    
    # Index telemetry facts by identity key
    dummy_alignment = AlignmentResult()
    telem_index: dict[tuple, Fact] = {}
    for tf in telemetry_graph.facts:
        key = _get_fact_match_key(tf, dummy_alignment)
        if key:
            # If multiple facts share an identity (e.g. lily has multiple items), 
            # we might need a more sophisticated index. 
            # For this pipeline, identity + predicate/type is usually unique enough.
            telem_index[key] = tf

    for rf in report_graph.facts:
        key = _get_fact_match_key(rf, alignment_result)
        
        if not key or key not in telem_index:
            result.novel_fact_ids.append(rf.id)
            continue
        
        tf = telem_index[key]
        conflicts: List[ConflictRecord] = []
        
        if isinstance(rf, LocationFact) and isinstance(tf, LocationFact):
            if not _compare_values(rf.location, tf.location):
                conflicts.append(ConflictRecord(
                    source_fact_id=rf.id,
                    target_fact_id=tf.id,
                    field_name="location",
                    expected_value=tf.location.model_dump(),
                    actual_value=rf.location.model_dump()
                ))
                
        elif isinstance(rf, RelationFact) and isinstance(tf, RelationFact):
            if not _compare_arguments(rf.object, tf.object, rf.id, "object", alignment_result):
                conflicts.append(ConflictRecord(
                    source_fact_id=rf.id,
                    target_fact_id=tf.id,
                    field_name="object",
                    expected_value=tf.object.value if tf.object else None,
                    actual_value=_get_normalized_argument_value(rf.object, rf.id, "object", alignment_result) if rf.object else None
                ))
            if not _compare_arguments(rf.target, tf.target, rf.id, "target", alignment_result):
                conflicts.append(ConflictRecord(
                    source_fact_id=rf.id,
                    target_fact_id=tf.id,
                    field_name="target",
                    expected_value=tf.target.value if tf.target else None,
                    actual_value=_get_normalized_argument_value(rf.target, rf.id, "target", alignment_result) if rf.target else None
                ))

        elif isinstance(rf, SpatialFact) and isinstance(tf, SpatialFact):
             if rf.direction != tf.direction:
                 conflicts.append(ConflictRecord(
                    source_fact_id=rf.id,
                    target_fact_id=tf.id,
                    field_name="direction",
                    expected_value=tf.direction,
                    actual_value=rf.direction
                 ))
             if not _compare_arguments(rf.reference, tf.reference, rf.id, "reference", alignment_result):
                 conflicts.append(ConflictRecord(
                    source_fact_id=rf.id,
                    target_fact_id=tf.id,
                    field_name="reference",
                    expected_value=tf.reference.value if tf.reference else None,
                    actual_value=_get_normalized_argument_value(rf.reference, rf.id, "reference", alignment_result) if rf.reference else None
                 ))

        elif isinstance(rf, ConnectionFact) and isinstance(tf, ConnectionFact):
            if not _compare_values(rf.location_b, tf.location_b):
                conflicts.append(ConflictRecord(
                    source_fact_id=rf.id,
                    target_fact_id=tf.id,
                    field_name="location_b",
                    expected_value=tf.location_b.model_dump(),
                    actual_value=rf.location_b.model_dump()
                ))

        if conflicts:
            result.conflicts.extend(conflicts)
        else:
            result.confirmed_fact_ids.append(rf.id)

    return result
