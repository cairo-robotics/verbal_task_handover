"""
Read raw telemetry and participant user report from disk and send them to gpt-4o-mini
(Chat Completions) for handover report generation, bypassing NarrativeView / graph pipeline.

Requires DATA_DIR. Participant id is the positional argument; optional --telemetry and
--user-report override default paths under DATA_DIR.

Very long telemetry is sent as-is (no truncation); may approach model context limits.

Prompts: Copy the same structural intent as FULL_REALIZATION_* and TASK_AWARE_* in generate_reports.py, but:
Replace references to “structured state” / NarrativeView with two labeled blocks: raw telemetry log and participant-written report.
Keep the same behavioral constraints: natural language, no new facts beyond what appears in those sources, task-aware variant still emphasizes patient needs / messages / inventory / locations.
Use string.Template with $telemetry and $user_report placeholders (escape $ in the template body where needed, or use .replace / f-strings for the two variables only—whichever matches local style).
"""

import argparse
import os
import sys
from string import Template

from openai import OpenAI

FULL_REALIZATION_SYSTEM_PROMPT = """
You are generating a clear and well-organized handoff report for a teammate who will continue the game.

Use natural language.
Organize the information logically.
Do not omit information from the inputs below.
Do not introduce new facts or strategies.
Do not infer information not explicitly present.
"""

FULL_REALIZATION_USER_PROMPT = Template("""
Generate a clear and well-structured handoff report based on the raw telemetry log and the
participant-written report below.

The report should include sections for:
- Current Player Status
- NPC Patients and Their Needs
- Items and Potions
- Message Requests and Responses
- Explored Locations
- Any Unresolved Inconsistencies

All information that appears in those two sources must be included somewhere in the report.
Use complete sentences and natural language.

--- Raw telemetry log ---
$telemetry

--- Participant-written report ---
$user_report
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
Do not speculate about information not present in the inputs.
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

--- Raw telemetry log ---
$telemetry

--- Participant-written report ---
$user_report
""")

PROMPT_SETS = {
    "full_realization": (FULL_REALIZATION_SYSTEM_PROMPT, FULL_REALIZATION_USER_PROMPT),
    "task_aware": (TASK_AWARE_SYSTEM_PROMPT, TASK_AWARE_USER_PROMPT),
}


def call_chatgpt(system_prompt: str, user_prompt: Template, telemetry: str, user_report: str) -> str:
    client = OpenAI()
    user_content = user_prompt.substitute(telemetry=telemetry, user_report=user_report)
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
    )
    return response.choices[0].message.content or ""


def read_text(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Send raw telemetry + participant user report to ChatGPT 4o-mini (ablation; no NarrativeView)."
        )
    )
    parser.add_argument(
        "id",
        help="Participant id (e.g. 302); used for default input paths and output filenames under DATA_DIR.",
    )
    parser.add_argument(
        "--telemetry",
        metavar="PATH",
        help="Override telemetry file (default: DATA_DIR/telemetry/<id>.txt).",
    )
    parser.add_argument(
        "--user-report",
        metavar="PATH",
        help="Override user report file (default: DATA_DIR/reports/<id>_user_report.txt).",
    )
    parser.add_argument(
        "--prompt-set",
        choices=("full_realization", "task_aware", "both"),
        default="full_realization",
        help=(
            "Prompt style: exhaustive report (full_realization), task-focused (task_aware), "
            "or both API calls in that order."
        ),
    )
    args = parser.parse_args()

    data_dir = os.environ.get("DATA_DIR")
    if not data_dir:
        print("Error: DATA_DIR must be set.", file=sys.stderr)
        sys.exit(1)

    participant_id = args.id
    telemetry_path = args.telemetry or os.path.join(data_dir, "telemetry", f"{participant_id}.txt")
    user_report_path = args.user_report or os.path.join(
        data_dir, "reports", f"{participant_id}_user_report.txt"
    )

    if not os.path.isfile(telemetry_path):
        print(f"Error: telemetry file not found: {telemetry_path}", file=sys.stderr)
        sys.exit(1)
    if not os.path.isfile(user_report_path):
        print(f"Error: user report file not found: {user_report_path}", file=sys.stderr)
        sys.exit(1)

    telemetry_text = read_text(telemetry_path)
    user_report_text = read_text(user_report_path)

    reports_dir = os.path.join(data_dir, "reports")
    os.makedirs(reports_dir, exist_ok=True)

    if args.prompt_set == "both":
        fr_sys, fr_user = PROMPT_SETS["full_realization"]
        ta_sys, ta_user = PROMPT_SETS["task_aware"]
        r1 = call_chatgpt(fr_sys, fr_user, telemetry_text, user_report_text)
        r2 = call_chatgpt(ta_sys, ta_user, telemetry_text, user_report_text)

        out_fr = os.path.join(
            reports_dir, f"{participant_id}_full_realization_raw_ablation_report.txt"
        )
        out_ta = os.path.join(reports_dir, f"{participant_id}_task_aware_raw_ablation_report.txt")
        with open(out_fr, "w", encoding="utf-8") as f:
            f.write(r1)
        print(f"Full realization (raw ablation) report saved to {out_fr}")
        with open(out_ta, "w", encoding="utf-8") as f:
            f.write(r2)
        print(f"Task-aware (raw ablation) report saved to {out_ta}")
    else:
        sys_p, user_p = PROMPT_SETS[args.prompt_set]
        report = call_chatgpt(sys_p, user_p, telemetry_text, user_report_text)
        suffix = "full_realization" if args.prompt_set == "full_realization" else "task_aware"
        output_path = os.path.join(reports_dir, f"{participant_id}_{suffix}_raw_ablation_report.txt")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"Report saved to {output_path}")


if __name__ == "__main__":
    main()
