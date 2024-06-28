from openai import OpenAI
import json
OPENAI_API_KEY = "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"

client = OpenAI(api_key=OPENAI_API_KEY)

PATIENT_FILE_NAME = "data/ipass_file_1.txt" # txt file, any format
HANDOVER_FILE_NAME = "data/ipass_handover_1_modified.json" # json file, contains "report" and "response" fields

SYSTEM_ROLE_MESSAGE  = """
You are a medical professional assisting in a nursing handover. Verify that no important patient information is missing from the handover transcript.
"""

def read_patient_file(file_name):
    with open(file_name, "r") as f:
        return f.read()

def read_handover_file(file_name):
    with open(file_name, "r") as f:
        return json.load(f)

if __name__ == "__main__":

    patient_record = read_patient_file(PATIENT_FILE_NAME)
    handover_transcript = read_handover_file(HANDOVER_FILE_NAME)["report"]

    prompt = f"""
    **Patient record:**
    {patient_record}

    **Handover transcript:**
    {handover_transcript}
    """

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": SYSTEM_ROLE_MESSAGE},
            {"role": "user", "content": prompt}
        ]
        # temperature=0.5
    )

    print(response.choices[0].message)