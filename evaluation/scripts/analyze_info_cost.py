# from vector_schema import GameState as GameStateSchema
from treasure_hunt.src.game_mdp import GameState
import os
import json
import sys

import re

"""
Basic IAC algorithm pseudocode:
given gt_state, report_state as dicts
net_cost = 0
for pt in range(1, 6):
	# what is the gt_state progress in this questline?
	current_req_id = gt_state[pt]
	# is the information required to complete this request available in the report?
	current_report_req_id = current_req_id
	criteria_met = False
	incurred_cost = 0
	while not criteria_met and current_report_req_id > 0:
		for criterion in info_criteria[current_report_req_id]:
			if is_valid_match(criterion, gt_state[pt], report_state[pt]):
				criteria_met = True # we can safely assume next player (p2) will start from this request
			else:
				incurred_cost += apply_cost(criterion)
		# if p2 has nothing to go off of, we assume they'll have to default to the previous step
		if not criteria_met:
			current_report_req_id -= 1
	net_cost += incurred_cost
return net_cost
"""

ROOM_WALK_COST = 25.0 # TODO replace with more nuanced cost based on distance, etc.

POTION_ROOM_CONTENTS = {
    "storage_1" : [
        "red_potion",
        "pale_blue_potion",
        "gold_potion"
    ],
    "storage_2": [
        "pink_potion",
        "green_potion",
        "blue_potion",
        "orange_potion",
        "purple_potion"
    ]
}

POTION_LOCATIONS = {value: key for key, values in POTION_ROOM_CONTENTS.items() for value in values}

QUEST_NPC_LOCATIONS = {
    "eliza" : "lounge_1",
    "steve" : "lounge_1",
    "lola": "lounge_2",
    "john": "lounge_2",
    "donna": "lounge_3",
    "brittany": "lounge_3"
}

PATIENT_DATA = {
    1 : {
        "name" : "lily",
        "potion" : "gold_potion",
        "npc_target" : "lola",
        "treasure" : "treasure1",
        "location" : "room1"
    },
    2 : {
        "name" : "oliver",
        "potion" : "blue_potion",
        "npc_target" : "john",
        "treasure" : "treasure2",
        "location" : "room2"
    },
    3 : {
        "name" : "nick",
        "potion": "red_potion",
        "npc_target": "donna",
        "treasure": "treasure3",
        "location": "room3"
    },
    4 : {
        "name" : "marie",
        "potion" : "green_potion",
        "npc_target" : "steve",
        "treasure" : "treasure4",
        "location" : "room4"
    },
    5: {
        "name" : "james",
        "potion" : "orange_potion",
        "npc_target" : "brittany",
        "treasure" : "treasure5",
        "location" : "room5"
    }
}

def strip_spacing(text: str) -> str:
    """
    Strip whitespace and underscores from a string.
    
    :param text: Input string to be stripped.
    :return: Stripped string with no whitespace or underscores.
    """
    return re.sub(r"\s|_", "", text.lower())

def load_game_state(file_path) -> GameState:
    """
    Load a game state from a pkl file.
    
    :param file_path: Path to the pkl file containing the game state save file.
    :return: GameState object.
    """
    return GameState.load(file_path)

def load_report_vector(file_path) -> dict:
    """
    Load a report vector from a json file.
    
    :param file_path: Path to the json file containing the report vector in format defined in vector_schema.py.
    :return: Dictionary representing the report vector.
    """
    with open(file_path, 'r') as f:
        return json.load(f)
    
def load_telemetry_text(file_path) -> list:
    """
    Load telemetry text from a file.
    
    :param file_path: Path to the file containing the telemetry text.
    :return: Telemetry text as a string.
    """
    with open(file_path, 'r') as file:
        lines = file.readlines()
        return [line.lower() for line in lines]

def check_completed_quests(telemetry_text: list) -> list:
    """
    Check which quests have been completed based on the telemetry text.
    
    :param telemetry_text: Telemetry text as a string.
    :return: List of completed quests.
    """
    completed_quests = [False, False, False, False, False]  # Assuming 5 patients
    for patient_id in range(1, 6):  # Assuming patient IDs are 1-5
        for line in telemetry_text:
            if PATIENT_DATA[patient_id]['name'] in line and f"response from {PATIENT_DATA[patient_id]['npc_target']}" in line:
                completed_quests[patient_id-1] = True
                break
    return completed_quests
        
def get_current_request_id(game_state: GameState, patient_id: int) -> int:
    """
    Get the current request ID for a given patient in the game state.
    
    :param game_state: GameState object representing the current state of the game.
    :param patient_id: ID of the patient for whom the request ID is being retrieved (1-5).
    :return: Current request ID as an integer.
    """
    # Example logic, replace with actual logic to retrieve current request ID (i.e. what P2 should be working on next)
    # raise NotImplementedError
    if patient_id < 1 or patient_id > 5:
        raise ValueError("Patient ID must be between 1 and 5.")
    
    for flag in game_state.player.flags:
        if flag.lower() == f"response from {PATIENT_DATA[patient_id]['npc_target']}":
            return 5
    
    if f"request from room {patient_id}".lower() in game_state.player.flags:
        return 3
    if game_state.player.held_item is not None and game_state.held_item.lower() == PATIENT_DATA[patient_id]['potion']:
        return 2
    return 1

