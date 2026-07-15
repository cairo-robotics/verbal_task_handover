import os
import json
import csv
import glob
import argparse
from token_count import TokenCount

# Default base directory (used when no arguments are supplied)
DEFAULT_BASE_DIR = "/media/kaleb/T7/handover_project/participant_data/analysis/metrics_output/"

CONDITIONS = ["no_report_full_realization", "no_report_task_aware", "full_realization", "task_aware", "user_report", "task_aware_raw_ablation"]


def parse_filename(filename, suffix):
    """
    Parses pid, condition, and optional model from filename.
    Expected formats:
      [pid]_[condition]_[model][suffix]
      [pid]_[condition][suffix]
    Examples:
      501_full_realization_gpt_iac.json
      501_full_realization_iac.json
    """
    name = filename.replace(suffix, "")
    
    # Check for model suffix
    model = None
    for m in ["gpt", "claude", "gemini"]:
        if name.endswith(f"_{m}"):
            model = m
            name = name[:-(len(m) + 1)]
            break
            
    for cond in CONDITIONS:
        if name.endswith(cond):
            pid = name[:-(len(cond) + 1)]
            return pid, cond, model
    return None, None, None


def process_iac(file_path):
    """Extracts IAC summary and categorical metrics."""
    with open(file_path, "r") as f:
        data = json.load(f)

    metrics = {
        "iac_cost_saved": data.get("total_cost_saved", 0),
        "iac_omission_cost": data.get("omission_cost", 0),
        "iac_misinformation_cost": data.get("misinformation_cost", 0),
        "iac_combined_cost": data.get("combined_cost", 0),
        "soft_precision": data.get("soft_precision", 0.0),
        "soft_recall": data.get("soft_recall", 0.0),
        "soft_f1": data.get("soft_f1", 0.0),
        "misinformation_count": data.get("misinformation_count", 0),
    }

    # Aggregate categorical savings
    loc_savings = 0
    need_savings = 0
    res_savings = 0

    entity_scores = data.get("entity_scores", {})
    for entity, scores in entity_scores.items():
        loc_savings += scores.get("location_score", {}).get("cost_saved", 0)
        need_savings += scores.get("need_score", {}).get("cost_saved", 0)
        res_savings += scores.get("resource_score", {}).get("cost_saved", 0)

    metrics["iac_location_savings"] = loc_savings
    metrics["iac_need_savings"] = need_savings
    metrics["iac_resource_savings"] = res_savings

    return metrics


