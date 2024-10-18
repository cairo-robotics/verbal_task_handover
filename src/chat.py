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

class HandoverState(Enum):
    CHECK_CONSISTENCY = 1
    QUESTION_GENERATION = 2
    UPDATE_GRAPH_DATA = 3
    IDENTIFY_MISSING_INFO = 4

CHAT_SAVE_FILE = "chat_save.txt"

CHECK_CONSISTENCY_PROMPT = Template("""
You are an assistant with access to a knowledge graph about a player's progress in a video game.
The user has provided a text description about their progress as well.
Check for specific, direct contradictions between the user's report and the knowledge graph. Missing info in the report is not a contradiction and can be addressed later.
If there are any contradictions with the graph, ask for clarification.
You may also update the knowledge graph based on the user's input; if you update the knowledge graph, include the text "Update graph" in your response.
If you do not identify any contradictions, include the text "No contradictions found" in your response.

Knowledge graph:
$graph
""")

QUESTION_GENERATION_PROMPT = Template("""
You are an assistant developing a knowledge graph representing the relevant information of a player's progress in a video game.
The purpose of this graph is to eventually to help another player, or the same player at a later time, understand the current state of the game \
    and complete the game from the state where it was left off.
The user cannot view this graph directly. The graph is below:
```
$graph
```
Your goal is to ensure the knowledge graph contains all the information that would be helpful or relevant to the next player.
Identify areas, if any, where the graph might be missing relevant information.
If you identify any such areas, ask specific questions to build on the information available in the graph.

Examples:
* If a player has interacted with a non-player character (NPC), but did not provide information about what they said, you could ask "I see you spoke with <NPC>; what did they say?"
* If a player has seen a locked door, you could ask "I see you found a locked door; did you get any info about how it was locked?" 
* If a player has found a key but not used it yet, and they have seen a locked door they haven't unlocked yet, you could ask if they tried the key on that door.
* Other questions in this vein could be about items they have obtained, rooms they have entered, or treasures they have found.

You may also update the knowledge graph based on the user's input; if you update the knowledge graph, include the text "Update graph" in your response.

Else, if you decide the graph contains all relevant information, include the text "No updates required" in your response.
""")

UPDATE_GRAPH_DATA_PROMPT = Template("""
Given the following existing knowledge graph in dictionary format: 
```
$graph
```
Isolate and return only the updates to the graph, in the format of the existing graph, from the last message."
""")

IDENTIFY_MISSING_INFO_PROMPT = Template("""
You are an assistant helping the user develop a text report about their current state in a video game.
The purpose of this report is to help another player, or the same player at a later time, understand the current state of the game \
    and complete the game from the state where it was left off.
You have access to a knowledge graph representing what you know about the current state of the game; the user cannot see this graph.
The user cannot view this graph directly. The graph is below:
```
$graph
```
The most recent version of the user's report is:
$user_report

Please identify any missing information from the user's text that is present in the knowledge graph AND may be relevant to the next player. \
    If you identify any missing information, ask the user to clarify; they may provide further information or clarify that this data is irrelevant.
    You may also update the knowledge graph based on the user's input; if you update the knowledge graph, include the text "Update graph" in your response.
    If you do not identify any missing relevant information, include the text "No missing information found" in your response.
""")

