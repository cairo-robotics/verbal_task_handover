import json
import jsons
from collections import defaultdict
import pickle
import time

from .telemetry import Event
from .modules import *

from collections import deque

MAX_SCORE = 7

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

class Stairs(Object):
    def __init__(self, name, position, id=None, **kwargs):
        super().__init__(name, "stairs", position, id, **kwargs)
        self._sprite = "stairs"
        # self.destination = destination

class Door(Object):
    def __init__(self, name, position, is_locked, key, id=None, **kwargs):
        super().__init__(name, "door", position, id, **kwargs)
        self.is_locked = is_locked
        self.was_unlocked = False
        self.is_open = False
        self.key = key

    @property
    def sprite(self):
        return "door_open" if self.is_open else "door_closed"

        # TODO: comment the below during the actual task! This is just for sanity checking during development
        # if self.is_locked:
        #     return "door_locked"
        # elif self.is_open:
        #     return "door_open"
        # elif self.was_unlocked:
        #     return "door_unlocked"
        # return "door_closed"

    @property
    def is_passable(self):
        return self.is_open
    
    def open(self):
        self.is_open = True

    def close(self):
        self.is_open = False

    def unlock(self):
        self.is_locked = False
        self.was_unlocked = True

    def on_update(self):
        self.close()
    
    def interact(self, player_items):
        if self.is_locked:
            if self.key in player_items:
                self.unlock()
                # self.is_open = True
                return True
            else:
                return False
        elif not self.is_open:
            self.open()
            return None
        return None

class Chest(Object):
    def __init__(self, name, position, contains, id=None, **kwargs):
        super().__init__(name, "chest", position, id, **kwargs)
        self.contains = contains
        self.is_open = False
    
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
        if self.is_open or not self.is_visible or not self.contains:
            return None
        else:
            self.is_open = True
            return self.contains
        
class Barrel(Chest):
    def __init__(self, name, position, contains, id=None, **kwargs):
        super().__init__(name, position, contains, id, **kwargs)
        self.type = "barrel"

    @property
    def sprite(self):
        return "barrel"
        
class Treasure(Object):
    def __init__(self, name, position, id=None, **kwargs):
        super().__init__(name, "treasure", position, id, **kwargs)
        self._sprite = "gem_red"
        self.collected = False

    def interact(self, *args):
        if not self.collected:
            self.collected = True
            return True
        return False

class NPC(Object):
    def __init__(self, name, position, facing, interact_data, conditional_interact_data=None):
        super().__init__(name, "npc", position)
        # self._sprite = name
        self.orientation = Direction.NAME_TO_DIRECTION[facing]
        self.interact_data = interact_data
        
        self.current_conversation = 0
        self.conditional_interact_data = conditional_interact_data if conditional_interact_data is not None else {}
        self.conditional_interact_counts = {key: 0 for key in self.conditional_interact_data}

    def interact(self, player_has_items):
        for key in self.conditional_interact_data:
            if key in player_has_items:
                if self.conditional_interact_counts[key] < len(self.conditional_interact_data[key]):
                    conversation = self.conditional_interact_data[key][self.conditional_interact_counts[key]]
                else:
                    conversation = self.conditional_interact_data[key][-1]
                
                self.conditional_interact_counts[key] += 1
                return deque(conversation)

        # Return the entire conversation
        conversation = self.interact_data[self.current_conversation] if self.current_conversation < len(self.interact_data) else self.interact_data[-1]
        self.current_conversation += 1
        return deque(conversation)
    
