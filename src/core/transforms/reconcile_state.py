#!/usr/bin/env python3
"""
Standalone step: load a merged knowledge graph JSON, replay event-driven state
effects on `state_relations`, write the result to a new JSON file.

Run after merge_graphs. Does not import or depend on merge_graphs.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import dotenv

try:
    from src.core.representations.pydantic_schema import (
        Event,
        EventType,
        KnowledgeGraphExtraction,
        RelationType,
        StateRelation,
    )
except ImportError:
    from pydantic_schema import (
        Event,
        EventType,
        KnowledgeGraphExtraction,
        RelationType,
        StateRelation,
    )

dotenv.load_dotenv()


def _state_exists(
    graph: KnowledgeGraphExtraction,
    subject: str,
    relation: RelationType,
    obj: str,
) -> bool:
    for rel in graph.state_relations:
        if (
            rel.subject == subject
            and rel.relation == relation
            and rel.object == obj
        ):
            return True
    return False


def _apply_event_effects(event: Event, graph: KnowledgeGraphExtraction) -> None:
    if event.event_type == EventType.OBTAIN:
        actor = event.participants.actor
        obj = event.participants.object
        if actor is None or obj is None:
            return

        if not _state_exists(graph, obj, RelationType.IN_INVENTORY_OF, actor):
            graph.state_relations.append(
                StateRelation(
                    subject=obj,
                    relation=RelationType.IN_INVENTORY_OF,
                    object=actor,
                    confidence=event.confidence,
                )
            )
        return

    if event.event_type == EventType.DELIVER or event.event_type == EventType.GIVE:
        actor = event.participants.actor
        obj = event.participants.object
        if actor is None or obj is None:
            return
        graph.state_relations = [
            rel
            for rel in graph.state_relations
            if not (
                rel.subject == obj
                and rel.relation == RelationType.IN_INVENTORY_OF
                and rel.object == actor
            )
        ]


def reconcile_state_from_events(graph: KnowledgeGraphExtraction) -> None:
    """Replay inventory-related effects for every event in `graph.events` (list order)."""
    for event in graph.events:
        _apply_event_effects(event, graph)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Read merged graph JSON, apply event effects to state_relations, "
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
        graph = KnowledgeGraphExtraction.model_validate_json(f.read())

    reconcile_state_from_events(graph)

    out_dir = os.path.dirname(out_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(graph.model_dump(), f, indent=2)


if __name__ == "__main__":
    main()
