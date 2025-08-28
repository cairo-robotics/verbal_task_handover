from openai import OpenAI

from string import Template
import argparse
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from analytics.graph import TelemetryGraph

import datetime



PROMPT_TRACE_ONLY = Template("""\
You are an assistant that generates a written handover report about the current state of a video game task. \
In this task, players must care for "patient" non-player characters (NPCs) by tracking which "potions" they each need, and delivering requests to and from other characters located around the game world. \
The purpose of this report is to detail the user's progress and game knowledge in order to help another player\
                  continue the task from where the user left off as efficiently as possible.\
You have access to a knowledge graph representing what data is available about the game state and the user's history so far.
Your role is to use this information to compose a complete and accurate report.\
                  
The current knowledge graph is:
```
$knowledge_graph
```
""")

PROMPT_WITH_REPORT = Template("""\
You are an assistant that generates a written handover report about the current state of a video game task. \
In this task, players must care for "patient" non-player characters (NPCs) by tracking which "potions" they each need, and delivering requests to and from other characters located around the game world. \
The purpose of this report is to detail the user's progress and game knowledge in order to help another player\
                  continue the task from where the user left off as efficiently as possible.\
You have access to a knowledge graph representing what data is available about the game state and the user's history so far.
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
        temperature=0,
        n=1,
        stop=None
    )
    return response.choices[0].text.strip()

def generate_report(pid, telemetry_dir, report_dir, save_dir, mode="hybrid"):
    # Generate the knowledge graph
    telemetry_file = os.path.join(telemetry_dir, f"{pid}_updated.txt")
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

    response += f"\n\n[This report generated at {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]\n"
    response += "[Using parameters: model={}, temperature=0, max_tokens=1500]\n".format(os.environ.get('GPT_MODEL', 'gpt-4o-mini-2024-07-18'))
    
    # Save the generated report
    if mode == "hybrid":
        save_file = os.path.join(save_dir, f"{pid}_hybrid_report.txt")
    else:
        save_file = os.path.join(save_dir, f"{pid}_generated_report.txt")
    
    
    save_generated_report(response, save_file)


# if __name__ == "__main__":
#     data_dir = os.environ.get('DATA_DIR')
#     report_dir = os.path.join(data_dir, 'participant_data')
#     telemetry_dir = os.path.join(report_dir, 'telemetry')
#     save_dir = os.path.join(data_dir, 'reports')

#     for pid in range(501, 510):
#         pid = str(pid)
#         generate_report(pid, telemetry_dir, report_dir, save_dir)
    # main(502, telemetry_dir, report_dir, save_dir)  # Example for a single participant

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    parser = argparse.ArgumentParser(description="Generate a hybrid report for a video game task.")
    parser.add_argument("pid", type=str, help="Participant ID")
    parser.add_argument("--telemetry_dir", type=str, required=True, help="Directory containing telemetry files")
    parser.add_argument("--report_dir", type=str, required=False, help="Directory containing user reports")
    parser.add_argument("--save_dir", type=str, required=True, help="Directory to save the generated report")
    parser.add_argument("--mode", type=str, choices=["hybrid", "trace_only"], default="trace_only", help="Mode of report generation")

    args = parser.parse_args()

    generate_report(args.pid, args.telemetry_dir, args.report_dir, args.save_dir, args.mode)