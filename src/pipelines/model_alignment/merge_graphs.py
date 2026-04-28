from __future__ import annotations

import json
import sys
import os
import argparse
from typing import List, Dict, Any, Optional

from src.core.representations.pydantic_schema import KnowledgeGraph, Fact, Conflict
from src.pipelines.model_alignment.entity_alignment import align_entities
from src.pipelines.model_alignment.fact_alignment import align_facts


def merge_graphs(base_graph: KnowledgeGraph, new_graph: KnowledgeGraph) -> KnowledgeGraph:
    """
    Merge two knowledge graphs.
    
    Logic:
    1. Perform entity alignment between new_graph (report) and base_graph (telemetry).
    2. Perform fact alignment between new_graph and base_graph.
    3. Include all facts from base_graph in the merged result.
    4. Include novel facts from new_graph in the merged result.
    5. For conflicting facts, preserve the base fact in the facts list and record 
       the conflict details (including the full new fact).
    """
    # 1. Align entities (new_graph is the 'report', base_graph is 'telemetry')
    alignment_result = align_entities(new_graph, base_graph)
    
    # 2. Align facts
    fact_alignment_result = align_facts(new_graph, base_graph, alignment_result)
    
    # 3. Construct merged graph
    # Start with all facts from base graph, setting source="base"
    merged_facts: List[Fact] = []
    for f in base_graph.facts:
        f_copy = f.model_copy()
        f_copy.source = "base"
        merged_facts.append(f_copy)
    
    merged_conflicts: List[Conflict] = []
    
    # Map for easy lookup of new facts by ID
    new_facts_map = {f.id: f for f in new_graph.facts}
    
    # Add novel facts from new graph
    for fact_id in fact_alignment_result.novel_fact_ids:
        f = new_facts_map[fact_id].model_copy()
        f.source = "new"
        merged_facts.append(f)
        
    # Process conflicts
    for cr in fact_alignment_result.conflicts:
        new_fact = new_facts_map[cr.source_fact_id].model_copy()
        new_fact.source = "new"
        
        # In case of conflict, we keep only the base fact in the facts list 
        # (which is already added above).
        # We record the conflict information.
        conflict = Conflict(
            base_fact_id=cr.target_fact_id,
            new_fact=new_fact,
            field_name=cr.field_name,
            base_value=cr.expected_value,
            new_value=cr.actual_value
        )
        merged_conflicts.append(conflict)
        
    return KnowledgeGraph(facts=merged_facts, conflicts=merged_conflicts)


def main():
    parser = argparse.ArgumentParser(description="Merge two KnowledgeGraph JSON files (report vs telemetry).")
    parser.add_argument("pid_or_base", help="Participant ID or path to the base (telemetry) graph JSON file.")
    parser.add_argument("new_graph", nargs="?", help="Optional path to the new (report) graph JSON file. If omitted, uses PID logic with DATA_DIR.")
    parser.add_argument("--output", "-o", help="Path to save the merged graph JSON file.")
    
    args = parser.parse_args()
    
    data_dir = os.environ.get("DATA_DIR")
    
    if args.new_graph is None:
        # PID mode
        if not data_dir:
            print("Error: DATA_DIR environment variable must be set for PID-based merging.")
            sys.exit(1)
        pid = args.pid_or_base
        base_path = os.path.join(data_dir, "processed_output", f"{pid}_telemetry_to_kg_output.json")
        new_path = os.path.join(data_dir, "processed_output", f"{pid}_dsl_to_kg_output.json")
        output_path = args.output or os.path.join(data_dir, "processed_output", f"{pid}_merge_graphs_output.json")
    else:
        # Explicit path mode
        base_path = args.pid_or_base
        new_path = args.new_graph
        output_path = args.output or "merged_graph.json"

    if not os.path.exists(base_path):
        print(f"Error: Base graph file not found: {base_path}")
        sys.exit(1)
    if not os.path.exists(new_path):
        print(f"Error: New graph file not found: {new_path}")
        sys.exit(1)
        
    with open(base_path, "r") as f:
        base_data = json.load(f)
        base_graph = KnowledgeGraph.model_validate(base_data)
        
    with open(new_path, "r") as f:
        new_data = json.load(f)
        new_graph = KnowledgeGraph.model_validate(new_data)
        
    merged_graph = merge_graphs(base_graph, new_graph)
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True) if os.path.dirname(output_path) else None
    with open(output_path, "w") as f:
        json.dump(merged_graph.model_dump(), f, indent=2)
        
    print(f"Successfully merged graphs. Output saved to {output_path}")


if __name__ == "__main__":
    main()