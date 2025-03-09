import json

"""
Needs to be rewritten -- I got confused at some point between recording player quest progress vs. tracking knowable info.
This is a mess.
"""

START_STATE_JSON = """{
    "player_items": [],
    "doors": [
        {
            "is_locked": true,
            "key": "silver key",
            "location": "room0"
        },
        {
            "is_locked": true,
            "key": "blue key",
            "location": "room3"
        },
        {
            "is_locked": true,
            "key": "gold key",
            "location": "room7"
        }
    ],
    "treasure": [
        {
            "found": false,
            "location": "room3"
        },
        {
            "found": false,
            "location": "room4"
        }
    ],
    "chests": [
        {
            "is_open": false,
            "location": "room2"
        },
        {
            "is_open": false,
            "location": "room2"
        },
        {
            "is_open": false,
            "location": "room15"
        },
        {
            "is_open": false,
            "location": "room16"
        }
    ],
    "npcs": [
        {
            "name": "lily",
            "location": "room0",
            "interacted": false
        },
        {
            "name": "jay",
            "location": "room0",
            "interacted": false
        },
        {
            "name": "guy",
            "location": "room0",
            "interacted": false
        },
        {
            "name": "mark",
            "location": "room1",
            "interacted": false
        },
        {
            "name": "eliza",
            "location": "room5",
            "interacted": false
        },
        {
            "name": "marie",
            "location": "room18",
            "interacted": false
        },
        {
            "name": "steve",
            "location": "room6",
            "interacted": false
        }
    ],
    "password_module": {
        "password": "asdf",
        "defused": false,
        "location": "room1"
    },
    "wire_module": {
        "num_wires": 4,
        "wires": [
            "blue",
            "red",
            "yellow",
            "blue"
        ],
        "serial_no": "S2411",
        "defused": false,
        "location": "room19"
    }
}
"""
def parse_from_telemetry(self, telemetry: str):
    telemetry_json = json.loads(START_STATE_JSON)

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

        elif event.startswith("Item obtained"):
            item_name = event.split(": ")[1]
            telemetry_json["player_items"].append(item_name)

        elif event.startswith("Door unlocked"):
            action_string = event.split(": ")[1]
            key = action_string.split("used ")[1]
            for door in telemetry_json["doors"]:
                if door["key"] == key:
                    door["is_locked"] = False