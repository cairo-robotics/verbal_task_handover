import os
import sys

import dotenv

dotenv.load_dotenv()

POTION_ROOM_CONTENTS = {
    "storage_1" : [
        "red",
        "pale_blue",
        "gold"
    ],
    "storage_2": [
        "pink",
        "green",
        "blue",
        "orange",
        "purple"
    ]
}

POTION_LOCATIONS = {value: key for key, values in POTION_ROOM_CONTENTS.items() for value in values}

QUEST_NPC_LOCATIONS = {
    "eliza" : "lounge_1",
    "steve" : "lounge_1",
    "lola": "lounge_2",
    "john": "lounge_2",
    "donna": "lounge_3",
    "brittany": "lounge_3"
}

PATIENT_DATA = {
    1 : {
        "name" : "lily",
        "potion" : "gold",
        "npc_target" : "lola",
        "treasure" : "treasure1",
        "location" : "room 1"
    },
    2 : {
        "name" : "oliver",
        "potion" : "blue",
        "npc_target" : "john",
        "treasure" : "treasure2",
        "location" : "room 2"
    },
    3 : {
        "name" : "nick",
        "potion": "red",
        "npc_target": "donna",
        "treasure": "treasure3",
        "location": "room 3"
    },
    4 : {
        "name" : "marie",
        "potion" : "green",
        "npc_target" : "steve",
        "treasure" : "treasure4",
        "location" : "room 4"
    },
    5: {
        "name" : "guy",
        "potion" : "orange",
        "npc_target" : "brittany",
        "treasure" : "treasure5",
        "location" : "room 5"
    } 
}

PATIENTS_TO_ROOMS = {i["name"] : i["location"] for i in PATIENT_DATA.values()}
ROOMS_TO_PATIENTS = {i["location"] : i["name"] for i in PATIENT_DATA.values()}
TARGETS_TO_PATIENTS = {i["npc_target"] : i["name"] for i in PATIENT_DATA.values()}
PATIENTS_TO_TARGETS = {i["name"] : i["npc_target"] for i in PATIENT_DATA.values()}
PATIENTS_TO_IDS = {i["name"] : key for key, i in PATIENT_DATA.items()}

def update_telem_file(telem_dir: str, filename: str):
    """
    Update the telemetry file with the latest patient data.
    """
    filepath = os.path.join(telem_dir, filename)
    if not os.path.exists(filepath):
        print(f"Telemetry file {filepath} does not exist.")
        return

    with open(filepath, 'r') as file:
        lines = file.readlines()

    updated_lines = []
    for line in lines:
        updated_lines.append(line)
        timecode, line = line.split(" - ")
        if "NPC interact:" in line:
            details = line.split(":")[1].strip()
            print(line, details)
            parsed_details = details.split(" ", 1)
            if len(parsed_details) < 2:
                continue
            npc_target, item = parsed_details
            if npc_target in TARGETS_TO_PATIENTS and "request" in item and \
                PATIENTS_TO_ROOMS[TARGETS_TO_PATIENTS.get(npc_target)] in item.lower():
                updated_lines.append(f"{timecode} - Item obtained: response from {npc_target}\n")
            elif npc_target in PATIENTS_TO_TARGETS and "response" in item and  \
                PATIENTS_TO_TARGETS.get(npc_target) in item.lower():
                updated_lines.append(f"{timecode} - Item obtained: treasure{PATIENTS_TO_IDS.get(npc_target)}\n")
        elif "Gave item to NPC" in line:
            patient = line.split(" ")[-1].strip()
            updated_lines.append(f"{timecode} - Item obtained: request from {PATIENTS_TO_ROOMS[patient]}\n")

    with open(filepath.split(".txt")[0] + "_updated.txt", 'w') as file:
        file.writelines(updated_lines)
    
    print(f"Telemetry file {filepath} updated successfully.")

def main():
    telemetry_dir = os.environ.get("DATA_DIR")
    telemetry_dir = os.path.join(telemetry_dir, "participant_data", "telemetry")

    for filename in os.listdir(telemetry_dir):
        if filename.endswith(".txt") and not "_updated" in filename:
            update_telem_file(telemetry_dir, filename)

# def main():
#     if len(sys.argv) != 3:
#         print("Usage: python update_telemetry.py <telemetry_dir> <telemetry_file>")
#         return


    # update_telem_file(sys.argv[1], sys.argv[2])

if __name__ == "__main__":
    main()