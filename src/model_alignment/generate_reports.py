"""
Read NarrativeView JSON files and send them to ChatGPT 4o-mini via the OpenAI API.
"""

import argparse
import json
import os
import sys

from string import Template

from openai import OpenAI

# Import NarrativeView from the same package layout as craft_narrative_view
from craft_narrative_view import NarrativeView

FULL_REALIZATION_SYSTEM_PROMPT = """
You are generating a clear and well-organized handoff report for a teammate who will continue the game.

Use natural language.
Organize the information logically.
Do not omit information from the structured input.
Do not introduce new facts or strategies.
Do not infer information not explicitly present.
"""

FULL_REALIZATION_USER_PROMPT = Template("""
Generate a clear and well-structured handoff report based on the structured state below.

The report should include sections for:
- Current Player Status
- NPC Patients and Their Needs
- Items and Potions
- Message Requests and Responses
- Explored Locations
- Any Unresolved Inconsistencies

All information in the structured state must be included somewhere in the report.
Use complete sentences and natural language.

Structured state:
$narrativeview
""")

TASK_AWARE_SYSTEM_PROMPT = """
You are generating a handoff report for a teammate who will continue the task.

The primary objective of the task is to fulfill the needs of NPC patients by:
- Delivering required potions
- Carrying request messages to specified NPCs
- Returning response messages to the original requester

Your report should prioritize information that is relevant to completing this objective.

You may briefly mention other explored information if useful for context, but you should emphasize:
- Which patients still need potions
- Which messages are pending delivery
- Which responses need to be returned
- What items are currently held that are relevant to patient needs
- The player’s current location relative to relevant NPCs

Do not introduce new facts.
Do not speculate about information not present in the structured state.
Do not invent strategies beyond what can be logically inferred from the data.
"""

TASK_AWARE_USER_PROMPT = Template("""
Generate a concise and task-focused handoff report for a teammate.

The goal is to fulfill NPC patient needs (potions and message delivery).

Prioritize:
- Outstanding patient needs
- Pending requests and responses
- Relevant inventory items
- NPC locations relevant to completing tasks

De-emphasize or briefly summarize information that is not directly relevant to patient care.

Do not omit critical task-relevant information.
Do not add new facts.

Structured state:
$narrativeview
""")

PROMPT_SETS = {
    "full_realization": (FULL_REALIZATION_SYSTEM_PROMPT, FULL_REALIZATION_USER_PROMPT),
    "task_aware": (TASK_AWARE_SYSTEM_PROMPT, TASK_AWARE_USER_PROMPT),
}

def load_narrative_view(path: str) -> NarrativeView:
    """Load and validate a NarrativeView from a JSON file."""
    with open(path, "r") as f:
        data = json.load(f)
    return NarrativeView.model_validate(data)


def call_chatgpt(prompt: str, user_prompt: Template, narrative_view: NarrativeView) -> str:
    """Send the narrative view as user message to gpt-4o-mini and return the reply."""
    client = OpenAI()
    user_content = user_prompt.substitute(narrativeview=narrative_view.model_dump_json(indent=2))
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0,
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": user_content},
        ],
    )
    return response.choices[0].message.content or ""


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Send NarrativeView JSON to ChatGPT 4o-mini and get a report."
    )
    parser.add_argument(
        "input",
        help=(
            "Input: base name (e.g. 'foo') when DATA_DIR is set, "
            "or path to a NarrativeView .json file."
        ),
    )
    # parser.add_argument(
    #     "-o",
    #     "--output",
    #     metavar="FILE",
    #     help="Write the model response to FILE instead of stdout.",
    # )
    parser.add_argument(
        "--prompt-set",
        choices=("full_realization", "task_aware", "both"),
        default="full_realization",
        help=(
            "Prompt style: exhaustive structured report (full_realization), "
            "task-focused (task_aware), or both API calls in that order."
        ),
    )
    args = parser.parse_args()

    data_dir = os.environ.get("DATA_DIR")
    if data_dir:
        input_path = os.path.join(
            data_dir, "processed_output", args.input + "_narrative_view_output.json"
        )
    else:
        input_path = args.input

    if not os.path.isfile(input_path):
        print(f"Error: input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    narrative_view = load_narrative_view(input_path)
    if args.prompt_set == "both":
        fr_sys, fr_user = PROMPT_SETS["full_realization"]
        ta_sys, ta_user = PROMPT_SETS["task_aware"]
        r1 = call_chatgpt(fr_sys, fr_user, narrative_view)
        r2 = call_chatgpt(ta_sys, ta_user, narrative_view)

        output_path = os.path.join(data_dir, "reports", args.input + "_full_realization_report.txt")
        with open(output_path, "w") as f:
            f.write(r1)
        print(f"Full realization report saved to {output_path}")
        output_path = os.path.join(data_dir, "reports", args.input + "_task_aware_report.txt")
        with open(output_path, "w") as f:
            f.write(r2)
        print(f"Task-aware report saved to {output_path}")
    else:
        sys_p, user_p = PROMPT_SETS[args.prompt_set]
        report = call_chatgpt(sys_p, user_p, narrative_view)
        output_path = os.path.join(data_dir, "reports", args.input + "_" + args.prompt_set + "_report.txt")
        with open(output_path, "w") as f:
            f.write(report)
        print(f"Report saved to {output_path}")

if __name__ == "__main__":
    main()
