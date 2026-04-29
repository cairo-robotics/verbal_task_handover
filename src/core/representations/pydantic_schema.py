from pydantic import BaseModel, Field
from typing import List, Optional, Union, Literal
from enum import Enum
from uuid import uuid4


# ---- Base ----

class StrictBase(BaseModel):
    class Config:
        extra = "forbid"


class BaseFact(StrictBase):
    id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Unique identifier for this fact."
    )
    is_partial: bool = Field(
        False,
        description="Set to True if any part of the fact is underspecified or unknown."
    )
    provenance: Optional[str] = Field(
        None,
        description="Original text span this fact was extracted from."
    )
    source: Optional[str] = Field(
        None,
        description="The source graph this fact came from (e.g., 'base', 'new')."
    )


class Direction(str, Enum):
    NORTH = "north"
    SOUTH = "south"
    EAST = "east"
    WEST = "west"
    NORTHEAST = "northeast"
    NORTHWEST = "northwest"
    SOUTHEAST = "southeast"
    SOUTHWEST = "southwest"


# ---- Location ----

class Location(StrictBase):
    type: Literal["room", "directional"] = Field(
        ...,
        description="Type of location reference. Use 'room' for named rooms (e.g., 'room 1'). Use 'directional' for relative directions like 'north' or 'west'."
    )

    room: Optional[str] = Field(
        None,
        description="Name of the room if type is 'room' (e.g., 'room 1')."
    )

    directions: Optional[List[Direction]] = Field(
        None,
        description="List of directions if type is 'directional'. For example, ['north', 'west'] for 'north and west'."
    )

    mode: Optional[Literal["path", "set"]] = Field(
        None,
        description="How to interpret multiple directions. Use 'set' for 'and' (e.g., 'north and west'). Use 'path' for ordered movement like 'north then east'."
    )


# ---- Arguments ----

class Argument(StrictBase):
    type: Literal["named", "existential"] = Field(
        ...,
        description=(
            "Type of argument. "
            "'named' = a named or described entity (e.g., 'lily', 'gold potion'). "
            "'existential' = an unknown or unspecified entity (e.g., 'someone', 'a potion'). "
        )
    )

    value: Optional[str] = Field(
        None,
        description=(
            "Surface form of the entity if known (e.g., 'lily', 'red potion', 'potion'). "
            "Leave null for existential arguments like 'someone'."
        )
    )

    location: Optional[Location] = Field(
        None,
        description=(
            "Optional location constraint on this argument. "
            "Use this when the text specifies location indirectly (e.g., 'someone to the east')."
        )
    )


# ---- Relation Facts ----

class RelationPredicate(str, Enum):
    NEEDS_POTION = "needs_potion"
    POTION_DELIVERED = "potion_delivered"
    HAS_MESSAGE_FOR = "has_message_for"
    MESSAGE_DELIVERED = "message_delivered"
    HAS_RESPONSE_FOR = "has_response_for"
    RESPONSE_DELIVERED = "response_delivered"
    HAS_ITEM = "has_item"


class RelationFact(BaseFact):
    predicate: RelationPredicate = Field(
        ...,
        description="Type of relation (e.g., needs_potion, has_message_for)."
    )

    subject: Argument = Field(
        ...,
        description="The main entity performing or holding the relation."
    )

    object: Optional[Argument] = Field(
        None,
        description=(
            "Secondary argument (e.g., item being transferred or needed). "
            "Use for objects like 'potion'."
        )
    )

    target: Optional[Argument] = Field(
        None,
        description=(
            "Target or recipient of the relation (e.g., message recipient). "
            "Used in communication-related predicates."
        )
    )


# ---- Location Facts ----

class LocationFact(BaseFact):
    entity: Argument = Field(
        ...,
        description="Entity being located."
    )

    location: Location = Field(
        ...,
        description="Location where the entity is found."
    )


# ---- Spatial Facts ----

class SpatialRelationType(str, Enum):
    RELATIVE = "relative"
    ABSOLUTE = "absolute"


class SpatialFact(BaseFact):
    type: SpatialRelationType = Field(
        ...,
        description=(
            "'absolute' = entity is in a direction without reference (e.g., 'to the north'). "
            "'relative' = entity is in a direction relative to another entity (e.g., 'north of room 1')."
        )
    )

    subject: Argument = Field(
        ...,
        description="Entity whose position is being described."
    )

    direction: Direction = Field(
        ...,
        description="Direction of the spatial relation."
    )

    reference: Optional[Argument] = Field(
        None,
        description=(
            "Reference entity for relative spatial relations. "
            "Only used when type is 'relative'."
        )
    )


# ---- Connectivity ----

class ConnectionFact(BaseFact):
    location_a: Location = Field(
        ...,
        description="First location in the connection."
    )

    location_b: Location = Field(
        ...,
        description="Second location in the connection."
    )

    direction: Optional[Direction] = Field(
        None,
        description="Direction from location_a to location_b."
    )


# ---- Conflicts (to be used at diff stage) ----
class Conflict(StrictBase):
    """Details about a mismatch between a report fact and a telemetry fact."""
    id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Unique identifier for this conflict."
    )
    base_fact_id: str = Field(..., description="ID of the fact in the base graph.")
    new_fact: 'Fact' = Field(..., description="The full fact from the new graph that conflicts.")
    field_name: str = Field(..., description="The specific field that mismatched.")
    base_value: Optional[Any] = Field(None, description="The value in the base fact.")
    new_value: Optional[Any] = Field(None, description="The value in the new fact.")

# ---- Graph ----

Fact = Union[
    RelationFact,
    LocationFact,
    SpatialFact,
    ConnectionFact
]


class KnowledgeGraph(StrictBase):
    facts: List[Fact] = Field(
        ...,
        description="List of all extracted facts from the input text."
    )
    conflicts: List[Conflict] = Field(
        default_factory=list,
        description="List of all conflicts found in the knowledge graph."
    )

if __name__ == "__main__":
    kg = KnowledgeGraph(
        facts=[
            RelationFact(
                predicate="needs_potion",
                subject=Argument(type="entity", value="lily"),
                object=Argument(type="entity", value="gold potion"),
            ),
        ]
    )
    print(kg)