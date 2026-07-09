import argparse
import os
import glob
import json
import csv

from token_count import TokenCount

DEFAULT_DIR = "/media/kaleb/T7/handover_project/participant_data/analysis/content_categorization/"

def parse_filename(filename, suffix):
    """
    Parses pid and condition from filename.
    Expected format: [pid][suffix]
    Example: 501_categorization.json
    """
    name = filename.replace(suffix, "")
    pid = name
    return pid

def process_categorization(file_path):

    tk = TokenCount(model_name="gpt-4o-mini")
    with open(file_path, "r") as f:
        data = json.load(f)

    metrics = {category: 0 for category in ["S", "K", "A", "M"]}
    # process content categorization
    for clause in data["clauses"]:
        metrics[clause["label"]] += tk.num_tokens_from_string(clause["text"])
    
    return metrics

def main():
    import dotenv
    dotenv.load_dotenv()

    parser = argparse.ArgumentParser(
        description="Aggregate the content categorization output of the user reports."
    )
    parser.add_argument(
        "dirs",
        nargs="*",
        default=[DEFAULT_DIR],
        metavar="DIRS",
        help=(
            "One or more content categorization directories"
            f"Defaults to: $DATA_DIR/{DEFAULT_DIR}"
        ),
    )

    args = parser.parse_args()
    if args.dirs == [DEFAULT_DIR]:
        args.dirs = [os.path.join(os.environ.get("DATA_DIR"), DEFAULT_DIR)]

    rows = {}

    for d in args.dirs:
        if not os.path.exists(d):
            print(f"Directory {d} does not exist. Skipping...")
            continue

        files = glob.glob(os.path.join(d, "*_categorization.json"))
        print(f"[{d}] Found {len(files)} content categorization files.")
        
        for fpath in files:
            fname = os.path.basename(fpath)
            pid = parse_filename(fname, "_categorization.json")

            metrics = process_categorization(fpath)

            if pid not in rows:
                rows[pid] = {"participant_id": pid}
            rows[pid].update(metrics)
        
    all_data = sorted(rows.values(), key=lambda x: x["participant_id"])
    
    cols = [
        "participant_id", "S", "K", "A", "M"
    ]
    full_labels = [
        "participant_id", "state", "knowledge", "ambiguous", "meta"
    ]

    output_csv = os.path.join(args.dirs[0], "aggregated_content_categorization.csv")
    with open(output_csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        # writer.writeheader()
        writer.writerow(dict(zip(cols, full_labels)))
        writer.writerows(all_data)

    print(f"\nSuccessfully aggregated metrics into {output_csv}")
    print(f"Total rows: {len(all_data)}")
    print(all_data)
            

if __name__ == "__main__":
    main()
