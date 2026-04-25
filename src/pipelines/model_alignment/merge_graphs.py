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
    parser = argparse.ArgumentParser(description="Merge two KnowledgeGraph JSON files.")
    parser.add_argument("base_graph", help="Path to the base (telemetry) graph JSON file.")
    parser.add_argument("new_graph", help="Path to the new (report) graph JSON file.")
    parser.add_argument("--output", "-o", help="Path to save the merged graph JSON file.", default="merged_graph.json")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.base_graph):
        print(f"Error: Base graph file not found: {args.base_graph}")
        sys.exit(1)
    if not os.path.exists(args.new_graph):
        print(f"Error: New graph file not found: {args.new_graph}")
        sys.exit(1)
        
    with open(args.base_graph, "r") as f:
        base_data = json.load(f)
        base_graph = KnowledgeGraph.model_validate(base_data)
        
    with open(args.new_graph, "r") as f:
        new_data = json.load(f)
        new_graph = KnowledgeGraph.model_validate(new_data)
        
    merged_graph = merge_graphs(base_graph, new_graph)
    
    with open(args.output, "w") as f:
        json.dump(merged_graph.model_dump(), f, indent=2)
        
    print(f"Successfully merged graphs. Output saved to {args.output}")


if __name__ == "__main__":
    main()