# from vector_schema import GameState as GameStateSchema
import os
import json
import re

from treasure_hunt.src.game_mdp import GameState
from analytics.iac_bfs import load_transitions, find_steps_between_rooms, MAP_DIR

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

# GAME_DIR = "/home/kaleb/code/verbal_task_handover/evaluation/treasure_hunt_py/treasure_hunt"
# MAP_DIR = os.path.join(GAME_DIR, "maps", "map2")

class ActiveGameRequest:
    POTION = 0
    REQUEST = 1
    RESPONSE = 2
    def __init__(self, req_type=0):
        self.type = req_type
        self.known_properties = {
            "item": False,  # e.g. potion color, request item, response item
            "target": False,  # e.g. patient name, NPC name
            "location": False  # e.g. room name, NPC location
        }

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
        "name" : "guy",
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
        
def get_current_request(game_state: GameState, patient_id: int) -> int:
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
            active_request = ActiveGameRequest(ActiveGameRequest.RESPONSE)
            active_request.known_properties['target'] = True
            active_request.known_properties['item'] = True
            active_request.known_properties['location'] = True
            return active_request
    
    if f"request from room {patient_id}".lower() in game_state.player.flags:
        active_request = ActiveGameRequest(ActiveGameRequest.REQUEST)
        active_request.known_properties['target'] = True
        active_request.known_properties['item'] = True
        active_request.known_properties['location'] = True # in theory P1 might not actually know the correct room --- something to consider for later
        return active_request
    
    if game_state.player.held_item is not None and game_state.player.held_item.lower() in PATIENT_DATA[patient_id]['potion']:
        active_request = ActiveGameRequest(ActiveGameRequest.POTION)
        active_request.known_properties['target'] = True
        active_request.known_properties['item'] = False # if the player already has the potion, they don't need to communicate which it is
        active_request.known_properties['location'] = False # similarly, the location is no longer needed if they have the potion
        return active_request
    
    else:
        active_request = ActiveGameRequest(ActiveGameRequest.POTION)
        active_request.known_properties['target'] = True
        active_request.known_properties['item'] = True
        active_request.known_properties['location'] = True # in theory P1 might not actually know the correct room --- something to consider for later
        return active_request

