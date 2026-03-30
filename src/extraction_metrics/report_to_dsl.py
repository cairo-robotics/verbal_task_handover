import argparse
import os
import sys

from openai import OpenAI

from extraction_paths import dsl_output_path_for_report_arg, normalize_report_arg, reports_file

try:
    import dotenv

    dotenv.load_dotenv()
except ImportError:
    pass

DEFAULT_MODEL = "gpt-4o-mini"

PROMPT = """
You are an information extraction system.

Your task is to extract structured facts from a narrative. Extract all facts that are explicitly stated in the text.

Return the facts using a controlled language with STRICT formatting rules. Each fact should be on a new line.

---

OUTPUT FORMAT RULES:

- Use ONLY the exact templates shown below
- Use ONLY lowercase letters
- Do NOT include punctuation
- Do NOT include extra words
- Do NOT paraphrase templates
- Do NOT infer unstated facts
- Do NOT include duplicate facts

---

FACT TEMPLATES:

# Potions
<patient> needs <potion_color> potion
<potion_color> potion delivered to <patient>

# Messaging
<patient> requested message from <npc>
message delivered from <patient> to <npc>
<npc> responded to <patient>
response delivered from <npc> to <patient>

# Locations
<npc> is in <room>
<potion_color> potion is in <room>
player is in <room>

# Inventory
player has <item>

---

EXAMPLE:

Input:
"Lily asked the wizard for help. The wizard replied. Lily is waiting in room1."

Output:
lily requested message from wizard
wizard responded to lily
player is in room1

---

Now extract facts from the following text:

{INPUT_TEXT}
"""


def _normalize_dsl_output(raw_output: str) -> str:
    """Normalize model output for stable line-based downstream use."""
    lines = [line.strip() for line in raw_output.strip().splitlines() if line.strip()]
    return "\n".join(lines)


def extract_dsl(user_prompt: str, *, model: str = DEFAULT_MODEL) -> str:
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    response = client.responses.create(
        model=model,
        input=[
            {"role": "user", "content": PROMPT.replace("{INPUT_TEXT}", user_prompt)},
        ],
        temperature=0,
    )
    text = response.output_text
    if not text or not text.strip():
        raise RuntimeError(
            "Model returned empty text output; "
            f"refusal={getattr(response, 'refusal', None)!r}"
        )
    return _normalize_dsl_output(text)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract line-based DSL facts from a report under DATA_DIR/reports via OpenAI."
    )
    parser.add_argument(
        "report_file",
        help=(
            "Filename or path under reports/ (optional ``reports/`` prefix), "
            "e.g. 302_user_report.txt or reports/302_user_report.txt"
        ),
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"OpenAI model name (default: {DEFAULT_MODEL}).",
    )
    args = parser.parse_args()

    data_dir = os.environ.get("DATA_DIR")
    if not data_dir:
        print("Error: DATA_DIR must be set.", file=sys.stderr)
        sys.exit(1)

    if not os.environ.get("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY must be set.", file=sys.stderr)
        sys.exit(1)

    report_rel = normalize_report_arg(args.report_file)
    try:
        report_path = reports_file(data_dir, report_rel)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    if not report_path.is_file():
        print(f"Error: report file not found: {report_path}", file=sys.stderr)
        sys.exit(1)

    report_text = report_path.read_text(encoding="utf-8")

    try:
        dsl_text = extract_dsl(report_text, model=args.model)
    except Exception as exc:
        print(f"Error: failed to extract DSL: {exc}", file=sys.stderr)
        sys.exit(1)

    output_path = dsl_output_path_for_report_arg(data_dir, args.report_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(dsl_text + "\n", encoding="utf-8")
    print(f"DSL output written to {output_path}")


if __name__ == "__main__":
    main()