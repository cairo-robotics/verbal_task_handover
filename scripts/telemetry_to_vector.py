import json
import sys

"""
Returns state vector from telemetry data -- this is the total information that COULD be
inferred by the LLM alone. 
This acts as a "ground truth" metric / comparison point for measuring
the graph+LLM's performance in retaining telemetry info.
"""

VECTOR_TEMPLATE = {
    "player_items" : set([]), # set
    "rooms" : set([]), # set
    "npcs": {}, # dict - names as unique identifiers included in telemetry
    "doors" : [],
    "treasure" : [],
    "chests" : [],
    "pages": [],
    "password_module": {}, # data entry (fields like location, password, defused)
    "wire_module": {}, # data entry (fields like location, num_wires, wires, serial_no, defused)
}

def parse_from_telemetry(telemetry: str):

    telemetry_json = VECTOR_TEMPLATE.copy()

    lines = telemetry.strip().split('\n')

    current_room = "room0"
    telemetry_json["rooms"].add(current_room)

    for line in lines:
        timestamp, event = line.split(" - ", 1)

        # process various events
        if event.startswith("Room entered:"):
            details = event.split(": ")[1]
            # direction = details.split(" ")[0]
            room_name = details.split(" ")[2]

            current_room = room_name

        elif event.startswith("NPC interact"):
            npc_name = event.split(": ")[1]

            if npc_name in telemetry_json["npcs"]:
                # NPC previously encountered
                    telemetry_json["npcs"][npc_name]["interacted"] = True
                    continue

            # NPC not previously encountered
            telemetry_json["npcs"][npc_name] = {
                "interacted": True,
                "location": current_room
            }

        elif event.startswith("Item obtained"):
            item_name = event.split(": ")[1]
            telemetry_json["player_items"].add(item_name)

        elif event.startswith("Door unlocked"):
            action_string = event.split(": ")[1]
            key = action_string.split("used ")[1]
            if key in telemetry_json["player_items"]:
                telemetry_json["player_items"].remove(key)

            for door in telemetry_json["doors"]:
                if door["location"] == current_room:
                    door["is_locked"] = False
                    door["key"] = key
                    continue

            # Door not previously encountered
            telemetry_json["doors"].append({
                "is_locked": False,
                "key": key,
                "location": current_room
            })

        elif event.startswith("Tried locked door"):
            for door in telemetry_json["doors"]:
                if door["location"] == current_room:
                    door["is_locked"] = True
                    continue

            # Door not previously encountered
            telemetry_json["doors"].append({
                "is_locked": True,
                "location": current_room
            })

        elif event.startswith("Item interacted"):
            item_name = event.split(": ")[1]
            if item_name == "page":
                for page in telemetry_json["pages"]:
                    if page["location"] == current_room:
                        page["interacted"] = True
                        continue
                # Page not previously encountered
                telemetry_json["pages"].append({
                    "location": current_room
                })

        elif event.startswith("Module interacted"):
            module_name = event.split(": ")[1]
            telemetry_json[module_name]["defused"] = False
            telemetry_json[module_name]["location"] = current_room

        elif event.startswith("Module defused"):
            module_name = event.split(": ")[1]
            telemetry_json[module_name]["defused"] = True

    telemetry_json["rooms"] = list(telemetry_json["rooms"])
    telemetry_json["player_items"] = list(telemetry_json["player_items"])

    return telemetry_json


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python telemetry_to_vector.py <input_file> <output_file>")
        sys.exit(1)

    filename = sys.argv[1]
    output_filename = sys.argv[2]

    with open(filename, 'r') as f:
        telemetry = f.read()
        telemetry_json = parse_from_telemetry(telemetry)
    with open(output_filename, 'w') as f:
        json.dump(telemetry_json, f, indent=4)
    print(f"Telemetry data parsed and saved to {output_filename}")