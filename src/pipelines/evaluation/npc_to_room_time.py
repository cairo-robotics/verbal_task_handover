#!/usr/bin/env python3
import argparse
from datetime import datetime
import os
import sys
import statistics
import glob

# Attempt to import PATIENT_DATA from the local costs.py
sys.path.append(os.path.dirname(__file__))
try:
    from costs import PATIENT_DATA
    PATIENT_NAMES = [v['name'].lower() for v in PATIENT_DATA.values()]
except ImportError:
    # Fallback to known patients if import fails
    PATIENT_NAMES = ['lily', 'oliver', 'nick', 'marie', 'guy']

def calculate_latencies(file_path, patient_names=None):
    """
    Parses a telemetry file and returns a list of durations (in seconds) between 
    a patient NPC interaction and the subsequent room entry.
    """
    if not os.path.exists(file_path):
        print(f"Warning: File {file_path} not found.")
        return []

    try:
        with open(file_path, 'r') as f:
            lines = f.readlines()
    except Exception as e:
        print(f"Warning: Could not read {file_path}: {e}")
        return []

    events = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        if ' - ' not in line:
            continue
            
        timestamp_str, details = line.split(' - ', 1)
        try:
            timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
            events.append((timestamp, details))
        except ValueError:
            continue

    latencies = []
    for i, (ts, details) in enumerate(events):
        if details.startswith('NPC interact:'):
            try:
                npc_part = details.split(':', 1)[1].strip()
                npc_name = npc_part.split(' ', 1)[0].lower()
            except (IndexError, AttributeError):
                continue

            if patient_names and npc_name not in patient_names:
                continue

            next_room_entry = None
            for j in range(i + 1, len(events)):
                next_ts, next_details = events[j]
                if next_details.startswith('Room entered:'):
                    next_room_entry = next_ts
                    break
            
            if next_room_entry:
                duration = (next_room_entry - ts).total_seconds()
                latencies.append(duration)

    return latencies

def main():
    parser = argparse.ArgumentParser(description="Analyze patient NPC interaction to room entry latency.")
    parser.add_argument("path", help="Path to a telemetry file or directory containing .txt files.")
    args = parser.parse_args()

    files_to_process = []
    if os.path.isdir(args.path):
        files_to_process = sorted(glob.glob(os.path.join(args.path, "*.txt")))
        if not files_to_process:
            print(f"No .txt files found in directory: {args.path}")
            return
    else:
        files_to_process = [args.path]

    all_latencies = []
    for f_path in files_to_process:
        latencies = calculate_latencies(f_path, PATIENT_NAMES)
        all_latencies.extend(latencies)

    if not all_latencies:
        print("No patient NPC interaction-to-room entry sequences found in the provided path.")
    else:
        avg_latency = statistics.mean(all_latencies)
        std_dev = statistics.stdev(all_latencies) if len(all_latencies) > 1 else 0.0
        
        print(f"--- Analysis Results ---")
        print(f"Files processed: {len(files_to_process)}")
        print(f"Total patient interactions: {len(all_latencies)}")
        print(f"Average latency: {avg_latency:.2f} seconds")
        print(f"Standard deviation: {std_dev:.2f} seconds")
        print(f"Minimum latency: {min(all_latencies):.2f}s")
        print(f"Maximum latency: {max(all_latencies):.2f}s")
        print(f"Filtered for NPCs: {', '.join(sorted(PATIENT_NAMES))}")

if __name__ == "__main__":
    main()
