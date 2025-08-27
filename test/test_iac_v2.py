from analytics.analyze_info_cost_v2 import *

import os
TEST_DIR = "/home/kaleb/code/verbal_task_handover/test"

def test_retrieve_groundtruth_test_state():
    print("Testing ground truth quest state retrieval...")
    """
    Test the retrieval of ground truth quest state for a specific patient.
    """
    # Example game state and report vector
    gt_state = load_game_state(os.path.join(TEST_DIR, "kb_test_0717"))
    state_dict = retrieve_knowledge_dict(os.path.join(TEST_DIR, "telemetry", 'kb_test_0717.txt'))
    # Retrieve the ground truth quest state for patient 1
    for patient_id in range(1, 6):
        quest_state = retrieve_groundtruth_quest_state(patient_id, gt_state, state_dict)
        print(f"Quest state for patient {patient_id}: {quest_state.quest_type} {quest_state.known_properties}")
        
def test_reconstruct_quest_state():
    print("Testing quest state reconstruction...")
    """
    Test the reconstruction of quest state from a report vector.
    """
    # Example game state and report vector
    gt_state = load_game_state(os.path.join(TEST_DIR, "kb_test_0728"))
    report_vector = load_report_vector(os.path.join(TEST_DIR, "kb_test_0728_generated_report_output.json"))
    state_dict = retrieve_knowledge_dict(os.path.join(TEST_DIR, "telemetry", 'kb_test_0728_updated.txt'))

    for patient_id in range(1, 6):
        gt_quest = retrieve_groundtruth_quest_state(patient_id, gt_state, state_dict)
        reconstructed_quest = reconstruct_quest_state(patient_id, gt_quest, report_vector, gt_state)
        print(f"Reconstructed quest for patient {patient_id}: {reconstructed_quest.quest_type} {reconstructed_quest.known_properties}")

def test_score_reconstruction():
    print("Testing quest state reconstruction scoring...")
    """
    Test the scoring of reconstructed quest states.
    """
    gt_state = load_game_state(os.path.join(TEST_DIR, "kb_test_0728"))

    reconstructed_quest = QuestState(quest_type=QuestState.DELIVER)
    reconstructed_quest.known_properties = {
        "item": False,
        "target_location": True,
        "sender_location": False
    }

    score = score_reconstruction(1, reconstructed_quest, gt_state)
    print(f"Reconstruction score: {score}")

def test_compare_status_cost():
    print("Testing comparison of status costs...")
    """
    Test the comparison of status costs between ground truth and reconstructed quests.
    """
    gt_state = load_game_state(os.path.join(TEST_DIR, "kb_test_0728"))
    report_vector = load_report_vector(os.path.join(TEST_DIR, "kb_test_0728_generated_report_output.json"))
    state_dict = retrieve_knowledge_dict(os.path.join(TEST_DIR, "telemetry", 'kb_test_0728_updated.txt'))

    for patient_id in range(2, 6):
        cost_comparison = compare_patient_status_cost(patient_id, report_vector, state_dict, gt_state)
        print(f"Cost comparison for patient {patient_id}: {cost_comparison}")

def test_completed_quests():
    print("Testing completed quests...")
    """
    Test the identification of completed quests.
    """
    # gt_state = load_game_state(os.path.join(TEST_DIR, "kb_test_0728"))
    state_dict = retrieve_knowledge_dict(os.path.join(TEST_DIR, "telemetry", 'kb_test_0728_updated.txt'))

    completed_quests = check_completed_quests(state_dict)
    print(f"Completed quests: {completed_quests}")