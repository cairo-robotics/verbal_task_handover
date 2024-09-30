import networkx as nx
import matplotlib.pyplot as plt
import os
import sys
import pickle
from collections import defaultdict
from datetime import datetime
from pprint import PrettyPrinter
import json

from colorama import Fore, Style
from queue import Queue
from openai import OpenAI

DEFAULT_SAVE_DIR = "data/"
DEFAULT_SAVE_FILENAME = "graph.pkl"

class NoStringWrappingPrettyPrinter(PrettyPrinter):
    def _format(self, object, *args):
        if isinstance(object, str):
            width = self._width
            self._width = sys.maxsize
            try:
                super()._format(object, *args)
            finally:
                self._width = width
        else:
            super()._format(object, *args)

class TelemetryGraph:
    def __init__(self):
        self.graph  = nx.MultiDiGraph()

    def __str__(self):
        events = []
        general_data = defaultdict(lambda: [])

        for u, v, k in self.graph.edges(keys=True):
            attr_data = self.graph.get_edge_data(u, v, k)
            time    = attr_data.get("time", None)
            action  = attr_data.get("action", None)

            if time is not None:
                timestamp = datetime.strptime(time, '%Y-%m-%d %H:%M:%S')
                event_string = f"{u}: {action} {v} at time={time}"
                events.append({
                    "event": event_string,
                    "timestamp": timestamp
                })

            else:
                general_data[u].append(f"{action} {v}")

        formatted_general_data = []
        # add general data
        for node, data in general_data.items():
            s = f"{node}: "
            for d in data:
                s += f"{d}, "
            formatted_general_data.append(s)

        # sort event data by time
        events = sorted(events, key=lambda x: x["timestamp"])
        event_list = []
        for e_dict in events:
            event_list.append(e_dict["event"])

        output_dict = {
            "player known data": formatted_general_data,
            "player history": event_list
        }

        return NoStringWrappingPrettyPrinter().pformat(output_dict)        
    
    def parse_from_string(self, graph_string: str):
        graph_string = graph_string.replace("'", '"')
        d = json.loads(graph_string)

        for event_string in d["player history"]:
            u, rest = event_string.split(": ")
            action, v, time = rest.split(" ", 2)
            time_str = time.split("=", 1)[1]

            self.graph.add_edge(u, v, action=action, time=time_str)

        for data_string in d["player known data"]:
            node, rest = data_string.split(":")
            data = rest.split(", ")
            for d in data:
                if not d:
                    continue
                action, v = d.strip().split(" ", 1)
                self.graph.add_edge(node, v, action=action)

    def save(self, filename: str=DEFAULT_SAVE_FILENAME):
        with open(os.path.join(DEFAULT_SAVE_DIR, filename), "wb") as f:
            pickle.dump(self.graph, f)

    def load(self, filename: str):
        filename = os.path.join(DEFAULT_SAVE_DIR, filename)
        self.graph = nx.read_gpickle(filename)

    def parse_from_file(self, filename: str):
        with open(filename, "r") as f:
            telemetry = f.read()
            self.parse_from_telemetry(telemetry)

    def get_node_name_from_position(self, room_name, position_coords):
        return f"{room_name} {position_coords}"

    def parse_from_telemetry(self, telemetry: str):
        G = self.graph

        # Split the telemetry data into lines
        lines = telemetry.strip().split('\n')
        
        # Initialize player node
        G.add_node("Player")

        last_position = None
        current_room = "room0"
        last_added_position_node = current_room
        G.add_node(current_room)
        G.add_edge("Player", current_room, action="Started_in")
        for line in lines:
            # Split the line into timestamp and event
            timestamp, event = line.split(" - ", 1)
            
            # Process different types of events
            if event.startswith("Player moved"):
                coords = event.split(": ")[1].strip("[]")
                # location_name = self.get_node_name_from_position(current_room, coords)
                # G.add_node(location_name)
                # G.add_edge(last_added_position_node, location_name, action="Moved to", time=timestamp)
                last_position = coords
                # last_added_position_node = location_name
            
            elif event.startswith("Room entered"):
                room_name = event.split(": ")[1]
                G.add_node(room_name)
                G.add_edge("Player", room_name, action="Entered", time=timestamp)
                G.add_edge(current_room, room_name, action="Connected_to")
                if last_position is not None and last_added_position_node != current_room:
                    G.add_edge(last_added_position_node, room_name, action="Moved_to", time=timestamp)
                current_room = room_name
                last_added_position_node = current_room
                last_position = None  # Reset after entering a new room
            
            elif event.startswith("NPC interact"):
                npc_name = event.split(": ")[1]
                # if last_position and current_room:
                #     position_node = self.get_node_name_from_position(current_room, last_position)
                #     if not G.has_node(position_node):
                #         G.add_node(position_node)
                    
                #     G.add_edge(position_node, npc_name, action="Contains")
                #     if position_node != last_added_position_node:
                #         G.add_edge(last_added_position_node, position_node, action="Moved to", time=timestamp)
                #     last_added_position_node = position_node
                G.add_edge(last_added_position_node, npc_name, action="Contains")
                G.add_edge("Player", npc_name, action="Interacted", time=timestamp)

            elif event.startswith("Item obtained"):
                item_name = event.split(": ")[1]
                G.add_node(item_name)
                # if last_position and current_room:
                #     position_node = self.get_node_name_from_position(current_room, last_position)
                #     G.add_edge(position_node, item_name, action="Contains")
                #     if position_node != last_added_position_node:
                #         G.add_edge(last_added_position_node, position_node, action="Moved to", time=timestamp)

                G.add_edge(last_added_position_node, item_name, action="Contains")
                G.add_edge("Player", item_name, action="Obtained", time=timestamp)

            elif event.startswith("Door unlocked"):
                door_name = "Door"
                G.add_node(door_name)
                # if last_position and current_room:
                #     position_node = self.get_node_name_from_position(current_room, last_position)
                #     G.add_edge(position_node, door_name, action="Contains")
                #     if position_node != last_added_position_node:
                #         G.add_edge(last_added_position_node, position_node, action="Moved to", time=timestamp)
                G.add_edge("Player", door_name, action="Unlocked", time=timestamp)

    def visualize(self):
        pos = nx.spring_layout(self.graph)
        edge_labels = nx.get_edge_attributes(self.graph, 'action')
        nx.draw(self.graph, pos, with_labels=True, node_size=2000, node_color="skyblue", font_size=16, font_weight="bold")
        nx.draw_networkx_edge_labels(self.graph, pos, edge_labels=edge_labels)
        plt.show()

    def analyze_history(self):
        # Extract all paths from the "Player" node
        graph = self.graph
        paths = nx.shortest_path(graph, source="Player")
        
        for target, path in paths.items():
            print(f"Path to {target}: {path}")
            
            # Sort the edges in the path by timestamp
            edges_in_path = [(path[i], path[i+1]) for i in range(len(path)-1)]
            sorted_edges = sorted(edges_in_path, key=lambda edge: graph.edges[edge]['time'])
            
            # Print out the sorted path
            for edge in sorted_edges:
                action = graph.edges[edge]['action']
                time = graph.edges[edge]['time']
                print(f"At {time}, {action} from {edge[0]} to {edge[1]}")
            print()

