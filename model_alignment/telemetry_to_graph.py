import re
import os
import sys
from typing import List, Dict, Tuple
from collections import defaultdict

import dotenv
dotenv.load_dotenv()

from pydantic_schema import *

ALL_NPCS = [
    "lily", "oliver", "nick", "marie", "guy",
    "eliza", "lola", "donna", "steve", "brittany", "john"
]

ALL_LOCATION_KEYWORDS = [
    "room", "hallway", "lounge", "storage"
]


# -------------------------------------------------
# Utility: Simple Entity Type Inference
# -------------------------------------------------

def infer_entity_type(entity_id: str) -> EntityType:
    entity_id = entity_id.lower()

    if any(keyword in entity_id for keyword in ALL_LOCATION_KEYWORDS):
        return EntityType.LOCATION
    if entity_id in ["player"] or entity_id in ALL_NPCS:
        return EntityType.AGENT
    if "potion" in entity_id:
        return EntityType.ITEM
    if "request" in entity_id or "response" in entity_id:
        return EntityType.MESSAGE

    return EntityType.ITEM  # Default to ITEM if unsure

# -------------------------------------------------
# Telemetry Parsing
# -------------------------------------------------

def parse_line(line: str) -> Tuple[str, str]:
    """
    Splits: "{timestamp} - event text"
    """
    timestamp, event_text = line.split(" - ", 1)
    return timestamp.strip(), event_text.strip()


# -------------------------------------------------
# Main Conversion Function
# -------------------------------------------------

def convert_telemetry_to_kg(file_path: str) -> KnowledgeGraphExtraction:
    entities: Dict[str, Entity] = {}
    events: List[Event] = []
    state_relations: List[StateRelation] = []
    spatial_relations: List[SpatialRelation] = []

    event_counter = 0
    player_location = "room0"
    held_item = None

    # import pdb; pdb.set_trace()  # DEBUGGING

    with open(file_path, "r") as f:
        for raw_line in f:
            raw_line = raw_line.strip()
            if not raw_line:
                continue

            timestamp, text = parse_line(raw_line)
            text_lower = text.lower()

            event_id = f"event_{event_counter}"
            event_counter += 1

            # -----------------------------------------
            # ENTER NEW LOCATION
            # -----------------------------------------
            match = re.match(r"room entered: (\w+) to (\w+)", text_lower)
            if match:
                direction, location = match.groups()
                actor = "player"

                # Register entities
                for ent in [actor, location]:
                    if ent not in entities:
                        entities[ent] = Entity(
                            id=ent,
                            type=infer_entity_type(ent)
                        )

                spatial_relations.append(SpatialRelation(
                    subject=player_location,
                    relation=SpatialRelationType(f"{direction}_of"),
                    object=location,
                    confidence=ConfidenceLevel.HIGH
                ))
                spatial_relations.append(SpatialRelation(
                    subject=location,
                    relation=SpatialRelationType(f"{invert_direction[direction]}_of"),
                    object=player_location,
                    confidence=ConfidenceLevel.HIGH
                ))

                player_location = location

                continue

            # -----------------------------------------
            # OBTAIN
            # -----------------------------------------
            match = re.match(r"item obtained: (.+)", text_lower)
            if match:
                item = match.groups()[0]
                item = item.replace(" ", "_")
    
                actor = "player"
                for ent in [actor, item]:
                    if ent not in entities:
                        entities[ent] = Entity(
                            id=ent,
                            type=infer_entity_type(ent)
                        )

                events.append(Event(
                    event_id=event_id,
                    event_type=EventType.OBTAIN,
                    participants={"actor": actor, "object": item},
                    timestamp=timestamp,
                    confidence=ConfidenceLevel.HIGH
                ))

                if entities[item].type == EntityType.ITEM:
                    # log the item as being found in this location
                    state_relations.append(StateRelation(
                        subject=item,
                        relation=RelationType.LOCATED_IN,
                        object=player_location,
                        confidence=ConfidenceLevel.HIGH
                    ))

                    # also log as held item
                    held_item = item

                if entities[item].type == EntityType.MESSAGE:
                    # requests and responses are permanently owned by the player
                    state_relations.append(StateRelation(
                        subject=item,
                        relation=RelationType.IN_INVENTORY_OF,
                        object=actor,
                        confidence=ConfidenceLevel.HIGH
                    ))

                continue

            # -----------------------------------------
            # TALK_TO
            # -----------------------------------------
            match = re.match(r"npc interact: (\w+)", text_lower)
            if match:
                target = match.groups()[0]
                actor = "player"

                for ent in [actor, target]:
                    if ent not in entities:
                        entities[ent] = Entity(
                            id=ent,
                            type=infer_entity_type(ent)
                        )

                events.append(Event(
                    event_id=event_id,
                    event_type=EventType.TALK_TO,
                    participants={"actor": actor, "target": target},
                    timestamp=timestamp,
                    confidence=ConfidenceLevel.HIGH
                ))

                # NPCs are always located in the same room as the player when talked to
                state_relations.append(StateRelation(
                    subject=target,
                    relation=RelationType.LOCATED_IN,
                    object=player_location,
                    confidence=ConfidenceLevel.HIGH
                ))

                continue

            # -----------------------------------------
            # GAVE ITEM
            # -----------------------------------------
            match = re.match(r"gave item to npc: (\w+) (\w+)", text_lower)
            if match:
                item, target = match.groups()
                actor = "player"

                for ent in [actor, target, item]:
                    if ent not in entities:
                        entities[ent] = Entity(
                            id=ent,
                            type=infer_entity_type(ent)
                        )

                events.append(Event(
                    event_id=event_id,
                    event_type=EventType.GIVE,
                    participants={"actor": actor, "target": target, "object": item},
                    timestamp=timestamp,
                    confidence=ConfidenceLevel.HIGH
                ))

                # NPCs are always located in the same room as the player when given an item
                state_relations.append(StateRelation(
                    subject=target,
                    relation=RelationType.LOCATED_IN,
                    object=player_location,
                    confidence=ConfidenceLevel.HIGH
                ))

                continue

    return KnowledgeGraphExtraction(
        entities=list(entities.values()),
        events=events,
        state_relations=state_relations,
        spatial_relations=spatial_relations
    )

def create_kg_json(telemetry_file: str, output_file: str):
    kg = convert_telemetry_to_kg(telemetry_file)
    with open(output_file, 'w') as f:
        f.write(kg.model_dump_json(indent=2))


if __name__ == "__main__":
    # telemetry_file = "telemetry/ari_test.txt"
    # output_file = "kg_outputs/ari_test_kg.json"
    # create_kg_json(telemetry_file, output_file)

    data_dir = os.environ.get("DATA_DIR")

    text_filename = os.path.join(data_dir, "telemetry", sys.argv[1] + ".txt")
    output_filename = os.path.join(data_dir, "processed_output", sys.argv[1] + "_telemetry_to_kg_output.json")
    create_kg_json(text_filename, output_filename)