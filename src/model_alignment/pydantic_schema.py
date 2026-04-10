# ── Imports ──────────────────────────────────────────────────────────────────
from __future__ import annotations
from typing import Literal, Optional, List
from pydantic import BaseModel, Field


# ── Spatial ───────────────────────────────────────────────────────────────────

class Location(BaseModel):
    """A room, expressed as a named ID and/or a directional path from origin."""
    room_id: Optional[str] = None          # e.g. "room_3", None if unknown
    path: Optional[List[Literal[           # ordered traversal, e.g. ["west","north"]
        "north", "south", "east", "west"
    ]]] = None
    region_hint: Optional[str] = None      # e.g. "east wing", free-text fallback


# ── Existential constraints (report-graph only) ───────────────────────────────

class ExistentialConstraints(BaseModel):
    """
    Describes what is known about an entity that couldn't be named.
    All fields are optional; populate as many as the report supports.
    """
    entity_type: Optional[Literal["agent", "item", "location"]] = None
    location: Optional[Location] = None
    role: Optional[Literal[
        "task_initiator", "task_recipient", "item_holder"
    ]] = None
    properties: Optional[dict[str, str]] = None  # e.g. {"color": "gold"}
    plurality: bool = False               # True → underspecified set, not one entity


# ── Argument (named entity OR existential) ────────────────────────────────────

class Argument(BaseModel):
    """
    A participant in a relation.
      - "entity"      → fully named; value holds the canonical ID
      - "location"    → a room argument; location holds the Location
      - "existential" → partially known; constraints holds what we do know
    """
    type: Literal["entity", "location", "existential"]
    value: Optional[str] = None                        # canonical ID when type="entity"
    location: Optional[Location] = None               # when type="location"
    constraints: Optional[ExistentialConstraints] = None  # when type="existential"


# ── Confidence & source ───────────────────────────────────────────────────────

Confidence = Literal["certain", "inferred", "contradicted"]
Source     = Literal["telemetry", "report", "merged"]


# ── Core relations ────────────────────────────────────────────────────────────

class LocatedIn(BaseModel):
    """<entity> is located in <location>."""
    entity: Argument
    location: Location
    confidence: Confidence = "certain"
    source: Source = "telemetry"


class PlayerHasItem(BaseModel):
    """The player has <item>."""
    item: Argument
    confidence: Confidence = "certain"
    source: Source = "telemetry"

class Task(BaseModel):
    """A unit of work that has been assigned to the player."""
    task_id: str
    initiator: Argument
    status: Literal["pending", "in_progress", "blocked", "complete"]
    status_confidence: Confidence = "certain"
    condition_type: Literal["item_delivery", "item_return", "prior_task"]
    condition_value: Argument
    target: Optional[Argument] = None
    target_confidence: Confidence = "certain"
    source: Source = "telemetry"


# ── Conflict record ───────────────────────────────────────────────────────────

class ConflictRecord(BaseModel):
    """
    A disagreement between the telemetry graph and the report graph
    on the same fact. Populated during graph comparison.
    """
    fact_type: Literal["located_in", "held_by", "task_status", "task_requirement"]
    entity_id: str                        # canonical ID of the entity in question
    telemetry_value: str                  # what telemetry says
    report_value: str                     # what the report says
    resolution: Literal[
        "telemetry_wins", "report_wins", "unresolved"
    ] = "unresolved"


# ── Top-level graph ───────────────────────────────────────────────────────────

class KnowledgeGraph(BaseModel):
    """
    The full graph for one source (telemetry or report) or the merged result.
    Telemetry graphs will never contain existential Arguments.
    Report graphs may contain existentials; conflicts are populated at merge time.
    """
    source: Source
    locations: List[LocatedIn] = Field(default_factory=list)
    holdings: List[PlayerHasItem] = Field(default_factory=list)
    tasks: List[Task] = Field(default_factory=list)
    conflicts: List[ConflictRecord] = Field(default_factory=list)