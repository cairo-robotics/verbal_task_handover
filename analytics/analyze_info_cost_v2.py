import os
import json
import re

from treasure_hunt.src.game_mdp import GameState
from analytics.iac_bfs import load_transitions, find_steps_between_rooms, MAP_DIR
from analytics.graph import TelemetryGraph

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

class QuestState:
    FETCH = 0
    DELIVER = 1
    RETURN = 2
    def __init__(self, quest_type=FETCH):
        self.quest_type = quest_type
        self.known_properties = {}  

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
    
def retrieve_knowledge_dict(telemetry_file: str) -> dict:
    """
    Retrieve the knowledge graph from a telemetry file.
    
    :param telemetry_file: Path to the telemetry file.
    :return: dict representing the TelemetryGraph object.
    """
    graph = TelemetryGraph()
    graph.parse_from_file(telemetry_file)
    return graph.to_dict()

def strip_spacing(text: str) -> str:
    """
    Strip whitespace and underscores from a string.
    
    :param text: Input string to be stripped.
    :return: Stripped string with no whitespace or underscores.
    """
    return re.sub(r"\s|_", "", text.lower())

def is_known_property(property_name: str, state_dict: dict) -> bool:
    """
    Check if a room is known in the game state.
    
    :param state_dict: Dictionary representing the game state.
    :param property: Name of the property (npc or room name) to check.
    :return: True if the room is known, False otherwise.
    """
    return any(strip_spacing(key) == strip_spacing(property_name) for key in state_dict.keys())

def retrieve_groundtruth_quest_state(patient_id: int, game_state: GameState, state_dict: dict):
    if f"response from {PATIENT_DATA[patient_id]['npc_target']}" in game_state.player.flags:
        current = QuestState(QuestState.RETURN)
        current.known_properties['target'] = True
        current.known_properties['target_location'] = True
        current.known_properties['item'] = True
        current.known_properties['sender'] = True
        current.known_properties['sender_location'] = True
        return current
    elif any(f"request from room {patient_id}".lower() == flag.lower() for flag in game_state.player.flags):
        current = QuestState(QuestState.DELIVER)
        current.known_properties['target'] = True
        current.known_properties['target_location'] = is_known_property(PATIENT_DATA[patient_id]['target_location'], state_dict)
        current.known_properties['item'] = True
        current.known_properties['sender'] = True
        current.known_properties['sender_location'] = True
        return current
    else:
        current = QuestState(QuestState.FETCH)
        current.known_properties['target'] = True

        required_potion = PATIENT_DATA[patient_id]['potion']
        potion_location = POTION_LOCATIONS[required_potion]
        current.known_properties['target_location'] = is_known_property(potion_location, state_dict)

        current.known_properties['item'] = True

        current.known_properties['sender'] = is_known_property(PATIENT_DATA[patient_id]['name'], state_dict)
        current.known_properties['sender_location'] = True # players are given the room name at the start of the quest
        return current
    
def reconstruct_quest_state(patient_id: int, gt_quest: QuestState, report_vector: dict, game_state: GameState) -> QuestState:
    reconstructed_quest = QuestState(gt_quest.quest_type)

    if gt_quest.quest_type == QuestState.FETCH:
        for character in report_vector['characters']:
            # known patient in that location?
            if character["location"] and strip_spacing(character["location"]) == strip_spacing(PATIENT_DATA[patient_id]['location']):
                # known (correct) patient name?
                if character["name"] and character["name"].lower() == PATIENT_DATA[patient_id]['name'].lower():
                    reconstructed_quest.known_properties['sender'] = True
                    reconstructed_quest.known_properties['sender_location'] = True
                # name unknown (but not incorrect)? 
                elif not character['name']:
                    reconstructed_quest.known_properties['sender'] = False
                    reconstructed_quest.known_properties['sender_location'] = True

                # correct potion known?
                if character["needs_potion"] and PATIENT_DATA[patient_id]['potion'] in character["potion_needed"]:
                    reconstructed_quest.known_properties['item'] = True
                
                break

        # known target location?
        for known_location in report_vector["location_map"]:
            if strip_spacing(known_location['name']) == strip_spacing(POTION_LOCATIONS[PATIENT_DATA[patient_id]['potion']]):
                if any(PATIENT_DATA[patient_id]['potion'] in potion for potion in known_location['contains_potions']):
                    reconstructed_quest.known_properties['target_location'] = True
                break

    elif gt_quest.quest_type == QuestState.DELIVER:
        for req in report_vector["character_quests"]:
            if req["item"] and PATIENT_DATA[patient_id]["location"] in strip_spacing(req["item"]):
                reconstructed_quest.known_properties["item"] = True
                reconstructed_quest.known_properties["sender_location"] = True
                if req["sender"] and strip_spacing(PATIENT_DATA[patient_id]["name"]) == strip_spacing(req["sender"]):
                    reconstructed_quest.known_properties["sender"] = True
            
            elif not req["item"] and req["sender"] and strip_spacing(PATIENT_DATA[patient_id]["name"]) == strip_spacing(req["sender"]):
                reconstructed_quest.known_properties["sender"] = True


    return reconstructed_quest

if __name__ == "__main__":
    data_dir = os.environ.get('DATA_DIR')
    telemetry_dir = os.path.join(data_dir, 'participant_data', 'telemetry')
    g = retrieve_knowledge_dict(os.path.join(telemetry_dir, '501_updated.txt'))
    print(g)