class ChatBot():
    def __init__(self, graph=None) -> None:
        self.model = "gpt-4o-mini"
        self.temperature = 0.9
        self.client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

        self.chat_file = CHAT_SAVE_FILE

        self.history = Queue(maxsize=10) # NOTE: does NOT include the system role message(s)
        self.graph = graph
        self.report_text = ""

        self.state = HandoverState.CHECK_CONSISTENCY # this is our default starting state

        self.system_prompts = {
            HandoverState.CHECK_CONSISTENCY: CHECK_CONSISTENCY_PROMPT,
            HandoverState.QUESTION_GENERATION: QUESTION_GENERATION_PROMPT,
            HandoverState.UPDATE_GRAPH_DATA: UPDATE_GRAPH_DATA_PROMPT,
            HandoverState.IDENTIFY_MISSING_INFO: IDENTIFY_MISSING_INFO_PROMPT
        }

        with open(self.chat_file, "w") as file:
            file.write("time\trole\tcontent\n")
            file.write("0\tsystem\t" + self.system_role_message + "\n")

    @property
    def system_role_message(self):
        return self.system_prompts[self.state].substitute(graph=self._paste_graph_as_text(), user_report=self.report_text)

    def _gpt_response(self, messages):
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=self.temperature
        )
        return response
    
    def clear_history(self):
        self.history = Queue(maxsize=10)
    
    def update_report(self, text):
        self.report_text = text
        with open(self.chat_file, "a") as file:
            file.write(f"{datetime.now().isoformat()}\t[USER REPORT UPDATED]\t{text}\n")

    def update_graph(self, graph):
        self.graph = graph
        print(self.graph)

    def check_graph_consistency_with_report(self):
        prompt = self.system_role_message
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": self.report_text}
        ]

        reply = self._gpt_response(messages).choices[0].message.content.strip()
        
        # log this prompt and initial reply
        with open(self.chat_file, "a") as file:
            file.write(f"{datetime.now().isoformat()}\tsystem\t{prompt}\n")
            file.write(f"{datetime.now().isoformat()}\tassistant\t{reply}\n")

        return reply

    def update_graph_from_msg(self, text):
        # prompt = "Given the following existing networkx directed graph:\n" + str(self.graph) + "\nIsolate and return only the updated networkx graph, in the format of the existing graph, from the last message."
        prompt = self.system_role_message

        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": text}
        ]

        # import pdb; pdb.set_trace()
        response = self._gpt_response(messages).choices[0].message.content.strip()
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

    def _paste_graph_as_text(self):
        return str(self.graph)
    
    def _chat_reply_with_history(self, user_message):
        messages = [
            {"role": "system", "content": self.system_role_message},
        ]
        self.append_to_chat({"role": "user", "content": user_message})
        messages.extend(list(self.history.queue))

        reply = self._gpt_response(messages).choices[0].message.content.strip()

        # write to chat log file
        with open(self.chat_file, "a") as file:
            file.write(f"{datetime.now().isoformat()}\tuser\t{user_message}\n")
            file.write(f"{datetime.now().isoformat()}\tassistant\t{reply}\n")

            if "Update graph" in reply:
                new_graph = self.isolate_graph_data(reply)
                self.update_graph(new_graph)
                # reply = "I have updated my knowledge base accordingly."
                file.write(f"{datetime.now().isoformat()}\tsystem\t[GRAPH UPDATED]\n")
  
        self.append_to_chat({"role": "assistant", "content": reply})
        return reply

    def append_to_chat(self, message):
        if self.history.full():
            self.history.get()
        self.history.put(message)

    def interaction_loop(self):
        # TODO finish and make actually work
        user_message = self.report_text
        while True:
            if self.state == HandoverState.CHECK_CONSISTENCY:
                reply = self.check_graph_consistency_with_report()

                if "No contradictions found" in reply:
                    self.state = HandoverState.QUESTION_GENERATION
                elif "Update graph" in reply:
                    new_graph = self.update_graph_from_msg(reply)
                    self.update_graph(new_graph)
                else:
                    print(Fore.GREEN + reply + Style.RESET_ALL)

    # def bot_loop(self):
    #     # if you want to run in terminal
    #     self.message = ""
    #     print(Fore.GREEN + self.initial_prompt() + Style.RESET_ALL)
     
    #     while True:
    #         message = input("Enter Your Query: ")
    #         reply = self._chat_reply_with_history(message)
                
    #         print(Fore.GREEN + reply + Style.RESET_ALL)

class ChatGUI(tk.Tk):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        self.title("Chatbot")
        self.geometry("1200x1000")

        self.chat_display = scrolledtext.ScrolledText(self, wrap=tk.WORD, state='disabled')
        self.chat_display.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

        entry_frame = tk.Frame(self)
        entry_frame.pack(padx=10, pady=10, fill=tk.X, expand=False)

        self.entry_field = tk.Entry(entry_frame, width=80)
        self.entry_field.pack(side=tk.LEFT, fill=tk.Y, expand=False)
        self.entry_field.bind("<Return>", lambda event: self.send_message())

        self.send_button = tk.Button(entry_frame, text="Send", command=self.send_message)
        self.send_button.pack(side=tk.RIGHT)

        self.launch_report_window()

    def send_message(self):
        user_input = self.entry_field.get().strip()
        self.entry_field.delete(0, tk.END)

        reply = self.bot._chat_reply_with_history(user_input)

        self.chat_display.configure(state='normal')
        self.chat_display.insert(tk.END, f"User: {user_input}\n")
        self.chat_display.insert(tk.END, f"Assistant: {reply}\n")
        self.chat_display.configure(state='disabled')
        self.chat_display.see(tk.END)

    def launch_report_window(self):
        report_window = tk.Toplevel(self)
        report_window.title("Report")
        report_window.geometry("800x600")

        report_text_area = scrolledtext.ScrolledText(report_window, wrap=tk.WORD)
        report_text_area.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

        save_button = tk.Button(report_window, text="Save Report", command=lambda: self.save_report(report_text_area))
        save_button.pack(pady=5)

    def save_report(self, text_area):
        # TODO: save to file?
        self.bot.update_report(text_area.get("1.0", tk.END).strip())  # Get all text from the text area
        print("Report saved.")  # You can remove or replace this with any feedback mechanism

        self.bot._chat_reply_with_history("I have updated the report.")

def test_chatbot_with_graph():
    from graph import TelemetryGraph
    g = TelemetryGraph()
    g.parse_from_file("/home/kaleb/code/verbal_task_handover/evaluation/treasure_hunt_py/treasure_hunt/saves/telemetry/test_telemetry.txt")

    print(g)
    tt = ChatBot(g)
    tt.bot_loop()

    # test_load_from_text()
    # test_graph_updates()

if __name__ == "__main__":
    # tt = ChatBot()
    # gui = ChatGUI(tt)
    # gui.mainloop()

    test_chatbot_with_graph()