class GameState:
    def __init__(self, player_pos, player_dir, current_room, objects=None):
        self.player_pos = player_pos
        self.player_dir = player_dir
        if not objects:
            self._objects = defaultdict(lambda: {})
        self._objects = objects
        self.current_room = current_room
        self.player_has_items = []

        self.text_queue = deque()
        self.displayed_text = None
        self.displayed_icon = None

        self.score = 0
        
        self.cooldown = 0
        self.cooldown_time_elapsed = 0

        self.current_module = None
    
    # def get_human_readable_state(self):
    #     # this doesn't cover 100% of the relevant state info, but it's a start
    #     printable_json = {}
    #     printable_json["current_room"] = self.current_room
    #     printable_json["player_has_items"] = self.player_has_items
    #     printable_json["score"] = self.score
    #     for room in self._objects:
    #         printable_json[room] = {}
    #         for obj in self._objects[room]:
    #             printable_json[room][obj] = self._objects[room][obj].__dict__
    #     return printable_json

    def __getstate__(self):
        # Create a copy of the object's __dict__
        state = self.__dict__.copy()
        
        # Convert the defaultdict to a regular dict
        state['_objects'] = dict(self._objects)

        # Get rid of telemetry pointer
        state['telemetry'] = None

        return state

    def __setstate__(self, state):
        # Restore the defaultdict
        self.__dict__.update(state)
        self._objects = defaultdict(dict, state['_objects'])

    def set_telemetry(self, telemetry):
        self.telemetry = telemetry

    def update_current_room(self, new_room):
        self.current_room = new_room
        player_dir = self.player_dir
        details = Direction.DIRECTION_TO_NAME[player_dir] + " to " + new_room
        self.telemetry.log_event(Event.ROOM_ENTERED, details)
        for name, obj in self._objects[self.current_room].items():
            obj.on_update()

    def tick(self, dt):
        prior_cooldown = self.cooldown
        self.cooldown = max(0, self.cooldown - dt)
        if prior_cooldown > 0 and self.cooldown == 0:
            self.cooldown_time_elapsed = 0
            self.displayed_text += " [done]"

        if self.cooldown > 0:
            self.cooldown_time_elapsed += dt
            if self.cooldown_time_elapsed >= 500 and self.displayed_text:
                self.cooldown_time_elapsed = 0
                self.displayed_text += " ."

    @property
    def objects(self):
        return self._objects[self.current_room].values()
    
    @property
    def player_in_interaction(self):
        return self.displayed_text is not None
    
    @property
    def player_in_module(self):
        return self.current_module is not None
    
    def _get_object_by_name(self, room, name):
        return self._objects[room][name]

    def _get_player_facing_position(self):
        return (self.player_pos[0] + self.player_dir[0], self.player_pos[1] + self.player_dir[1])

    def _get_object_at_position(self, position):
        for obj in self.objects:
            if tuple(obj.position) == tuple(position):
                return obj
        return None

    def _get_facing_object(self):
        return self._get_object_at_position(self._get_player_facing_position())
    
    def check_available_transition(self, x, y):
        obj = self._get_object_at_position((x, y))
        if obj is None or (obj.is_visible and obj.is_passable):
            return True
        return False
    
    def handle_keypress(self, key):
        if self.player_in_module and not self.current_module.on_cooldown:
            res = self.current_module.on_keypress(key)
            if res is not None:
                if res:
                    self.got_item(self.current_module.contains)
                    self.text_queue = deque([("You defused the module! Press SPACE to continue.", None)])
                    self.telemetry.log_event(Event.MODULE_DEFUSED, self.current_module.name)
                    self.current_module = None

                    return
                elif "wire" in self.current_module.type:
                    self.displayed_text = "You tried to cut the wrong wire. Please wait 60 seconds to try again. Press ESC to exit."
                    self.displayed_icon = None
                elif "password" in self.current_module.type:
                    self.displayed_text = "You entered the wrong password. Please wait 5 seconds to try again. Press ESC to exit."
                    self.displayed_icon = None
                self.telemetry.log_event(Event.MODULE_ATTEMPTED, self.current_module.name)

    def handle_esc(self):
        self.current_module = None
        self.displayed_text = None
        self.displayed_icon = None

    def got_item(self, item):
        if "treasure" in item:
            self.score += 1
            print("score: ", self.score)
            event_type = Event.TREASURE_FOUND
            self.displayed_text = "You received a TREASURE!"
            self.displayed_icon = "red gem"

            if self.score == MAX_SCORE:
                self.displayed_text = "You found all the treasures! Please let the experimenter know."

        else:
            self.player_has_items.append(item)
            self.displayed_text = f"You received the {item.upper()}."
            self.displayed_icon = item
            event_type = Event.ITEM_OBTAINED

        return event_type

    def handle_interact(self):
        print("handling interact: ", self.displayed_text, self.text_queue)

        # check for item cooldowns before continuing
        if self.cooldown > 0:
            return None, None
        
        # continue any ongoing interactions
        if self.text_queue:
            print(self.text_queue)
            next_line, item = self.text_queue.popleft()
            if next_line:
                self.displayed_text = next_line
                if "page" in next_line:
                    self.displayed_icon = "page"
                return None, None
            elif item:
                event_type = self.got_item(item)
                details = item
                return event_type, details
            
        # end active interaction if there's no data left
        elif self.displayed_text:
            self.displayed_text = None
            self.displayed_icon = None
            return None, None

        obj = self._get_object_at_position(self.player_pos)

        if obj is not None and obj.type == "treasure":
            res = obj.interact()
            if res:
                self.score += 1
                print("score: ", self.score)
                self.displayed_text = "You found a TREASURE!"
                self.displayed_icon = "red gem"
                if self.score == MAX_SCORE:
                    self.displayed_text = "You found all the treasures! Please let the experimenter know."
                event_type = Event.TREASURE_FOUND
                details = ""
                self.player_has_items.append(obj.name)

                self.telemetry.log_event(event_type, details)
                return event_type, details    

        obj = self._get_facing_object()
        event_type = None
        details = None
        if obj:
            if "module" in obj.type:
                if not obj.on_cooldown:
                    module_trigger = obj.interact()
                    if module_trigger:
                        self.current_module = obj
                        self.displayed_text = obj.item_text
                        self.displayed_icon = None
                        print("activating module...")
                        self.telemetry.log_event(Event.MODULE_INTERACTED, obj.name)
                    return None, None
                else:
                    self.displayed_text = "The module is locked. Wait before trying again."
                    self.displayed_icon = None
                    return None, None

            elif obj.type == "npc":
                conversation = obj.interact(self.player_has_items)
                if conversation:
                    event_type = Event.NPC_INTERACT
                    details = obj.name

                    self.telemetry.log_event(event_type, details)

                    self.text_queue = conversation
                    return self.handle_interact()

            elif (obj.type == "chest" or obj.type == "barrel"):
                if obj.type == "barrel" and not self.displayed_text:
                    self.displayed_text = "You search around inside the barrel."
                    self.displayed_icon = None
                    self.cooldown = 2000
                    self.telemetry.log_event(Event.ITEM_INTERACTED, "barrel")
                    item = obj.interact()
                    if not item and not obj.item_text:
                        self.text_queue = deque([("There's nothing in here.", None)])
                    elif item:
                        self.text_queue = deque([("", item)])
                    elif obj.item_text:
                        self.text_queue = deque(obj.item_text)

                elif (obj.type == "chest" and self.displayed_text is None) or self.displayed_text == "You search around inside the barrel...":
                    item = obj.interact()
                    if item:
                        details = item
                        event_type = self.got_item(item)
                    else:
                        self.displayed_text = "There's nothing in here."
                        self.displayed_icon = None

            elif obj.type == "door":
                res = obj.interact(self.player_has_items)
                if res is not None:
                    if res:
                        self.player_has_items.remove(obj.key)
                        self.displayed_text = f"You used the {obj.key.upper()} to unlock the door."
                        event_type = Event.DOOR_UNLOCKED
                        details = "used " + obj.key
                        self.telemetry.log_event(event_type, details)
                        return event_type, details
                    elif obj.item_text:
                        self.text_queue = deque(obj.item_text)
                        event_type = Event.DOOR_LOCKED
                        details = obj.name
                        self.telemetry.log_event(event_type, details)
                        return self.handle_interact()
                    else:
                        self.displayed_text = "Looks like you don't have the key for this door."
                        event_type = Event.DOOR_LOCKED
                        details = ""
                        # self.telemetry.log_event(event_type, details)
            else:
                res = obj.interact()
                self.telemetry.log_event(Event.ITEM_INTERACTED, obj.name)
                # if res:
                #     self.displayed_text = res

                if obj.item_text:
                    self.text_queue = deque(obj.item_text)
                    return self.handle_interact()

        else:
            self.displayed_text = None
            self.displayed_icon = None
        
        self.telemetry.log_event(event_type, details)
        return event_type, details

    def save(self, filename="save"):
        with open(filename + ".pkl", "wb") as file:
            pickle.dump(self, file)
        # with open(filename + ".json", "w") as file:
        #     json.dump(self.get_human_readable_state(), file, indent=4)

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
    
    objects = defaultdict(lambda: {})

    for room in all_entities["objects"]:
        room_objs = all_entities["objects"][room]
        for obj_name in room_objs:
            new_obj_dict = room_objs[obj_name]
            obj_type = new_obj_dict["type"]
            obj_id = new_obj_dict.get("id", None)
            obj_text = new_obj_dict.get("item text", None)
            if obj_type == "chest":
                new_obj = Chest(obj_name, new_obj_dict["position"], new_obj_dict["contains"], obj_id, item_text=obj_text)
            elif obj_type == "barrel":
                new_obj = Barrel(obj_name, new_obj_dict["position"], new_obj_dict["contains"], obj_id, item_text=obj_text)
            elif obj_type == "door":
                new_obj = Door(obj_name, new_obj_dict["position"], new_obj_dict["is_locked"], new_obj_dict["key"], obj_id, item_text=obj_text)
            elif obj_type == "treasure":
                new_obj = Treasure(obj_name, new_obj_dict["position"], obj_id, item_text=obj_text)
            elif obj_type == "stairs":
                new_obj = Stairs(obj_name, new_obj_dict["position"], obj_id, item_text=obj_text)
            elif obj_type == "key object":
                new_obj = KeyObject(
                    objects[room][new_obj_dict["linked_object"]],
                    **new_obj_dict["key_object"], 
                    id=obj_id,
                    item_text=obj_text
                        )
            elif obj_type == "wire_module":
                new_obj = WireModule(new_obj_dict["position"], new_obj_dict["contains"], new_obj_dict["serial_no"], new_obj_dict["wires"])
            elif obj_type == "password_module":
                new_obj = PasswordModule(new_obj_dict["position"], new_obj_dict["contains"], new_obj_dict["password"])
            else:
                new_obj = Object(obj_name, obj_type, new_obj_dict["position"], obj_id, item_text=obj_text)

            objects[room][obj_name] = new_obj

    for room in all_entities["npcs"]:
        room_objs = all_entities["npcs"][room]
        for obj_name in room_objs:
            new_obj_dict = room_objs[obj_name]

            if "conditional_interacts" in new_obj_dict:
                conditional_interact_data = new_obj_dict["conditional_interacts"]
            else:
                conditional_interact_data = None

            new_obj = NPC(obj_name, new_obj_dict["position"], new_obj_dict["facing"], new_obj_dict["interact_data"], conditional_interact_data)
            objects[room][obj_name] = new_obj

    return objects