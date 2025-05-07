import os
import sys
from save_to_vector import output_ground_truth
from report_to_vector import convert_to_vector

PARTICIPANTS = list(range(502, 510, 2))

def main(load_dir, output_dir):
    for pid in PARTICIPANTS:
        save_file = os.path.join(load_dir, f"{pid}")
        save_output_file = os.path.join(output_dir, f"{pid}_save_output.json")
        output_ground_truth(save_file, save_output_file)

        report_file = os.path.join(load_dir, f"{pid}_user_report.txt")
        report_output_file = os.path.join(output_dir, f"{pid}_report_output.json")
        convert_to_vector(report_file, report_output_file)
        print(f"Processed participant {pid}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python process_all_states_and_reports.py <load_dir> <outputdir>")
        sys.exit(1)

    load_dir = sys.argv[1]
    output_dir = sys.argv[2]
    print(f"Loading from {load_dir} and saving to {output_dir}")
    main(load_dir, output_dir)