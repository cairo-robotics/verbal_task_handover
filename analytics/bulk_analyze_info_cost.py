import os
import csv
# from analyze_info_cost import analyze_info_cost, MAP_DIR, load_transitions, load_game_state, load_report_vector, load_telemetry_text, check_completed_quests
from analyze_info_cost_v2 import *

import dotenv

dotenv.load_dotenv()

def main():
    data_dir = os.environ.get("DATA_DIR")
    save_dir = os.path.join(data_dir, "participant_data")
    telemetry_dir = os.path.join(save_dir, "telemetry")
    report_file_dir = os.path.join(data_dir, "processed_output")

    output_filename = "info_cost_analysis.csv"

    column_titles = ["pid", "report_type", "npc1_ground_truth", "npc1_reconstruction", "npc2_ground_truth", "npc2_reconstruction", "npc3_ground_truth", "npc3_reconstruction", "npc4_ground_truth", "npc4_reconstruction", "npc5_ground_truth", "npc5_reconstruction", "total_diff"]

    with open(output_filename, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(column_titles)

        for pid in range(501, 510):
            pid = str(pid)
            save_file_name = pid
            game_state = load_game_state(os.path.join(save_dir, pid))
            state_dict = retrieve_knowledge_dict(os.path.join(telemetry_dir, f"{pid}_updated.txt"))
            completed_quests = check_completed_quests(state_dict)
            # print(game_state.player.flags)
            print(f"completed_quests for participant {pid}:", completed_quests)

            map_transitions = load_transitions(os.path.join(MAP_DIR, "transitions.json"))
            for report_type in ["user", "generated", "hybrid"]:
            # for report_type in ["generated", "hybrid"]:
                report_filename = f"{pid}_{report_type}_report_output.json"
                print(f"Analyzing info cost for {report_filename}...")
                report_vector = load_report_vector(os.path.join(report_file_dir, report_filename))
                row = [pid, report_type]
                # BUG: why is npc 4 always having a ground truth cost of 0? it's seemingly not always being marked complete
                total_cost = 0.0
                for patient_id in range(1, 6):
                    ground_truth_quest = retrieve_groundtruth_quest_state(patient_id, game_state, state_dict)
                    if completed_quests[patient_id-1]:
                        ground_truth_cost = 0.0
                    else:
                        ground_truth_cost = score_reconstruction(patient_id, ground_truth_quest, game_state)
                    row.append(ground_truth_cost)

                    reconstructed_quest = reconstruct_quest_state(patient_id, ground_truth_quest, report_vector, game_state)
                    reconstruction_cost = score_reconstruction(patient_id, reconstructed_quest, game_state)
                    row.append(reconstruction_cost)

                    total_cost += (ground_truth_cost - reconstruction_cost)
                row.append(total_cost)
                writer.writerow(row)

if __name__ == "__main__":
    main()