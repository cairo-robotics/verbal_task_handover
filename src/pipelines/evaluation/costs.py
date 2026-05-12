from dataclasses import dataclass

@dataclass
class CostConfig:
    traversal_cost_per_room: float = 1.0
    interaction_cost: float = 7.5 # python3 src/pipelines/evaluation/npc_to_room_time.py $DATA_DIR/telemetry/
    misinformation_multiplier: float = 2.0 # alpha

    # partial credit weights
    partial_location_credit: float = 0.5
    partial_need_credit: float = 0.5
    
# ground truth patient data, for reference
PATIENT_DATA = {
    1 : {
        "name" : "lily",
        "potion" : "gold",
        "npc_target_1" : "eliza",
        "npc_target_2": "lola",
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