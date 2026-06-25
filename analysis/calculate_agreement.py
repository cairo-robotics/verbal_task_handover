import argparse
import os
import csv
from sklearn.metrics import cohen_kappa_score

DEFAULT_CSV_PATH = "/media/kaleb/T7/handover_project/participant_data/analysis/content_categorization/clauses_for_annotation.csv"

def main():
    import dotenv
    dotenv.load_dotenv()

    parser = argparse.ArgumentParser(
        description="Calculate inter-rater agreement (Cohen's Kappa and category-specific metrics) "
                    "between LLM categories and human annotations."
    )
    parser.add_argument(
        "csv_path",
        nargs="?",
        default=DEFAULT_CSV_PATH,
        help=f"Path to the annotated CSV file. Defaults to: $DATA_DIR/analysis/content_categorization/clauses_for_annotation.csv"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Run the script with synthetic test data to verify calculations."
    )

    args = parser.parse_args()
    
    y_llm = []
    y_human = []
    raw_rows = []
    csv_path = args.csv_path

    if args.test:
        # Generate synthetic test data with some agreement and disagreement
        # S: 20 rows (15 agree, 3 S-K, 2 S-A)
        # K: 15 rows (10 agree, 3 K-S, 2 K-M)
        # A: 10 rows (5 agree, 3 A-S, 2 A-K)
        # M: 5 rows (4 agree, 1 M-A)
        test_data = (
            [("S", "S")] * 15 + [("S", "K")] * 3 + [("S", "A")] * 2 +
            [("K", "K")] * 10 + [("K", "S")] * 3 + [("K", "M")] * 2 +
            [("A", "A")] * 5 + [("A", "S")] * 3 + [("A", "K")] * 2 +
            [("M", "M")] * 4 + [("M", "A")] * 1
        )
        for llm_cat, human_cat in test_data:
            y_llm.append(llm_cat)
            y_human.append(human_cat)
            raw_rows.append((llm_cat, human_cat))
        csv_path = "SYNTHETIC_TEST_DATA"
    else:
        if csv_path == DEFAULT_CSV_PATH:
            data_dir = os.environ.get("DATA_DIR")
            if data_dir:
                csv_path = os.path.join(data_dir, "analysis/content_categorization/clauses_for_annotation.csv")

        if not os.path.exists(csv_path):
            print(f"Error: CSV file '{csv_path}' does not exist.")
            return

        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                llm_cat = row.get("category", "").strip().upper()
                human_cat = row.get("annotation_category", "").strip().upper()
                
                # Skip rows where human has not annotated yet
                if not human_cat:
                    continue

                y_llm.append(llm_cat)
                y_human.append(human_cat)
                raw_rows.append((llm_cat, human_cat))

    n_samples = len(y_llm)
    if n_samples == 0:
        print("Error: No annotated rows found where 'annotation_category' is non-empty.")
        return

    print("=" * 88)
    print(f"Loaded {n_samples} annotated clauses from {csv_path}")
    print("=" * 88)

    # Compute overall Cohen's Kappa
    overall_kappa = cohen_kappa_score(y_llm, y_human)
    print(f"Overall Cohen's Kappa: {overall_kappa:.4f}")
    print("-" * 88)

    # Compute agreement for each category
    labels = ["S", "K", "A", "M"]
    label_full_names = {
        "S": "State Transfer (S)",
        "K": "Knowledge Transfer (K)",
        "A": "Ambiguous/Mixed (A)",
        "M": "Meta/Other (M)"
    }

    print(f"{'Category':<25} | {'N_LLM':<6} | {'N_Human':<7} | {'Agree':<5} | {'Specific Agreement (F1)':<23} | {'Binary Kappa':<12}")
    print("-" * 88)

    for label in labels:
        # Calculate counts
        n_llm = sum(1 for y in y_llm if y == label)
        n_human = sum(1 for y in y_human if y == label)
        agreed = sum(1 for y_l, y_h in raw_rows if y_l == label and y_h == label)
        
        # 1. Specific Agreement (Dice Coefficient / F1-equivalent): 2 * agreed / (n_llm + n_human)
        if n_llm + n_human > 0:
            specific_agreement = (2.0 * agreed) / (n_llm + n_human)
        else:
            specific_agreement = 0.0

        # 2. Binary Kappa (treating this category vs all others combined)
        y_llm_binary = [1 if y == label else 0 for y in y_llm]
        y_human_binary = [1 if y == label else 0 for y in y_human]
        binary_kappa = cohen_kappa_score(y_llm_binary, y_human_binary)

        print(f"{label_full_names[label]:<25} | {n_llm:<6} | {n_human:<7} | {agreed:<5} | {specific_agreement:<23.4f} | {binary_kappa:<12.4f}")

    print("=" * 88)

if __name__ == "__main__":
    main()
