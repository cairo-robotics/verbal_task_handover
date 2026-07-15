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
try:
    from src.pipelines.model_alignment.craft_narrative_view import NarrativeView
except ImportError:
    from craft_narrative_view import NarrativeView

FULL_REALIZATION_SYSTEM_PROMPT = """
You are an expert agent generating a comprehensive, highly-structured, and exhaustive handoff report for a teammate who will continue the game.

To maximize extraction accuracy while ensuring completeness, you MUST write the report in a highly organized, bulleted, and structured template. You MUST include ALL known details from the structured input, including player status, all NPC locations, all active and completed patient needs, all message delivery tasks, and all spatial/directional facts.

Your report MUST strictly follow this exact template:

### PLAYER STATUS
- player is in [Room Name]
- player holds [Item Name or "- None"]

### ACTIVE NPC PATIENTS & NEEDS
- [NPC Name] needs a [Potion Color] potion
- [NPC Name] has a message for [Recipient Name]

### COMPLETED ACTIONS & HISTORY
- [NPC Name] has received a [Potion Color] potion
- message delivered from [Sender Name] to [Recipient Name]

### POTION & NPC LOCATIONS
- [Potion Color] potion is in [Room Name]
- [NPC Name] is in [Room Name]

### UNRESOLVED / DIRECTIONAL FACTS
- [Describe any unanchored, directional, or conflicting facts, e.g., "someone to the east needs a red potion"]

---
INSTRUCTIONS:
1. You MUST include every single fact present in the structured state. Do not filter or summarize.
2. Each fact MUST be listed under its appropriate section using the exact bullet point patterns provided (e.g., "[Entity] is in [Room]", "[NPC Name] needs a [Potion Color] potion", "[NPC Name] has received a [Potion Color] potion").
3. Do NOT include any introductory or concluding text. Write only the template sections.
"""

FULL_REALIZATION_USER_PROMPT = Template("""
Generate an exhaustive, structured handoff report based on the provided structured state.

Remember the rules:
- Strictly use the five header sections: "### PLAYER STATUS", "### ACTIVE NPC PATIENTS & NEEDS", "### COMPLETED ACTIONS & HISTORY", "### POTION & NPC LOCATIONS", and "### UNRESOLVED / DIRECTIONAL FACTS".
- Be extremely detailed. Do NOT omit any facts from the narrative view.
- Use the exact bullet-point templates specified to ensure perfect parsing downstream.

Structured state:
$narrativeview
""")

TASK_AWARE_SYSTEM_PROMPT = """
You are an expert agent generating a high-density, task-focused handoff report for a teammate who will continue the game.

The primary objective of the game is to fulfill the needs of NPC patients by:
- Delivering required potions.
- Carrying request messages from patients to specified NPCs.
- Returning response messages to the original requester.

To maximize efficiency and communicative compression, you MUST write the report in a highly concise, telegraphic, and structured format. Completely omit conversational padding, pleasantries, and descriptions of past completed events (e.g., do not list completed potion deliveries or past messages already delivered).

Your report MUST strictly follow this exact template:

### OUTSTANDING NEEDS
- [NPC Name] needs a [Potion Color] potion
- [NPC Name] has a message for [Recipient Name]

### POTION & NPC LOCATIONS
- [Potion Color] potion is in [Room Name]
- [NPC Name] is in [Room Name]
- player is in [Room Name]

### UNRESOLVED / DIRECTIONAL FACTS
- [Describe any unanchored or directional facts, e.g., "someone to the east needs a red potion"]

---
INSTRUCTIONS:
1. Under "### OUTSTANDING NEEDS", list ONLY NPCs that currently have active, unfinished tasks. If there are none, write "- None".
   - Note: Refer to messages, requests, and responses all generically as "a message" to fit the template (e.g., "Steve has a message for John").
2. Under "### POTION & NPC LOCATIONS", list the location of the player, all potions found in storage/rooms, and the locations of ALL patient NPCs encountered/visited so far (even if they currently have no outstanding needs). Each location MUST be on its own bullet point using the exact "[Entity] is in [Room]" pattern.
3. Do NOT include any introductory or concluding text. Write only the template sections.
4. Do NOT include past completed actions or history.
"""

TASK_AWARE_USER_PROMPT = Template("""
Generate a high-density, task-focused handoff report based on the provided structured state.

Remember the rules:
- Strictly use the three header sections: "### OUTSTANDING NEEDS", "### POTION & NPC LOCATIONS", and "### UNRESOLVED / DIRECTIONAL FACTS".
- Be extremely concise. Avoid complete conversational sentences. Use the exact bullet-point format specified.
- List ALL encountered NPCs and potions in the locations section, even if they have no active needs.
- Omit all past completed events.

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
    model = os.environ.get("GPT_MODEL", "gpt-4.1-mini")
    kwargs = {
        "model": model,
        "input": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": user_content},
        ],
    }
    if "sol" in model or "gpt-5" in model or "o1" in model or "o3" in model:
        kwargs["reasoning"] = {"effort": "medium"}
    else:
        kwargs["temperature"] = 0
    response = client.responses.create(**kwargs)
    return response.output_text


def main() -> None:
    import dotenv
    dotenv.load_dotenv()

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
            data_dir, "processed_output", "kg", args.input + "_narrative_view.json"
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
