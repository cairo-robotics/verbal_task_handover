# from pydantic import BaseModel, Field
# from typing import List, Dict, Optional
# import json
# import pydantic
# print(pydantic.__version__)

# class GameStateNPC(BaseModel):
#     location: Optional[str] = Field(None, description="The room or lounge where the NPC is located.")
#     potion_needed: Optional[str] = Field(
#         None, description="The potion the NPC needs, or null if no potion is needed."
#     )
#     potion_given: Optional[bool] = Field(None, description="Whether the potion has been given to the NPC.")

#     class Config:
#         json_schema_extra = {
#             "required": []
#         }


# class GameState(BaseModel):
#     player_items: Optional[List[str]] = Field(None, description="A list of items currently in the player's inventory.")
#     player_held_item: Optional[str] = Field(
#         None, description="The item currently held by the player, or null if none."
#     )
#     npcs: Optional[Dict[str, GameStateNPC]] = Field(
#         None, description="A dictionary mapping NPC names to their current state."
#     )
#     active_quests: Optional[Dict[str, str]] = Field(
#         None, description="Active quests represented as {item: destination} pairs."
#     )

#     class Config:
#         json_schema_extra = {
#             "required": []
#         }

from pydantic import BaseModel, Field
from typing import List, Optional
import json


class Quest(BaseModel):
    item: Optional[str] = Field(
        None, description="The item to be brought to the target character (e.g. 'request from room 1'), or null if unknown."
    )
    target: Optional[str] = Field(
        None, description="The target character to whom the player must bring the item, or null if unknown."
    )

class Character(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    location: Optional[str] = None
    needs_potion: Optional[bool] = Field(
        False, description="Whether the character needs (or previously needed) a potion or not."
    )
    potion_needed: Optional[str] = Field(
        None, description="The potion the character needs OR has previously received, or null if unknown or if no potion is needed."
    )

class Location(BaseModel):
    name: str
    connects_to: List[str] = Field(default_factory=list)
    contains_characters: List[str] = Field(default_factory=list)
    contains_potions: List[str] = Field(default_factory=list)

class GameState(BaseModel):
    character_quests: List[Quest] = Field(
        description="A list of currently active (i.e. not yet completed) quests from characters",
        default_factory=list
        )
    characters: List[Character] = Field(
        description="A list of all known or referenced characters in the game, along with any known data about them.",
        default_factory=list
    )
    locations_visited: List[str] = Field(default_factory=list)
    location_map: List[Location] = Field(default_factory=list)

    class Config:
        json_schema_extra = {
            "required": []
        }

if __name__ == "__main__":
    # Print the JSON schema
    schema = GameState.model_json_schema()
    with open("game_state_schema.json", "w") as f:
        json.dump(schema, f, indent=2)