def get_step_cost(game_state: GameState, patient_id: int, active_request: ActiveGameRequest, map_transitions: dict) -> float:
    """
    Calculate the cost of a step based on the game state and report vector.
    Step cost assessment based on this outline: https://www.notion.so/kalebishop/basic-algorithm-for-information-access-cost-IAC-218e358fbe66801691bfef74f10ceedd?source=copy_link
    
    :param game_state: GameState object representing the current state of the game.
    :param patient_id: ID of the patient for whom the cost is being calculated (1-5).
    :param active_request: ActiveGameRequest object representing the *available information* about the current request for the patient.
    :return: Cost of accessing missing information, as a float.
    """
    patient_pos = game_state._objects[PATIENT_DATA[patient_id]['location']][PATIENT_DATA[patient_id]["name"]].position
    target_npc_pos = game_state._objects[QUEST_NPC_LOCATIONS[PATIENT_DATA[patient_id]['npc_target']]][PATIENT_DATA[patient_id]['npc_target']].position
    
    total_cost = 0.0

    def shortest_patient_lap(start_room, start_pos):
        valid_visit_orders = {
            "room1": ["room2", "room5", "room3", "room4"],
            "room2": ["room1", "room5", "room3", "room4"],
            "room3": ["room4", "room5", "room1", "room2"],
            "room4": ["room3", "room5", "room1", "room2"],
            "room5": ["room1", "room2", "room3", "room4"]
        }

        patient_positions = {room: game_state._objects[room][PATIENT_DATA[i+1]['name']].position for i, room in enumerate(valid_visit_orders.keys())}
        total_steps = 0

        if start_room in valid_visit_orders:
            visit_order = valid_visit_orders[start_room]
            current_pos = start_pos
            current_room = start_room
        else:
            # find closest room to start lap
            closest_room = min(valid_visit_orders.keys(), key=lambda room: find_steps_between_rooms(MAP_DIR, start_room, start_pos, room, patient_positions[room], map_transitions))
            visit_order = valid_visit_orders[closest_room]
            current_pos = patient_positions[closest_room]
            current_room = closest_room
            total_steps += find_steps_between_rooms(MAP_DIR, start_room, start_pos, closest_room, current_pos, map_transitions)

        for room in visit_order:
            steps = find_steps_between_rooms(MAP_DIR, current_room, current_pos,
                                             room, patient_positions[room],
                                            map_transitions)
            total_steps += steps
            current_pos = patient_positions[room]
            current_room = room
        return total_steps
        
    if active_request.type == ActiveGameRequest.POTION:
        if not active_request.known_properties['item']:
            # if the potion is not known, must talk to patient
            total_cost += find_steps_between_rooms(MAP_DIR,
                                            game_state.current_room, game_state.player.pos,
                                            PATIENT_DATA[patient_id]["location"], patient_pos,
                                            map_transitions)
        elif not (active_request.known_properties['target']):
            # if we have the potion but not the patient, we have to check each room
            total_cost += shortest_patient_lap(game_state.current_room, game_state.player.pos)
        
        if not active_request.known_properties['location']:
            # if we have the potion color and the patient, but not the location, we have to check each (storage) room
            total_cost += (min(
                find_steps_between_rooms(MAP_DIR, game_state.current_room, game_state.player.pos,
                                        "storage_1", (5, 1), map_transitions),
                find_steps_between_rooms(MAP_DIR, game_state.current_room, game_state.player.pos,
                                        "storage_2", (1, 3), map_transitions)
            ) + find_steps_between_rooms(MAP_DIR, "storage_1", (5, 1),
                                        "storage_2", (1, 3), map_transitions))
            
    elif active_request.type == ActiveGameRequest.REQUEST:
        if not active_request.known_properties['target']:
            # must get target from patient
            total_cost += find_steps_between_rooms(MAP_DIR,
                                            game_state.current_room, game_state.player.pos,
                                            PATIENT_DATA[patient_id]["location"], patient_pos,
                                            map_transitions)
            total_cost += shortest_patient_lap(game_state.current_room, game_state.player.pos)
        
        elif not active_request.known_properties['item']:
            # if we have the target NPC but don't know the request's origin, we'll have to try each one
            total_cost += len(game_state.player.flags) * 3  # each takes 3 keypresses

        if not active_request.known_properties['location']:
            # it target npc's location is unknown we have to check each (lounge) room
            total_cost += (min(
                find_steps_between_rooms(MAP_DIR, game_state.current_room, game_state.player.pos,
                                        "lounge_1", (4, 1), map_transitions),
                find_steps_between_rooms(MAP_DIR, game_state.current_room, game_state.player.pos,
                                        "lounge_2", (2, 2), map_transitions),
                find_steps_between_rooms(MAP_DIR, game_state.current_room, game_state.player.pos,
                                        "lounge_3", (6, 2), map_transitions)
            ) + find_steps_between_rooms(MAP_DIR, "lounge_1", (4, 1),
                                        "lounge_2", (2, 2), map_transitions) +
                find_steps_between_rooms(MAP_DIR, "lounge_2", (2, 2),
                                        "lounge_3", (6, 2), map_transitions))

    elif active_request.type == ActiveGameRequest.RESPONSE:
        if not active_request.known_properties['item']:
            # if we don't know the response item, we have to check each request
            total_cost += len(game_state.player.flags) * 3
        if not active_request.known_properties['location']:
            # if we don't know the target, we have to check each patient room
            total_cost += shortest_patient_lap(game_state.current_room, game_state.player.pos)

    return total_cost
                
