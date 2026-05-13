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
from src.core.utils.spatial_reasoning import get_entity_location, is_location_satisfying_constraint

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


def _args_align(a: Argument | None, b: Argument | None, graph: KnowledgeGraph) -> bool:
    """Return True if two Arguments refer to the same entity, possibly via existential resolution."""
    if a is None or b is None:
        return False

    # 1. Direct value match
    if a.type == "named" and b.type == "named":
        return a.value == b.value

    # 2. Both existential
    if a.type == "existential" and b.type == "existential":
        if not a.location and not b.location:
            return True
        if a.location and b.location:
            return a.location.model_dump() == b.location.model_dump()
        return False  # One has location, other doesn't? Let's be conservative.

    # 3. One named, one existential
    named_arg = a if a.type == "named" else b
    existential_arg = b if a.type == "named" else a

    if not existential_arg.location:
        return True  # Existential with no constraint matches any named entity

    # Must satisfy location constraint
    ent_loc = get_entity_location(graph, named_arg.value or "")
    if ent_loc and is_location_satisfying_constraint(ent_loc, existential_arg.location, graph):
        return True

    return False


# ---------------------------------------------------------------------------
# Reconciliation rules
# ---------------------------------------------------------------------------

_NEED_TO_DELIVERY: dict[RelationPredicate, RelationPredicate] = {
    RelationPredicate.HAS_MESSAGE_FOR: RelationPredicate.MESSAGE_DELIVERED,
}


def _find_matching_delivery(
    need: RelationFact,
    delivery_predicate: RelationPredicate,
    relation_facts: list[RelationFact],
    graph: KnowledgeGraph,
) -> RelationFact | None:
    """Return the first delivery fact that satisfies *need*, or None."""
    for fact in relation_facts:
        if fact.predicate != delivery_predicate:
            continue
        if _args_align(fact.subject, need.subject, graph):
            # For need/delivery pairs, we consider the need satisfied if the subjects align.
            # We also check target compatibility if both have a target.
            if need.target and fact.target:
                if not _args_align(need.target, fact.target, graph):
                    continue
            return fact
    return None


def reconcile_state(graph: KnowledgeGraph) -> KnowledgeGraph:
    """
    Reconcile declarative relation facts in *graph*.

    For each 'need' predicate (NEEDS_POTION, HAS_MESSAGE_FOR),
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
        if _find_matching_delivery(need, delivery_predicate, rel_facts, graph) is not None:
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

    # --- Resolve HAS_ITEM against MESSAGE_DELIVERED (responses) ---
    delivered_senders = {
        f.subject.value
        for f in rel_facts
        if (
            f.predicate == RelationPredicate.MESSAGE_DELIVERED
            and f.subject is not None
            and f.subject.value
        )
    }
    for fact in rel_facts:
        if (
            fact.predicate == RelationPredicate.HAS_ITEM
            and fact.object is not None
            and fact.object.value
        ):
            obj_val_lower = fact.object.value.lower()
            for sender in delivered_senders:
                sender_lower = sender.lower()
                if obj_val_lower in [f"response from {sender_lower}", f"request from {sender_lower}"]:
                    facts_to_remove.add(fact.id)
                    break

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
            "Participant id: reads DATA_DIR/processed_output/kg/<pid>_merged_kg.json "
            "and writes <pid>_reconciled_kg.json (requires DATA_DIR)."
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
            data_dir, "processed_output", "kg", f"{args.pid}_merged_kg.json"
        )
        out_path = os.path.join(
            data_dir, "processed_output", "kg", f"{args.pid}_reconciled_kg.json"
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
