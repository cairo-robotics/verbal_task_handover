import json
from collections import defaultdict
import pickle

from .telemetry import Event


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
    NAME_TO_DIRECTION = { name:d for d, name in DIRECTION_TO_NAME.items()}

class Object:
    def __init__(self, type, position):
        self.type = type
        self.position = position
        self._sprite = None
        self.sprite_scaling = 1.0

    @property
    def sprite(self):
        return self._sprite

    @property
    def is_passable(self):
        return True

    def interact(self):
        pass

class Door(Object):
    def __init__(self, position, is_locked, key):
        super().__init__("door", position)
        self.is_locked = is_locked
        # self.is_open = False
        self.key = key

    @property
    def sprite(self):
        return "door_open" if not self.is_locked else "door_closed"

    @property
    def is_passable(self):
        return not self.is_locked
    
    def interact(self, player_items):
        if self.is_locked:
            if self.key in player_items:
                self.is_locked = False
                # self.is_open = True
                return True, "The door is unlocked."
            else:
                return False, "The door is locked."
        return None, None

class Chest(Object):
    def __init__(self, position, contains):
        super().__init__("chest", position)
        self.contains = contains
        self.is_open = False
        self.sprite_scaling = 0.7
    
    @property
    def sprite(self):
        if self.is_open:
            return "chest_open"
        else:
            return "chest_closed"

    @property
    def is_passable(self):
        return False

    def interact(self, *args):
        if self.is_open:
            return None, None
        else:
            self.is_open = True
            return True, self.contains

class NPC(Object):
    def __init__(self, name, position, facing, interact_data):
        super().__init__("npc", position)
        # self._sprite = name
        self.name = name
        self.orientation = Direction.NAME_TO_DIRECTION[facing]
        self.interact_data = interact_data
        self.interact_count = 0

    def interact(self, *args):
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
        self.player_has_items = []
        self.displayed_text = None
        self.score = 0

    def __getstate__(self):
        # Create a copy of the object's __dict__
        state = self.__dict__.copy()
        
        # Convert the defaultdict to a regular dict
        state['_objects'] = dict(self._objects)

        return state

    def __setstate__(self, state):
        # Restore the defaultdict
        self.__dict__.update(state)
        self._objects = defaultdict(list, state['_objects'])

    def update_current_room(self, new_room):
        self.current_room = new_room

    @property
    def objects(self):
        return self._objects[self.current_room]
    
    @property
    def player_in_interaction(self):
        return self.displayed_text is not None

    def _get_player_facing_position(self):
        return (self.player_pos[0] + self.player_dir[0], self.player_pos[1] + self.player_dir[1])

    def _get_object_at_position(self, position):
        for obj in self.objects:
            if tuple(obj.position) == tuple(position):
                return obj
        return None

    def _get_facing_object(self):
        return self._get_object_at_position(self._get_player_facing_position())

    def handle_interact(self):
        obj = self._get_facing_object()
        res = None
        if obj:
            if obj.type == "npc":
                speech, item_data = obj.interact(self.player_has_items)
                if item_data:
                    self.player_has_items += item_data
                    print("got item: ", item_data)
                    self.displayed_text = "You received " + item_data + "."
                    res = Event.ITEM_OBTAINED

                elif speech != self.displayed_text:
                    if not self.displayed_text:
                        res = Event.NPC_INTERACT
                    self.displayed_text = speech
                else:
                    self.displayed_text = None

            elif self.displayed_text:
                self.displayed_text = None

            elif obj.type == "door":
                output = obj.interact(self.player_has_items)
                if output[0]:
                    self.player_has_items.remove(obj.key)
                    print("used key: ", obj.key)
                    self.displayed_text = "The door is unlocked."
                    res = Event.DOOR_UNLOCKED

            elif obj.type == "chest":
                output = obj.interact(self.player_has_items)
                if output[0]:
                    self.player_has_items += output[1]
                    print("got item: ", output[1])
                    self.displayed_text = "You found " + str(output[1]) + "."
                    res = Event.ITEM_OBTAINED

        else:
            self.displayed_text = None
        
        return res

    def save(self, filename="save.pkl"):
        with open(filename, "wb") as file:
            pickle.dump(self, file)

    @classmethod
    def load(cls, filename="save.pkl"):
        try:
            with open(filename, "rb") as file:
                st =  pickle.load(file)
                return st
        except FileNotFoundError:
            print(f"No save file found at {filename}")
            return None

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
            elif obj_type == "door":
                new_obj = Door(new_obj_dict["position"], new_obj_dict["is_locked"], new_obj_dict["key"])

            objects[room].append(new_obj)

    for room in all_entities["npcs"]:
        room_objs = all_entities["npcs"][room]
        for obj_name in room_objs:
            new_obj_dict = room_objs[obj_name]
            new_obj = NPC(obj_name, new_obj_dict["position"], new_obj_dict["facing"], new_obj_dict["interact_data"])
            objects[room].append(new_obj)

    return objects