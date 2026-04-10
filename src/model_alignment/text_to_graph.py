import json
import os
import sys
import dotenv
from openai import OpenAI

from string import Template
from pydantic_schema import *


dotenv.load_dotenv()

SYSTEM_PROMPT = """
You are extracting structured knowledge from a handover report written by a human participant in a task handover study. Your output will be used to compare and combine the information content of the report with ground-truth telemetry data.

Your job is to extract every fact the reporter states or implies about the current task state, and represent it faithfully — including uncertainty, vagueness, and partial knowledge. Do not infer facts that are not supported by the report. Do not fill in missing information with guesses.

## Entities in this task domain
The task involves the following entity types:
- Agents: named NPCs (e.g. "lily", "steve", "john") located in rooms around the map
- Items: colored potions (e.g. "gold_potion", "red_potion") and message objects (e.g. "request_from_steve", "response_from_john")
- The player, referred to as "player"
- Locations: rooms, referred to by ID (e.g. "room_3") or directional path from origin (e.g. ["west", "north"])

## Task structure
Tasks follow a three-step chain:
1. A patient NPC requires a specific colored potion to be delivered to them
2. That NPC gives the player a request object to deliver to a secondary NPC
3. The secondary NPC gives the player a response object to bring back to the original patient

Not all steps will be mentioned in every report. Represent what is stated; leave the rest absent.

## Extraction rules

**Named vs. existential arguments**
- Use type="entity" with the canonical name when the reporter names an entity directly (normalize to lowercase with underscores, e.g. "gold_potion", "lily")
- Use type="existential" when the reporter refers to an entity without naming it (e.g. "someone in the east wing", "a person"). Populate as many constraint fields as the report supports — entity_type, location, role, properties, plurality
- Use type="location" for room arguments

**Confidence**
- Use "certain" when the reporter states a fact directly and without hedging
- Use "inferred" when the reporter hedges (e.g. "I think", "I believe", "maybe"), or when you are inferring a fact that is implied but not stated (e.g. a task is "pending" because the reporter says they didn't finish it)
- Use "contradicted" only during graph merging — do not assign it during report extraction

**Task status**
- Use "pending" when the reporter indicates a task has not been started or was left unfinished
- Use "in_progress" when the reporter indicates they began a task but did not complete it
- Use "complete" when the reporter states a task is done
- When status must be inferred from context (e.g. "I could not attend to"), set status_confidence="inferred"

**Task IDs**
- Assign task_id values of the form "task_<initiator>_<brief_descriptor>", e.g. "task_lily_potion" or "task_steve_john"
- For fully existential initiators, use "task_unknown_<location>_<index>", e.g. "task_unknown_west_1"

**Plurality**
- Set plurality=True on an existential when the reporter uses plural language ("people", "some patients") indicating an underspecified set rather than a single unknown entity

**What not to do**
- Do not invent entity names or room IDs not supported by the report
- Do not split a vague plural claim into multiple individual tasks — represent it as one Task with a plural existential initiator
- Do not assign confidence="certain" to status values you had to infer from context
- Do not create a HeldBy relation unless the report gives clear evidence of current possession; implied past possession is not enough

## Example 1: Named entity with inferred task status
Input fragment: "Lily needs a gold potion."
Output fragment: Task(task_id="task_lily_potion",
                        initiator=Argument(type="entity", value="lily"),
                        status="pending", status_confidence="inferred", requirements=[TaskRequirement(condition_type="item_delivery", condition_value=Argument(type="entity", value="gold_potion"), target=Argument(type="entity", value="lily"), confidence="inferred")])

"""

USER_PROMPT = Template("""
Extract structured knowledge from the following text:
<report>
{INPUT_TEXT}
</report>
""")

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
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": USER_PROMPT.substitute(INPUT_TEXT=prompt)}
        ],
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

    text_filename = os.path.join(data_dir, "reports", sys.argv[1] + "_user_report.txt")
    output_filename = os.path.join(data_dir, "processed_output", sys.argv[1] + "_text_to_kg_output.json")
    convert_text_to_knowledge_graph(text_filename, output_filename)
