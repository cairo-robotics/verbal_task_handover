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