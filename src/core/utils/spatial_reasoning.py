
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
        # Check if target_room is in one of the directions from reference_room
        for direction in constraint.directions:
            if is_room_in_direction(graph, target_room, reference_room, direction):
                return True
    
    return False

def is_room_in_direction(
    graph: KnowledgeGraph, 
    target_room: str, 
    source_room: str, 
    direction: Direction
) -> bool:
    """
    Check if target_room is in the given direction from source_room.
    Uses ConnectionFacts and SpatialFacts.
    """
    if target_room == source_room:
        return False
        
    # Build a simple adjacency map for directions
    # (source, direction) -> set of targets
    adj: Dict[Tuple[str, Direction], Set[str]] = {}
    
    for fact in graph.facts:
        if isinstance(fact, ConnectionFact):
            u = fact.location_a.room
            v = fact.location_b.room
            d = fact.direction
            if u and v and d:
                adj.setdefault((u, d), set()).add(v)
        elif isinstance(fact, SpatialFact):
            if fact.type == SpatialRelationType.RELATIVE:
                if (fact.subject.type == "named" and fact.subject.value and 
                    fact.reference and fact.reference.type == "named" and fact.reference.value):
                    u = fact.reference.value
                    v = fact.subject.value
                    d = fact.direction
                    adj.setdefault((u, d), set()).add(v)

    # Simplified reachability: what rooms can be reached by going in 'allowed' directions
    # e.g. for WEST, allowed are WEST, NORTHWEST, SOUTHWEST.
    allowed_dirs = {direction}
    if direction == Direction.WEST:
        allowed_dirs.update({Direction.NORTHWEST, Direction.SOUTHWEST})
    elif direction == Direction.EAST:
        allowed_dirs.update({Direction.NORTHEAST, Direction.SOUTHEAST})
    elif direction == Direction.NORTH:
        allowed_dirs.update({Direction.NORTHWEST, Direction.NORTHEAST})
    elif direction == Direction.SOUTH:
        allowed_dirs.update({Direction.SOUTHWEST, Direction.SOUTHEAST})

    visited = {source_room}
    queue = [source_room]
    
    while queue:
        curr = queue.pop(0)
        if curr == target_room:
            return True
            
        for d in allowed_dirs:
            for neighbor in adj.get((curr, d), []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)
                    
    return False
