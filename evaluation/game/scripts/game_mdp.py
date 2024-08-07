import json
from collections import defaultdict
class Direction(object):
    """
    The four possible directions a player can be facing.
    """
    
    NORTH = (-1, 0)
    SOUTH = (1, 0)
    EAST  = (0, 1)
    WEST  = (0, -1)
    ALL_DIRECTIONS = INDEX_TO_DIRECTION = [NORTH, SOUTH, EAST, WEST]
    DIRECTION_TO_INDEX = { a:i for i, a in enumerate(INDEX_TO_DIRECTION) }
    OPPOSITE_DIRECTIONS = { NORTH: SOUTH, SOUTH: NORTH, EAST: WEST, WEST: EAST }
    DIRECTION_TO_NAME = { d:name for d, name in zip([NORTH, SOUTH, EAST, WEST], ["NORTH", "SOUTH", "EAST", "WEST"])}

class Object:
    def __init__(self, type, position):
        self.type = type
        self.is_passable = True
        self.position = position
        self._sprite = None
        self.sprite_scaling = 1.0

    @property
    def sprite(self):
        return self._sprite

    def interact(self):
        pass

class Chest(Object):
    def __init__(self, position, contains):
        super().__init__("chest", position)
        self.contains = contains
        self.is_open = False
        self.is_passable = False
        self.sprite_scaling = 0.7
    
    @property
    def sprite(self):
        if self.is_open:
            return "chest_open"
        else:
            return "chest_closed"

    def interact(self):
        if self.is_open:
            return None
        else:
            self.is_open = True
            return self.contains

class NPC(Object):
    def __init__(self, name, position, interact_data):
        super().__init__("npc", position)
        # self._sprite = name
        self.name = name
        self.orientation = Direction.SOUTH
        self.interact_data = interact_data
        self.interact_count = 0

    # @property
    # def sprite(self):
    #     return self._sprite + "_" + Direction.DIRECTION_TO_NAME[self.orientation] + "_2.png"

    def interact(self):
        if self.interact_count >= len(self.interact_data):
            return "...", None
        speech, item = tuple(self.interact_data[self.interact_count])
        self.interact_count += 1

        return speech, item

class GameState:
    def __init__(self, player_pos, player_dir, current_room, objects=None):
        self.player_pos = player_pos
        self.player_dir = player_dir
        if not objects:
            self._objects = defaultdict(lambda: {})
        self._objects = objects
        self.current_room = current_room
        self.displayed_text = None

    @property
    def objects(self):
        return self._objects[self.current_room]

    def _get_player_facing_position(self):
        return (self.player_pos[0] + self.player_dir[0], self.player_pos[1] + self.player_dir[1])

    def _get_object_at_position(self, position):
        for obj in self.objects:
            if tuple(obj.position) == position:
                return obj
        return None

    def _get_facing_object(self):
        return self._get_object_at_position(self._get_player_facing_position())

    def handle_interact(self, game_map):
        obj = self._get_facing_object()
        output = None, None
        if self.displayed_text:
            self.displayed_text = None
        
        elif obj:
            # print("Interacting with object: ", self._get_facing_object())
            output = obj.interact()
            if output:
                print("Received: ", output)

        if output[0]:
            self.displayed_text = output[0]
        return output

def start_state(object_filename):
    with open(object_filename, 'r') as f:
        all_entities = json.load(f)
    
    objects = defaultdict(lambda: [])

    for room in all_entities["objects"]:
        room_objs = all_entities["objects"][room]
        for obj_name in room_objs:
            new_obj_dict = room_objs[obj_name]
            obj_type = new_obj_dict["type"]
            if obj_type == "chest":
                new_obj = Chest(new_obj_dict["position"], new_obj_dict["contains"])
            
            objects[room].append(new_obj)

    for room in all_entities["npcs"]:
        room_objs = all_entities["npcs"][room]
        for obj_name in room_objs:
            new_obj_dict = room_objs[obj_name]
            new_obj = NPC(obj_name, new_obj_dict["position"], new_obj_dict["interact_data"])
            objects[room].append(new_obj)

    return objects