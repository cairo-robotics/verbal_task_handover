from pydantic import BaseModel
from typing import List, Union, Literal


# --- Base Fact Types ---

class PatientNeedsPotion(BaseModel):
    type: Literal["PatientNeedsPotion"]
    patient: str
    potion_color: str


class PotionDelivered(BaseModel):
    type: Literal["PotionDelivered"]
    patient: str
    potion_color: str
    delivery_stage: Literal["first", "second"]


class MessageRequest(BaseModel):
    type: Literal["MessageRequest"]
    sender_patient: str
    target_npc: str


class MessageDelivered(BaseModel):
    type: Literal["MessageDelivered"]
    sender_patient: str
    target_npc: str


class MessageResponse(BaseModel):
    type: Literal["MessageResponse"]
    target_npc: str
    sender_patient: str


class ResponseDelivered(BaseModel):
    type: Literal["ResponseDelivered"]
    target_npc: str
    sender_patient: str


class NpcLocation(BaseModel):
    type: Literal["NpcLocation"]
    npc: str
    room: str


class PotionLocation(BaseModel):
    type: Literal["PotionLocation"]
    potion_color: str
    room: str


class PlayerLocation(BaseModel):
    type: Literal["PlayerLocation"]
    room: str


class PlayerHasItem(BaseModel):
    type: Literal["PlayerHasItem"]
    item: str


# --- Union of all fact types ---

Fact = Union[
    PatientNeedsPotion,
    PotionDelivered,
    MessageRequest,
    MessageDelivered,
    MessageResponse,
    ResponseDelivered,
    NpcLocation,
    PotionLocation,
    PlayerLocation,
    PlayerHasItem,
]


class FactExtraction(BaseModel):
    facts: List[Fact]