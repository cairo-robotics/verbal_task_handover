#!/usr/bin/env python3
"""
Generate a composite floor-plan figure from per-room text-grid files + a
transitions.json adjacency file.

Room file format:
    '#' = wall, ' ' = floor, single-char digit = door (labelled)

transitions.json format:
    {
      "room_name": {
        "door_label": ["other_room_name", "other_room_door_label"],
        ...
      },
      ...
    }

Usage:
    python generate_map.py --rooms_dir rooms/ --transitions transitions.json \
        --out floor_plan.svg [--start hallway_1]
"""

import argparse
import json
import os
from collections import deque

import matplotlib.pyplot as plt
import matplotlib.patches as patches

WALL = "#"

# direction vectors in (dx, dy) room-grid units; +y is drawn downward
EDGE_TO_OFFSET = {
    "top": (0, -1),
    "bottom": (0, 1),
    "left": (-1, 0),
    "right": (1, 0),
}
OPPOSITE_EDGE = {"top": "bottom", "bottom": "top", "left": "right", "right": "left"}


def parse_room(filepath):
    """Return (grid: list[str], doors: dict[label -> (row, col, edge)])."""
    with open(filepath, "r") as f:
        raw_lines = [line.rstrip("\n") for line in f.readlines()]
    # drop fully empty trailing lines
    while raw_lines and raw_lines[-1] == "":
        raw_lines.pop()
    width = max(len(line) for line in raw_lines)
    grid = [line.ljust(width) for line in raw_lines]
    height = len(grid)

    doors = {}
    for r, row in enumerate(grid):
        for c, ch in enumerate(row):
            if ch.isdigit():
                if r == 0:
                    edge = "top"
                elif r == height - 1:
                    edge = "bottom"
                elif c == 0:
                    edge = "left"
                elif c == width - 1:
                    edge = "right"
                else:
                    # interior digit: fall back to nearest edge by distance
                    dists = {
                        "top": r,
                        "bottom": height - 1 - r,
                        "left": c,
                        "right": width - 1 - c,
                    }
                    edge = min(dists, key=dists.get)
                doors[ch] = (r, c, edge)
    return grid, doors, width, height


def load_rooms(rooms_dir):
    rooms = {}
    for fname in os.listdir(rooms_dir):
        if not fname.endswith(".txt"):
            continue
        name = os.path.splitext(fname)[0]
        grid, doors, w, h = parse_room(os.path.join(rooms_dir, fname))
        rooms[name] = {"grid": grid, "doors": doors, "w": w, "h": h}
    return rooms


def layout_rooms(rooms, transitions, start=None):
    """BFS placement in cell-level coordinates, using door edge to align rooms.
    Returns dict[name -> (grid_x, grid_y)]. Rooms unreachable from start
    are placed at a fallback row below the main layout.
    """
    if start is None:
        start = next(iter(rooms))

    # Build bidirectional adjacency list from transitions to handle asymmetric transitions
    adj = {}
    for r1, doors in transitions.items():
        for d1, (r2, d2) in doors.items():
            d1_str = str(d1)
            d2_str = str(d2)
            if r1 not in adj:
                adj[r1] = {}
            adj[r1][d1_str] = (r2, d2_str)
            if r2 not in adj:
                adj[r2] = {}
            adj[r2][d2_str] = (r1, d1_str)

    positions = {start: (0, 0)}
    visited = {start}
    # Keep track of bounding boxes of placed rooms: (x1, y1, x2, y2)
    occupied = [(0, 0, rooms[start]["w"], rooms[start]["h"])]
    queue = deque([start])
    conflicts = []
    unresolved_edges = []

    def get_non_overlapping_pos(new_x, new_y, W_B, H_B, occupied_list, gap=4):
        """Checks proposed bounding box and shifts new_x right until no overlaps exist."""
        while True:
            overlap = False
            for X1, Y1, X2, Y2 in occupied_list:
                # Check for overlap between proposed bounding box and existing room box
                if (new_x < X2 and new_x + W_B > X1 and
                    new_y < Y2 and new_y + H_B > Y1):
                    new_x = X2 + gap
                    overlap = True
                    break
            if not overlap:
                break
        return new_x, new_y

    while queue:
        cur = queue.popleft()
        cur_pos = positions[cur]
        cur_room = rooms[cur]
        cur_adj = adj.get(cur, {})
        for door_label_str, (other, other_door_str) in cur_adj.items():
            if other not in rooms:
                unresolved_edges.append((cur, door_label_str, other))
                continue
            if door_label_str not in cur_room["doors"]:
                unresolved_edges.append((cur, door_label_str, other))
                continue
            other_room = rooms[other]
            if other_door_str not in other_room["doors"]:
                unresolved_edges.append((cur, door_label_str, other))
                continue

            # Align the two rooms using their door positions
            r_A, c_A, edge_A = cur_room["doors"][door_label_str]
            r_B, c_B, edge_B = other_room["doors"][other_door_str]
            W_A, H_A = cur_room["w"], cur_room["h"]
            W_B, H_B = other_room["w"], other_room["h"]

            cur_x, cur_y = cur_pos
            if edge_A == "top":
                new_x = cur_x + c_A - c_B
                new_y = cur_y - H_B
            elif edge_A == "bottom":
                new_x = cur_x + c_A - c_B
                new_y = cur_y + H_A
            elif edge_A == "left":
                new_x = cur_x - W_B
                new_y = cur_y + r_A - r_B
            elif edge_A == "right":
                new_x = cur_x + W_A
                new_y = cur_y + r_A - r_B
            else:
                unresolved_edges.append((cur, door_label_str, other))
                continue

            new_pos = (new_x, new_y)
            if other not in visited:
                # Resolve potential overlaps before placing the new room
                resolved_x, resolved_y = get_non_overlapping_pos(new_x, new_y, W_B, H_B, occupied)
                positions[other] = (resolved_x, resolved_y)
                occupied.append((resolved_x, resolved_y, resolved_x + W_B, resolved_y + H_B))
                visited.add(other)
                queue.append(other)
            elif positions[other] != new_pos:
                # If a room was already placed and its final position differs from this new connection path,
                # we record it as a conflict but do not move it.
                conflicts.append((cur, other, positions[other], new_pos))

    # Place any unreachable rooms below the main layout
    if positions:
        min_x = min(x for x, y in positions.values())
        max_x = max(x + rooms[r]["w"] for r, (x, y) in positions.items())
        min_y = min(y for x, y in positions.values())
        max_y = max(y + rooms[r]["h"] for r, (x, y) in positions.items())
        fallback_y = max_y + 4
        fallback_x = min_x
    else:
        fallback_y = 0
        fallback_x = 0

    for name in rooms:
        if name not in positions:
            positions[name] = (fallback_x, fallback_y)
            fallback_x += rooms[name]["w"] + 2

    return positions, conflicts, unresolved_edges