def reconstruct_active_request(game_state: GameState, report_vector: dict, actual_active_request: ActiveGameRequest, patient_id: int) -> ActiveGameRequest:
    """
    Reconstruct the active request for a given patient based on the game state and report vector.
    
    :param game_state: GameState object representing the current state of the game.
    :param report_vector: Dictionary representing the report vector.
    :param patient_id: ID of the patient for whom the request is being reconstructed (1-5).
    :return: ActiveGameRequest object representing the reconstructed request.
    """
    # Example logic, replace with actual logic to reconstruct active request
    # raise NotImplementedError
    if patient_id < 1 or patient_id > 5:
        raise ValueError("Patient ID must be between 1 and 5.")
    

    reconstructed_request = ActiveGameRequest(actual_active_request.type)
    reconstructed_request.known_properties = {p: False for p in actual_active_request.known_properties}

    if actual_active_request.type == ActiveGameRequest.POTION:
        # verify item type and/or target
        for character in report_vector['characters']:
            if (character['name'] and character['name'].lower() == PATIENT_DATA[patient_id]["name"].lower()) or \
                (character["location"] and strip_spacing(character["location"]) == PATIENT_DATA[patient_id]["location"]):
                if character['potion_needed'] and strip_spacing(character['potion_needed']) == strip_spacing(PATIENT_DATA[patient_id]['potion']):
                    reconstructed_request.known_properties['item'] = True
                    reconstructed_request.known_properties['target'] = True
                elif character['needs_potion'] and character['potion_needed'] is None:
                    reconstructed_request.known_properties['item'] = False
                    reconstructed_request.known_properties['target'] = True

                if strip_spacing(character['location']) == strip_spacing(PATIENT_DATA[patient_id]['location']):
                    reconstructed_request.known_properties['location'] = True
    
    elif actual_active_request.type == ActiveGameRequest.REQUEST:
        for req in report_vector['character_requests']:
            if req["item"] and strip_spacing(req["item"]) == strip_spacing(f"request from {patient_id}"):
                reconstructed_request.known_properties['item'] = True
            if req["target"] and req["target"].lower() == PATIENT_DATA[patient_id]['npc_target'].lower():
                if reconstructed_request.known_properties['item'] or not req['item']:
                    reconstructed_request.known_properties['target'] = True

            # do we know the location of the target NPC?
            for character in report_vector['characters']:
                if character["name"] and character['name'].lower() == PATIENT_DATA[patient_id]['npc_target'].lower():
                    if character["location"] and strip_spacing(character['location']) == strip_spacing(QUEST_NPC_LOCATIONS[PATIENT_DATA[patient_id]['npc_target']]):
                        reconstructed_request.known_properties['location'] = True

    elif actual_active_request.type == ActiveGameRequest.RESPONSE:
        for req in report_vector['character_requests']:
            if req["item"] and strip_spacing(req["item"]) == strip_spacing(f"response from {PATIENT_DATA[patient_id]['npc_target']}"):
                reconstructed_request.known_properties['item'] = True
            
            if req["target"] and req["target"].lower() == PATIENT_DATA[patient_id]['name'].lower():
                reconstructed_request.known_properties['target'] = True
                for character in report_vector['characters']:
                    if character["name"] and character['name'].lower() == PATIENT_DATA[patient_id]['name'].lower():
                        if character["location"] and strip_spacing(character['location']) == strip_spacing(PATIENT_DATA[patient_id]['location']):
                            reconstructed_request.known_properties['location'] = True
            elif req["target"] and strip_spacing(PATIENT_DATA[patient_id]['location']) in strip_spacing(req['target']): 
                # knowing the correct room is sufficient to know the target
                reconstructed_request.known_properties['target'] = True
                reconstructed_request.known_properties['location'] = True

    return reconstructed_request

def analyze_info_cost(gt_state: GameState, report_vector: dict, patient_id: int, map_transitions: dict) -> float:
    """
    Analyze the information cost for a given patient based on the game state and report vector.
    
    :param gt_state: GameState object representing the ground truth state of the game.
    :param report_vector: Dictionary representing the report vector.
    :param patient_id: ID of the patient for whom the cost is being calculated (1-5).
    :return: Total information cost as a float.
    """
    raise NotImplementedError
    

    return incurred_cost

def run_single_condition(save_file_name: str, report_datafile_name: str, data_dir: str) -> None:
    """
    Run the information cost analysis for a single participant.
    
    :param participant_id: ID of the participant to analyze.
    :param data_dir: Directory containing the game state and report vector files.
    """
    # gt_save_file = os.path.join(data_dir, "participant_data", save_file_name)
    # report_file = os.path.join(data_dir, "processed_output", report_datafile_name)
    gt_save_file = os.path.join(data_dir, save_file_name)
    report_file = os.path.join(data_dir, report_datafile_name)

    gt_state = load_game_state(gt_save_file)
    report_vector = load_report_vector(report_file)

    map_transitions = load_transitions(os.path.join(MAP_DIR, "transitions.json"))
    
    total_cost = 0.0
    for patient_id in range(1, 6):  # Assuming patient IDs are 1-5
        cost = analyze_info_cost(gt_state, report_vector, patient_id, map_transitions)
        total_cost += cost
    
    return total_cost

