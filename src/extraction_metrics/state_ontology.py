from pydantic import BaseModel
from typing import List, Optional, Literal, Union, Dict


Direction = Literal["north", "south", "east", "west"]

Predicate = Literal[
    "needs",
    "delivered",
    "request",
    "message_delivered",
    "response",
    "response_delivered",
    "located",
    "exists",
    "has"
]

class Location(BaseModel):
    type: Literal["room", "directional"]
    room: Optional[str] = None
    directions: Optional[List[Direction]] = None
    mode: Optional[Literal["path", "set"]] = None  # then vs and


class Argument(BaseModel):
    type: Literal["entity", "location", "existential"]
    value: Optional[str] = None   # e.g., "lily", "gold potion", "potion"
    location: Optional[Location] = None  # for constraints

class CanonicalFact(BaseModel):
    predicate: Predicate

    agent: Optional[Argument] = None
    patient: Optional[Argument] = None
    object: Optional[Argument] = None
    source: Optional[Argument] = None
    target: Optional[Argument] = None
    location: Optional[Location] = None

class FactExtraction(BaseModel):
    facts: List[CanonicalFact]