from pydantic import BaseModel, Field
from typing import List, Optional
import json

class Quest(BaseModel):
    item: Optional[str] = Field(
        None, description="The name of the potion, request or response item to be brought to the target NPC (e.g. 'purple potion', 'request from room 6' or 'response from Anthony'), or null if unknown."
    )
    sender: Optional[str] = Field(
        None, description="Name (or location) of the NPC who gave the player the request or response, or null if unknown."
    )
    target: Optional[str] = Field(
        None, description="The target NPC to whom the player must bring the item, or null if unknown."
    )

class Character(BaseModel):
    name: Optional[str] = None
    location: Optional[str] = Field(
        None, description="The location where this NPC is currently located, or null if unknown."
    )
    potion_needed: Optional[str] = Field(
        None, description="The potion the NPC needs OR has previously received, or null if unknown or if no potion is needed."
    )

class Location(BaseModel):
    name: str
    # connects_to: List[str] = Field(default_factory=list, description="List of locations this location connects to.")
    contains_potions: List[str] = Field(default_factory=list, description="List of potion items found in this location.")

class GameState(BaseModel):
    character_quests: List[Quest] = Field(
        description="A list of yet-to-be-completed quests for the player.",
        default_factory=list
        )
    characters: List[Character] = Field(
        description="A list of all known or referenced NPCs in the game, along with any known data about them.",
        default_factory=list
    )
    # locations_visited: List[str] = Field(default_factory=list)
    locations: List[Location] = Field(default_factory=list)

    class Config:
        json_schema_extra = {
            "required": []
        }

if __name__ == "__main__":
    # Print the JSON schema
    schema = GameState.model_json_schema()
    with open("game_state_schema.json", "w") as f:
        json.dump(schema, f, indent=2)
