#!/usr/bin/env python3
"""
Standalone step: load a merged knowledge graph JSON, reconcile declarative
relation facts (e.g. mark needs as satisfied when a corresponding delivery fact
exists), and write the result to a new JSON file.

Run after merge_graphs. Does not import or depend on merge_graphs.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import dotenv

from src.core.representations.pydantic_schema import (
    Argument,
    KnowledgeGraph,
    RelationFact,
    RelationPredicate,
)

dotenv.load_dotenv()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _relation_facts(graph: KnowledgeGraph) -> list[RelationFact]:
    """Return only the RelationFact entries from the graph's fact list."""
    return [f for f in graph.facts if isinstance(f, RelationFact)]


def _args_match(a: Argument | None, b: Argument | None) -> bool:
    """Return True if two Arguments refer to the same entity (by value)."""
    if a is None or b is None:
        return False
    return a.type == b.type and a.value == b.value


# ---------------------------------------------------------------------------
# Reconciliation rules
# ---------------------------------------------------------------------------

_NEED_TO_DELIVERY: dict[RelationPredicate, RelationPredicate] = {
    RelationPredicate.NEEDS_POTION: RelationPredicate.POTION_DELIVERED,
    RelationPredicate.HAS_MESSAGE_FOR: RelationPredicate.MESSAGE_DELIVERED,
    RelationPredicate.HAS_RESPONSE_FOR: RelationPredicate.RESPONSE_DELIVERED,
}


def _find_matching_delivery(
    need: RelationFact,
    delivery_predicate: RelationPredicate,
    relation_facts: list[RelationFact],
) -> RelationFact | None:
    """Return the first delivery fact that satisfies *need*, or None."""
    for fact in relation_facts:
        if fact.predicate != delivery_predicate:
            continue
        if _args_match(fact.subject, need.subject) and _args_match(fact.target, need.target):
            return fact
    return None


def reconcile_state(graph: KnowledgeGraph) -> KnowledgeGraph:
    """
    Reconcile declarative relation facts in *graph*.

    For each 'need' predicate (NEEDS_POTION, HAS_MESSAGE_FOR, HAS_RESPONSE_FOR),
    check whether a corresponding delivery fact exists for the same subject/target
    pair.  If so, remove the need fact so the graph only retains outstanding needs.

    Also reconciles HAS_ITEM: if an item appears in both a HAS_ITEM fact and a
    POTION_DELIVERED fact (subject of HAS_ITEM matches object of delivery),
    the HAS_ITEM fact is considered consumed and removed.

    Returns a new KnowledgeGraph with the reconciled fact list.
    """
    rel_facts = _relation_facts(graph)
    facts_to_remove: set[str] = set()

    # --- Resolve needs against deliveries ---
    for need in rel_facts:
        delivery_predicate = _NEED_TO_DELIVERY.get(need.predicate)
        if delivery_predicate is None:
            continue
        if _find_matching_delivery(need, delivery_predicate, rel_facts) is not None:
            facts_to_remove.add(need.id)

    # --- Resolve HAS_ITEM against POTION_DELIVERED ---
    delivered_objects = {
        f.object.value
        for f in rel_facts
        if f.predicate == RelationPredicate.POTION_DELIVERED and f.object is not None
    }
    for fact in rel_facts:
        if (
            fact.predicate == RelationPredicate.HAS_ITEM
            and fact.object is not None
            and fact.object.value in delivered_objects
        ):
            facts_to_remove.add(fact.id)

    reconciled_facts = [f for f in graph.facts if getattr(f, "id", None) not in facts_to_remove]

    return KnowledgeGraph(facts=reconciled_facts)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Read merged graph JSON, reconcile relation facts, "
            "write JSON to a new file."
        )
    )
    parser.add_argument(
        "pid",
        nargs="?",
        metavar="PID",
        help=(
            "Participant id: reads DATA_DIR/processed_output/<pid>_merge_graphs_output.json "
            "and writes <pid>_reconcile_state_output.json (requires DATA_DIR)."
        ),
    )
    parser.add_argument(
        "-i",
        "--input",
        metavar="PATH",
        help="Path to merge_graphs JSON output (overrides pid-based paths).",
    )
    parser.add_argument(
        "-o",
        "--output",
        metavar="PATH",
        help="Path to write reconciled graph JSON (overrides pid-based paths).",
    )
    args = parser.parse_args()

    if args.input is not None and args.output is not None:
        in_path = args.input
        out_path = args.output
    elif args.pid is not None:
        data_dir = os.environ.get("DATA_DIR")
        if not data_dir:
            parser.error("Set DATA_DIR or pass both --input and --output.")
        in_path = os.path.join(
            data_dir, "processed_output", f"{args.pid}_merge_graphs_output.json"
        )
        out_path = os.path.join(
            data_dir, "processed_output", f"{args.pid}_reconcile_state_output.json"
        )
    else:
        parser.error("Provide a participant PID or both --input and --output.")

    with open(in_path, "r", encoding="utf-8") as f:
        graph = KnowledgeGraph.model_validate_json(f.read())

    reconciled = reconcile_state(graph)

    out_dir = os.path.dirname(out_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(reconciled.model_dump(), f, indent=2)


if __name__ == "__main__":
    main()
