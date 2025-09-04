import sys
import os
import json

from openai import OpenAI

from vector_schema import GameState

# see https://openai.com/index/introducing-structured-outputs-in-the-api/

VECTOR_PROMPT = """You are an AI assistant tasked with converting written descriptions of a game state into JSON schema representing the state.\
The user has given a verbal description of their current game state and relevant progress in a 2D video game. The game requires the user to care for "patient" non-player characters \
by tracking which ones need which color of potion. In addition, the user must deliver requests to and from "patients" to other characters located around the game world. \
Extract the information included in the description into the given JSON schema.
"""

# TEST_TEXT = """I have a silver key and a blue key. I found a door with a gold lock, but I don't remember where. I also talked to an NPC named Lily and learned a password 'asdf'. """
def convert_to_vector(text_filename, output_filename):
    try:
        with open(text_filename, 'r') as file:
            prompt = file.read()
    except FileNotFoundError:
        print(f"File {text_filename} not found.")
        return

    temperature = 0
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    # model = "gpt-4.1-2025-04-14"
    # response = client.beta.chat.completions.parse(
    #     model=model,
    #     messages=[
    #         {"role": "system", "content": VECTOR_PROMPT},
    #         {"role": "user", "content": prompt}
    #     ],
    #     temperature=temperature,
    #     response_format = GameState
    # )
    # message = response.choices[0].message
    
    model = "gpt-5-mini"
    message = client.responses.parse(
        model=model,
        reasoning={"effort": "low"},
        instructions = VECTOR_PROMPT,
        input = prompt,
        # temperature=temperature,
        text_format = GameState
    )
    message = message.output_parsed
    # print([attr for attr in dir(message) if not attr.startswith('_')])
    
    if message:
        with open(output_filename, 'w') as output_file:
            # output_file.write(response.choices[0].choices[0].message.content.strip())
            output_file.write(json.dumps(message.model_dump(), indent=2))
    else:
        print("Failed to parse response.")
        print(message.refusal)

# def batch_convert_to_vector(input_dir, output_dir):
#     for filename in os.listdir(input_dir):
#         if filename.endswith("hybrid_report.txt"):
#             text_filename = os.path.join(input_dir, filename)
#             output_filename = os.path.join(output_dir, filename.replace(".txt", "_output.json"))
#             convert_to_vector(text_filename, output_filename)

def main():
    if len(sys.argv) != 3:
        print("Usage: python report_to_vector.py <text_filename> <output_filename>")
        return

    data_dir = os.environ.get("DATA_DIR")

    text_filename = os.path.join(data_dir, "reports", sys.argv[1])
    output_filename = os.path.join(data_dir, "processed_output", sys.argv[2])
    convert_to_vector(text_filename, output_filename)

# def batch_convert():
#     data_dir = os.environ.get("DATA_DIR")
#     input_dir = os.path.join(data_dir, "reports")
#     output_dir = os.path.join(data_dir, "processed_output")
#     batch_convert_to_vector(input_dir, output_dir)

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    # main()
    # batch_convert()

    text_filename = sys.argv[1]
    output_filename = sys.argv[2]
    convert_to_vector(text_filename, output_filename)