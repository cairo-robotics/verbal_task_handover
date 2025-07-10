from analytics.analyze_info_cost import (
    MAP_DIR,
    ActiveGameRequest,
    load_game_state,
    load_report_vector,
    load_transitions,
    check_completed_quests,
    get_step_cost,
    get_current_request,
    reconstruct_active_request
)

import os
TEST_DIR = "/home/kaleb/code/verbal_task_handover/evaluation/test"

def test_step_cost():
    print("Testing step cost calculation...")
    """
    Test the step cost calculation function with a sample game state and report vector.
    """
    # Example game state and report vector
    TEST_DIR = "/home/kaleb/code/verbal_task_handover/test"
    gt_state = load_game_state(os.path.join(TEST_DIR, "kb_test_0701"))
    report_vector = load_report_vector(os.path.join(TEST_DIR, "kb_test_0701_gt.json"))
    map_transitions = load_transitions(os.path.join(MAP_DIR, "transitions.json"))

    # Known properties -- all known should induce 0 IAC
    potion_req = ActiveGameRequest(ActiveGameRequest.POTION)
    potion_req.known_properties = {
        "item": True,
        "target": True,
        "location": True
    }

    assert(get_step_cost(gt_state, 1, potion_req, map_transitions) == 0.0)

    #  Unknown item should induce 45 cost (45 steps to speak w patient)
    potion_req = ActiveGameRequest(ActiveGameRequest.POTION)
    potion_req.known_properties = {
        "item": False,
        "target": True,
        "location": True
    }

    assert(get_step_cost(gt_state, 1, potion_req, map_transitions) == 45)

    #  Unknown target should induce a much higher cost -- need to speak with each patient
    potion_req = ActiveGameRequest(ActiveGameRequest.POTION)
    potion_req.known_properties = {
        "item": True,
        "target": False,
        "location": True
    }

    assert(get_step_cost(gt_state, 1, potion_req, map_transitions) == 189)

def test_current_request():
    print("Testing current request retrieval...")
    """
    Test the retrieval of the current active request from the game state.
    """
    # Example game state
    TEST_DIR = "/home/kaleb/code/verbal_task_handover/test"
    gt_state = load_game_state(os.path.join(TEST_DIR, "kb_test_0701"))

    # Check for a specific patient ID
    patient_id = 1
    active_request = get_current_request(gt_state, patient_id)

    # Validate the properties of the active request
    assert isinstance(active_request, ActiveGameRequest)
    assert active_request.type == ActiveGameRequest.RESPONSE
    assert active_request.known_properties['target'] is True
    assert active_request.known_properties['item'] is True
    assert active_request.known_properties['location'] is True

    # Check for another patient who we haven't interacted with
    patient_id = 5
    active_request = get_current_request(gt_state, patient_id)
    assert isinstance(active_request, ActiveGameRequest)
    assert active_request.type == ActiveGameRequest.POTION
    assert active_request.known_properties['target'] is True
    assert active_request.known_properties['item'] is True
    assert active_request.known_properties['location'] is True # in theory P1 might not actually know the correct room --- something to consider for later

def test_reconstruct_request():
    TEST_DIR = "/home/kaleb/code/verbal_task_handover/test"
    gt_state = load_game_state(os.path.join(TEST_DIR, "kb_test_0701"))
    report_vector = load_report_vector(os.path.join(TEST_DIR, "kb_test_0701_gt.json"))
    map_transitions = load_transitions(os.path.join(MAP_DIR, "transitions.json"))

    # Check for a specific patient ID
    patient_id = 1
    actual_active_request = get_current_request(gt_state, patient_id)
    reconstructed_request = reconstruct_active_request(gt_state, report_vector, actual_active_request, patient_id)

    assert isinstance(reconstructed_request, ActiveGameRequest)
    assert reconstructed_request.type == ActiveGameRequest.RESPONSE
    assert reconstructed_request.known_properties['target'] is True
    assert reconstructed_request.known_properties['item'] is True
    assert reconstructed_request.known_properties['location'] is True

    # Check for another patient at a different stage
    patient_id = 5
    actual_active_request = get_current_request(gt_state, patient_id)
    reconstructed_request = reconstruct_active_request(gt_state, report_vector, actual_active_request, patient_id)
    assert isinstance(reconstructed_request, ActiveGameRequest)
    assert reconstructed_request.type == ActiveGameRequest.POTION
    assert reconstructed_request.known_properties['target'] is True
    assert reconstructed_request.known_properties['item'] is True
    assert reconstructed_request.known_properties['location'] is True  # in theory P1 might

    # modify report to test other cases
    report_vector['characters'][4]['name'] = None
    report_vector['characters'][4]['potion_needed'] = None

    reconstructed_request = reconstruct_active_request(gt_state, report_vector, actual_active_request, patient_id)
    print(reconstructed_request.known_properties)