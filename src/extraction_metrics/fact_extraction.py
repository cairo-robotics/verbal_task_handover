SYSTEM_PROMPT = """You are an information extraction system.

Your task is to extract structured facts from a game report.

You must ONLY extract facts using the predefined ontology below.
Do NOT invent new fact types.
Do NOT infer information that is not explicitly stated.
Do NOT include duplicate facts.
Do NOT include explanations.

---

ONTOLOGY (Allowed Fact Types)

1. PatientNeedsPotion(patient, potion_color)
2. PotionDelivered(patient, potion_color)

3. MessageRequest(sender_patient, target_npc)
4. MessageDelivered(sender_patient, target_npc)

5. MessageResponse(sender_npc, target_patient)
6. ResponseDelivered(sender_npc, target_patient)

7. NpcLocation(npc, room)
8. PotionLocation(potion_color, room)

9. PlayerLocation(room)
10. PlayerHasItem(item)

---

ENTITY NORMALIZATION RULES

- Use lowercase for all values
- Replace spaces with underscores
- Examples:
  "Emily" → "emily"
  "Red Potion" → "red_potion"
  "Room 1" → "room1"

---

ARGUMENT SCHEMAS

PatientNeedsPotion:
  patient, potion_color

PotionDelivered:
  patient, potion_color

MessageRequest:
  sender_patient, target_npc

MessageDelivered:
  sender_patient, target_npc

MessageResponse:
  sender_npc, target_patient

ResponseDelivered:
  sender_npc, target_patient

NpcLocation:
  npc, room

PotionLocation:
  potion_color, room

PlayerLocation:
  room

PlayerHasItem:
  item

---

IMPORTANT RULES

- Only extract facts explicitly stated in the text
- Do not infer missing steps in the task
- If something is unclear, omit it
- Do not include duplicate facts
- Output must be valid JSON

---

Now extract facts from the following report.
"""

import argparse
import json
import os
import sys
from pathlib import Path

from openai import OpenAI

import state_ontology

try:
    import dotenv

    dotenv.load_dotenv()
except ImportError:
    pass

DEFAULT_MODEL = "gpt-4o-mini"


def _reports_file(data_dir: str, filename: str) -> Path:
    """Resolve DATA_DIR/reports/<filename> and reject path traversal."""
    base = (Path(data_dir) / "reports").resolve()
    candidate = (base / filename).resolve()
    try:
        candidate.relative_to(base)
    except ValueError as exc:
        raise ValueError(f"Report path must stay under {base}") from exc
    return candidate


def extract_facts(user_prompt: str, *, model: str = DEFAULT_MODEL) -> state_ontology.FactExtraction:
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    response = client.responses.parse(
        model=model,
        input=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
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
        description="Extract structured facts from a report under DATA_DIR/reports via OpenAI."
    )
    parser.add_argument(
        "report_file",
        help="Filename (or path under reports/) to read, e.g. 302_user_report.txt",
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

    path = _reports_file(data_dir, args.report_file)
    if not path.is_file():
        print(f"Error: report file not found: {path}", file=sys.stderr)
        sys.exit(1)

    user_prompt = path.read_text(encoding="utf-8")
    result = extract_facts(user_prompt, model=args.model)
    # print(json.dumps(result.model_dump(), indent=2))
    
    output_filename = os.path.join(data_dir, "analysis", args.report_file.replace(".txt", "_fact_extraction_output.json"))
    with open(output_filename, "w") as f:
        json.dump(result.model_dump(), f, indent=2)
    print(f"Fact extraction output written to {output_filename}")


if __name__ == "__main__":
    main()