def process_pr(file_path):
    """Extracts Precision, Recall, and F1 metrics."""
    with open(file_path, "r") as f:
        data = json.load(f)

    m = data.get("metrics", {})
    return {
        "precision": m.get("precision"),
        "recall": m.get("recall"),
        "f1": m.get("f1"),
        "tp": m.get("true_positives"),
        "fp": m.get("false_positives"),
        "fn": m.get("false_negatives"),
    }


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Aggregate IAC and Precision-Recall metrics from one or more "
            "experiment output directories into a single CSV file."
        )
    )
    parser.add_argument(
        "dirs",
        nargs="*",
        default=[DEFAULT_BASE_DIR],
        metavar="DIR",
        help=(
            "One or more base metric output directories "
            "(each must contain 'iac/' and 'precision_recall/' sub-directories). "
            f"Defaults to: {DEFAULT_BASE_DIR}"
        ),
    )
    parser.add_argument(
        "--output",
        default=None,
        metavar="CSV_PATH",
        help=(
            "Path for the output CSV file. "
            "Defaults to 'aggregated_metrics.csv' inside the first supplied directory."
        ),
    )
    args = parser.parse_args()

    base_dirs = args.dirs
    output_csv = args.output or os.path.join(base_dirs[0], "aggregated_metrics.csv")

    rows = {}  # Key: (pid, condition) -> Value: metrics_dict

    for base_dir in base_dirs:
        iac_dir = os.path.join(base_dir, "iac")
        pr_dir = os.path.join(base_dir, "precision_recall")

        # 1. Process IAC files
        if os.path.exists(iac_dir):
            iac_files = glob.glob(os.path.join(iac_dir, "*_iac.json"))
            print(f"[{base_dir}] Found {len(iac_files)} IAC files.")
            for fpath in iac_files:
                fname = os.path.basename(fpath)
                pid, cond, model = parse_filename(fname, "_iac.json")
                if not pid:
                    print(f"  Warning: Could not parse PID/Condition from {fname}")
                    continue

                model = model or ("human" if cond == "user_report" else "gpt")
                metrics = process_iac(fpath)
                key = (pid, cond, model)
                if key not in rows:
                    rows[key] = {"participant_id": pid, "condition": cond, "model": model}
                rows[key].update(metrics)
        else:
            print(f"  IAC directory not found: {iac_dir}")

        # 2. Process PR files
        if os.path.exists(pr_dir):
            pr_files = glob.glob(os.path.join(pr_dir, "*_pr.json"))
            print(f"[{base_dir}] Found {len(pr_files)} Precision-Recall files.")
            for fpath in pr_files:
                fname = os.path.basename(fpath)
                pid, cond, model = parse_filename(fname, "_pr.json")
                if not pid:
                    # Try fallback parsing if suffix is missing
                    pid, cond, model = parse_filename(fname, ".json")
                    if not pid:
                        print(f"  Warning: Could not parse PID/Condition from {fname}")
                        continue

                model = model or ("human" if cond == "user_report" else "gpt")
                metrics = process_pr(fpath)
                key = (pid, cond, model)
                if key not in rows:
                    rows[key] = {"participant_id": pid, "condition": cond, "model": model}
                rows[key].update(metrics)
        else:
            print(f"  Precision-Recall directory not found: {pr_dir}")

    if not rows:
        print("No metrics found to aggregate.")
        return

    # Derive kg_dirs and reports_dirs from base_dirs
    kg_dirs = [os.path.normpath(os.path.join(b, "..", "..", "processed_output", "kg")) for b in base_dirs]
    kg_dirs = list(set(kg_dirs))
    
    reports_dirs = [os.path.normpath(os.path.join(b, "..", "..", "reports")) for b in base_dirs]
    reports_dirs = list(set(reports_dirs))
    
    tk = TokenCount(model_name="gpt-4o-mini")

    # 2.5 Process Raw IAC files and Token Counts
    for row_data in rows.values():
        pid = row_data["participant_id"]
        cond = row_data["condition"]
        
        # Token Count
        row_data["token_count"] = 0
        report_filename = f"{pid}_{cond}.txt" if cond == "user_report" else f"{pid}_{cond}_report.txt"
        
        for reports_dir in reports_dirs:
            report_path = os.path.join(reports_dir, report_filename)
            if os.path.exists(report_path):
                with open(report_path, "r", encoding="utf-8") as rf:
                    content = rf.read()
                    row_data["token_count"] = tk.num_tokens_from_string(content)
                break
                
        # Raw IAC
        # for kg_dir in kg_dirs:
        #     raw_iac_path = os.path.join(kg_dir, f"{pid}_raw_iac.json")
        #     if os.path.exists(raw_iac_path):
        #         raw_metrics = process_iac(raw_iac_path)
        #         for k, v in raw_metrics.items():
        #             row_data[f"raw_{k}"] = v
        #         break

    # 3. Sort data
    all_data = sorted(rows.values(), key=lambda x: (x["participant_id"], x["condition"], x.get("model", "")))

    # 4. Define column order
    cols = [
        "participant_id", "condition", "model", "token_count", "precision", "recall", "f1", "tp", "fp", "fn",
        "soft_precision", "soft_recall", "soft_f1", "misinformation_count",
        "iac_cost_saved", "iac_omission_cost", "iac_misinformation_cost", "iac_combined_cost",
        "iac_location_savings", "iac_need_savings", "iac_resource_savings",
        # "raw_iac_cost_saved", "raw_iac_omission_cost", "raw_iac_misinformation_cost", "raw_iac_combined_cost",
        # "raw_iac_location_savings", "raw_iac_need_savings", "raw_iac_resource_savings",
    ]

    # 5. Save to CSV
    os.makedirs(os.path.dirname(os.path.abspath(output_csv)), exist_ok=True)
    with open(output_csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(all_data)

    print(f"\nSuccessfully aggregated metrics into {output_csv}")
    print(f"Total rows: {len(all_data)}")


if __name__ == "__main__":
    main()
