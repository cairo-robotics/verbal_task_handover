import argparse
import json
import os
from dataclasses import asdict
from typing import Dict

from src.core.representations.pydantic_schema import KnowledgeGraph, Fact
from src.pipelines.evaluation.costs import CostConfig
from src.pipelines.evaluation.map_graph import load_transitions
from src.pipelines.evaluation.report_iac import IACResult, EntityScore

from treasure_hunt.src.game_mdp import GameState

def _load_game_state(pid: str) -> GameState:
    """Loads the GameState for a given player ID."""
    return GameState.load(pid)

def _load_map_data(map_directory: str) -> Dict:
    transitions = load_transitions(os.path.join(map_directory, "transitions.json"))
    return transitions

def _score_location(entity, fact_set, ground_truth: GameState, map_graph: Dict, cost_config: CostConfig) -> ComponentScore:
    # TODO implement
    return 0

def _score_need(entity, fact_set, ground_truth: GameState, cost_config: CostConfig) -> ComponentScore:
    # TODO implement
    return 0

def _score_resource(entity, fact_set, ground_truth: GameState, cost_config: CostConfig) -> ComponentScore:
    # TODO implement
    return 0

def _score_entity(entity, fact_set, ground_truth: GameState, map_graph: Dict, cost_config: CostConfig) -> EntityScore:
    location_score = _score_location(entity, fact_set, ground_truth, map_graph, cost_config)
    need_score = _score_need(entity, fact_set, ground_truth, cost_config)
    resource_score = _score_resource(entity, fact_set, ground_truth, cost_config)
    # Note: EntityScore from report_iac expects ComponentScore objects, 
    # but for now we are just returning a stub or using the local one if we had it.
    # Since we are supposed to just wire it up, I'll leave the scoring stubs as they are
    # but fix the call to match what compute_iac might eventually do.
    raise NotImplementedError("Entity scoring not yet implemented")

def compute_iac(
    pred_facts: list[Fact],
    true_state: GameState,
    cost_config: CostConfig = CostConfig()
) -> IACResult:
    """
    Computes the Information Access Cost (IAC) based on predicted facts and ground truth.
    """
    # TODO: Implement the actual calculation logic here.
    # This currently returns a stub IACResult to allow the CLI to be tested.
    
    # Example stub result
    stub_result = IACResult(
        entity_scores={},
        alpha=cost_config.alpha,
        tokens=0,
        total_cost_saved=0.0,
        omission_cost=0.0,
        misinformation_cost=0.0,
        combined_cost=0.0
    )
    return stub_result

def main():
    parser = argparse.ArgumentParser(description="Calculate Information Access Cost (IAC) for a Knowledge Graph.")
    parser.add_argument("--kg-file", type=str, required=True, help="Path to the KnowledgeGraph JSON file.")
    parser.add_argument("--pid", type=str, required=True, help="Player ID to load the saved GameState.")
    parser.add_argument("--output-file", type=str, required=True, help="Path to save the IACResult JSON.")
    parser.add_argument("--map-dir", type=str, default="evaluation/map_data", help="Directory containing map transitions.")

    args = parser.parse_args()

    # 1. Load Knowledge Graph
    if not os.path.exists(args.kg_file):
        print(f"Error: Knowledge Graph file not found: {args.kg_file}")
        return

    with open(args.kg_file, "r") as f:
        kg_data = json.load(f)
    
    kg = KnowledgeGraph.model_validate(kg_data)
    pred_facts = kg.facts

    # 2. Load Ground Truth Game State
    true_state = _load_game_state(args.pid)
    if true_state is None:
        print(f"Error: Could not load GameState for PID: {args.pid}")
        return

    # 3. Compute IAC
    cost_config = CostConfig() # Could eventually take these from args too
    result = compute_iac(pred_facts, true_state, cost_config)

    # 4. Save result
    output_dir = os.path.dirname(args.output_file)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)

    with open(args.output_file, "w") as f:
        json.dump(asdict(result), f, indent=4)

    print(f"IAC calculation complete. Result saved to {args.output_file}")

if __name__ == "__main__":
    main()