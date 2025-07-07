from collections import deque
import os
import json

GAME_DIR = "/home/kaleb/code/verbal_task_handover/evaluation/treasure_hunt_py/treasure_hunt"
MAP_DIR = os.path.join(GAME_DIR, "maps", "map2")

def parse_room(room_file):
    """Parses a room file into a 2D grid and records door positions."""
    grid = []
    doors = {}  # {door_num: (x, y)}
    with open(room_file, 'r') as f:
        for y, line in enumerate(f):
            row = []
            for x, ch in enumerate(line.rstrip('\n')):
                row.append(ch)
                if ch.isdigit():
                    doors[int(ch)] = (x, y)
            grid.append(row)
    return grid, doors

def get_neighbors(x, y, grid):
    """Returns walkable neighbors of a given tile."""
    neighbors = []
    for dx, dy in [(-1,0), (1,0), (0,-1), (0,1)]:
        nx, ny = x + dx, y + dy
        if 0 <= ny < len(grid) and 0 <= nx < len(grid[0]):
            if grid[ny][nx] != '#':
                neighbors.append((nx, ny))
    return neighbors

def bfs(start, goal, grid):
    """Basic BFS from start to goal within one room."""
    queue = deque([(start, 0)])
    visited = set([start])

    while queue:
        (x, y), dist = queue.popleft()
        if (x, y) == goal:
            return dist
        for nx, ny in get_neighbors(x, y, grid):
            if (nx, ny) not in visited:
                visited.add((nx, ny))
                queue.append(((nx, ny), dist + 1))
    return None  # Unreachable

def find_steps_between_rooms(rooms_dir, start_room, start_pos, end_room, end_pos, connections):
    """Finds total player steps from one position to another across rooms."""
    # Cache of parsed rooms
    room_grids = {}
    room_doors = {}

    def load_room(room_name):
        if room_name not in room_grids:
            grid, doors = parse_room(os.path.join(rooms_dir, f"{room_name}.txt"))
            room_grids[room_name] = grid
            room_doors[room_name] = doors
        return room_grids[room_name], room_doors[room_name]

    # BFS across rooms and doors
    queue = deque([(start_room, start_pos, 0)])
    visited = set()

    while queue:
        current_room, current_pos, total_dist = queue.popleft()
        state_id = (current_room, current_pos)
        if state_id in visited:
            continue
        visited.add(state_id)

        if current_room == end_room and current_pos == end_pos:
            return total_dist

        grid, doors = load_room(current_room)

        # First, move within current room
        for nx, ny in get_neighbors(*current_pos, grid):
            queue.append((current_room, (nx, ny), total_dist + 1))

        # Then, move through doors
        for door_num, (dx, dy) in doors.items():
            if (dx, dy) == current_pos and str(door_num) in connections.get(current_room, {}).keys():
                # import pdb; pdb.set_trace()  # Debugging breakpoint
                target_room, target_door_num = connections[current_room][str(door_num)]
                _, target_doors = load_room(target_room)
                if target_door_num in target_doors:
                    target_pos = target_doors[target_door_num]
                    queue.append((target_room, target_pos, total_dist + 1))

    return -1  # No path found

def load_transitions(transition_filename):
    """Loads room transitions from file"""
    with open(transition_filename, 'r') as f:
        transitions = json.load(f)
    return transitions

if __name__ == "__main__":
    # Example usage
    transitions = load_transitions(os.path.join(MAP_DIR, "transitions.json"))
    
    start_room = "room1"
    start_pos = (3, 4)
    end_room = "room0"
    end_pos = (1, 1)

    steps = find_steps_between_rooms(MAP_DIR, start_room, start_pos, end_room, end_pos, transitions)
    print(f"Steps from {start_room} at {start_pos} to {end_room} at {end_pos}: {steps}")