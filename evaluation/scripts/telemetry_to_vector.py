import json

"""
Returns state vector from telemetry data -- this is the total information that could be
inferred by the LLM alone. 
This acts as a "ground truth" metric / comparison point for measuring
the graph+LLM's performance in retaining telemetry info.
"""

VECTOR_TEMPLATE_JSON = """
{
    "player_items" : [],
    "doors" : [],
    "treasure" : [],
    "chests" : [],
    "npcs": [],
    "password_module": {},
    "wire_module": {},
}
"""

def parse_from_telemetry(self, telemetry: str):
    telemetry_json = json.loads(VECTOR_TEMPLATE_JSON)

    lines = telemetry.strip().split('\n')

    current_room = "room0"
    for line in lines:
        timestamp, event = line.split(" - ", 1)

        # process various events
        if event.startswith("Room entered:"):
            details = event.split(": ")[1]
            direction = details.split(" ")[0]
            room_name = details.split(" ")[2]

            current_room = room_name

        elif event.startswith("NPC interact"):
            npc_name = event.split(": ")[1]
            for npc in telemetry_json["npcs"]:
                if npc["name"] == npc_name:
                    npc["interacted"] = True
                    continue
            # NPC not previously encountered
            telemetry_json["npcs"].append({
                "name": npc_name,
                "interacted": True,
                "location": current_room
            })

        elif event.startswith("Item obtained"):
            item_name = event.split(": ")[1]
            telemetry_json["player_items"].append(item_name)

        elif event.startswith("Door unlocked"):
            action_string = event.split(": ")[1]
            key = action_string.split("used ")[1]
            if key in telemetry_json["player_items"]:
                telemetry_json["player_items"].remove(key)
            for door in telemetry_json["doors"]:
                if door["key"] == key:
                    door["is_locked"] = False
                    continue
            # Door not previously encountered
            telemetry_json["doors"].append({
                "is_locked": False,
                "key": key,
                "location": current_room
            })

        elif event.startswith("Item interacted"):
            item_name = event.split(": ")[1]
            # TODO finish
            raise NotImplementedError
