import json
import argparse

def load_facts(path: str) -> list[dict]:
    with open(path, "r") as f:
        return json.load(f)

def canonicalize_fact(fact: dict) -> tuple:
    """
    Convert a fact dict into a hashable canonical representation.
    """
    fact_type = fact["type"]
    
    # Sort attributes to ensure consistency
    attributes = tuple(sorted(
        (k.lower(), json.dumps(v, sort_keys=True).lower())
        for k, v in fact.items()
        if k != "type"
    ))
    
    return (fact_type, attributes)

def facts_to_set(facts: list[dict]) -> set:
    return {canonicalize_fact(f) for f in facts}

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

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compute precision, recall, and F1 score for fact extraction."
    )
    parser.add_argument("pred_facts", help="Path to predicted facts JSON file.")
    parser.add_argument("gold_facts", help="Path to ground-truth facts JSON file.")
    args = parser.parse_args()
    
    pred_facts = load_facts(args.pred_facts)
    gold_facts = load_facts(args.gold_facts)
    metrics = compute_precision_recall(pred_facts, gold_facts)

    metrics = add_f1(metrics)
    print(json.dumps(metrics, indent=2))
    inspect_errors(pred_facts, gold_facts)