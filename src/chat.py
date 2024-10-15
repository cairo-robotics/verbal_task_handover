from colorama import Fore, Style
from queue import Queue
import os
from datetime import datetime

from openai import OpenAI
import tkinter as tk
from tkinter import scrolledtext, font
# import threading
import re

CHAT_SAVE_FILE = "chat_save.txt"

QUESTION_PROMPT = """
Where applicable, ask specific questions to build on the information available in the graph and make sure your summary is complete.
Examples:
* If a player has interacted with a non-player character (NPC), but did not provide information about what they said, you could ask "I see you spoke with <NPC>; what did they say?"
* If a player has seen a locked door, you could ask "I see you found a locked door; did you get any info about how it was locked?" 
* If a player has found a key but not used it yet, and they have seen a locked door they haven't unlocked yet, you could ask if they tried the key on that door.
* Other questions in this vein could be about items they have obtained, rooms they have entered, or treasures they have found.
"""

class ChatBot():
    def __init__(self, graph=None) -> None:
        self.model = "gpt-4o-mini"
        self.temperature = 0.9
        self.client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

        self.chat_file = CHAT_SAVE_FILE

        self.history = Queue(maxsize=10)
        self.graph = graph
        self.report_text = ""

        with open(self.chat_file, "w") as file:
            file.write("time\trole\tcontent\n")
            file.write("0\tsystem\t" + self.system_role_message + "\n")

    def _gpt_response(self, messages):
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=self.temperature
        )
        return response
    
    def update_report(self, text):
        self.report_text = text

    def update_graph(self, graph):
        self.graph = graph
        print(self.graph)

    def isolate_graph_data(self, text):
        prompt = "Given the following existing networkx directed graph:\n" + str(self.graph) + "\nIsolate and return only the updated networkx graph, in the format of the existing graph, from the last message."

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

    @property
    def system_role_message(self) -> str:
        if self.graph is None:
            return "You are a helpful assistant."
        elif not self.report_text:
            return  "You are an assistant helping the user develop a summary about their current state in a video game.\
                The following is a knowledge graph representing what you know about the current state of the game.\n" \
                + str(self.graph) \
                + """
                You can ask clarifying questions about the game state and update the knowledge graph from user information.
                You can also answer the user's questions using the knowledge graph.
                The user does not have access to the knowledge graph directly.
                If you update the knowledge graph, include the text "Update graph" in your response.
                """ + QUESTION_PROMPT
        else:
            return "You are an assistant helping the user formulate a written report about their current state and progress\
                in a video game. Your goal is to help the user write a report that is concise while not omitting any relevant info. \
                The report will be given to the next user, who will use it to continue playing the game from this point. \
                The following is a knowledge graph extracted from the game's telemetry, representing what you currently know about the state of the game.\
                \n" + str(self.graph) \
                + "\nThe following is the most current version of the user's report so far:\n" + self.report_text \
                + "\nYou can 1. ask clarifying questions about the game state, 2. suggest edits to the report, or 3. update the knowledge graph from user information." \
                + "\nIf you update the knowledge graph, include the text \"Update graph\" in your response."
    
    def _paste_graph_as_text(self):
        return str(self.graph)
    
    def initial_prompt(self):
        return self._chat_reply_with_history("Please start by asking one or more specific clarifying questions about the game state.")

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
        self.append_to_chat({"role": "assistant", "content": reply})
        return reply

    def append_to_chat(self, message):
        if self.history.full():
            self.history.get()
        self.history.put(message)

    def bot_loop(self):
        # if you want to run in terminal
        self.message = ""
        print(Fore.GREEN + self.initial_prompt() + Style.RESET_ALL)
     
        while True:
            message = input("Enter Your Query: ")
            reply = self._chat_reply_with_history(message)
                
            print(Fore.GREEN + reply + Style.RESET_ALL)

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