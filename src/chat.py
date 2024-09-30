from colorama import Fore, Style
from queue import Queue
import os
from datetime import datetime

from openai import OpenAI
import tkinter as tk
from tkinter import scrolledtext, font
import threading

CHAT_SAVE_FILE = "chat_save.txt"

class textBot():
    def __init__(self, graph=None) -> None:
        self.model = "gpt-3.5-turbo"
        self.temperature = 0.9
        self.client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

        self.history = Queue(maxsize=10)
        self.chat_file = CHAT_SAVE_FILE

        self.graph = graph
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
    
    @property
    def system_role_message(self) -> str:
        if self.graph is None:
            return "You are a helpful assistant."
        else:
            return  "You are an assistant helping the user answer questions about their current state in a video game.\
                The following is a knowledge graph representing what you know about the current state of the game.\n" \
                + str(self.graph)

    def _paste_graph_as_text(self):
        return str(self.graph)
    
    def _chat_reply_with_history(self, user_message):
        messages = [
            {"role": "system", "content": self.system_role_message},
        ]
        self.append_to_chat({"role": "user", "content": user_message})
        messages.extend(list(self.history.queue))

        reply = self._gpt_response(messages).choices[0].message.content.strip()
        self.append_to_chat({"role": "assistant", "content": reply})

        # write to chat log file
        with open(self.chat_file, "a") as file:
            file.write(f"{datetime.now().isoformat()}\tuser\t{user_message}\n")
            file.write(f"{datetime.now().isoformat()}\tassistant\t{reply}\n")

        return reply

    def append_to_chat(self, message):
        if self.history.full():
            self.history.get()
        self.history.put(message)

    def bot_loop(self):
        self.message = ""
     
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
        self.entry_field.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.entry_field.bind("<Return>", lambda event: self.send_message())

        self.send_button = tk.Button(entry_frame, text="Send", command=self.send_message)
        self.send_button.pack(side=tk.RIGHT)

    def send_message(self):
        self.send_button.config(state='disabled', text='Sending...')

        user_input = self.entry_field.get().strip()
        self.entry_field.delete(0, tk.END)

        reply = self.bot._chat_reply_with_history(user_input)

        self.chat_display.configure(state='normal')
        self.chat_display.insert(tk.END, f"User: {user_input}\n")
        self.chat_display.insert(tk.END, f"Assistant: {reply}\n")
        self.chat_display.configure(state='disabled')
        self.chat_display.see(tk.END)

        self.send_button.config(state='normal', text='Send')


def test_chatbot_with_graph():
    from graph import TelemetryGraph
    g = TelemetryGraph()
    g.parse_from_file("llm_telemetry/saves/telemetry/telemetry_test.txt")

    tt = textBot(g)
    tt.bot_loop()

    # test_load_from_text()
    # test_graph_updates()

if __name__ == "__main__":
    tt = textBot()
    gui = ChatGUI(tt)
    gui.mainloop()