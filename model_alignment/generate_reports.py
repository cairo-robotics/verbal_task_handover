"""
Read NarrativeView JSON files and send them to ChatGPT 4o-mini via the OpenAI API.
"""

import argparse
import json
import os
import sys

from openai import OpenAI

# Import NarrativeView from the same package layout as craft_narrative_view
from craft_narrative_view import NarrativeView

SYSTEM_PROMPT = "System prompt goes here"


def load_narrative_view(path: str) -> NarrativeView:
    """Load and validate a NarrativeView from a JSON file."""
    with open(path, "r") as f:
        data = json.load(f)
    return NarrativeView.model_validate(data)


def call_chatgpt(narrative_view: NarrativeView) -> str:
    """Send the narrative view as user message to gpt-4o-mini and return the reply."""
    client = OpenAI()
    user_content = narrative_view.model_dump_json(indent=2)
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
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
    parser.add_argument(
        "-o",
        "--output",
        metavar="FILE",
        help="Write the model response to FILE instead of stdout.",
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
    report = call_chatgpt(narrative_view)

    if args.output:
        with open(args.output, "w") as f:
            f.write(report)
    else:
        print(report)


if __name__ == "__main__":
    main()
