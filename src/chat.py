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

from pprint import pprint

import argparse

CHAT_SAVE_FILE = "chat_save.txt"

GENERAL_PROMPT = Template("""\
You are an assistant helping the user develop a text "handover report" about their current state in a video game.
The purpose of this report is to help another player, or the same player at a later time, understand the current state of the game \
and complete the game from the state where it was left off as efficiently as possible..
You have access to a knowledge graph representing what you know about the current state of the game.
Your role is to help the user compose a complete and accurate report. You can assist in any of the following ways:
- Check if the report and your knowledge graph have conflicting information. For example, if the report states they didn't use a key If so, ask the user to clarify which is correct.
- Suggest additional information from your knowledge graph that could be included in the report.
- Update the knowledge graph based on the user's report or input. If you update the knowledge graph, include the text "Update graph" in your response. 
- Provide feedback on the user's report, such as pointing out missing or inconsistent information.
- If you believe the report is complete and requires no further edits, include the text "Report complete" in your response.
                                                    
Assume the knowledge graph is incomplete and the user's report may contain information not present in the graph.
Assume the user cannot see the knowledge graph. In your responses, refer to the knowledge graph as "the data I have access to."
Avoid referring to specific rooms by name or number, as the user does not know these identifiers. Instead, refer to rooms by their contents or locations (e.g. South of the starting room.).
The user may have forgetten certain information or purposely chosen not to include it, so be polite and nonconfrontational in your responses.

The current knowledge graph is:
```
$graph
```
                          
The user's most recent report is:
$user_report
""")

class ChatBot():
    def __init__(self, graph=None, save_file=None) -> None:
        self.model = "gpt-4o-mini"
        self.temperature = 0.2
        self.client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

        self.chat_file = save_file

        self.history = Queue(maxsize=15) # NOTE: does NOT include the system role message(s)
        self.graph = graph
        self.report_text = ""
        self.initial_report_saved = False

        with open(self.chat_file, "w") as file:
            file.write("time\trole\tcontent\n")
            file.write("0\tsystem\t" + self.system_role_message + "\n")

    @property
    def system_role_message(self):
        # return self.system_prompts[self.state].substitute(graph=self._paste_graph_as_text(), user_report=self.report_text)
        return GENERAL_PROMPT.substitute(graph=self._paste_graph_as_text(), user_report=self.report_text)

    def _gpt_response(self, messages):
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=self.temperature
        )
        return response
    
    def clear_history(self):
        self.history = Queue(maxsize=15)
    
    def update_report(self, text):
        self.report_text = text
        with open(self.chat_file, "a") as file:
            file.write(f"{datetime.now().isoformat()}\t[USER REPORT UPDATED]\t{text}\n")

        print(f"DEBUG: Report updated: {text}")

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
        # reply = "This is a test reply from check_graph_consistency."

        # log this prompt and initial reply
        with open(self.chat_file, "a") as file:
            file.write(f"{datetime.now().isoformat()}\tsystem\t{prompt}\n")
            file.write(f"{datetime.now().isoformat()}\tassistant\t{reply}\n")

        return reply

    def update_graph_from_msg(self, response):
        # prompt = "Given the following existing networkx directed graph:\n" + str(self.graph) + "\nIsolate and return only the updated networkx graph, in the format of the existing graph, from the last message."
        # prompt = self.system_role_message

        # messages = [
        #     {"role": "system", "content": prompt},
        #     {"role": "user", "content": text}
        # ]

        # import pdb; pdb.set_trace()
        # response = self._gpt_response(messages).choices[0].message.content.strip()
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
        print("System prompt:", messages[0]["content"])
        self.append_to_chat({"role": "user", "content": user_message})
        messages.extend(list(self.history.queue))

        reply = self._gpt_response(messages).choices[0].message.content.strip()
        pprint(messages)

        # write to chat log file
        with open(self.chat_file, "a") as file:
            file.write(f"{datetime.now().isoformat()}\tuser\t{user_message}\n")
            file.write(f"{datetime.now().isoformat()}\tassistant\t{reply}\n")

            if "Update graph" in reply:
                # new_graph = self.isolate_graph_data(reply)
                # self.update_graph(new_graph)
                # reply = "I have updated my knowledge base accordingly."
                file.write(f"{datetime.now().isoformat()}\tsystem\t[GRAPH UPDATED]\n")
  
        self.append_to_chat({"role": "assistant", "content": reply})
        return reply

    def append_to_chat(self, message):
        if self.history.full():
            self.history.get()
        self.history.put(message)

    def interact(self, user_message):
        return self._chat_reply_with_history(user_message)
        
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

        self.chat_display.tag_config("user", foreground="blue")

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

        # reply = self.bot._chat_reply_with_history(user_input)
        reply = self.bot.interact(user_input)

        self.chat_display.configure(state='normal')
        self.chat_display.insert(tk.END, f"User: {user_input}\n", "user")
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
        self.bot.update_report(text_area.get("1.0", tk.END).strip())  # Get all text from the text area
        print("Report saved.")  # You can remove or replace this with any feedback mechanism

        with open("user_report.txt", "w") as file:
            file.write(self.bot.report_text)

        reply = self.bot.interact("(Report updated.)")
        self.chat_display.configure(state='normal')
        self.chat_display.insert(tk.END, f"Assistant: {reply}\n")
        self.chat_display.configure(state='disabled')
        self.chat_display.see(tk.END)


def test_chatbot_with_graph():
    from graph import TelemetryGraph
    g = TelemetryGraph()
    g.parse_from_file("/home/kaleb/code/verbal_task_handover/evaluation/treasure_hunt_py/treasure_hunt/saves/telemetry/kb_test_run.txt")

    print(g)
    tt = ChatBot(g)
    # tt.bot_loop()

    gui = ChatGUI(tt)
    gui.mainloop()

    # test_load_from_text()
    # test_graph_updates()


def main(args):
    telem_file = "/home/kaleb/code/verbal_task_handover/evaluation/treasure_hunt_py/treasure_hunt/saves/telemetry/{}.txt".format(args.pid)
    from graph import TelemetryGraph
    g = TelemetryGraph()
    g.parse_from_file(telem_file)
    save_filename = "{}_chat_save.txt".format(args.pid)
    tt = ChatBot(g, save_filename)

    gui = ChatGUI(tt)
    gui.mainloop()

if __name__ == "__main__":
    # tt = ChatBot()
    # gui = ChatGUI(tt)
    # gui.mainloop()

    # test_chatbot_with_graph()

    # Set up argument parser
    parser = argparse.ArgumentParser(description="Chatbot for handover support project")
    parser.add_argument('--pid', type=str, help='participant ID for telemetry and chat logs')
    args = parser.parse_args()

    main(args)
