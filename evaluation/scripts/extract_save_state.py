import sys
import json

from treasure_hunt.src.game_mdp import GameState, Direction, start_state

"""
For extracting the "ground truth" game state in json format.
Restricted mainly to strictly task-relevant aspects, like rooms entered, NPCs interacted, and so on.
"""

def extract_state_data(state):
    print(state.player_has_items)
    json_data = {
        "player_items" : state.player_has_items,
        "doors" : [],
        "treasure" : [],
        "chests" : [],
        "npcs": []
    }

    for room in state._objects:
        for obj in state._objects[room].values():
            if obj.type == "door" and (obj.is_locked or obj.was_unlocked):
                door = {
                    "is_locked" : obj.is_locked,
                    "key" : obj.key,
                    "location" : room
                }
                json_data["doors"].append(door)

            elif obj.type == "treasure":
                treasure = {
                    "found" : obj.collected,
                    "location" : room
                }
                json_data["treasure"].append(treasure)

            elif obj.type == "chest" :
                chest = {
                    "is_open" : obj.is_open,
                    "location" : room
                }
                json_data["chests"].append(chest)

            elif obj.type == "wire_module":
                wire_module = {
                    "num_wires" : obj.num_wires,
                    "wires" : obj.wires,
                    "serial_no" : obj.serial_no,
                    "defused" : obj.defused,
                    "location" : room
                }
                json_data["wire_module"] = wire_module

            elif obj.type == "password_module":
                password_module = {
                    "password" : obj.password,
                    "defused" : obj.defused,
                    "location" : room
                }
                json_data["password_module"] = password_module

            elif obj.type == "npc":
                npc = {
                    "name" : obj.name,
                    "location" : room,
                    "interacted" : (obj.current_conversation > 0)
                }
                # TODO: will this cause issues if regular interaction did not occur before conditional interaction?
                json_data["npcs"].append(npc)

    return json_data

if __name__ == "__main__":

    if len(sys.argv) != 3:
        print("Usage: python extract_save_state.py <save_state> <output_file>")
        sys.exit(1)
    filename = sys.argv[1]
    output_file = sys.argv[2]

    state = GameState.load(filename)
    json_data = extract_state_data(state)
    with open(output_file, 'w') as f:
        json.dump(json_data, f, indent=4)