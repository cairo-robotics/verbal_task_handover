import sys
import json

from treasure_hunt.src.game_mdp import GameState, Direction, start_state

"""
For extracting the "ground truth" game state in json format, regardless of player knowledge.
Restricted mainly to strictly task-relevant aspects, like rooms entered, NPCs interacted, and so on.
"""

def extract_ground_truth_data(state):
    # print(state.player_has_items)
    json_data = {
        "player_items" : state.player.flags,
        "player_held_item" : state.player.held_item,
        "npcs": {}, # dict - names as unique identifiers
    }

    for room in state._objects:
        # json_data["rooms"].append(room)
        for obj in state._objects[room].values():
            if obj.type == "npc":
                npc = {
                    "location" : room,
                    "interacted" : (obj.current_conversation > 0),
                    "potion_needed" : list(obj.held_item_interact_data.keys())[0] if obj.held_item_interact_data else None,
                    "potion_given" : obj.held_item_interact_complete
                }
                # TODO: will this cause issues if regular interaction did not occur before conditional interaction?
                json_data["npcs"][obj.name] = npc

    return json_data

def update_quest_info(state, json_data):
    # json_data["npcs"]["lily"].update({
    #     "given_request" : ("request from room1" in json_data["player_items"]),
    #     "got_treasure" : ("treasure1" in json_data["player_items"]) 
    #     })
    # json_data["npcs"]["oliver"].update({
    #     "given_request" : ("request from room2" in json_data["player_items"]),
    #     "got_treasure" : ("treasure2" in json_data["player_items"]) 
    #     }),
    # json_data["npcs"]["nick"].update({
    #     "given_request" : ("request from room3" in json_data["player_items"]),
    #     "got_treasure" : ("treasure3" in json_data["player_items"]) 
    #     }),
    # json_data["npcs"]["marie"].update({
    #     "given_request" : ("request from room4" in json_data["player_items"]),
    #     "got_treasure" : ("treasure4" in json_data["player_items"]) 
    #     }),
    # json_data["npcs"]["guy"].update({
    #     "given_request" : ("request from room5" in json_data["player_items"]),
    #     "got_treasure" : ("treasure5" in json_data["player_items"]) 
    #     }),
    
    potions_needed = {
        "lily" : "gold_potion",
        "oliver" : "blue_potion",
        "nick" : "red_potion",
        "marie" : "green_potion",
        "guy" : "orange_potion",
    }
    active_quests = {}


    for i, npc, potion in zip(range(1, 6), potions_needed.keys(), potions_needed.values()):
        if not(json_data["npcs"][npc]["potion_given"] and "treasure" + str(i) not in json_data["player_items"]):
            active_quests[potion] = "bring to " + npc

    for item in json_data["player_items"]:
        if item == "request from room 1":
            if not ("response from eliza" in json_data["player_items"]):
                active_quests[item] = "bring to eliza"
            elif not ("response from lola" in json_data["player_items"]):
                active_quests[item] = "bring to lola"
        elif item == "request from room 2":
            if not ("response from John" in json_data["player_items"]):
                active_quests[item] = "bring to john"
        elif item == "request from room 3":
            if not ("response from Donna" in json_data["player_items"]):
                active_quests[item] = "bring to donna"
        elif item == "request from room 4":
            if not ("response from steve" in json_data["player_items"] or "letter from steve" in json_data["player_items"]):
                active_quests[item] = "bring to steve"
        elif item == "request from room 5":
            if not ("response from Brittany" in json_data["player_items"]):
                active_quests[item] = "bring to brittany"
        
        elif item == "response from lola":
            if not ("treasure1" in json_data["player_items"]):
                active_quests[item] = "bring to lily"
        elif item == "response from steve" or item == "letter from steve":
            if not ("treasure4" in json_data["player_items"]):
                active_quests[item] = "bring to marie"
        elif item == "response from John":
            if not ("treasure2" in json_data["player_items"]):
                active_quests[item] = "bring to oliver"
        elif item == "response from Donna":
            if not ("treasure3" in json_data["player_items"]):
                active_quests[item] = "bring to nick"
        elif item == "response from Brittany":
            if not ("treasure5" in json_data["player_items"]):
                active_quests[item] = "bring to guy"

    json_data["active_quests"] = active_quests


            

if __name__ == "__main__":

    if len(sys.argv) != 3:
        print("Usage: python extract_save_state.py <save_state> <output_file>")
        sys.exit(1)
    filename = sys.argv[1]
    output_file = sys.argv[2]

    state = GameState.load(filename)
    json_data = extract_ground_truth_data(state)
    update_quest_info(state, json_data)
    with open(output_file, 'w') as f:
        json.dump(json_data, f, indent=4)
    print(f"Ground truth data saved to {output_file}")