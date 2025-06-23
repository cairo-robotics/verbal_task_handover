# from vector_schema import GameState as GameStateSchema
from treasure_hunt.src.game_mdp import GameState
import os
import json

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

def load_game_state(file_path) -> GameState:
    """
    Load a game state from a pkl file.
    
    :param file_path: Path to the pkl file containing the game state save file.
    :return: GameState object.
    """
    raise NotImplementedError

def load_report_vector(file_path) -> dict:
    """
    Load a report vector from a json file.
    
    :param file_path: Path to the json file containing the report vector in format defined in vector_schema.py.
    :return: Dictionary representing the report vector.
    """
    with open(file_path, 'r') as f:
        return json.load(f)
    
def get_current_request_id(game_state: GameState, patient_id: int) -> int:
    """
    Get the current request ID for a given patient in the game state.
    
    :param game_state: GameState object representing the current state of the game.
    :param patient_id: ID of the patient for whom the request ID is being retrieved (1-5).
    :return: Current request ID as an integer.
    """
    # Example logic, replace with actual logic to retrieve current request ID (i.e. what P2 should be working on next)
    raise NotImplementedError

def get_step_cost(game_state: GameState, report_vector: dict, patient_id: int, task_step: int) -> float:
    """
    Calculate the cost of a step based on the game state and report vector.
    Step cost assessment based on this outline: https://www.notion.so/kalebishop/basic-algorithm-for-information-access-cost-IAC-218e358fbe66801691bfef74f10ceedd?source=copy_link
    
    :param game_state: GameState object representing the current state of the game.
    :param report_vector: Dictionary representing the report vector.
    :param patient_id: ID of the patient for whom the cost is being calculated (1-5).
    :param task_step: The step number in the task for which the cost is being calculated (0-6)
    :return: Cost of the step as a float.
    """
    # Example calculation, replace with actual logic
    # This is a placeholder for the actual cost calculation logic
    return 1.0  # Placeholder value, replace with actual cost calculation logic

def is_valid_match(game_state: GameState, report_vector: dict, patient_id: int, task_step: int) -> bool:
    """
    Check if the report vector matches the game state for a given patient and task step.
    
    :param game_state: GameState object representing the current state of the game.
    :param report_vector: Dictionary representing the report vector.
    :param patient_id: ID of the patient for whom the match is being checked (1-5).
    :param task_step: The step number in the task for which the match is being checked (0-6)
    :return: True if the report vector matches the game state for this field, False otherwise.
    """
    # Example validation logic, replace with actual logic (which will vary based on the step and patient)
    return True  # Placeholder value, replace with actual validation logic

def analyze_info_cost(gt_state: GameState, report_vector: dict, patient_id: int) -> float:
    """
    Analyze the information cost for a given patient based on the game state and report vector.
    
    :param gt_state: GameState object representing the ground truth state of the game.
    :param report_vector: Dictionary representing the report vector.
    :param patient_id: ID of the patient for whom the cost is being calculated (1-5).
    :return: Total information cost as a float.
    """
    total_cost = 0.0
    
    #     current_req_id = get_current_request_id(gt_state, patient_id)
    #     current_report_req_id = current_req_id
    #     criteria_met = False
    #     incurred_cost = 0.0
        
    #     while not criteria_met and current_report_req_id > 0:
    #         if is_valid_match(gt_state, report_vector, patient_id, task_step):
    #             criteria_met = True
    #         else:
    #             incurred_cost += get_step_cost(gt_state, report_vector, patient_id, task_step)
    #         current_report_req_id -= 1
        
    #     total_cost += incurred_cost
    
    return total_cost