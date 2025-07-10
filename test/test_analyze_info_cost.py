from analytics.analyze_info_cost import (
    MAP_DIR,
    ActiveGameRequest,
    load_game_state,
    load_report_vector,
    load_transitions,
    check_completed_quests,
    get_step_cost
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