def render(rooms, positions, transitions, out_path, cell_size=0.12, room_gap=1.5):
    """Render the floor plan as a vector SVG."""
    fig, ax = plt.subplots(figsize=(14, 10), facecolor="#eef2f5")
    ax.set_facecolor("#eef2f5")

    room_origin = {}  # name -> (x0, y0) in plot units, top-left corner
    for name, (gx, gy) in positions.items():
        room_origin[name] = (gx * cell_size, gy * cell_size)

    door_world_pos = {}  # (room, door_label) -> (x, y) world coords, for connector lines

    for name, room in rooms.items():
        x0, y0 = room_origin[name]
        grid = room["grid"]
        for r, row in enumerate(grid):
            for c, ch in enumerate(row):
                x = x0 + c * cell_size
                y = y0 + r * cell_size
                if ch == WALL:
                    ax.add_patch(
                        patches.Rectangle(
                            (x, y), cell_size, cell_size,
                            facecolor="#2c3e50", edgecolor="none",
                        )
                    )
                elif ch.isdigit():
                    ax.add_patch(
                        patches.Rectangle(
                            (x, y), cell_size, cell_size,
                            facecolor="#e67e22", edgecolor="none",
                        )
                    )
                    door_world_pos[(name, ch)] = (x + cell_size / 2, y + cell_size / 2)
                else:
                    # Floor cell: draw as white to make it clear and distinct from empty space
                    ax.add_patch(
                        patches.Rectangle(
                            (x, y), cell_size, cell_size,
                            facecolor="#ffffff", edgecolor="none",
                        )
                    )

        # room label: centered inside the room with a clean semi-transparent background
        ax.text(
            x0 + (room["w"] * cell_size) / 2,
            y0 + (room["h"] * cell_size) / 2,
            name,
            ha="center", va="center", fontsize=8, fontweight="bold",
            color="#2c3e50",
            bbox=dict(facecolor='white', alpha=0.85, edgecolor='none', boxstyle='round,pad=0.2'),
            zorder=3
        )

    # draw connector lines between matched doors (avoid double-drawing)
    drawn = set()
    for room_name, doors in transitions.items():
        for door_label, (other_room, other_door) in doors.items():
            key = frozenset({(room_name, door_label), (other_room, other_door)})
            if key in drawn:
                continue
            drawn.add(key)
            p1 = door_world_pos.get((room_name, str(door_label)))
            p2 = door_world_pos.get((other_room, str(other_door)))
            if p1 and p2:
                ax.plot(
                    [p1[0], p2[0]], [p1[1], p2[1]],
                    color="#e67e22", linewidth=1.2, linestyle="--", zorder=0,
                )

    ax.set_aspect("equal")
    ax.invert_yaxis()  # row 0 at top, matching text-file orientation
    ax.axis("off")
    fig.savefig(out_path, bbox_inches="tight")
    print(f"Saved: {out_path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rooms_dir", default="rooms")
    ap.add_argument("--transitions", default="transitions.json")
    ap.add_argument("--out", default="floor_plan.svg")
    ap.add_argument("--start", default=None, help="room name to anchor layout at (0,0)")
    args = ap.parse_args()

    rooms = load_rooms(args.rooms_dir)
    with open(args.transitions) as f:
        transitions = json.load(f)

    positions, conflicts, unresolved = layout_rooms(rooms, transitions, start=args.start)

    if conflicts:
        print("WARNING: layout conflicts detected (room wanted in two places).")
        print("This usually means the map has a loop that doesn't close geometrically,")
        print("or a door's inferred edge doesn't match its real-world direction.")
        for cur, other, existing, attempted in conflicts:
            print(f"  {other}: placed at {existing}, but {cur} implies {attempted}")
        print("You may need to manually override positions in the `positions` dict.\n")

    if unresolved:
        print("WARNING: some transitions reference rooms/doors not found in rooms_dir:")
        for cur, label, other in unresolved:
            print(f"  {cur} door {label} -> {other} (not found)")

    render(rooms, positions, transitions, args.out)


if __name__ == "__main__":
    main()
