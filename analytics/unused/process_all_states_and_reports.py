import os
import sys
from analytics.save_to_vector import output_ground_truth
from analytics.report_to_vector import convert_to_vector

PARTICIPANTS = list(range(501, 510, 1))  # Example participant IDs from 501 to 509

def main(load_dir, output_dir):
    for pid in PARTICIPANTS:
        save_file = os.path.join(load_dir, f"{pid}")
        save_output_file = os.path.join(output_dir, f"{pid}_save_output.json")
        output_ground_truth(save_file, save_output_file)

        # report_file = os.path.join(load_dir, f"{pid}_user_report.txt")
        # report_output_file = os.path.join(output_dir, f"{pid}_report_output.json")
        # convert_to_vector(report_file, report_output_file)
        print(f"Processed participant {pid}")

if __name__ == "__main__":

    data_dir = os.environ.get("DATA_DIR", ".")
    load_dir = os.path.join(data_dir, "participant_data")
    output_dir = os.path.join(data_dir, "processed_output")
    print(f"Loading from {load_dir} and saving to {output_dir}")
    main(load_dir, output_dir)