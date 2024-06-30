from openai import OpenAI
import json
OPENAI_API_KEY = "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"

client = OpenAI(api_key=OPENAI_API_KEY)
MODEL  = "gpt-4-turbo"

PATIENT_FILE_NAME = "data/ipass_file_1.txt" # txt file, any format
HANDOVER_FILE_NAME = "data/ipass_handover_1_modified.json" # json file, contains "report" and "response" fields

def read_patient_file(file_name):
    with open(file_name, "r") as f:
        return f.read()

def read_handover_file(file_name):
    with open(file_name, "r") as f:
        return json.load(f)
    
def gpt_response(system_role_message, prompt):
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_role_message},
            {"role": "user", "content": prompt}
        ]
        # temperature=0.5
    )
    return response

def one_shot_comparison(patient_record, handover_transcript):
    system_role_message = """
    You are a medical professional assisting in a nursing handover. Concisesly list any important patient information that is missing from the handover transcript.
    """

    prompt = f"""
    **Patient record:**
    {patient_record}

    **Handover transcript:**
    {handover_transcript}
    """

    response = gpt_response(system_role_message, prompt)
    return response

def distill_from_transcript(handover_transcript):
    system_role_messsage = """
        Convert the transcript of the following patient handover into a bullet-pointed list of key information.
    """

    prompt = f"""
    **Handover transcript:**
    {handover_transcript}
    """

    response = gpt_response(system_role_messsage, prompt)
    return response

def distill_from_emr(patient_record):
    system_role_message = """
        Convert the following patient record into a bullet-pointed list of key information.
    """

    prompt = f"""
    **Patient record:**
    {patient_record}
    """

    response = gpt_response(system_role_message, prompt)
    return response

def compare_summaries(record_summary, transcript_summary):
    system_role_message = """
        Compare the two sets of key patient information and list any discrepancies that should be known by an incoming nurse.
    """

    prompt = f"""
    **Patient record summary:**
    {record_summary}

    **End-of-shift summary:**
    {transcript_summary}
    """

    response = gpt_response(system_role_message, prompt)
    return response

if __name__ == "__main__":

    patient_record = read_patient_file(PATIENT_FILE_NAME)
    handover_transcript = read_handover_file(HANDOVER_FILE_NAME)["report"]

    # response = one_shot_comparison(patient_record, handover_transcript)
    
    transcript_summary = distill_from_transcript(handover_transcript).choices[0].message.content
    record_summary = distill_from_emr(patient_record).choices[0].message.content
    response = compare_summaries(record_summary, transcript_summary)    

    print(response.choices[0].message.content)