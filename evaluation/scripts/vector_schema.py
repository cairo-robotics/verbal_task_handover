from pydantic import BaseModel
from typing import List, Optional

class Door(BaseModel):
    is_locked: Optional[bool] = None
    key: Optional[str] = None
    location: Optional[str] = None

class Treasure(BaseModel):
    found: Optional[bool] = None
    location: Optional[str] = None

class Chest(BaseModel):
    is_open: Optional[bool] = None
    location: Optional[str] = None

class NPC(BaseModel):
    name: Optional[str] = None
    location: Optional[str] = None
    interacted: Optional[bool] = None

class PasswordModule(BaseModel):
    password: Optional[str] = None
    defused: Optional[bool] = None
    location: Optional[str] = None

class WireModule(BaseModel):
    num_wires: Optional[int] = None
    wires: Optional[List[str]] = None
    serial_no: Optional[str] = None
    defused: Optional[bool] = None
    location: Optional[str] = None

class GameStateSchema(BaseModel):
    player_items: Optional[List[str]] = None
    doors: Optional[List[Door]] = None
    treasure: Optional[List[Treasure]] = None
    chests: Optional[List[Chest]] = None
    npcs: Optional[List[NPC]] = None
    password_module: Optional[PasswordModule] = None
    wire_module: Optional[WireModule] = None

def create_example():
    # Example usage:
    game_state = GameStateSchema(
        player_items=[],
        doors=[
            Door(is_locked=True, key="silver key", location="room0"),
            Door(is_locked=True, key="blue key", location="room3"),
            Door(is_locked=True, key="gold key", location="room7")
        ],
        treasure=[
            Treasure(found=False, location="room3"),
            Treasure(found=False, location="room4")
        ],
        chests=[
            Chest(is_open=False, location="room2"),
            Chest(is_open=False, location="room2"),
            Chest(is_open=False, location="room15"),
            Chest(is_open=False, location="room16")
        ],
        npcs=[
            NPC(name="lily", location="room0", interacted=False),
            NPC(name="jay", location="room0", interacted=False),
            NPC(name="guy", location="room0", interacted=False),
            NPC(name="mark", location="room1", interacted=False),
            NPC(name="eliza", location="room5", interacted=False),
            NPC(name="marie", location="room18", interacted=False),
            NPC(name="steve", location="room6", interacted=False)
        ],
        password_module=PasswordModule(password="asdf", defused=False, location="room1"),
        wire_module=WireModule(num_wires=4, wires=["blue", "red", "yellow", "blue"], serial_no="S2411", defused=False, location="room19")
    )

    # Generate JSON schema
    print(game_state.schema_json(indent=2))

if __name__ == "__main__":
    create_example()