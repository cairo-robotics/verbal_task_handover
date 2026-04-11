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

Your task is to extract structured facts about a game task from a narrative. Extract all facts that are explicitly stated in the text.

Return the facts using a controlled language with STRICT formatting rules. Each fact should be on a new line.
Do not include information that can not fit in this format.

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
ENTITY TYPES include npcs, locations, and items (potions, requests or messages, responses).
- npcs: <npc name>
- location: <location name>
- item: <potion_color> potion

If the entity agent is unspecified (e.g., "someone", "a patient", "a potion"), use <unknown>:
- npcs: someone
- items: a potion
- locations: somewhere

FACT TEMPLATES:

# Potions
<npc> needs a <potion_color or unknown> potion
<potion_color or unknown> potion delivered to <npc>

# Messaging
<npc> has a message/response for <npc>
message/response delivered from <npc> to <npc>

# Locations and spatial relationships
player is in <room>
<entity> is in <room>
<entity> is to the <direction>
<entity> is <direction> of <entity>
<location> is connected to <location>

# Inventory
player has <item>


If the agent is unspecified (e.g., "someone", "a patient"), use:

someone needs <potion_color> potion
someone has a message/response for someone

If a location constraint is given, include it:

someone to the <direction> needs <potion_color> potion

Do not infer specific agents, locations, or objects.

---

EXAMPLE 1:

INPUT:
"Northwest Room (Room 1) needs the gold potion
Southwest Room (Room 2) needs the blue potion
Northeast Room (Room 3) needs the red potion
Southeast Room (Room 4) needs the green potion

There is a fifth room that I did not get around to (NPC named GUY), there is also someone there who wants a potion, I did not get around to it.

The NPCs won't give you medals just for giving them a potion, you will also have to actually deliver messages for them. Make sure you explore all rooms, and names of people in the rooms. Usually helps to make exploration a side taks when fetching items or delivering messages."

OUTPUT:
room 1 is to the northwest
room 1 needs a gold potion
room 2 is to the southwest
room 2 needs a blue potion
room 3 is to the northeast
room 3 needs a red potion
room 4 is to the southeast
room 4 needs a green potion
guy is in room 5
room 5 needs a potion

---
EXAMPLE 2:

INPUT:
"You have to assist with delivering potions and messages from certain people. I have done some of it. These are the things you need to finish for me and there are some more that I do not remember.
1. Lily (in West and then North) requires another Gold potion.
2. Some people require red and green potions in the East wing.
3. I think a person wanted an orange potion in the South wing.
4. Steve has a message for John.
5. I also saw teal and pale blue potion, along with dark purple in the South wing. 
6. There were some other potions in the north and then east wing. 
7. There were people with messages on the West wing that I could not attend to."

OUTPUT:
lily is to the west-then-north
someone to the east needs a red potion
someone to the east needs a green potion
someone to the south needs an orange potion
steve has a message for john
teal potion is to the south
pale blue potion is to the south
dark purple potion is to the south
some potion is to the north-then-east
someone to the west has a message for someone

---
EXAMPLE 3:

INPUT:
"**Handoff Report**

**Outstanding Patient Needs:**
1. **Room 1 (Lily)** - Requires **gold potion**.
2. **Room 2 (Oliver)** - Requires **blue potion**.
3. **Room 3 (Nick)** - Requires **red potion**.
4. **Room 4 (Marie)** - Requires **green potion**.

**Pending Requests and Responses:**
- None.

**Relevant Inventory Items:**
- None.

**NPC Locations:**
- **Lily** is in **Room 1**.
- **Oliver** is in **Room 2**.
- **Nick** is in **Room 3**.
- **Marie** is in **Room 4**.
- **Storage 2** (where **blue potion** and **green potion** are located) is accessible from **Hallway 5**.
- **Storage 1** (where **red potion** is located) is accessible from **Hallway 3**.

**Current Location:**
- The player is currently in **Hallway 1**. 

**Next Steps:**
- Retrieve the required potions from the respective storage areas and deliver them to the patients in their rooms."

OUTPUT:
room 1 needs a gold potion
room 2 needs a blue potion
room 3 needs a red potion
room 4 needs a green potion
lily is in room 1
oliver is in room 2
nick is in room 3
marie is in room 4
blue potion is in storage 2
green potion is in storage 2
storage 2 is connected to hallway 5
red potion is in storage 1
storage 1 is connected to hallway 3
player is in hallway 1
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