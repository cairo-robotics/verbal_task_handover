# Project: LLM support for task handover
Code for a research paper on LLM's ability to improve task handover performance on human-to-human handoffs.

## Goals & overview

1. This paper asks: 
    * Do LLMs produce handover reports that include more task information? 
    * Does the information included in LLM-produced handover reports result in decreased time-to-complete of the given task?
    
2. Using data:
    * Handover reports written by both humans and LLMs for equivalent task states in  a simulated hospital floor task
    * Annotations of these reports to convert them to Boolean vectors [WIP]
    * An estimated minimum completion time (for the next participant/agent) given the data included in these reports [WIP]

3. To show:
    * Whether the task model conveyed by the handover report is more optimal for task completion than those written by humans alone 

4. So that we learn:
    * Whether LLMs can help us to structure and complete handover reports by providing more complete and relevant task data (even when said LLMs are provided with limited prior task knowledge, and limited observations of the task environment/history)

## Tech stack

- Language/runtime: Python 3.11+
- Key libraries: OpenAI API, Pydantic

## Architecture Overview
- `evaluation/` - code/packages used for user study data collection, including the video game task (`treasure_hunt_py`)
- `src/model_alignment` - code for the study-data-to-final-report LLM pipeline, which consists of:
    1a. `telemetry_to_graph.py`: Converting telemetry data to a "ground truth" Pydantic representation.
    1b. `text_to_graph.py`: Converting user notes into the same Pydantic representation.
    2. `compare_graphs.py`: Comparing the knowledge graphs from 1a and 1b to find differences and contradictions
    3. Using the diff produced in step 2 to produce a merged graph (`merge_graphs.py`)
    4. And finally, generating a final report using the merged graph output ([WIP], no code for this yet).

## Current focus / Active work
1. The final system pipeline to generate reports from graphs
2. Moving to metrics -- creating an evaluation pipeline to compare report creation methods

## Known constraints / don'ts
- Don't worry about anything in `unused/` -- that's just in case we need to recover anything from older versions of the project