import os
import dotenv
dotenv.load_dotenv()

from report_to_vector import convert_to_vector

def main():
    data_dir = os.environ.get("DATA_DIR")
    input_dir = os.path.join(data_dir, "reports")
    output_dir = os.path.join(data_dir, "processed_output")

    # for filename in os.listdir(input_dir):
    # for pid in range(501, 510):
    for pid in ["ari_test", "himanshu_test", "shiv_test", "ys_pilot"]:
        pid = str(pid)
        # for suffix in ["user", "generated", "hybrid"]:
        for suffix in ["hybrid"]:
            filename = f"{pid}_{suffix}_report.txt"
            text_filename = os.path.join(input_dir, filename)
            output_filename = os.path.join(output_dir, filename.replace(".txt", "_output.json"))
            print(f"Converting {text_filename} to vector format...")
            convert_to_vector(text_filename, output_filename)

if __name__ == "__main__":
    main()