import json
import os
import sys
import dotenv
from openai import OpenAI

from string import Template
from pydantic_schema import *


dotenv.load_dotenv()

SYSTEM_PROMPT = """
You are extracting structured knowledge from a handover report written in a controlled language for a task handover study. Your output will be used to compare and combine the information content of the report with ground-truth telemetry data.

Your job is to convert each fact expressed in the report (each line) into a structured Fact, and do so faithfully — including uncertainty, vagueness, and partial knowledge. Do not infer facts that are not supported by the report. Do not fill in missing information with guesses.
Output format is a KnowledgeGraph, containing a list of Facts.

# TODO update examples
## Example Fact 1: "lily is to the west then north"
LocationFact(
    entity=Argument(type="named", value="lily"),
    location=Location(type="directional", directions=[Direction.WEST, Direction.NORTH], mode="path"),
    is_partial=False,
    provenance="lily is to the west then north"
)

## Example Fact 2: "someone to the east needs a red potion"
RelationFact(
    predicate=RelationPredicate.NEEDS_POTION,
    subject=Argument(type="existential", value=None, location=Location(type="directional", directions=[Direction.EAST], mode="path")),
    object=Argument(type="named", value="red potion"),
    is_partial=True,
    provenance="someone to the east needs a red potion"
)

## Example Fact 3: "someone to the west has a message for someone"
RelationFact(
    predicate=RelationPredicate.HAS_MESSAGE_FOR,
    subject=Argument(type="existential", location=Location(type="directional", directions=[Direction.WEST], mode="path")),
    target=Argument(type="existential"),
    is_partial=True,
    provenance="someone to the west has a message for someone"
)
"""

USER_PROMPT = """
Convert the following text into a KnowledgeGraph:

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

    input = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": USER_PROMPT + prompt}
    ]

    message = client.responses.parse(
        model=model,
        input = input,
        temperature=temperature,
        text_format = KnowledgeGraph
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

    # text_filename = os.path.join(data_dir, "reports", sys.argv[1] + "_user_report.txt")
    text_filename = os.path.join(data_dir, "analysis", sys.argv[1] + "_report_dsl_output.txt")
    output_filename = os.path.join(data_dir, "processed_output", sys.argv[1] + "_dsl_to_kg_output.json")
    convert_text_to_knowledge_graph(text_filename, output_filename)
