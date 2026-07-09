import os
import sys
import json
import itertools
import argparse
from typing import List, Dict, Optional, Tuple, Union

# Add the project root to sys.path
sys.path.append("/home/kaleb/code/verbal_task_handover")

from src.pipelines.evaluation.map_graph import find_steps_between_rooms, load_transitions

GAME_DIR = "/home/kaleb/code/verbal_task_handover/evaluation/treasure_hunt_py/treasure_hunt"
MAP_DIR = os.path.join(GAME_DIR, "maps", "map2")

def get_room_center(room_file: str) -> Optional[Tuple[int, int]]:
    """Finds the center of the walkable area in a room."""
    walkable_tiles = []
    if not os.path.exists(room_file):
        return None
    with open(room_file, 'r') as f:
        for y, line in enumerate(f):
            for x, ch in enumerate(line.rstrip('\n')):
                if ch != '#':
                    walkable_tiles.append((x, y))
    
    if not walkable_tiles:
        return None
        
    avg_x = sum(t[0] for t in walkable_tiles) / len(walkable_tiles)
    avg_y = sum(t[1] for t in walkable_tiles) / len(walkable_tiles)
    
    # Return the walkable tile closest to the average
    return min(walkable_tiles, key=lambda t: (t[0] - avg_x)**2 + (t[1] - avg_y)**2)

def expected_search_cost(start_rooms: Union[str, List[str]], 
                         rooms_to_search: List[str], 
                         room_probs: Optional[Dict[str, float]] = None) -> float:
    """
    Calculates the minimum expected search cost for an optimal search of rooms_to_search.
    
    E[cost] = Σ_i P(entity in room_i) × cumulative_travel_cost(s, room_i, search_order)
    
    If start_rooms is a list, returns the average expected cost across all starting rooms.
    """
    if not rooms_to_search:
        return 0.0

    if room_probs is None:
        # Default to uniform prior
        prob = 1.0 / len(rooms_to_search)
        room_probs = {room: prob for room in rooms_to_search}
    
    # Ensure start_rooms is a list
    if isinstance(start_rooms, str):
        start_rooms = [start_rooms]
        
    # Load transitions for distance calculations
    transitions_file = os.path.join(MAP_DIR, "transitions.json")
    if not os.path.exists(transitions_file):
        # If map2 doesn't exist or transitions missing, we can't calculate distances accurately
        # Return a fallback based on room count as in calculate_iac.py
        return len(rooms_to_search) / 2.0
        
    transitions = load_transitions(transitions_file)
    
    # Cache room centers
    room_centers = {}
    all_rooms_needed = set(start_rooms) | set(rooms_to_search)
    for room in all_rooms_needed:
        room_file = os.path.join(MAP_DIR, f"{room}.txt")
        center = get_room_center(room_file)
        if center:
            room_centers[room] = center
        else:
            # Fallback for missing room files
            room_centers[room] = (0, 0)
        
    # Distance cache
    dist_cache = {}
    
    def get_dist(r1, r2):
        if r1 == r2:
            return 0
        if (r1, r2) in dist_cache:
            return dist_cache[(r1, r2)]
        
        # find_steps_between_rooms is symmetric in many cases but let's be safe
        d = find_steps_between_rooms(MAP_DIR, r1, room_centers[r1], r2, room_centers[r2], transitions)
        dist_cache[(r1, r2)] = d
        return d

    total_expected_cost_across_starts = 0.0
    
    for s in start_rooms:
        min_expected_cost = float('inf')
        
        # Try all permutations of rooms_to_search
        # Note: 5! = 120, which is small enough for brute force
        for order in itertools.permutations(rooms_to_search):
            expected_cost = 0.0
            cumulative_travel_time = 0.0
            current_loc = s
            
            for room in order:
                dist = get_dist(current_loc, room)
                if dist == -1: # Unreachable
                    cumulative_travel_time = float('inf')
                    break
                cumulative_travel_time += dist
                expected_cost += room_probs.get(room, 0.0) * cumulative_travel_time
                current_loc = room
            
            if expected_cost < min_expected_cost:
                min_expected_cost = expected_cost
        
        if min_expected_cost == float('inf'):
            # Fallback if some rooms are unreachable
            total_expected_cost_across_starts += len(rooms_to_search) / 2.0
        else:
            total_expected_cost_across_starts += min_expected_cost
        
    return total_expected_cost_across_starts / len(start_rooms)

def main():
    parser = argparse.ArgumentParser(description="Calculate expected search cost for an optimal search order.")
    parser.add_argument("--start", type=str, default="room0", help="Starting room(s), comma-separated.")
    parser.add_argument("--rooms", type=str, default="room1,room2,room3,room4,room5", help="Rooms to search, comma-separated.")
    parser.add_argument("--probs", type=str, help="Probabilities for each room, comma-separated (e.g. 0.1,0.2...). Must match room order.")
    
    args = parser.parse_args()
    
    start_rooms = [r.strip() for r in args.start.split(",")]
    rooms_to_search = [r.strip() for r in args.rooms.split(",")]
    
    room_probs = None
    if args.probs:
        probs = [float(p.strip()) for p in args.probs.split(",")]
        if len(probs) != len(rooms_to_search):
            print("Error: Number of probabilities must match number of rooms.")
            return
        room_probs = dict(zip(rooms_to_search, probs))
    
    cost = expected_search_cost(start_rooms, rooms_to_search, room_probs)
    print(f"Expected Search Cost: {cost:.2f}")

if __name__ == "__main__":
    main()
