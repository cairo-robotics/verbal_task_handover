"""
Convert line-based DSL facts to FactExtraction JSON (stage 2 of two-stage extraction).

Usage:
  1. Run stage 1: ``python report_to_dsl.py <report>.txt`` → ``analysis/<stem>_dsl_output.txt``.
  2. Run stage 2 with the **same report identifier** as step 1 (basename or ``reports/...``), or pass
     the DSL basename under ``analysis/`` (e.g. ``<stem>_dsl_output.txt`` or
     ``analysis/<stem>_dsl_output.txt``) → ``analysis/<stem>_fact_extraction_output.json``.
  3. Evaluate: ``python precision_recall.py <pred.json> <gt.json>`` using the stage-2 JSON.
"""

import argparse
import json
import os
import sys

from openai import OpenAI

import state_ontology
from extraction_paths import fact_extraction_json_path_for_dsl_path, resolve_dsl_input_path

try:
    import dotenv

    dotenv.load_dotenv()
except ImportError:
    pass

DEFAULT_MODEL = "gpt-4o-mini"

PROMPT = """
You are a converter that transforms controlled language facts into structured JSON.

Each input line is one fact written in a controlled grammar.

Convert each line into the corresponding JSON object using the provided schema.

---

RULES:

- Each line maps to exactly one JSON object
- Use the exact field names from the schema
- Do not infer or modify values
- Output a single JSON object with a "facts" list

---

OUTPUT FORMAT:

# --- Base Fact Types ---

class PatientNeedsPotion(BaseModel):
    type: Literal["PatientNeedsPotion"]
    patient: str
    potion_color: str


class PotionDelivered(BaseModel):
    type: Literal["PotionDelivered"]
    patient: str
    potion_color: str


class MessageRequest(BaseModel):
    type: Literal["MessageRequest"]
    sender_patient: str
    target_npc: str


class MessageDelivered(BaseModel):
    type: Literal["MessageDelivered"]
    sender_patient: str
    target_npc: str


class MessageResponse(BaseModel):
    type: Literal["MessageResponse"]
    sender_npc: str
    target_patient: str


class ResponseDelivered(BaseModel):
    type: Literal["ResponseDelivered"]
    sender_npc: str
    target_patient: str


class NpcLocation(BaseModel):
    type: Literal["NpcLocation"]
    npc: str
    room: str


class PotionLocation(BaseModel):
    type: Literal["PotionLocation"]
    potion_color: str
    room: str


class PlayerLocation(BaseModel):
    type: Literal["PlayerLocation"]
    room: str


class PlayerHasItem(BaseModel):
    type: Literal["PlayerHasItem"]
    item: str


# --- Union of all fact types ---

Fact = Union[
    PatientNeedsPotion,
    PotionDelivered,
    MessageRequest,
    MessageDelivered,
    MessageResponse,
    ResponseDelivered,
    NpcLocation,
    PotionLocation,
    PlayerLocation,
    PlayerHasItem,
]


class FactExtraction(BaseModel):
    facts: List[Fact]
---

EXAMPLE INPUT:
lily needs red potion

EXAMPLE OUTPUT:
{
  "facts": [
    {
      "type": "PatientNeedsPotion",
      "patient": "lily",
      "potion_color": "red"
    }
  ]
}

---

Now convert the following:

{DSL_FACTS}
"""


def dsl_to_fact_extraction(dsl_text: str, *, model: str = DEFAULT_MODEL) -> state_ontology.FactExtraction:
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    user_content = PROMPT.replace("{DSL_FACTS}", dsl_text)
    response = client.responses.parse(
        model=model,
        input=[
            {"role": "user", "content": user_content},
        ],
        temperature=0,
        text_format=state_ontology.FactExtraction,
    )
    parsed = response.output_parsed
    if parsed is None:
        raise RuntimeError(
            "Model returned no structured output; "
            f"refusal={getattr(response, 'refusal', None)!r}"
        )
    return parsed


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Parse DSL lines from DATA_DIR/analysis (or derive from a report name) "
            "into FactExtraction JSON via OpenAI."
        )
    )
    parser.add_argument(
        "dsl_or_report",
        help=(
            "DSL file under analysis/ (basename or analysis/...), or a report path "
            "under reports/ (optional reports/ prefix) to load analysis/<stem>_dsl_output.txt."
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

    try:
        dsl_path = resolve_dsl_input_path(data_dir, args.dsl_or_report)
    except (ValueError, FileNotFoundError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    if not dsl_path.is_file():
        print(f"Error: DSL file not found: {dsl_path}", file=sys.stderr)
        sys.exit(1)

    dsl_text = dsl_path.read_text(encoding="utf-8").strip()
    if not dsl_text:
        print(f"Error: DSL file is empty: {dsl_path}", file=sys.stderr)
        sys.exit(1)

    try:
        result = dsl_to_fact_extraction(dsl_text, model=args.model)
    except Exception as exc:
        print(f"Error: failed to parse DSL into facts: {exc}", file=sys.stderr)
        sys.exit(1)

    output_path = fact_extraction_json_path_for_dsl_path(dsl_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(result.model_dump(), f, indent=2)
        f.write("\n")
    print(f"Fact extraction output written to {output_path}")


if __name__ == "__main__":
    main()
