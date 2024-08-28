import networkx as nx
import matplotlib.pyplot as plt

class TelemetryGraph:
    def __init__(self):
        self.graph  = nx.MultiDiGraph()
        self.seen_npcs = 0
        self.seen_items = 0
        self.seen_doors = 0

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
        G.add_edge("Player", current_room, action="Started in")
        
        for line in lines:
            # Split the line into timestamp and event
            timestamp, event = line.split(" - ", 1)
            
            # Process different types of events
            if event.startswith("Player moved"):
                coords = event.split(": ")[1].strip("[]")
                last_position = coords
            
            elif event.startswith("Room entered"):
                room_name = event.split(": ")[1]
                G.add_node(room_name)
                # G.add_edge("Player", room_name, action="Entered")
                # G.add_edge(current_room, room_name, action="Connected to")
                if last_position is not None and last_added_position_node != current_room:
                    G.add_edge(last_added_position_node, room_name, action="Moved to", time=timestamp)
                current_room = room_name
                last_added_position_node = current_room
                last_position = None  # Reset after entering a new room
            
            elif event.startswith("NPC interact"):
                if last_position and current_room:
                    position_node = self.get_node_name_from_position(current_room, last_position)
                    if not G.has_node(position_node):
                        # TODO: make it so the position is the position of the actual NPC (not the player, which could vary for the same NPC)
                        G.add_node(position_node)
                        self.seen_npcs += 1
                        npc_name = f"NPC {self.seen_npcs}"
                        G.add_node(npc_name)
                        
                        G.add_edge(position_node, npc_name, action="Contains")
                    if position_node != last_added_position_node:
                        G.add_edge(last_added_position_node, position_node, action="Moved to", time=timestamp)
                    last_added_position_node = position_node
                # G.add_edge("Player", npc_name, action="Interacted", time=timestamp)

            elif event.startswith("Item obtained"):
                item_name = "Item"
                G.add_node(item_name)
                if last_position and current_room:
                    position_node = self.get_node_name_from_position(current_room, last_position)
                    G.add_edge(position_node, item_name, action="Contains")
                    if position_node != last_added_position_node:
                        G.add_edge(last_added_position_node, position_node, action="Moved to", time=timestamp)
                # G.add_edge("Player", item_name, action="Obtained", time=timestamp)

            elif event.startswith("Door unlocked"):
                door_name = "Door"
                G.add_node(door_name)
                if last_position and current_room:
                    position_node = self.get_node_name_from_position(current_room, last_position)
                    G.add_edge(position_node, door_name, action="Contains")
                    if position_node != last_added_position_node:
                        G.add_edge(last_added_position_node, position_node, action="Moved to", time=timestamp)
                # G.add_edge("Player", door_name, action="Unlocked", time=timestamp)

    def visualize(self):
        pos = nx.spring_layout(self.graph)
        edge_labels = nx.get_edge_attributes(self.graph, 'action')
        nx.draw(self.graph, pos, with_labels=True, node_size=2000, node_color="skyblue", font_size=10, font_weight="bold")
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


if __name__ == "__main__":
    graph = TelemetryGraph()
    graph.parse_from_file("llm_telemetry/saves/telemetry/llm_test_telemetry_1.txt")
    graph.visualize()
    graph.analyze_history()