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
# pyrefly: ignore [missing-import]
from src.pipelines.model_alignment.generate_reports import TASK_AWARE_SYSTEM_PROMPT

TASK_AWARE_USER_PROMPT = Template("""
Generate a high-density, task-focused handoff report based on the provided telemetry and user report.

Remember the rules:
- Strictly use the three header sections: "### OUTSTANDING NEEDS", "### POTION & NPC LOCATIONS", and "### UNRESOLVED / DIRECTIONAL FACTS".
- Be extremely concise. Avoid complete conversational sentences. Use the exact bullet-point format specified.
- List ALL encountered NPCs and potions in the locations section, even if they have no active needs.
- Omit all past completed events.

--- Participant-written report ---
$user_report

--- Raw telemetry log ---
$telemetry
""")

PROMPT_SETS = {
    # "full_realization": (FULL_REALIZATION_SYSTEM_PROMPT, FULL_REALIZATION_USER_PROMPT),
    "task_aware": (TASK_AWARE_SYSTEM_PROMPT, TASK_AWARE_USER_PROMPT),
}

def _collect_pids(args: argparse.Namespace) -> list[str]:
    # from_file: list[str] = []
    # if args.pids_file is not None:
    #     text = args.pids_file.read_text(encoding="utf-8")
    #     for line in text.splitlines():
    #         s = line.strip()
    #         if s and not s.startswith("#"):
    #             from_file.append(s)
    # combined = list(dict.fromkeys(from_file + args.pids))  # stable dedupe
    combined = args.pids
    if not combined:
        raise SystemExit("No participant IDs: pass pids as arguments and/or use --pids-file.")
    return combined

from src.core.utils.experiment_logging import log_message, get_log_file, log_api_call

def call_chatgpt(system_prompt: str, user_prompt: Template, telemetry: str, user_report: str) -> str:
    model = os.environ.get("GPT_MODEL", "gpt-5.6-sol")
    user_content = user_prompt.substitute(telemetry=telemetry, user_report=user_report)

    kwargs = {
        "model": model,
        "input": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
    }
    if "sol" in model or "gpt-5" in model or "o1" in model or "o3" in model:
        kwargs["reasoning"] = {"effort": "medium"}
    else:
        kwargs["temperature"] = 0
        
    log_api_call("openai", model, kwargs)

    if os.environ.get("DRY_RUN") == "1":
        log_message("Mock API Call (DRY RUN) - generate_reports_raw_ablation.py")
        return "### OUTSTANDING NEEDS\n- lily needs a gold potion\n\n### POTION & NPC LOCATIONS\n- lily is in room 1\n- player is in room 1\n\n### UNRESOLVED / DIRECTIONAL FACTS\n- None"
        
    client = OpenAI()
    response = client.responses.create(**kwargs)
    return response.output_text


def read_text(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


def main() -> None:
    get_log_file()
    import dotenv
    dotenv.load_dotenv()
    parser = argparse.ArgumentParser(
        description=(
            "Send raw telemetry + participant user report to ChatGPT 4o-mini (ablation; no NarrativeView)."
        )
    )
    parser.add_argument(
        "pids",
        nargs="*",
        help="Participant IDs (e.g. 302 303). Combine with --pids-file.",
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
        "--data-dir",
        metavar="PATH",
        help="Override the data directory path. Default is the DATA_DIR environment variable.",
    )

    args = parser.parse_args()
    pids = _collect_pids(args)

    data_dir = args.data_dir or os.environ.get("DATA_DIR")
    if not data_dir:
        print("Error: DATA_DIR must be set.", file=sys.stderr)
        sys.exit(1)

    for pid in pids:
        telemetry_path = args.telemetry or os.path.join(data_dir, "telemetry", f"{pid}.txt")
        user_report_path = args.user_report or os.path.join(
            data_dir, "reports", f"{pid}_user_report.txt"
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

        model_suffix = ""
        try:
            from src.core.utils.extraction_paths import get_current_model_suffix
            if os.environ.get("GPT_MODEL") or os.environ.get("MODEL"):
                model_suffix = f"_{get_current_model_suffix()}"
        except ImportError:
            pass

        sys_p, user_p = PROMPT_SETS["task_aware"]
        report = call_chatgpt(sys_p, user_p, telemetry_text, user_report_text)
        suffix = "task_aware"
        output_path = os.path.join(reports_dir, f"{pid}_{suffix}_raw_ablation_report{model_suffix}.txt")
        with open(output_path, "w", encoding="utf-8") as f:
                f.write(report)
        print(f"Report saved to {output_path}")


if __name__ == "__main__":
    main()
