import argparse
import json
import os
import sys

import dotenv
from openai import OpenAI
from pydantic import BaseModel
from typing import Literal

CATEGORIZATION_PROMPT = """
You are annotating handover reports written by participants in a 
cognitive task. Your job is to break each report into clauses and 
label each one with a content category.

## Categories

S — State Transfer: A factual claim about the current game world 
state at handover time. Could be verified true or false against a 
game snapshot. Includes item/NPC locations, player inventory, task 
completion, explicit negatives ("the chest is empty").

K — Knowledge Transfer: Something the player learned or believes 
from experience that a fresh agent with full state visibility 
wouldn't automatically know. Includes strategy, priorities, causal 
knowledge ("you need X to do Y"), dead ends already ruled out, 
warnings, predictions.

A — Ambiguous/Mixed: Has features of both S and K, or is genuinely 
unclear. Use for hedged location claims, strategic claims that 
imply state, or anything you can't cleanly assign.

M — Meta/Other: About the report or the player's experience rather 
than the task. Includes confidence hedges, apologies, comments about 
the task framework, and filler.

## Instructions

1. Split the report into clauses. A clause is the smallest unit 
   that expresses a complete thought — don't go smaller than that, 
   but don't keep clauses joined if they express different types 
   of content.
2. For each clause, output: the clause text, its label, and a 
   one-sentence justification.
3. Use A when you genuinely can't decide — don't force S or K.
4. Output valid JSON only, with no preamble or explanation outside 
   the JSON. Format:

{
  "clauses": [
    {
      "text": "<clause text>",
      "label": "<S|K|A|M>",
      "justification": "<one sentence>"
    }
  ]
}

## Examples

Report: "The blue potion is in the room to the north. Focus on the 
west side first — I already cleared the east rooms and there's 
nothing left there. I didn't have time to finish everything."

Output:
{
  "clauses": [
    {
      "text": "The blue potion is in the room to the north.",
      "label": "S",
      "justification": "Direct location claim verifiable against 
        game state."
    },
    {
      "text": "Focus on the west side first.",
      "label": "K",
      "justification": "Strategic priority based on player experience, not a state fact."
    },
    {
      "text": "I already cleared the east rooms and there's 
        nothing left there.",
      "label": "K",
      "justification": "Dead-end ruling-out based on player 
        experience; the current emptiness is a state fact but 
        the 'already cleared' framing encodes experiential 
        knowledge."
    },
    {
      "text": "I didn't have time to finish everything.",
      "label": "M",
      "justification": "Comment about the player's experience, 
        not a task-relevant claim."
    },
    {
      "text": "Tutorial is basic.",
      "label": "M",
      "justification": "Comment about the task framework (not a claim about strategy or the state of the game)"
    }
  ]
}

---

Now annotate the following report:

"""

class Clause(BaseModel):
    text: str
    label: Literal["S", "K", "A", "M"]
    justification: str

class CategorizationResult(BaseModel):
    clauses: list[Clause]

def call_chatgpt(report_text: str) -> CategorizationResult:
    """Send the prompt and report to gpt-4o-mini and parse structured output."""
    client = OpenAI()
    user_content = CATEGORIZATION_PROMPT + report_text
    
    response = client.beta.chat.completions.parse(
        model="gpt-4o-mini",
        temperature=0,
        messages=[
            {"role": "user", "content": user_content},
        ],
        response_format=CategorizationResult,
    )
    return response.choices[0].message.parsed

def main() -> None:
    dotenv.load_dotenv()

    parser = argparse.ArgumentParser(
        description="Categorize a user report using ChatGPT 4o-mini."
    )
    # parser.add_argument(
    #     "report_filename",
    #     help="Input report file name (e.g., 'user1_report.txt').",
    # )
    parser.add_argument(
        "pids",
        nargs="*",
        help="Participant IDs (e.g. 302 303).",
    )

    parser.add_argument(
        "--data-dir",
        help="Path to DATA_DIR. Defaults to DATA_DIR env variable.",
        default=os.environ.get("DATA_DIR")
    )
    
    args = parser.parse_args()
    data_dir = args.data_dir
    
    if not data_dir:
        print("Error: DATA_DIR must be provided via --data-dir or environment variable.", file=sys.stderr)
        sys.exit(1)
        
    for pid in args.pids:
        report_filename = f"{pid}_user_report.txt"
        input_path = os.path.join(data_dir, "reports", report_filename)
        if not os.path.isfile(input_path):
            print(f"Error: input file not found: {input_path}", file=sys.stderr)
            sys.exit(1)
        
        with open(input_path, "r", encoding="utf-8") as f:
            report_text = f.read()
            
        print(f"Processing report: {input_path}...")
        result = call_chatgpt(report_text)
        
        output_dir = os.path.join(data_dir, "analysis", "content_categorization")
        os.makedirs(output_dir, exist_ok=True)
        
        output_path = os.path.join(output_dir, f"{pid}_categorization.json")
        
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(result.model_dump_json(indent=2))
            
        print(f"Categorization saved to {output_path}")

if __name__ == "__main__":
    main()