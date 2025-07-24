import os
import csv
from analyze_info_cost import analyze_info_cost, MAP_DIR, load_transitions, load_game_state, load_report_vector, load_telemetry_text, check_completed_quests


def main():
    data_dir = os.environ.get("DATA_DIR")
    save_dir = os.path.join(data_dir, "participant_data")
    telemetry_dir = os.path.join(save_dir, "telemetry")
    report_file_dir = os.path.join(data_dir, "processed_output")

    output_filename = "info_cost_analysis.csv"

    column_titles = ["pid", "report_type", "npc1", "npc2", "npc3", "npc4", "npc5", "total"]

    with open(output_filename, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(column_titles)

        for pid in range(501, 502):
            pid = str(pid)
            save_file_name = pid
            game_state = load_game_state(os.path.join(save_dir, pid))
            telemetry_text = load_telemetry_text(os.path.join(telemetry_dir, f"{pid}_updated.txt"))
            completed_quests = check_completed_quests(telemetry_text)
            print("completed_quests for participant {pid}:", completed_quests)

            map_transitions = load_transitions(os.path.join(MAP_DIR, "transitions.json"))
            # for report_type in ["user", "generated", "hybrid"]:
            for report_type in ["generated", "hybrid"]:
                report_filename = f"{pid}_{report_type}_report_output.json"
                print(f"Analyzing info cost for {report_filename}...")
                report_vector = load_report_vector(os.path.join(report_file_dir, report_filename))
                row = [pid, report_type]
                total_cost = 0.0
                for patient_id in range(1, 6):
                    if completed_quests[patient_id-1]:
                        patient_cost = 0.0
                    else:
                        patient_cost, true_request, recon_request = analyze_info_cost(
                            game_state, report_vector, patient_id, map_transitions)    
                        print(f"{pid} {patient_id} {report_type} {true_request.type} {true_request.known_properties} {recon_request.known_properties} {patient_cost}")
                    total_cost += patient_cost
                    row.append(patient_cost)
                row.append(total_cost)
                writer.writerow(row)

if __name__ == "__main__":
    main()