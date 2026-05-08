
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
    for fact in graph.facts:
        if isinstance(fact, LocationFact):
            if fact.entity.type == "named" and fact.entity.value == entity_name:
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
    if constraint.type == "room":
        return target_room == constraint.room
    
    if constraint.type == "directional" and constraint.directions:
        return is_room_in_direction(graph, target_room, reference_room, constraint.directions)
    
    return False

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
    if target_room == source_room:
        return not expected_directions # Empty path matches same room? Or False? Usually False if constraint exists.
        
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
            u = fact.location_a.room
            v = fact.location_b.room
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
                    u = fact.reference.value
                    v = fact.subject.value
                    d = fact.direction
                    adj.setdefault(u, []).append((v, d))
                    # Add reverse edge
                    if d in opposite:
                        adj.setdefault(v, []).append((u, opposite[d]))

    # BFS to find shortest path of directions
    # queue stores (current_room, direction_path_so_far)
    visited = {source_room}
    queue = [(source_room, [])]
    
    while queue:
        curr, path = queue.pop(0)
        
        if curr == target_room:
            # Check if expected_directions is a prefix of path
            if len(expected_directions) > len(path):
                return False
            return path[:len(expected_directions)] == expected_directions
            
        for neighbor, d in adj.get(curr, []):
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append((neighbor, path + [d]))
                    
    return False
