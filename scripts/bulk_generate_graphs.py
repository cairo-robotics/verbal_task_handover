import os
from graph import TelemetryGraph, save_graph_as_text

def main():
    data_dir = os.environ.get('DATA_DIR')
    telemetry_dir = os.path.join(data_dir, 'participant_data', 'telemetry')
    save_dir = os.path.join(data_dir, 'processed_output')

    for pid in range(501, 510):
        filename = f"{pid}_updated.txt"
        g = TelemetryGraph()
        g.parse_from_file(os.path.join(telemetry_dir, filename))
        graph_save_file = os.path.join(save_dir, f"{pid}_knowledge_graph.txt")
        save_graph_as_text(g, graph_save_file)

if __name__ == "__main__":
    main()