from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from enum import Enum

# ----------------------------
# Enums
# ----------------------------

class EntityType(str, Enum):
    AGENT = "Agent"
    LOCATION = "Location"
    ITEM = "Item"
    MESSAGE = "Message/Request/Response"

class EventType(str, Enum):
    OBTAIN = "obtained"
    DROP = "dropped"
    TALK_TO = "talked_to"
    GIVE = "given"
    DELIVER = "delivered"

class RelationType(str, Enum):
    IN_INVENTORY_OF = "in_inventory_of"
    LOCATED_IN = "located_in"
    REQUIRES = "requires"
    INTENDED_FOR = "intended_for"

class SpatialRelationType(str, Enum):
    NORTH_OF = "north_of"
    SOUTH_OF = "south_of"
    EAST_OF = "east_of"
    WEST_OF = "west_of"

invert_direction = {
    "west": "east",
    "east": "west",
    "north": "south",
    "south": "north"
}

class ConfidenceLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# ----------------------------
# Core Models
# ----------------------------

class Entity(BaseModel):
    id: str = Field(..., description="Unique identifier for the entity")
    type: EntityType

class Participants(BaseModel):
    actor: Optional[str] = None
    object: Optional[str] = None
    target: Optional[str] = None

class Event(BaseModel):
    event_id: str = Field(..., description="Unique identifier for the event")
    event_type: EventType

    participants: Participants
    location: Optional[str] = Field(
        None,
        description="Location where the event occurred"
    )

    timestamp: Optional[str] = Field(
        None,
        description="Time at which the event occurred"
    )

    confidence: ConfidenceLevel

class StateRelation(BaseModel):
    subject: str
    relation: RelationType
    object: str
    confidence: ConfidenceLevel

class SpatialRelation(BaseModel):
    subject: str = Field(..., description="Location entity subject")
    relation: SpatialRelationType
    object: str = Field(..., description="Location entity object")
    confidence: ConfidenceLevel

class ConflictRecord(BaseModel):
    conflict_id: str
    new_fact_id: str
    existing_fact_id: str
    conflict_type: str

class UpdateRecord(BaseModel):
    added_events: List[str]
    added_state_relations: List[str]
    added_spatial_relations: List[str]
    added_entities: List[str]
    conflicts_created: List[str]

class KnowledgeGraphExtraction(BaseModel):
    entities: List[Entity]
    events: List[Event]
    state_relations: List[StateRelation]
    spatial_relations: List[SpatialRelation]
    conflicts: List[ConflictRecord] = Field(default_factory=list)
