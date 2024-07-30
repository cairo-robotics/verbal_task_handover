import json
class Direction(object):
    """
    The four possible directions a player can be facing.
    """
    
    NORTH = (0, -1)
    SOUTH = (0, 1)
    EAST  = (1, 0)
    WEST  = (-1, 0)
    ALL_DIRECTIONS = INDEX_TO_DIRECTION = [NORTH, SOUTH, EAST, WEST]
    DIRECTION_TO_INDEX = { a:i for i, a in enumerate(INDEX_TO_DIRECTION) }
    OPPOSITE_DIRECTIONS = { NORTH: SOUTH, SOUTH: NORTH, EAST: WEST, WEST: EAST }
    DIRECTION_TO_NAME = { d:name for d, name in zip([NORTH, SOUTH, EAST, WEST], ["NORTH", "SOUTH", "EAST", "WEST"])}

class Object:
    def __init__(self, name, type, room, position, data={}):
        self.name = name
        self.type = type
        self.room = room
        self.position = position
        self.data = data

class NPC:
    def __init__(self, name, position, data={}):
        self.name = name
        self.position = position
        self.data = data

        self.orientation = Direction.SOUTH

class GameState:
    def __init__(self, player_pos, player_dir, current_room, objects={}):
        self.player_pos = player_pos
        self.player_dir = player_dir
        self.objects = objects
        self.current_room = current_room

def start_state(object_filename):
    with open(object_filename, 'r') as f:
        all_entities = json.load(f)
    
    objects = []

    for obj in all_entities["objects"]:
        obj_name = obj
        new_obj = Object(obj_name, all_entities["objects"][obj_name]["type"], all_entities["objects"][obj_name]["location"], all_entities["objects"][obj_name]["position"])
        new_obj.data["contains"] = all_entities["objects"][obj_name]["contains"]
        new_obj.data["is_open"] = False

        objects.append(new_obj)
    
    return objects