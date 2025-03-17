import sys
import os
from openai import OpenAI

VECTOR_PROMPT = """\
prompt text goes here!
"""

def main():
    raise NotImplementedError("TODO: provide info in VECTOR_PROMPT")

    if len(sys.argv) != 3:
        print("Usage: python report_to_vector.py <text_filename> <output_filename>")
        return

    text_filename = sys.argv[1]
    output_filename = sys.argv[2]

    try:
        with open(text_filename, 'r') as file:
            prompt = file.read()
    except FileNotFoundError:
        print(f"File {text_filename} not found.")
        return

    model = "gpt-4o-mini"
    temperature = 0.2
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": VECTOR_PROMPT},
            {"role": "user", "content": prompt}
        ],
        temperature=temperature
    )

    with open(output_filename, 'w') as output_file:
        output_file.write(response.choices[0].choices[0].message.content.strip())

if __name__ == "__main__":
    main()