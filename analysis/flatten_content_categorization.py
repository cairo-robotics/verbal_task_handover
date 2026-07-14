import argparse
import os
import glob
import json
import csv

DEFAULT_DIR = "/media/kaleb/T7/handover_project/participant_data/analysis/content_categorization/"

def parse_filename(filename, suffix):
    """
    Parses pid from filename.
    Expected format: [pid][suffix]
    Example: 501_categorization.json
    """
    name = filename.replace(suffix, "")
    pid = name
    return pid

def process_categorization(file_path, pid):
    """
    Reads the content categorization JSON and returns a list of rows,
    where each row is a dict containing participant_id, clause, category, and justification.
    """
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    rows = []
    for clause in data.get("clauses", []):
        rows.append({
            "participant_id": pid,
            "clause": clause.get("text", ""),
            "category": clause.get("label", ""),
            "justification": clause.get("justification", "")
        })
    return rows

def main():
    import dotenv
    dotenv.load_dotenv()

    parser = argparse.ArgumentParser(
        description="Flatten the content categorization JSON files into a single CSV."
    )
    parser.add_argument(
        "dirs",
        nargs="*",
        default=[DEFAULT_DIR],
        metavar="DIRS",
        help=(
            "One or more content categorization directories. "
            f"Defaults to: $DATA_DIR/{DEFAULT_DIR}"
        ),
    )
    parser.add_argument(
        "--output",
        "-o",
        help="Path to the output CSV file. Defaults to 'clauses_for_annotation.csv' in the first input directory."
    )

    args = parser.parse_args()
    if args.dirs == [DEFAULT_DIR]:
        data_dir = os.environ.get("DATA_DIR")
        if data_dir:
            args.dirs = [os.path.join(data_dir, "analysis/content_categorization/")]
        else:
            args.dirs = [DEFAULT_DIR]

    all_rows = []

    for d in args.dirs:
        if not os.path.exists(d):
            print(f"Directory {d} does not exist. Skipping...")
            continue

        files = glob.glob(os.path.join(d, "*_categorization.json"))
        print(f"[{d}] Found {len(files)} content categorization files.")
        
        # Sort files by PID so the final output CSV is grouped and sorted by participant_id
        sorted_files = []
        for fpath in files:
            fname = os.path.basename(fpath)
            pid = parse_filename(fname, "_categorization.json")
            sorted_files.append((pid, fpath))
        
        # Sort by PID
        sorted_files.sort(key=lambda x: x[0])

        for pid, fpath in sorted_files:
            clauses = process_categorization(fpath, pid)
            all_rows.extend(clauses)

    if not all_rows:
        print("No clauses found. Exiting.")
        return

    cols = ["participant_id", "clause", "category", "justification"]

    if args.output:
        output_csv = args.output
    else:
        output_csv = os.path.join(args.dirs[0], "clauses_for_annotation.csv")

    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"\nSuccessfully exported clauses into {output_csv}")
    print(f"Total rows (clauses): {len(all_rows)}")

if __name__ == "__main__":
    main()
