from colorama import Fore, Style
from queue import Queue
import os
from datetime import datetime
from string import Template
from enum import Enum

from openai import OpenAI
import tkinter as tk
from tkinter import scrolledtext, font
# import threading
import re

CHAT_SAVE_FILE = "chat_save.txt"

CHECK_CONSISTENCY_PROMPT = Template("""
You are an assistant with access to a knowledge graph about a player's progress in a video game.
The user has provided a text description about their progress as well.
Check for specific, direct contradictions between the user's report and the knowledge graph. Missing info in the report is not a contradiction and can be addressed later.
If there are any contradictions with the graph, ask for clarification.
You may also update the knowledge graph based on the user's input; if you update the knowledge graph, include the text "Update graph" in your response.
If you do not identify any contradictions, include the text "No contradictions found" in your response.

Knowledge graph:
```
$graph
```

User's report:
$user_report
""")


class HandoverState(Enum):
    CHECK_CONSISTENCY = 1
    IDENTIFY_MISSING_INFO = 2
    # TODO: what about converting the text to a graph itself? 

    PROMPT_MAPPING = {
        CHECK_CONSISTENCY: CHECK_CONSISTENCY_PROMPT
        # TODO finish
    }

class ChatBot():
    def __init__(self, graph=None):
        self.model = "gpt-4o-mini"
        self.temperature = 0.9
        self.client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

        self.chat_file = CHAT_SAVE_FILE

        self.history = Queue(maxsize=10) # NOTE: does NOT include the system role message(s)
        self.graph = graph

        self.report_text = ""

        self.state = HandoverState.CHECK_CONSISTENCY

    @property
    def system_role_message(self):
        if self.state == HandoverState.CHECK_CONSISTENCY:
            return CHECK_CONSISTENCY_PROMPT.substitute(
                graph=str(self.graph),
                user_report=self.report_text
            )

    def _gpt_response(self, messages):
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=self.temperature
        )
        return response
    
    def _append_to_history(self, message):
        if self.history.full():
            self.history.get()
        self.history.put(message)

    def _state_transition(self, new_state):
        self.history = Queue(maxsize=10) # clear history
        self.state = new_state

    def _init_consistency_check(self):
        return self._chat_reply("Given the text and knowledge graph, Given this knowledge graph, does the report text contain any claims that contradict the graph?")

    def _chat_reply(self, user_message):
        messages = [
            {"role": "system", "content": self.system_role_message},
        ]
        self._append_to_history({"role": "user", "content": user_message})
        messages.extend(list(self.history.queue))

        response = self._gpt_response(messages)

        # state transition logic
        if self.state == HandoverState.CHECK_CONSISTENCY and "No contradictions found" in response:
            self._state_transition(HandoverState.IDENTIFY_MISSING_INFO)
        elif "Update graph" in response:
            graph = self.extract_graph_from_text(response)
            if graph:
                # TODO fix: this won't work if the self.graph isn't already a dict
                self.graph.update(graph)

    def extract_graph_from_text(self, response):
        match = re.search(r'```(?:python\s+)?([\S\s]*?)```', response, re.DOTALL)
        if match:
            graph_data = match.group(1).strip()
            try:
                graph_dict = eval(graph_data)
                return graph_dict
            except Exception as e:
                print(f"Error parsing graph data: {e}")
                return None
        else:
            try:
                graph_dict = eval(response)
                return graph_dict
            except Exception as e:
                print(f"Error parsing graph data: {e}")
                return None