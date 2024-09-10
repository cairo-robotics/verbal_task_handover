import openai, os, re
import matplotlib.pyplot as plt
import pickle
import json
import shutil
import numpy as np
from pathlib import Path

from langchain.llms import OpenAI
from langchain.chat_models import ChatOpenAI
from langchain.memory import ConversationBufferMemory
from langchain.chains import ConversationChain

from colorama import Fore, Style
from queue import Queue
from abc import ABC

class textBot(ABC):
    def __init__(self) -> None:
        super().__init__()
        self.API_KEY            =  os.environ['OPENAI_API_KEY']
        self.memory             =  ConversationBufferMemory()
        self.llm                =  ChatOpenAI(model='gpt-3.5-turbo')
        self.conversation       =  ConversationChain(
                                        llm=self.llm,
                                        memory=self.memory
                                        )
        self.nodes_logs         =  None

    def chatbot_prompt(self):
        self.message += "\nGiven this information, you're now given a human user who has observed the entire experiment happen, by taking inputs from the user you have to perform a root cause analysis on the behaviortree and suggest changes in a final report. You can ask the user questions in one by one manner, you can start by asking how did the experiment go, followed by subsequent questions that you think will be helpful for debugging the system."

    def bot_loop(self):
        """_summary_
        """

        self.message = ""
        # self.chatbot_prompt()
        save_conversation = ""
        save_conversation += "User response: " + self.message + "\n \n"
        # Reply after conditioning GPT to be a chat agent
        reply = self.conversation.predict(input=self.message)
        save_conversation += "AI response: " + reply + "\n \n"

        print(Fore.GREEN + reply + Style.RESET_ALL)

        # Predict is string of an int because text classifier
        # mapping takes str of respective numbers
        # to identify clustered nodes from the KMeans model
        predict = "-1"

        while True:
            if predict != "-1":
                occurance_log = ""
            self.message = "User's response: "
            self.message += input("Enter Your Response: ")

            if "ANALYSIS COMPLETE" in self.message:


                with open("Conversation.txt", "w") as text_file:
                    text_file.write(save_conversation)

                shutil.move("Conversation.txt",
                            str(Path.home()) + "/HRIPapers/Experiments/Conversation.txt"
                            )
                
                save_conversation += "User response: " + self.message[21:] + "\n \n"
                reply = self.conversation.predict(input=self.message)
                save_conversation += "AI response: " + reply + "\n \n"
                # shutil.move(str(Path.home()) + "/.ros/log/CommandServer.log",
                #             str(Path.home()) + "/HRIPapers/Experiments/CommandServer.log"
                # )
                print(Fore.GREEN + "Experiment Complete!" + Style.RESET_ALL)
                return
                
            save_conversation += "User response: " + self.message[21:] + "\n \n"

            reply = self.conversation.predict(input=self.message)

            save_conversation += "AI response: " + reply + "\n \n"
            # print('save conversation:', save_conversation)
                


def bot_test():
    """_summary_
    """
    tt = textBot()
    tt.bot_loop()

bot_test()