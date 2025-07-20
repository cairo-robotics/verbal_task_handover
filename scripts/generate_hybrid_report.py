from openai import OpenAI

from string import Template
import argparse
import os
import sys

sys.path.append('..')
from graph import TelemetryGraph



PROMPT_TRACE_ONLY = Template("""\
You are an assistant that generates a written handover report about the current state of a video game task. \
In this task, players must care for "patient" non-player characters (NPCs) by tracking which "potions" they each need, and delivering requests to and from other characters located around the game world. \
The purpose of this report is to summarize the user's progress and game knowledge in order to help another player\
                  continue the task from where the user left off as efficiently as possible.\
You have access to a knowledge graph representing what you know about the game state and the user's history so far.
Your role is to use this information to compose a complete and accurate report.\
                  
The current knowledge graph is:
```
$knowledge_graph
```
""")

PROMPT_WITH_REPORT = Template("""\
You are an assistant that generates a written handover report about the current state of a video game task. \
In this task, players must care for "patient" non-player characters (NPCs) by tracking which "potions" they each need, and delivering requests to and from other characters located around the game world. \
The purpose of this report is to summarize the user's progress and game knowledge in order to help another player\
                  continue the task from where the user left off as efficiently as possible.\
You have access to a knowledge graph representing what you know about the game and the user's history so far.
You also have access to a set of notes that the user has written about the task.
Your role is to combine this information to compose a complete and accurate report.\
                  
The current knowledge graph is:
```
$knowledge_graph
```
The user's notes are:
$report
""")

def generate_graph(telemetry_file):
    g = TelemetryGraph()
    g.parse_from_file(telemetry_file)
    return g

def retrieve_user_report(report_file):
    with open(report_file, 'r') as f:
        report = f.read()
    return report

def save_knowledge_graph(g, save_file):
    with open(save_file, 'w') as f:
        f.write(str(g))

def save_generated_report(report, save_file):
    with open(save_file, 'w') as f:
        f.write(report)

def get_gpt_response(prompt):
    client = OpenAI(api_key=os.environ.get('OPENAI_API_KEY'))
    model = os.environ.get('GPT_MODEL', 'gpt-4o-mini-2024-07-18')
    response = client.completions.create(
        model=model,
        prompt=prompt,
        max_tokens=1500,
        temperature=0.1,
        top_p=1.0,
        n=1,
        stop=None
    )
    return response.choices[0].text.strip()

def generate_report(pid, telemetry_dir, report_dir, save_dir, mode="hybrid"):
    # Generate the knowledge graph
    telemetry_file = os.path.join(telemetry_dir, f"{pid}.txt")
    g = generate_graph(telemetry_file)
    graph_save_file = os.path.join(save_dir, f"{pid}_knowledge_graph.txt")
    save_knowledge_graph(g, graph_save_file)

    # Generate the final report
    if mode == "hybrid":

    # Retrieve the user's report
        report_file = os.path.join(report_dir, f"{pid}_user_report.txt")
        report = retrieve_user_report(report_file)
        prompt = PROMPT_WITH_REPORT.substitute(knowledge_graph=str(g), report=report)
    
    else:
        prompt = PROMPT_TRACE_ONLY.substitute(knowledge_graph=str(g))

    # Use OpenAI API to generate the report
    response = get_gpt_response(prompt)
    
    # Save the generated report
    if mode == "hybrid":
        save_file = os.path.join(save_dir, f"{pid}_hybrid_report.txt")
    else:
        save_file = os.path.join(save_dir, f"{pid}_generated_report.txt")
    
    
    save_generated_report(response, save_file)


if __name__ == "__main__":
    data_dir = os.environ.get('DATA_DIR')
    report_dir = os.path.join(data_dir, 'participant_data')
    telemetry_dir = os.path.join(report_dir, 'telemetry')
    save_dir = os.path.join(data_dir, 'reports')

    for pid in range(501, 510):
        pid = str(pid)
        generate_report(pid, telemetry_dir, report_dir, save_dir)
    # main(502, telemetry_dir, report_dir, save_dir)  # Example for a single participant