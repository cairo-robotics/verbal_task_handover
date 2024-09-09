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
    def __init__(self, name, position, is_locked, key):
        self.name = name
        super().__init__("door", position)
        self.is_locked = is_locked
        # self.is_open = False
        self.key = key

    @property
    def sprite(self):
        if "stairs" in self.name:
            return "stairs"
        else:
            return "door_open" if not self.is_locked else "door_closed"

    @property
    def is_passable(self):
        return not self.is_locked
    
    def interact(self, player_items):
        if self.is_locked:
            if self.key in player_items:
                self.is_locked = False
                # self.is_open = True
                return True
            else:
                return False
        return None

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
            return None
        else:
            self.is_open = True
            return self.contains
        
class Treasure(Object):
    def __init__(self, position):
        super().__init__("treasure", position)
        self._sprite = "gem_red"
        self.collected = False

    def interact(self, *args):
        if not self.collected:
            self.collected = True
            return True
        return False

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
        self.displayed_icon = None
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
        obj = self._get_object_at_position(self.player_pos)
        if obj is None:
            obj = self._get_facing_object()
        event_type = None
        details = None
        if obj:
            if obj.type == "npc":
                speech, item= obj.interact(self.player_has_items)
                if item:
                    details = item
                    
                    if "treasure" in item:
                        self.score += 1
                        print("score: ", self.score)
                        event_type = Event.TREASURE_FOUND
                        self.displayed_text = "You received a TREASURE!"
                        self.displayed_icon = "red gem"

                    else:
                        self.player_has_items.append(item)
                        self.displayed_text = f"You received the {item.upper()} from {obj.name.upper()}."
                        self.displayed_icon = item
                        event_type = Event.ITEM_OBTAINED

                elif speech != self.displayed_text:
                    if not self.displayed_text:
                        event_type = Event.NPC_INTERACT
                        details = obj.name
                    self.displayed_text = speech
                    self.displayed_icon = None
                else:
                    self.displayed_text = None

            elif self.displayed_text:
                self.displayed_text = None
                self.displayed_icon = None

            elif obj.type == "treasure":
                res = obj.interact()
                if res:
                    self.score += 1
                    print("score: ", self.score)
                    self.displayed_text = "You found a TREASURE!"
                    self.displayed_icon = "red gem"
                    event_type = Event.TREASURE_FOUND
                    details = "treasure"

            elif obj.type == "door":
                res = obj.interact(self.player_has_items)
                if res is not None:
                    if res:
                        self.player_has_items.remove(obj.key)
                        self.displayed_text = f"You used the {obj.key.upper()} to unlock the door."
                        event_type = Event.DOOR_UNLOCKED
                        details = obj.name + " using " + obj.key
                    else:
                        self.displayed_text = "Looks like you don't have the key for this door."

            elif obj.type == "chest":
                item = obj.interact()
                if item:
                    self.player_has_items.append(item)
                    self.displayed_text = f"You found the {item.upper()} in the chest."
                    self.displayed_icon = item
                    event_type = Event.ITEM_OBTAINED
                    details = item

        else:
            self.displayed_text = None
            self.displayed_icon = None
        
        return event_type, details

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
                new_obj = Door(obj_name, new_obj_dict["position"], new_obj_dict["is_locked"], new_obj_dict["key"])
            elif obj_type == "treasure":
                new_obj = Treasure(new_obj_dict["position"])

            objects[room].append(new_obj)

    for room in all_entities["npcs"]:
        room_objs = all_entities["npcs"][room]
        for obj_name in room_objs:
            new_obj_dict = room_objs[obj_name]
            new_obj = NPC(obj_name, new_obj_dict["position"], new_obj_dict["facing"], new_obj_dict["interact_data"])
            objects[room].append(new_obj)

    return objects