def get_step_cost(game_state: GameState, patient_id: int, task_step: int) -> float:
    """
    Calculate the cost of a step based on the game state and report vector.
    Step cost assessment based on this outline: https://www.notion.so/kalebishop/basic-algorithm-for-information-access-cost-IAC-218e358fbe66801691bfef74f10ceedd?source=copy_link
    
    :param game_state: GameState object representing the current state of the game.
    :param patient_id: ID of the patient for whom the cost is being calculated (1-5).
    :param task_step: The step number in the task for which the cost is being calculated (0-6)
    :return: Cost of the step as a float.
    """
    if task_step == 0:
        # must go to patient room
        return ROOM_WALK_COST
    elif task_step == 1:
        # must locate correct potion, assuming no prior knowledge of map
        return ROOM_WALK_COST*11 # 11 rooms in the game
    elif task_step == 2:
        # must give potion (or simply talk agian) and get request
        return ROOM_WALK_COST
    elif task_step == 3:
        # locate target NPC, assuming no prior knowledge of map
        return ROOM_WALK_COST*11 # 11 rooms in the game
    elif task_step == 4:
        # must ask about correct item
        return len(game_state.player.flags) - 1
    elif task_step == 5:
        # must bring response to correct patient
        return ROOM_WALK_COST*11 # 11 rooms in the game
    elif task_step == 6:
        # must ask about the correct response
        return len(game_state.player.flags) - 1

def is_valid_match(game_state: GameState, report_vector: dict, patient_id: int, task_step: int) -> bool:
    """
    Check if the report vector matches the game state for a given patient and task step.
    
    :param game_state: GameState object representing the current state of the game.
    :param report_vector: Dictionary representing the report vector.
    :param patient_id: ID of the patient for whom the match is being checked (1-5).
    :param task_step: The step number in the task for which the match is being checked (0-6)
    :return: True if the report vector matches the game state for this field, False otherwise.
    """
    # TODO: needs testing!
    # Example validation logic, replace with actual logic (which will vary based on the step and patient)
    if task_step == 0: # identity of correct potion
        for npc in report_vector['characters']:
            if strip_spacing(npc["potion_needed"]) == strip_spacing(PATIENT_DATA[patient_id]['potion']):
                if strip_spacing(npc["name"]) == strip_spacing(PATIENT_DATA[patient_id]['name']) or \
                   strip_spacing(npc["location"]) == strip_spacing(PATIENT_DATA[patient_id]['location']):
                    return True
    elif task_step == 1: # location of correct potion
        for room in report_vector["location_map"]:
            if strip_spacing(room["name"]) == strip_spacing(POTION_LOCATIONS[PATIENT_DATA[patient_id]['potion']]):
                for potion in room["contains_potions"]:
                    if strip_spacing(potion) == strip_spacing(PATIENT_DATA[patient_id]['potion']):
                        return True
                
    elif task_step == 2: # identity of request npc
        for request in report_vector["character_requests"]:
            if strip_spacing(request["target"]) == strip_spacing(PATIENT_DATA[patient_id]['npc_target']):
                return True
            
    elif task_step == 3: # locating request npc
        for npc in report_vector["characters"]:
            if strip_spacing(npc["name"]) == strip_spacing(PATIENT_DATA[patient_id]['npc_target']) and \
                strip_spacing(npc["location"]) == QUEST_NPC_LOCATIONS[PATIENT_DATA[patient_id]['npc_target']]:
                return True

    # TODO: i don't feel great about the ordering of these
    elif task_step == 4:
        # asking about correct item
        for req in report_vector["character_requests"]:
            if strip_spacing(req["target"]) == strip_spacing(PATIENT_DATA[patient_id]['npc_target']) and \
                strip_spacing(req["item"]) == strip_spacing(f"request from room {patient_id}"):
                return True
            
    elif task_step == 5: # bringing response to correct patient
        for req in report_vector["character_requests"]:
            if strip_spacing(req["target"]) == strip_spacing(PATIENT_DATA[patient_id]['name']) or \
                    strip_spacing(PATIENT_DATA[patient_id]['location']) in strip_spacing(req["target"]):
                    return True

    elif task_step == 6: # asking about the correct response
        for req in report_vector["character_requests"]:
            if strip_spacing(req["item"]) == strip_spacing(f"response from {PATIENT_DATA[patient_id]['npc_target']}"):
                if strip_spacing(req["target"]) == strip_spacing(PATIENT_DATA[patient_id]['name']) or \
                    strip_spacing(PATIENT_DATA[patient_id]['location']) in strip_spacing(req["target"]):
                    return True

    return False

