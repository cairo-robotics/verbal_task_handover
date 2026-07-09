import json
import argparse
import os
import re
from pathlib import Path
from typing import Any, Union

from src.core.representations.pydantic_schema import KnowledgeGraph, Fact, RelationFact, LocationFact, SpatialFact, ConnectionFact


from src.core.utils.normalization import normalize_entity_name


def _normalize_value(value: str) -> str:
    """
    Robust normalization to make matching robust across sources.
    Lowercase, removes spaces/underscores/hyphens.
    """
    return normalize_entity_name(value)

def load_facts(path: str) -> list[Fact]:
    """
    Load facts from a JSON file and validate against the KnowledgeGraph schema.
    """
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # If it's a dict with "facts", validate as KnowledgeGraph
    if isinstance(data, dict) and "facts" in data:
        return KnowledgeGraph.model_validate(data).facts

    # If it's a raw list of facts, wrap it and validate
    if isinstance(data, list):
        return KnowledgeGraph.model_validate({"facts": data}).facts

    raise ValueError(
        f"Unrecognized facts JSON shape in {path}: "
        f"expected {{'facts': [...]}} or a list, got {type(data)}"
    )

def canonicalize_fact(fact: Fact) -> tuple:
    """
    Convert a Fact Pydantic model into a hashable canonical representation.
    Exclude metadata like id and provenance.
    """
    # Use class name as an extra differentiator for fact types
    fact_type = fact.__class__.__name__
    
    # Convert to dict and exclude metadata
    data = fact.model_dump(exclude={"id", "provenance", "source"})
    
    # Recursively canonicalize the dictionary
    attributes = _canonicalize_item(data)
    
    return (fact_type, attributes)

def _canonicalize_item(item: Any) -> Any:
    """
    Recursively canonicalize nested structures.
    """
    if isinstance(item, dict):
        # Sort and filter nulls to ensure consistency
        return tuple(sorted(
            (k.lower(), _canonicalize_item(v))
            for k, v in item.items()
            if v is not None
        ))
    elif isinstance(item, list):
        return tuple(_canonicalize_item(x) for x in item)
    elif isinstance(item, str):
        return _normalize_value(item)
    elif item is None:
        return None
    else:
        return item

def facts_to_set(facts: list[Fact]) -> set:
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

def error_breakdown(pred_facts: list[Fact], gold_facts: list[Fact]) -> dict:
    pred_set = facts_to_set(pred_facts)
    gold_set = facts_to_set(gold_facts)
    
    # Map back from canonical tuple to a serializable format
    # Since we can't easily reverse the normalization and Pydantic dump,
    # we just return the tuples or a simplified dict for inspection.
    def tuple_to_reportable(t):
        if not isinstance(t, tuple):
            return t
        if len(t) == 2 and isinstance(t[1], tuple):
            # This looks like (fact_type, attributes_tuple)
            fact_type, attrs = t
            try:
                return {"fact_type": fact_type, "attributes": {k: tuple_to_reportable(v) for k, v in attrs}}
            except (ValueError, TypeError):
                # Not a dict-like structure after all
                pass
        return [tuple_to_reportable(x) for x in t]

    false_positives = sorted(pred_set - gold_set)
    false_negatives = sorted(gold_set - pred_set)
    
    return {
        "false_positives": [tuple_to_reportable(f) for f in false_positives],
        "false_negatives": [tuple_to_reportable(f) for f in false_negatives],
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

    # Exclude ConnectionFacts from evaluation as they are often omitted from narrative reports
    pred_facts = [f for f in pred_facts if not isinstance(f, ConnectionFact)]
    gold_facts = [f for f in gold_facts if not isinstance(f, ConnectionFact)]
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
