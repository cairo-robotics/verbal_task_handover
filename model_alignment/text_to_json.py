from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from enum import Enum
import json
import os
import sys
import dotenv
from openai import OpenAI

dotenv.load_dotenv()

# ----------------------------
# Enums
# ----------------------------

class EntityType(str, Enum):
    AGENT = "Agent"
    LOCATION = "Location"
    ITEM = "Item"
    OBJECT = "Object"

class EventType(str, Enum):
    ENTER = "enter"
    OBTAIN = "obtain"
    DROP = "drop"
    TALK_TO = "talk_to"
    GIVE = "give"

class RelationType(str, Enum):
    IN_INVENTORY_OF = "in_inventory_of"
    LOCATED_IN = "located_in"
    REQUIRES = "requires"

class ConfidenceLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# ----------------------------
# Core Models
# ----------------------------

class Entity(BaseModel):
    id: str = Field(..., description="Unique identifier for the entity")
    type: EntityType

class Participants(BaseModel):
    actor: Optional[str] = None
    object: Optional[str] = None
    target: Optional[str] = None

class Event(BaseModel):
    event_id: str = Field(..., description="Unique identifier for the event")
    event_type: EventType

    participants: Participants

    location: Optional[str] = Field(
        None,
        description="Location where the event occurred"
    )

    timestamp: Optional[str] = Field(
        None,
        description="Time at which the event occurred"
    )

    confidence: ConfidenceLevel

class StateRelation(BaseModel):
    subject: str
    relation: RelationType
    object: str
    confidence: ConfidenceLevel

class KnowledgeGraphExtraction(BaseModel):
    entities: List[Entity]
    events: List[Event]
    state_relations: List[StateRelation]


# ----------------------------
# Prompt & model interaction
# ----------------------------

KNOWLEDGE_GRAPH_PROMPT = """
You are an AI assistant tasked with converting written descriptions of a game state into structured JSON representing the entities, events, and state relations in the game world.

Use only the allowed enum values where specified in the given schema. If certain information is not present in the text, you can omit that field or set it to null:

class EntityType(str, Enum):
    AGENT = "Agent"
    LOCATION = "Location"
    ITEM = "Item"
    OBJECT = "Object"

class EventType(str, Enum):
    ENTER = "enter"
    OBTAIN = "obtain"
    DROP = "drop"
    TALK_TO = "talk_to"
    GIVE = "give"

class RelationType(str, Enum):
    IN_INVENTORY_OF = "in_inventory_of"
    LOCATED_IN = "located_in"
    REQUIRES = "requires"

class ConfidenceLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
"""

def convert_text_to_knowledge_graph(text_filename, output_filename):
    try:
        with open(text_filename, 'r') as file:
            prompt = file.read()
    except FileNotFoundError:
        print(f"File {text_filename} not found.")
        return

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    model = "gpt-4o-mini"
    temperature = 0

    message = client.responses.parse(
        model=model,
        input = [
            {"role": "system", "content": KNOWLEDGE_GRAPH_PROMPT},
            {"role": "user", "content": prompt}
        ],
        temperature=temperature,
        text_format = KnowledgeGraphExtraction
    )

    print(message)
    message = message.output_parsed

    if message:
        with open(output_filename, 'w') as output_file:
            output_file.write(json.dumps(message.model_dump(), indent=2))
    else:
        print("Failed to parse response.")
        print(message.refusal)


if __name__ == "__main__":
    data_dir = os.environ.get("DATA_DIR")

    text_filename = os.path.join(data_dir, "reports", sys.argv[1])
    output_filename = os.path.join(data_dir, "processed_output", sys.argv[1] + "_text_to_kg_output.json")
    convert_text_to_knowledge_graph(text_filename, output_filename)