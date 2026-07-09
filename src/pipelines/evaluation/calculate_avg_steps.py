import os
import sys
import json
from collections import deque

# Add the project root to sys.path so we can import from src
sys.path.append("/home/kaleb/code/verbal_task_handover")

from src.pipelines.evaluation.map_graph import find_steps_between_rooms, load_transitions

GAME_DIR = "/home/kaleb/code/verbal_task_handover/evaluation/treasure_hunt_py/treasure_hunt"
MAP_DIR = os.path.join(GAME_DIR, "maps", "map2")

def get_room_center(room_file):
    """Finds the center of the walkable area in a room."""
    walkable_tiles = []
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

def main():
    transitions = load_transitions(os.path.join(MAP_DIR, "transitions.json"))
    
    start_room = "room0"
    start_pos = (4, 3)  # Roughly the middle of room 0
    
    room_files = [f for f in os.listdir(MAP_DIR) if f.endswith('.txt') and f != 'room0.txt']
    
    # Define categories
    categories = {
        "Patient Rooms": ["room1", "room2", "room3", "room4", "room5"],
        "Hallways": ["hallway_1", "hallway_2", "hallway_3", "hallway_4", "hallway_5"],
        "Lounges": ["lounge_1", "lounge_2", "lounge_3"],
        "Storage Rooms": ["storage_1", "storage_2"]
    }
    
    category_distances = {cat: [] for cat in categories}
    all_results = []
    
    print(f"Calculating steps from {start_room} at {start_pos} by category:\n")
    
    for room_file in sorted(room_files):
        room_name = room_file.replace('.txt', '')
        pos = get_room_center(os.path.join(MAP_DIR, room_file))
        
        if pos:
            steps = find_steps_between_rooms(MAP_DIR, start_room, start_pos, room_name, pos, transitions)
            if steps != -1:
                # Find which category this room belongs to
                found_cat = "Other"
                for cat, rooms in categories.items():
                    if room_name in rooms:
                        found_cat = cat
                        break
                
                if found_cat not in category_distances:
                    category_distances[found_cat] = []
                
                category_distances[found_cat].append(steps)
                all_results.append((found_cat, room_name, pos, steps))
    
    # Print results by category
    for cat in sorted(category_distances.keys()):
        if not category_distances[cat]:
            continue
            
        print(f"--- {cat} ---")
        cat_results = [r for r in all_results if r[0] == cat]
        for _, name, pos, steps in sorted(cat_results, key=lambda x: x[1]):
            print(f"  {name:12} at {str(pos):10}: {steps} steps")
            
        avg = sum(category_distances[cat]) / len(category_distances[cat])
        print(f"  Average for {cat}: {avg:.2f}\n")

    # Overall average
    all_distances = [d for dists in category_distances.values() for d in dists]
    if all_distances:
        overall_avg = sum(all_distances) / len(all_distances)
        print(f"Overall Average: {overall_avg:.2f}")

if __name__ == "__main__":
    main()