def analyze_info_cost(gt_state: GameState, report_vector: dict, patient_id: int) -> float:
    """
    Analyze the information cost for a given patient based on the game state and report vector.
    
    :param gt_state: GameState object representing the ground truth state of the game.
    :param report_vector: Dictionary representing the report vector.
    :param patient_id: ID of the patient for whom the cost is being calculated (1-5).
    :return: Total information cost as a float.
    """
    total_cost = 0.0
    
    """
        current_req_id = get_current_request_id(gt_state, patient_id)
        current_report_req_id = current_req_id
        criteria_met = False
        incurred_cost = 0.0
        
        while not criteria_met and current_report_req_id > 0:
            if is_valid_match(gt_state, report_vector, patient_id, task_step):
                criteria_met = True
            else:
                incurred_cost += get_step_cost(gt_state, report_vector, patient_id, task_step)
            current_report_req_id -= 1
        
        total_cost += incurred_cost
    """
    current_req_id = get_current_request_id(gt_state, patient_id)
    current_report_req_id = current_req_id
    criteria_met = False
    incurred_cost = 0.0

    while not criteria_met and current_report_req_id >= 0:
        if is_valid_match(gt_state, report_vector, patient_id, current_report_req_id):
            criteria_met = True
        else:
            incurred_cost += get_step_cost(gt_state, patient_id, current_report_req_id)
        current_report_req_id -= 1
    
    return incurred_cost

def run_single_condition(save_file_name: str, report_datafile_name: str, data_dir: str) -> None:
    """
    Run the information cost analysis for a single participant.
    
    :param participant_id: ID of the participant to analyze.
    :param data_dir: Directory containing the game state and report vector files.
    """
    gt_save_file = os.path.join(data_dir, "participant_data", save_file_name)
    report_file = os.path.join(data_dir, "processed_output", report_datafile_name)
    
    gt_state = load_game_state(gt_save_file)
    report_vector = load_report_vector(report_file)
    
    total_cost = 0.0
    for patient_id in range(1, 6):  # Assuming patient IDs are 1-5
        cost = analyze_info_cost(gt_state, report_vector, patient_id)
        total_cost += cost
    
    return total_cost

def test_step_matching():
    """
    Test the step matching function with a sample game state and report vector.
    """
    # Example game state and report vector
    TEST_DIR = "/home/kaleb/code/verbal_task_handover/evaluation/test"
    gt_state = GameState.load(os.path.join(TEST_DIR, "kb_test_0701"))

    report_vector = load_report_vector(os.path.join(TEST_DIR, "test_save_state.json"))
    
    for patient_id in range(1, 6):
        current_request_id = get_current_request_id(gt_state, patient_id)
        for task_step in range(0, 7):  # Assuming task steps are 0-6
            is_match = is_valid_match(gt_state, report_vector, patient_id, task_step)
            step_cost = get_step_cost(gt_state, patient_id, task_step)
            print(f"Patient {patient_id}, Task Step {task_step}: "
                  f"Current Request ID: {current_request_id}, "
                  f"Is Match: {is_match}, "
                  f"Step Cost: {step_cost}")

# for testing
if __name__ == "__main__":

    test_step_matching()

    # Uncomment the following lines to run the script with command line arguments
    # if len(sys.argv) != 3:
    #     print("Usage: python analyze_info_cost.py <save_file_name> <report_datafile_name>")
    #     sys.exit(1)
    
    # save_file_name = sys.argv[1]
    # # report_datafile_name = sys.argv[2]

    # # data_dir = os.environ.get("DATA_DIR", ".")
    # data_dir = "/home/kaleb/code/verbal_task_handover/evaluation/treasure_hunt_py/treasure_hunt/saves"

    # # save_file_state = load_game_state(os.path.join(data_dir, "participant_data", save_file_name))
    # save_file_state = load_game_state(os.path.join(data_dir, save_file_name))
    # print("load_game_state:", save_file_state)
    # # report_datafile_state = load_report_vector(os.path.join(data_dir, "processed_output", report_datafile_name))
    # # print("load_report_vector:", report_datafile_state)
    # # telemetry_text = load_telemetry_text(os.path.join(data_dir, "participant_data", "telemetry", save_file_name + ".txt"))
    # telemetry_text = load_telemetry_text(os.path.join(data_dir, "telemetry", save_file_name + ".txt"))
    # print("load_telemetry_text:", telemetry_text)
    # completed_quests = check_completed_quests(telemetry_text)
    # print("check_completed_quests:", completed_quests)

    # print(get_current_request_id(save_file_state, 1))  # Example for patient ID 1
    # print(get_step_cost(save_file_state, 1, 5))  # Example for patient ID 1 at task step 5
    
    
    # # total_cost = run_single_condition(save_file_name, report_datafile_name, data_dir)
    # # print(f"Total information cost for {report_datafile_name}: {total_cost:.2f}")