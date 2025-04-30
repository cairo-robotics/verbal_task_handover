from pydantic import BaseModel, Field
from typing import List, Dict, Optional
import json
import pydantic
print(pydantic.__version__)

class GameStateNPC(BaseModel):
    location: Optional[str] = Field(None, description="The room or lounge where the NPC is located.")
    potion_needed: Optional[str] = Field(
        None, description="The potion the NPC needs, or null if no potion is needed."
    )
    potion_given: Optional[bool] = Field(None, description="Whether the potion has been given to the NPC.")

    class Config:
        json_schema_extra = {
            "required": []
        }


class GameState(BaseModel):
    player_items: Optional[List[str]] = Field(None, description="A list of items currently in the player's inventory.")
    player_held_item: Optional[str] = Field(
        None, description="The item currently held by the player, or null if none."
    )
    npcs: Optional[Dict[str, GameStateNPC]] = Field(
        None, description="A dictionary mapping NPC names to their current state."
    )
    active_quests: Optional[Dict[str, str]] = Field(
        None, description="Active quests represented as {item: destination} pairs."
    )

    class Config:
        json_schema_extra = {
            "required": []
        }


if __name__ == "__main__":
    # Print the JSON schema
    schema = GameState.model_json_schema()
    with open("game_state_schema.json", "w") as f:
        json.dump(schema, f, indent=2)
