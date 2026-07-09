import argparse
import os
import sys

from openai import OpenAI

try:
    from src.core.utils.extraction_paths import dsl_output_path_for_report_arg, normalize_report_arg, reports_file
except ImportError:
    # pyrefly: ignore [missing-import]
    from extraction_paths import dsl_output_path_for_report_arg, normalize_report_arg, reports_file

try:
    import dotenv

    dotenv.load_dotenv()
except ImportError:
    pass

DEFAULT_MODEL = "gpt-4.1-mini"

PROMPT = """
You are an information extraction system.

Your task is to extract structured facts from a handoff report about a game task. Extract ONLY concrete state facts that are explicitly stated in the text (outstanding needs, locations, messaging, and completed past events).

Return the facts using a controlled language with STRICT formatting rules. Each fact should be on a new line.
Do not include information that cannot fit in this format.

---

STRICT OUTPUT RULES:

1. **Exact Templates and Verbs Only**: Every line of the output MUST be an exact instantiation of one of the defined templates below. Do NOT use custom verbs (like 'requires', 'wanted', 'contains', 'located'). You MUST map them to the allowed template verbs.
   - Map 'requires', 'wants', 'wanted', 'demands', 'requests' -> **'needs'**
   - Map 'contains', 'has', 'holds', 'placed in', 'located in' -> **'is in'** (for storage) or **'is to the'** (for directions)
2. **Room Type Disambiguation**:
   - Rooms named 'room 1', 'room 2', 'room 3', 'room 4', 'room 5' are patient rooms. A listing like 'room 1 (gold)' means: **'room 1 needs a gold potion'** (do NOT use 'is in').
   - Rooms named 'storage 1', 'storage room 2', 'lounge 1', etc., are storage/lounge areas. A listing like 'storage room 1 (red, gold)' means: **'red potion is in storage room 1'** and **'gold potion is in storage room 1'**.
3. **Ignore Gameplay Strategy/Advice**: Ignore advice, gameplay instructions, or general strategies (e.g. 'reduced trips', 'remember potion color', 'deliver then get message'). ONLY extract concrete state facts (e.g., locations, needs, message history).
4. **No Plural Subjects or Objects**: Do NOT output plurals like 'npcs', 'potions', 'patients', or 'people'. You must map them to singular existential terms:
   - 'npcs', 'people', or 'patients' -> 'someone' (e.g., 'someone is to the north')
   - 'potions' -> 'a potion' or 'some potion' (e.g., 'a potion is to the south')
5. **Separation of Inline Facts**: If a sentence mentions both location and need/history inline, you MUST extract them on separate lines.
6. **No Punctuation**: Do NOT include punctuation, capital letters, or extra words.

---
ENTITY TYPES:
- npcs: <npc name> (lily, oliver, nick, marie, guy, steve, john, eliza, lola, donna, brittany) or "someone"
- locations: <location name> (room 1, hallway 3, storage 1, lounge 2, etc.) or "somewhere"
- items: <potion_color> potion, "message", "a potion", "some potion"

FACT TEMPLATES:

# Potions and Inventory
<npc> needs a <potion_color or unknown> potion
<potion_color or unknown> potion delivered to <npc>
<potion_color or unknown> potion is in <room>
player has <item>

# Messaging
<npc> has a message for <npc>
message delivered from <npc> to <npc>

# Locations and Spatial Relationships
player is in <room>
<entity> is in <room>
<entity> is to the <direction>
<entity> is to the <direction> of <reference>
<room> is connected to <room>

# Past/Completed Events
<npc> has received <item>
<npc> was delivered a message from <npc>

---

EXAMPLE 1: Structured Report (Needs, Messaging, Locations)
INPUT:
"Player Status: Currently in hallway 5.
Lily (room 1): Has received a gold potion and message from Eliza.
Oliver (room 2): Needs blue potion, has message for John.
Steve (lounge 1): Present."

OUTPUT:
player is in hallway 5
lily is in room 1
lily has received gold potion
lily was delivered a message from eliza
oliver is in room 2
oliver needs a blue potion
oliver has a message for john
steve is in lounge 1

---

EXAMPLE 2: Vague/Directional Needs, Plurals, and Strategies
INPUT:
"N and S sides have NPCs to send and receive msgs. Potions are also N and S.
Advised to go ask both rooms on W (or remember their potion colour from the start).
Then get one potion -> deliver, take the msg -> Give the msg -> take the response."

OUTPUT:
someone to the north has a message for someone
someone to the south has a message for someone
a potion is to the north
a potion is to the south

---

EXAMPLE 3: Patient vs. Storage Rooms and Verb Mapping
INPUT:
"room 1 (gold potion)
storage room 1: north of hallway 3 (red, gold).
storage room 2 contains blue and green potions.
some people requires a red potion in the east wing.
a person wanted an orange potion in the south wing."

OUTPUT:
room 1 needs a gold potion
red potion is in storage room 1
gold potion is in storage room 1
storage room 1 is to the north of hallway 3
blue potion is in storage room 2
green potion is in storage room 2
someone to the east needs a red potion
someone to the south needs an orange potion

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