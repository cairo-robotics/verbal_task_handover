import sys
import json
import os

from treasure_hunt.src.game_mdp import GameState, Direction, start_state
from analyze_info_cost import strip_spacing
"""
For extracting the "ground truth" game state in json format, regardless of player knowledge.
Restricted mainly to strictly task-relevant aspects, like rooms entered, NPCs interacted, and so on.
"""

CHARACTERS = [
    {
        "name": "lily",
        "location": "room1",
        "needs_potion": True,
        "potion_needed": "gold_potion",
    },
    {
        "name": "oliver",
        "location": "room2",
        "needs_potion": True,
        "potion_needed": "blue_potion",
    },
    {
        "name": "nick",
        "location": "room3",
        "needs_potion": True,
        "potion_needed": "red_potion",
    },
    {
        "name": "marie",
        "location": "room4",
        "needs_potion": True,
        "potion_needed": "green_potion",
    },
    {
        "name": "guy",
        "location": "room5",
        "needs_potion": True,
        "potion_needed": "orange_potion",
    },
    {
        "name": "eliza",
        "location": "lounge_1",
        "needs_potion": False,
        "potion_needed": None,
    },
    {
        "name": "lola",
        "location": "lounge_2",
        "needs_potion": False,
        "potion_needed": None,
    },
    {
        "name": "john",
        "location": "lounge_2",
        "needs_potion": False,
        "potion_needed": None,
    },
    {
        "name": "donna",
        "location": "lounge_3",
        "needs_potion": False,
        "potion_needed": None,
    },
    {
        "name": "steve",
        "location": "lounge_1",
        "needs_potion": False,
        "potion_needed": None,
    },
    {
        "name": "brittany",
        "location": "lounge_3",
        "needs_potion": False,
        "potion_needed": None,
    }
]

def update_quest_info(state):
    state_vector = {
        "characters": CHARACTERS,
    }
    flags = state.player.flags

    # TODO: fix because the treasure items are not in the flags

    active_requests = []
    overall_progress = 0

    for item in flags:
        if item == "request from room 1":
            overall_progress += 1
            if not ("response from Lola" in flags):
                if not ("response from Eliza" in flags):
                    request = {
                        "target": "eliza",
                        "item": "request from room 1",
                    }
                    active_requests.append(request)
                    continue
                
                overall_progress += 1
                request = {
                    "target": "lola",
                    "item": "request from room 1",
                }
                active_requests.append(request)
        elif item == "request from room 2":
            overall_progress += 1
            if not ("response from John" in flags):
                active_requests.append({
                    "target": "john",
                    "item": "request from room 2"
                })
        elif item == "request from room 3":
            overall_progress += 1
            if not ("response from Donna" in flags):
                active_requests.append({
                    "target": "donna",
                    "item": "request from room 3"
                })
        elif item == "request from room 4":
            overall_progress += 1
            if not ("response from Steve" in flags or "letter from steve" in flags):
                active_requests.append({
                    "target": "Steve",
                    "item": "request from room 4"
                })
        elif item == "request from room 5":
            overall_progress += 1
            if not ("response from Brittany" in flags):
                active_requests.append({
                    "target": "Brittany",
                    "item": "request from room 5"
                })

        elif item == "response from Lola":
            overall_progress += 1
            if not ("treasure1" in flags):
                active_requests.append({
                    "target": "lily",
                    "item": "response from Lola"
                })
        elif item == "response from Steve" or item == "letter from steve":
            overall_progress += 1
            if not ("treasure4" in flags):
                active_requests.append({
                    "target": "marie",
                    "item": "response from Steve"
                })
        elif item == "response from John":
            overall_progress += 1
            if not ("treasure2" in flags):
                active_requests.append({
                    "target": "nick",
                    "item": "response from John"
                })
        elif item == "response from Donna":
            overall_progress += 1
            if not ("treasure3" in flags):
                active_requests.append({
                    "target": "oliver",
                    "item": "response from Donna"
                })
        elif item == "response from Brittany":
            overall_progress += 1
            if not ("treasure5" in flags):
                active_requests.append({
                    "target": "guy",
                    "item": "response from Brittany"
                })

        elif "treasure" in item:
            overall_progress += 1

    state_vector["character_requests"] = active_requests
    state_vector["meta_score"] = overall_progress
    return state_vector

def output_ground_truth(state_filename, output_filename):
    print(f"Loading game state from {state_filename}")

    state = GameState.load(state_filename)
    state_vector = update_quest_info(state)

    with open(output_filename, 'w') as f:
        print(state_vector)
        json.dump(state_vector, f, indent=4)
    print(f"Ground truth data saved to {output_filename}")

if __name__ == "__main__":

    # if len(sys.argv) != 3:
    #     print("Usage: python extract_save_state.py <save_state> <output_file>")
    #     sys.exit(1)

    # save_dir = os.environ.get("DATA_DIR", ".")


    # filename = os.path.join(save_dir, "participant_data", sys.argv[1])
    # output_file = os.path.join(save_dir, "processed_output", sys.argv[2])
    # output_ground_truth(filename, output_file)

    TEST_DIR = "/home/kaleb/code/verbal_task_handover/evaluation/test"
    filename = os.path.join(TEST_DIR, "test_save_state.json")
    input_file = os.path.join(TEST_DIR, sys.argv[1])
    output_ground_truth(input_file, filename)