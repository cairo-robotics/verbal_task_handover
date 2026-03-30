import json
import argparse
import os
import re
from pathlib import Path


def _normalize_value(value: str) -> str:
    """
    Ontology-style normalization to make matching robust across sources.

    Mirrors `narrative_view_to_fact_extraction._normalize_value`:
    - lowercase
    - spaces -> underscores
    - collapse non [a-z0-9_] to underscores
    - collapse repeated underscores
    - strip underscores
    """
    s = value.strip().lower().replace(" ", "_")
    s = re.sub(r"[^a-z0-9_]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s

def load_facts(path: str) -> list[dict]:
    """
    Load facts from either:
      - FactExtraction JSON: {"facts": [ {type: ...}, ... ]}
      - A raw list of fact dicts: [ {type: ...}, ... ]
    """
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Primary schema from state_ontology.FactExtraction
    if isinstance(data, dict) and "facts" in data:
        facts = data["facts"]
        if not isinstance(facts, list):
            raise ValueError(f'Invalid "facts" value in {path}: expected list, got {type(facts)}')
        return facts

    # Back-compat for older format
    if isinstance(data, list):
        return data

    raise ValueError(
        f"Unrecognized facts JSON shape in {path}: "
        f"expected {{'facts': [...]}} or a list, got {type(data)}"
    )

def canonicalize_fact(fact: dict) -> tuple:
    """
    Convert a fact dict into a hashable canonical representation.
    """
    if not isinstance(fact, dict):
        raise TypeError(f"Each fact must be a dict; got {type(fact)}")

    fact_type = str(fact["type"]).strip()
    
    # Sort attributes to ensure consistency
    attributes = tuple(sorted(
        (k.lower(), _canonicalize_value_for_match(v))
        for k, v in fact.items()
        if k != "type"
    ))
    
    return (fact_type, attributes)

def _canonicalize_value_for_match(v) -> str:
    # For our ontology v is almost always str, but keep it defensive.
    if isinstance(v, str):
        return _normalize_value(v)
    return json.dumps(v, sort_keys=True).lower()

def facts_to_set(facts: list[dict]) -> set:
    return {canonicalize_fact(f) for f in facts}

def canonical_tuple_to_dict(canonical_fact: tuple) -> dict:
    fact_type, attributes = canonical_fact
    fact = {"type": fact_type}
    for k, v in attributes:
        fact[k] = v
    return fact

def compute_precision_recall(pred_facts: list[dict], gold_facts: list[dict]):
    pred_set = facts_to_set(pred_facts)
    gold_set = facts_to_set(gold_facts)
    
    true_positives = pred_set & gold_set
    false_positives = pred_set - gold_set
    false_negatives = gold_set - pred_set
    
    precision = len(true_positives) / len(pred_set) if pred_set else 0.0
    recall = len(true_positives) / len(gold_set) if gold_set else 0.0
    
    return {
        "precision": precision,
        "recall": recall,
        "true_positives": len(true_positives),
        "false_positives": len(false_positives),
        "false_negatives": len(false_negatives),
    }

def add_f1(metrics: dict):
    p = metrics["precision"]
    r = metrics["recall"]
    
    if p + r == 0:
        metrics["f1"] = 0.0
    else:
        metrics["f1"] = 2 * (p * r) / (p + r)
    
    return metrics

def inspect_errors(pred_facts, gold_facts):
    pred_set = facts_to_set(pred_facts)
    gold_set = facts_to_set(gold_facts)
    
    print("\nFalse Positives (hallucinations):")
    for f in pred_set - gold_set:
        print(f)
    
    print("\nFalse Negatives (missed facts):")
    for f in gold_set - pred_set:
        print(f)

def error_breakdown(pred_facts: list[dict], gold_facts: list[dict]) -> dict:
    pred_set = facts_to_set(pred_facts)
    gold_set = facts_to_set(gold_facts)
    false_positives = sorted(pred_set - gold_set)
    false_negatives = sorted(gold_set - pred_set)
    return {
        "false_positives": [canonical_tuple_to_dict(f) for f in false_positives],
        "false_negatives": [canonical_tuple_to_dict(f) for f in false_negatives],
    }

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compute precision, recall, and F1 score for fact extraction."
    )
    parser.add_argument("pred_path", help="Path to predicted facts JSON file.")
    parser.add_argument("gt_path", help="Path to ground-truth facts JSON file.")
    parser.add_argument(
        "--output-path",
        default=None,
        help=(
            "Path to write JSON metrics output. Defaults to "
            "$DATA_DIR/analysis/{pred_path filename}_pr.json"
        ),
    )
    args = parser.parse_args()

    def resolve_path(p: str) -> str:
        # If user passed an existing path, trust it.
        if os.path.isabs(p) and os.path.exists(p):
            return p
        if os.path.exists(p):
            return p

        data_dir = os.environ.get("DATA_DIR")
        if data_dir:
            candidate = os.path.join(data_dir, "analysis", p)
            if os.path.exists(candidate):
                return candidate

        # Fall back to the original behavior (may raise FileNotFound later)
        if os.environ.get("DATA_DIR"):
            return os.path.join(os.environ["DATA_DIR"], "analysis", p)
        return p

    pred_path = resolve_path(args.pred_path)
    gt_path = resolve_path(args.gt_path)
    
    pred_facts = load_facts(pred_path)
    gold_facts = load_facts(gt_path)
    metrics = compute_precision_recall(pred_facts, gold_facts)

    metrics = add_f1(metrics)
    print(json.dumps(metrics, indent=2))
    inspect_errors(pred_facts, gold_facts)

    output_payload = {
        "pred_path": pred_path,
        "gt_path": gt_path,
        "metrics": metrics,
        "errors": error_breakdown(pred_facts, gold_facts),
    }

    if args.output_path:
        output_path = args.output_path
    else:
        data_dir = os.environ.get("DATA_DIR")
        if not data_dir:
            raise ValueError(
                "DATA_DIR must be set when --output-path is not provided."
            )
        pred_filename = Path(pred_path).name
        output_path = os.path.join(data_dir, "analysis", f"{pred_filename.replace(".json", "")}_pr.json")
        print(output_path)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_payload, f, indent=2)

    print(f"\nDetailed metrics output written to: {output_path}")

if __name__ == "__main__":
    main()
