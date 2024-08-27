import networkx as nx
import matplotlib.pyplot as plt

class TelemetryGraph:
    def __init__(self):
        self.graph  = nx.DiGraph()

    def parse_from_file(self, filename: str):
        with open(filename, "r") as f:
            telemetry = f.read()
            self.parse_from_telemetry(telemetry)

    def parse_from_telemetry(self, telemetry: str):
        lines = telemetry.strip().split("\n")
        self.graph.add_node("player")

        current_room = None

        for line in lines:
            timestamp, event = line.split(" - ", 1)

            # Process different types of events
            if event.startswith("Player moved"):
                coords = event.split(": ")[1].strip("[]")
                # Add the move as an edge between previous and current coordinates
                if "last_position" in locals():
                    self.graph.add_edge(f"Position {last_position}", f"Position {coords}", action="Moved", time=timestamp)
                last_position = coords
            
            elif event.startswith("Room entered"):
                room_name = event.split(": ")[1]
                current_room = room_name
                self.graph.add_node(room_name)
                self.graph.add_edge("Player", room_name, action="Entered", time=timestamp)
                self.graph.add_edge(f"Position {last_position}", room_name, action="Entered", time=timestamp)
                last_position = None  # Reset after entering a new room
            
            elif event.startswith("NPC interact"):
                if current_room:
                    npc_name = "NPC"
                    self.graph.add_node(npc_name)
                    self.graph.add_edge(current_room, npc_name, action="Contains")
                    self.graph.add_edge("Player", npc_name, action="Interacted", time=timestamp)
            
            elif event.startswith("Item obtained"):
                item_name = "Item"
                if current_room:
                    self.graph.add_node(item_name)
                    self.graph.add_edge(current_room, item_name, action="Contains")
                    self.graph.add_edge("Player", item_name, action="Obtained", time=timestamp)
        
    def visualize(self):
        pos = nx.spring_layout(self.graph)
        edge_labels = nx.get_edge_attributes(self.graph, 'action')
        nx.draw(self.graph, pos, with_labels=True, node_size=2000, node_color="skyblue", font_size=10, font_weight="bold")
        nx.draw_networkx_edge_labels(self.graph, pos, edge_labels=edge_labels)
        plt.show()

    def analyze_history(self):
        player_history = nx.shortest_path(self.graph, source="player")
        for room, path in player_history.items():
            print(f"Player path to {room}: {path}")


if __name__ == "__main__":
    graph = TelemetryGraph()
    graph.parse_from_file("llm_telemetry/saves/telemetry/llm_test_telemetry.txt")
    graph.visualize()
    graph.analyze_history()