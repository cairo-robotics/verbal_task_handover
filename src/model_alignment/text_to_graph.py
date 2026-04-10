import json
import os
import sys
import dotenv
from openai import OpenAI

from pydantic_schema import *


dotenv.load_dotenv()

# ----------------------------
# Prompt & model interaction
# ----------------------------

def _enum_class_prompt_block(enum_cls) -> str:
    """Serialize enum members for the system prompt; keeps prompt aligned with pydantic_schema."""
    lines = [f"class {enum_cls.__name__}(str, Enum):"]
    for member in enum_cls:
        lines.append(f'    {member.name} = "{member.value}"')
    return "\n".join(lines)


_KG_ENUM_CLASSES = (
    EntityType,
    EventType,
    RelationType,
    SpatialRelationType,
    ConfidenceLevel,
)

KNOWLEDGE_GRAPH_PROMPT = (
    """
You are an AI assistant tasked with converting written descriptions of a game state into structured JSON representing the entities, events, and state relations in the game world.

Use only the allowed enum values where specified in the given schema. If certain information is not present in the text, you can omit that field or set it to null:

"""
    + "\n\n".join(_enum_class_prompt_block(cls) for cls in _KG_ENUM_CLASSES)
    + """

For RelationType intended_for: use a Message/Request/Response entity as the subject and the recipient agent's id as the object when the text states who the message is for.
"""
)


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

    text_filename = os.path.join(data_dir, "reports", sys.argv[1] + "_user_report.txt")
    output_filename = os.path.join(data_dir, "processed_output", sys.argv[1] + "_text_to_kg_output.json")
    convert_text_to_knowledge_graph(text_filename, output_filename)
