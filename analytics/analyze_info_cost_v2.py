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

def check_completed_quests(state_dict: dict) -> list[bool]:
    completed_quests = [False, False, False, False, False]
    for patient_id in range(1, 6):
        if f"response from {PATIENT_DATA[patient_id]['npc_target']}" in state_dict['Player']:
            completed_quests[patient_id-1] = True
    return completed_quests

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

def score_reconstruction(patient_id, reconstructed_quest: QuestState, game_state: GameState) -> float:
    """
    Score the reconstruction of a quest state.
    
    :param gt_quest: Ground truth quest state.
    :param reconstructed_quest: Reconstructed quest state.
    :return: Score as an integer representing info access cost.
    """

    map_transitions = load_transitions(os.path.join(MAP_DIR, "transitions.json"))

    score = 0
    patient_pos = game_state._objects[PATIENT_DATA[patient_id]['location']][PATIENT_DATA[patient_id]["name"]].position

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

    if reconstructed_quest.quest_type == QuestState.FETCH:
        if not reconstructed_quest.known_properties.get("item", False):
            if reconstructed_quest.known_properties.get("sender_location", False):
                # must talk to patient
                print("must talk to patient")
                score += find_steps_between_rooms(
                    MAP_DIR, 
                    game_state.current_room,
                    game_state.player.pos, 
                    PATIENT_DATA[patient_id]['location'],
                    patient_pos,
                    map_transitions
                )
            else:
                # must talk to all patients
                print("must talk to all patients")
                score += shortest_patient_lap(game_state.current_room, game_state.player.pos)

        elif not reconstructed_quest.known_properties.get("sender_location", False):
            # must talk to all patients
            print("must talk to all patients")
            score += shortest_patient_lap(game_state.current_room, game_state.player.pos)
        
        if not reconstructed_quest.known_properties.get("target_location", False):
            # must check both storage rooms
            print("must check both storage rooms")
            score += (min(  find_steps_between_rooms(MAP_DIR, game_state.current_room, game_state.player.pos,
                                        "storage_1", (5, 1), map_transitions),
                            find_steps_between_rooms(MAP_DIR, game_state.current_room, game_state.player.pos,
                                        "storage_2", (1, 3), map_transitions)) + 
                    find_steps_between_rooms(MAP_DIR, "storage_1", (5, 1),
                        "storage_2", (1, 3), map_transitions))

    elif reconstructed_quest.quest_type == QuestState.DELIVER:
        if not reconstructed_quest.known_properties.get("target", False) or (not reconstructed_quest.known_properties.get("item", False) and not reconstructed_quest.known_properties.get("sender_location", False)):
            if not reconstructed_quest.known_properties.get("sender_location", False) and not reconstructed_quest.known_properties.get("item", False): # item id contains sender location regardless
                # must talk to all patients
                score += shortest_patient_lap(game_state.current_room, game_state.player.pos)
            else:   
                # must talk to specific patient
                score += find_steps_between_rooms(
                    MAP_DIR, 
                    game_state.current_room,
                    game_state.player.pos, 
                    PATIENT_DATA[patient_id]['location'],
                    patient_pos,
                    map_transitions
                )

        if not reconstructed_quest.known_properties.get("target_location", False):
            # TODO: check if "target_location" can be marked true even if target is unknown (so when we learn the name, we learn the location)
            # must check all 3 lounges
            score += (min(  find_steps_between_rooms(MAP_DIR, game_state.current_room, game_state.player.pos,
                                        "lounge_1", (4, 1), map_transitions),
                            find_steps_between_rooms(MAP_DIR, game_state.current_room, game_state.player.pos,
                                        "lounge_2", (2, 2), map_transitions),
                            find_steps_between_rooms(MAP_DIR, game_state.current_room, game_state.player.pos,
                                        "lounge_3", (6, 2), map_transitions)) +
                    find_steps_between_rooms(MAP_DIR, "lounge_1", (4, 1),
                                        "lounge_2", (2, 2), map_transitions) +
                    find_steps_between_rooms(MAP_DIR, "lounge_2", (2, 2),
                                        "lounge_3", (6, 2), map_transitions))

    elif reconstructed_quest.quest_type == QuestState.RETURN:
        if not reconstructed_quest.known_properties.get("target_location", False) or not reconstructed_quest.known_properties.get("item", False):
            if reconstructed_quest.known_properties.get("sender_location", False):
                # return to sender to get more information
                score += find_steps_between_rooms(
                    MAP_DIR, 
                    game_state.current_room,
                    game_state.player.pos, 
                    PATIENT_DATA[patient_id]['target_location'],
                    game_state._objects[PATIENT_DATA[patient_id]['target_location']][PATIENT_DATA[patient_id]['npc_target']].position,
                    map_transitions
                )
            else:
                if reconstructed_quest.known_properties.get("sender_location", False):
                    # replay previous step by returning to patient and then going to target location again
                    score += find_steps_between_rooms(
                        MAP_DIR, 
                        game_state.current_room,
                        game_state.player.pos, 
                        PATIENT_DATA[patient_id]['location'],
                        patient_pos,
                        map_transitions
                    )

                if not reconstructed_quest.known_properties.get("target_location", False):
                    # must check all 3 lounges
                    score += (min(  find_steps_between_rooms(MAP_DIR, game_state.current_room, game_state.player.pos,
                                                "lounge_1", (4, 1), map_transitions),
                                    find_steps_between_rooms(MAP_DIR, game_state.current_room, game_state.player.pos,
                                                "lounge_2", (2, 2), map_transitions),
                                    find_steps_between_rooms(MAP_DIR, game_state.current_room, game_state.player.pos,
                                                "lounge_3", (6, 2), map_transitions)) +
                            find_steps_between_rooms(MAP_DIR, "lounge_1", (4, 1),
                                                "lounge_2", (2, 2), map_transitions) +
                            find_steps_between_rooms(MAP_DIR, "lounge_2", (2, 2),
                                        "lounge_3", (6, 2), map_transitions))
    return score

def compare_patient_status_cost(patient_id, report_vector: dict, state_dict: dict, game_state: GameState) -> float:
    """
    Compare the cost of the current patient status with the report vector.
    
    :param patient_id: ID of the patient to compare.
    :param report_vector: Report vector containing the current patient status.
    :param game_state: Current game state.
    :return: Cost of the current patient status.
    """
    gt_quest = retrieve_groundtruth_quest_state(patient_id, game_state, state_dict)
    reconstructed_quest = reconstruct_quest_state(patient_id, gt_quest, report_vector, game_state)
    print("Expected known properties:", gt_quest.known_properties)
    print("Reconstructed known properties:", reconstructed_quest.known_properties)
    return score_reconstruction(patient_id, reconstructed_quest, game_state), score_reconstruction(patient_id, gt_quest, game_state)

if __name__ == "__main__":
    data_dir = os.environ.get('DATA_DIR')
    telemetry_dir = os.path.join(data_dir, 'participant_data', 'telemetry')
    g = retrieve_knowledge_dict(os.path.join(telemetry_dir, '501_updated.txt'))
    print(g)
