from typing import List, Optional, Dict
from pydantic import BaseModel, Field


from pydantic import BaseModel, Field
from typing import List, Dict, Optional
import json


class NPC(BaseModel):
    location: str = Field(..., description="The room or lounge where the NPC is located.")
    interacted: bool = Field(..., description="Whether the player has interacted with this NPC.")
    potion_needed: Optional[str] = Field(
        None, description="The potion the NPC needs, or null if no potion is needed."
    )
    potion_given: bool = Field(..., description="Whether the potion has been given to the NPC.")


class GameState(BaseModel):
    player_items: List[str] = Field(..., description="A list of items currently in the player's inventory.")
    player_held_item: Optional[str] = Field(
        None, description="The item currently held by the player, or null if none."
    )
    npcs: Dict[str, NPC] = Field(
        ..., description="A dictionary mapping NPC names to their current state."
    )
    active_quests: Dict[str, str] = Field(
        ..., description="Active quests represented as {item: npc_destination} pairs."
    )


if __name__ == "__main__":
    # Print the JSON schema
    schema = GameState.model_json_schema()
    print(json.dumps(schema, indent=2))
