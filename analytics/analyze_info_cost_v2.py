import os
import json
import re

from treasure_hunt.src.game_mdp import GameState
from iac_bfs import load_transitions, find_steps_between_rooms, MAP_DIR

import sys
from graph import TelemetryGraph

PATIENT_DATA = {
    1 : {
        "name" : "lily",
        "potion" : "gold",
        "npc_target" : "lola",
        "target_location" : "lounge_2",
        "treasure" : "treasure1",
        "location" : "room1"
    },
    2 : {
        "name" : "oliver",
        "potion" : "blue",
        "npc_target" : "john",
        "target_location" : "longue_2",
        "treasure" : "treasure2",
        "location" : "room2"
    },
    3 : {
        "name" : "nick",
        "potion": "red",
        "npc_target": "donna",
        "target_location": "lounge_3",
        "treasure": "treasure3",
        "location": "room3"
    },
    4 : {
        "name" : "marie",
        "potion" : "green",
        "npc_target" : "steve",
        "target_location" : "lounge_1",
        "treasure" : "treasure4",
        "location" : "room4"
    },
    5: {
        "name" : "guy",
        "potion" : "orange",
        "npc_target" : "brittany",
        "target_location" : "lounge_3",
        "treasure" : "treasure5",
        "location" : "room5"
    }
}

POTION_ROOM_CONTENTS = {
    "storage_1" : [
        "red",
        "pale_blue",
        "gold"
    ],
    "storage_2": [
        "pink",
        "green",
        "blue",
        "orange",
        "purple"
    ]
}

POTION_LOCATIONS = {value: key for key, values in POTION_ROOM_CONTENTS.items() for value in values}

def load_game_state(file_path) -> GameState:
    """
    Load a game state from a pkl file.
    
    :param file_path: Path to the pkl file containing the game state save file.
    :return: GameState object.
    """
    state = GameState.load(file_path)
    state.player.pos = int(state.player.pos[0]), int(state.player.pos[1])  # Ensure position is a tuple of integers
    return state

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
    
def retrieve_knowledge_graph(telemetry_file: str) -> TelemetryGraph:
    """
    Retrieve the knowledge graph from a telemetry file.
    
    :param telemetry_file: Path to the telemetry file.
    :return: TelemetryGraph object.
    """
    graph = TelemetryGraph()
    graph.parse_from_file(telemetry_file)
    return graph

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

def strip_spacing(text: str) -> str:
    """
    Strip whitespace and underscores from a string.
    
    :param text: Input string to be stripped.
    :return: Stripped string with no whitespace or underscores.
    """
    return re.sub(r"\s|_", "", text.lower())

# def get_current_request(game_state: GameState, state_graph_dict: dict, patient_id: int) -> dict:
#     """
#     Get the current active request for a patient based on the game state and state graph.
    
#     :param game_state: Current game state.
#     :param state_graph: TelemetryGraph object representing the knowledge graph.
#     :param patient_id: ID of the patient for whom to retrieve the request.
#     :return: Dictionary representing the active request for the patient.
#     """
#     patient_data = PATIENT_DATA[patient_id]
    
#     active_request = {}

#     for flag in game_state.player.flags:
#         if flag.lower() == f"response from {PATIENT_DATA[patient_id]['npc_target']}":
#             active_request['type'] = 'RESPONSE'
#             active_request['item'] = f"response from {PATIENT_DATA['npc_target']}"
#             active_request['sender'] = PATIENT_DATA[patient_id]['npc_target']
#             active_request['target'] = PATIENT_DATA['name']
#             active_request['target_location'] = patient_data['location']

#             sender_location = state_graph_dict
#             break
    
#     return active_request

if __name__ == "__main__":
    data_dir = os.environ.get('DATA_DIR')
    telemetry_dir = os.path.join(data_dir, 'participant_data', 'telemetry')
    g = retrieve_knowledge_graph(os.path.join(telemetry_dir, '501_updated.txt'))
    print(g.to_dict())