def save_graph_as_text(graph: TelemetryGraph, filename: str):
    with open(filename, "w") as f:
        f.write(str(graph))

def test_load_from_text():
    # g = TelemetryGraph()
    # g.parse_from_file("llm_telemetry/saves/telemetry/telemetry_test.txt")
    # save_graph_as_text(g, DEFAULT_SAVE_DIR + "graph.txt")
    with open("data/graph.txt", "r") as f:
        s = f.read()
        s = s.replace("'", '"')
        g = TelemetryGraph()
        g.parse_from_string(s)
        print(g)

def test_graph_updates():
    graph = TelemetryGraph()
    graph.parse_from_file("llm_telemetry/saves/telemetry/telemetry_test.txt")
    # save_graph_as_text(graph, DEFAULT_SAVE_DIR + "graph.txt")

    while True:
        print("Current graph: ")
        print(graph)
        print()

        print("Enter modified graph string: ")
        s = ""
        while (line := input()) != "":
            s += line + "\n"
        
        if s == "exit":
            break

        graph = TelemetryGraph()
        graph.parse_from_string(s)


class textBot():
    def __init__(self) -> None:
        self.model = "gpt-3.5-turbo"
        self.temperature = 0.9
        self.client = OpenAI(api_key = os.environ["OPENAI_API_KEY"])

        self.history = Queue(maxsize=10)

        # self.system_role_message = "\nGiven the above networkX graph of the current game states, please provide an answer to the user's questions."
        self.system_role_message = {
            "role" : "system",
            "content" : "You are a helpful assistant."   
        }

    def _gpt_response(self, messages):
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=self.temperature
        )
        return response
    
    def _chat_reply_with_history(self, user_message):
        messages = [self.system_role_message]
        self.append_to_chat({"role": "user", "content": user_message})
        messages.extend(list(self.history.queue))

        print(messages)

        reply = self._gpt_response(messages).choices[0].message.content.strip()
        self.append_to_chat({"role": "assistant", "content": reply})
        return reply

    def append_to_chat(self, message):
        if self.history.full():
            self.history.get()
        self.history.put(message)
        
    # def paste_context(self, graph):
        # self.message += "\n" + str(graph)

    def bot_loop(self):
        self.message = ""
     
        # print(Fore.GREEN + reply + Style.RESET_ALL)

        while True:
            message = input("Enter Your Query: ")
            reply = self._chat_reply_with_history(message)
                
            print(Fore.GREEN + reply + Style.RESET_ALL)

            # save_conversation += "AI response: " + reply + "\n \n"
            # print('save conversation:', save_conversation)
                

if __name__ == "__main__":
    # graph = TelemetryGraph()
    # graph.parse_from_file("llm_telemetry/saves/telemetry/telemetry_test.txt")

    tt = textBot()
    tt.bot_loop()

    # test_load_from_text()
    # test_graph_updates()W