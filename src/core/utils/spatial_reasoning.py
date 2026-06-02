
from typing import Dict, List, Optional, Set, Tuple
from src.core.representations.pydantic_schema import (
    KnowledgeGraph,
    Location,
    LocationFact,
    ConnectionFact,
    Direction,
    SpatialFact,
    SpatialRelationType,
)

def get_entity_location(graph: KnowledgeGraph, entity_name: str) -> Optional[str]:
    """Find the room name where an entity is located in the graph."""
    from src.core.utils.normalization import normalize_entity_name
    entity_norm = normalize_entity_name(entity_name)
    for fact in graph.facts:
        if isinstance(fact, LocationFact):
            if fact.entity.type == "named" and normalize_entity_name(fact.entity.value) == entity_norm:
                if fact.location.type == "room":
                    return fact.location.room
    return None

def is_location_satisfying_constraint(
    target_room: str, 
    constraint: Location, 
    graph: KnowledgeGraph,
    reference_room: str = "room 0"
) -> bool:
    """Check if a room satisfies a location constraint (e.g. 'room 1' or 'west')."""
    from src.core.utils.normalization import normalize_entity_name
    
    if constraint.type == "room":
        return normalize_entity_name(target_room) == normalize_entity_name(constraint.room)
    
    if constraint.type == "directional" and constraint.directions:
        return is_room_in_direction(graph, target_room, reference_room, constraint.directions)
    
    return False

def expand_directions(dirs: List[Direction]) -> List[List[Direction]]:
    if not dirs:
        return [[]]
    first = dirs[0]
    rest_expanded = expand_directions(dirs[1:])
    
    # Define expansions for compound directions
    expansions = {
        Direction.NORTHWEST: [[Direction.NORTH, Direction.WEST], [Direction.WEST, Direction.NORTH]],
        Direction.NORTHEAST: [[Direction.NORTH, Direction.EAST], [Direction.EAST, Direction.NORTH]],
        Direction.SOUTHWEST: [[Direction.SOUTH, Direction.WEST], [Direction.WEST, Direction.SOUTH]],
        Direction.SOUTHEAST: [[Direction.SOUTH, Direction.EAST], [Direction.EAST, Direction.SOUTH]],
    }
    
    first_paths = expansions.get(first, [[first]])
    
    result = []
    for fp in first_paths:
        for rp in rest_expanded:
            result.append(fp + rp)
    return result

def is_room_in_direction(
    graph: KnowledgeGraph, 
    target_room: str, 
    source_room: str, 
    expected_directions: List[Direction]
) -> bool:
    """
    Check if target_room is in the given direction path from source_room.
    Uses ConnectionFacts and SpatialFacts to find the shortest path.
    Returns True if expected_directions is a prefix of the shortest path.
    """
    from src.core.utils.normalization import normalize_entity_name
    
    target_norm = normalize_entity_name(target_room)
    source_norm = normalize_entity_name(source_room)
    
    if target_norm == source_norm:
        # For target == source, it satisfies if the expected direction list expands to an empty path
        possible_expected_paths = expand_directions(expected_directions)
        return any(not p for p in possible_expected_paths)
        
    # Build adjacency map: source -> list of (target, direction)
    adj: Dict[str, List[Tuple[str, Direction]]] = {}
    
    opposite = {
        Direction.NORTH: Direction.SOUTH,
        Direction.SOUTH: Direction.NORTH,
        Direction.EAST: Direction.WEST,
        Direction.WEST: Direction.EAST,
        Direction.NORTHEAST: Direction.SOUTHWEST,
        Direction.SOUTHWEST: Direction.NORTHEAST,
        Direction.NORTHWEST: Direction.SOUTHEAST,
        Direction.SOUTHEAST: Direction.NORTHWEST,
    }

    for fact in graph.facts:
        if isinstance(fact, ConnectionFact):
            u = normalize_entity_name(fact.location_a.room) if fact.location_a.room else None
            v = normalize_entity_name(fact.location_b.room) if fact.location_b.room else None
            d = fact.direction
            if u and v and d:
                adj.setdefault(u, []).append((v, d))
                # Add reverse edge
                if d in opposite:
                    adj.setdefault(v, []).append((u, opposite[d]))
        elif isinstance(fact, SpatialFact):
            if fact.type == SpatialRelationType.RELATIVE:
                if (fact.subject.type == "named" and fact.subject.value and 
                    fact.reference and fact.reference.type == "named" and fact.reference.value):
                    u = normalize_entity_name(fact.reference.value)
                    v = normalize_entity_name(fact.subject.value)
                    d = fact.direction
                    adj.setdefault(u, []).append((v, d))
                    # Add reverse edge
                    if d in opposite:
                        adj.setdefault(v, []).append((u, opposite[d]))

    # BFS to find shortest path of directions
    visited = {source_norm}
    queue = [(source_norm, [])]
    
    while queue:
        curr, path = queue.pop(0)
        
        if curr == target_norm:
            # Check if any of the expanded paths is a prefix of path
            possible_expected_paths = expand_directions(expected_directions)
            for exp_path in possible_expected_paths:
                if len(exp_path) <= len(path) and path[:len(exp_path)] == exp_path:
                    return True
            return False
            
        for neighbor, d in adj.get(curr, []):
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append((neighbor, path + [d]))
                    
    return False


def resolve_directional_path(
    start_room: str,
    directions: List[Direction],
    graph: KnowledgeGraph
) -> Optional[str]:
    """
    Resolve a directional path starting from a room using ConnectionFacts in the graph.
    Returns the resolved room name, or None if the path cannot be fully resolved.
    """
    from src.core.utils.normalization import normalize_entity_name
    
    # Build opposite direction map for bidirectional traversal
    opposite = {
        Direction.NORTH: Direction.SOUTH,
        Direction.SOUTH: Direction.NORTH,
        Direction.EAST: Direction.WEST,
        Direction.WEST: Direction.EAST,
        Direction.NORTHEAST: Direction.SOUTHWEST,
        Direction.SOUTHWEST: Direction.NORTHEAST,
        Direction.NORTHWEST: Direction.SOUTHEAST,
        Direction.SOUTHEAST: Direction.NORTHWEST,
    }
    
    current_room = start_room
    
    for d in directions:
        found_next = False
        current_norm = normalize_entity_name(current_room)
        
        # Look for a ConnectionFact connecting current_room in direction d
        for fact in graph.facts:
            if isinstance(fact, ConnectionFact):
                u = normalize_entity_name(fact.location_a.room) if fact.location_a.room else None
                v = normalize_entity_name(fact.location_b.room) if fact.location_b.room else None
                conn_dir = fact.direction
                
                if u == current_norm and conn_dir == d:
                    current_room = fact.location_b.room
                    found_next = True
                    break
                elif v == current_norm and conn_dir and opposite.get(conn_dir) == d:
                    current_room = fact.location_a.room
                    found_next = True
                    break
                    
        if not found_next:
            return None
            
    return current_room

