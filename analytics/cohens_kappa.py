import json
import os

from sklearn.metrics import cohen_kappa_score

def load_annotations(file_path):
    with open(file_path, 'r') as file:
        return json.load(file)
    

def flatten_annotations(annotations1, annotations2):
    """
    Extracts matching True/False values across both annotation dicts.
    Returns two equal-length lists for rater1 and rater2.
    """
    y1, y2 = [], []
    for patient in sorted(annotations1.keys()):
        if patient not in annotations2:
            continue
        for key in sorted(annotations1[patient].keys()):
            if key not in annotations2[patient]:
                continue
            y1.append(bool(annotations1[patient][key]))
            y2.append(bool(annotations2[patient][key]))
    return y1, y2

def compute_per_participant_and_global_kappa(folder, reviewer1_prefix="reviewer1_", reviewer2_prefix="reviewer2_"):
    results = []
    y1_all, y2_all = [], []
    
    reviewer1_files = sorted(glob.glob(os.path.join(folder, f"{reviewer1_prefix}*.json")))

    for f1 in reviewer1_files:
        base = os.path.basename(f1).replace(reviewer1_prefix, "")
        f2 = os.path.join(folder, reviewer2_prefix + base)
        if not os.path.exists(f2):
            print(f"⚠️ Missing match for {f1}, skipping.")
            continue

        ann1 = load_annotations(f1)
        ann2 = load_annotations(f2)
        y1, y2 = flatten_annotations(ann1, ann2)

        if not y1:
            print(f"⚠️ No overlapping keys found for {base}, skipping.")
            continue

        kappa = cohen_kappa_score(y1, y2)
        results.append({"participant": base, "kappa": kappa, "n_items": len(y1)})

        # Add to global pool
        y1_all.extend(y1)
        y2_all.extend(y2)

    # Compute global kappa
    global_kappa = cohen_kappa_score(y1_all, y2_all) if y1_all else None
    results.append({"participant": "GLOBAL", "kappa": global_kappa, "n_items": len(y1_all)})

    return results

def save_results_to_csv(results, output_file="kappa_results.csv"):
    with open(output_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["participant", "kappa", "n_items"])
        writer.writeheader()
        for row in results:
            writer.writerow(row)

if __name__ == "__main__":
    folder = "annotations"  # folder containing all JSON files
    results = compute_per_participant_and_global_kappa(folder)
    save_results_to_csv(results)
    print("✅ Saved results to kappa_results.csv")
    for r in results:
        print(f"{r['participant']}: kappa={r['kappa']:.3f} (N={r['n_items']})")