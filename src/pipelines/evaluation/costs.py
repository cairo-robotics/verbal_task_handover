from dataclasses import dataclass

# TODO: calibrate costs based on session data

@dataclass
class CostConfig:
    traversal_cost_per_room: float = 1.0
    interaction_cost: float = 1.0
    misinformation_cost: float = 1.0

    # partial credit weights
    partial_location_credit: float = 0.5
    partial_need_credit: float = 0.5
    
# ground truth patient data, for reference
PATIENT_DATA = {
    1 : {
        "name" : "lily",
        "potion" : "gold",
        "npc_target" : "lola",
        "target_location" : "lounge_2",
        "treasure" : "treasure1",
        "location" : "room1"
    },
    2 : {
        "name" : "oliver",
        "potion" : "blue",
        "npc_target" : "john",
        "target_location" : "lounge_2",
        "treasure" : "treasure2",
        "location" : "room2"
    },
    3 : {
        "name" : "nick",
        "potion": "red",
        "npc_target": "donna",
        "target_location": "lounge_3",
        "treasure": "treasure3",
        "location": "room3"
    },
    4 : {
        "name" : "marie",
        "potion" : "green",
        "npc_target" : "steve",
        "target_location" : "lounge_1",
        "treasure" : "treasure4",
        "location" : "room4"
    },
    5: {
        "name" : "guy",
        "potion" : "orange",
        "npc_target" : "brittany",
        "target_location" : "lounge_3",
        "treasure" : "treasure5",
        "location" : "room5"
    }
}

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