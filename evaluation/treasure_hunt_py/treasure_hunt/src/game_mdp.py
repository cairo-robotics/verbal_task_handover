import json
import jsons
from collections import defaultdict
import pickle
import time

from .telemetry import Event
from .modules import *

from collections import deque

MAX_SCORE = 5

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
        

class NPC(Object):
    def __init__(self, name, position, facing, interact_data, held_item_interact_data={}, conditional_interact_data={},
                 player2_interact_data={}):
        super().__init__(name, "npc", position)
        # self._sprite = name
        self.orientation = Direction.NAME_TO_DIRECTION[facing]

        self.interact_data = interact_data

        self.held_item_interact_data = held_item_interact_data
        self.player2_held_item_interact_data = player2_interact_data
        self.held_item_interact_complete = False
        self.player2_held_item_interact_complete = False

        
        self.current_conversation = 0
        self.conditional_interact_data = conditional_interact_data
        self.conditional_interact_counts = {key: 0 for key in self.conditional_interact_data}
        
        self.default_conversation = self.interact_data[-1]

    def do_menu_select_interact(self, player):
        """Return True if interaction should trigger a menu select, False otherwise.
        """
        if self.held_item_interact_data and not self.held_item_interact_complete:
            return False
        elif self.player2_held_item_interact_data and (not self.player2_held_item_interact_complete) and player.name == "player2" and player.held_item:
            return False
            
        if self.conditional_interact_data and player.flags and (not player.held_item or player.held_item.name not in self.held_item_interact_data):
            for key in player.flags:
                if key in self.conditional_interact_data:
                    return True
        return False
        # return True # FOR TESTING

    def menu_select_interact(self, player, key):
        """Return the conversation and updated player object after menu select interaction."""
        if key in self.conditional_interact_data:
            if self.conditional_interact_counts[key] < len(self.conditional_interact_data[key]):
                conversation = self.conditional_interact_data[key][self.conditional_interact_counts[key]]

            else:
                conversation = self.conditional_interact_data[key][-1]
            self.default_conversation = self.conditional_interact_data[key][-1]

            event = Event.NPC_INTERACT
            details = self.name + " about " + key
            self.conditional_interact_counts[key] += 1
            return deque(conversation), player, event, details
        else:
            return deque(self.conditional_interact_data["default"][0]), player, None, None

    def interact(self, player):
        conversation = None
        event = None
        details = self.name

        if not self.held_item_interact_complete and player.held_item is not None:
            if player.held_item.name in self.held_item_interact_data:
                conversation = self.held_item_interact_data[player.held_item.name][0]
                # Mark this as complete to avoid repeating the same interaction
                self.held_item_interact_complete = True
                event = Event.GAVE_ITEM_TO_NPC  # Log the event of giving an item to the NPC
                details = player.held_item.name + " " + self.name

                self.default_conversation = self.held_item_interact_data[player.held_item.name][-1]

                player.held_item = None  # Clear the held item after interaction
                return deque(conversation), player, event, details
            
            elif "default" in self.held_item_interact_data:
                # Fallback to a default interaction if the specific held item interaction is not found
                conversation = self.held_item_interact_data["default"][0]
                event = Event.GAVE_WRONG_ITEM
                details = player.held_item.name + " " + self.name
                return deque(conversation), player, event, details

        # TODO finish 
        elif player.name == "player2" and (not self.player2_held_item_interact_complete) and player.held_item is not None:
            if player.held_item.name in self.player2_held_item_interact_data:
                conversation = self.player2_held_item_interact_data[player.held_item.name][0]
                event = Event.GAVE_ITEM_TO_NPC  # Log the event of giving an item to the NPC
                details = player.held_item.name + " " + self.name
                self.player2_held_item_interact_complete = True

                player.held_item = None  # Clear the held item after interaction
                return deque(conversation), player, event, details

        for key in self.conditional_interact_data:
            if key in player.flags:
                if self.conditional_interact_counts[key] < len(self.conditional_interact_data[key]):
                    conversation = self.conditional_interact_data[key][self.conditional_interact_counts[key]]
                    event = Event.NPC_INTERACT
                    details = ""      
                else:
                    conversation = self.conditional_interact_data[key][-1]
                
                self.conditional_interact_counts[key] += 1
                return deque(conversation), player, event, details

        # Return the entire conversation
        if self.current_conversation < len(self.interact_data) and not self.held_item_interact_complete:
            conversation = self.interact_data[self.current_conversation]
            self.current_conversation += 1
        else:
            conversation = self.default_conversation
        # self.current_conversation += 1
        return deque(conversation), player, Event.NPC_INTERACT, details
    

class Player:
    def __init__(self, pos=(0, 0), dir=Direction.NORTH):
        """
        Initialize the player with a starting position and direction.
        """
        self.pos = pos
        self.dir = dir

        self.held_item = None
        self.flags = []
        
        self.name = "player1"
    
class GameState:
    def __init__(self, player_pos, player_dir, current_room, objects=None):
        self.player = Player(pos=player_pos, dir=player_dir)

        if not objects:
            self._objects = defaultdict(lambda: {})
        self._objects = objects
        self.current_room = current_room

        self.text_queue = deque()
        self.displayed_text = None
        self.displayed_icon = None

        self.score = 0
        
        self.cooldown = 0
        self.cooldown_time_elapsed = 0
        self.elapsed_time = 0

        self.current_module = None

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
        player_dir = self.player.dir
        details = Direction.DIRECTION_TO_NAME[player_dir] + " to " + new_room
        self.telemetry.log_event(Event.ROOM_ENTERED, details)
        for name, obj in self._objects[self.current_room].items():
            obj.on_update()

    def tick(self, dt):
        self.elapsed_time += dt / 1000

        prior_cooldown = self.cooldown
        self.cooldown = max(0, self.cooldown - dt)
        if prior_cooldown > 0 and self.cooldown == 0:
            self.cooldown_time_elapsed = 0
            self.displayed_text += " [SPACE to continue]"

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
        return (
            self.player.pos[0] + self.player.dir[0],
            self.player.pos[1] + self.player.dir[1]
        )

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
    
    def handle_NPC_menu_interact(self, selected_item):
        npc = self._get_facing_object()
        conversation, player, event, details = npc.menu_select_interact(self.player, selected_item)
        self.player = player
        event_type = event
        details = details
        if event_type:
            self.telemetry.log_event(event_type, details)
        if conversation:
            self.text_queue = conversation
            return self._handle_interact()

    def handle_keypress(self, key):
        if self.player_in_module and not self.current_module.on_cooldown:
            res = self.current_module.on_keypress(key)
            if res is not None:
                if res == -1: # exit the module
                    self.handle_esc()

                else:
                    self.current_module = None
                    self.handle_NPC_menu_interact(res)

    def handle_esc(self):
        self.current_module = None
        self.displayed_text = None
        self.displayed_icon = None

    def got_item(self, item):
        event_type = None
        if "treasure" in item:
            self.score += 1
            print("score: ", self.score)
            event_type = Event.TREASURE_FOUND
            self.displayed_text = "You received a TREASURE!"
            self.displayed_icon = "red gem"

            if self.score == MAX_SCORE and self.player.name != "player2":
                self.displayed_text = "You found all the treasures! Please let the experimenter know."

        else:
            if item not in self.player.flags:
                self.player.flags.append(item)
                event_type = Event.ITEM_OBTAINED
            self.displayed_text = f"You received the {item.upper()}."
            self.displayed_icon = item

        return event_type
    
    def handle_interact(self):
        event_type, details = self._handle_interact()
        if event_type:
            self.telemetry.log_event(event_type, details)

    def _handle_interact(self):
        # print("handling interact: ", self.displayed_text, self.text_queue)

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

        if any(isinstance(coord, float) for coord in self.player.pos):
            rounded_pos = (
                round(self.player.pos[0] + 0.5 * self.player.dir[0]),
                round(self.player.pos[1] + 0.5 * self.player.dir[1])
            )
            obj = self._get_object_at_position(rounded_pos)
        else:
            obj = self._get_object_at_position(self.player.pos)

        obj = self._get_facing_object()
        event_type = None
        details = None
        if obj:
            if obj.type == "npc":
                if obj.do_menu_select_interact(self.player):
                    # raise NotImplementedError
                    self.current_module = InteractiveDialogue(self.player.flags, "Press the number key of the option to ask {} about. Press ESC to go back.".format(obj.name.upper()), obj.name)
                    self.displayed_text = self.current_module.display_text
                    return None, None
                else:
                    conversation, player, event, details = obj.interact(self.player)
                    self.player = player
                    event_type = event
                    details = details
                    if event_type:
                        self.telemetry.log_event(event_type, details)
                    if conversation:
                        self.text_queue = conversation
                        return self._handle_interact()

            elif obj.type == "potion":
                if self.player.held_item is not None and self.player.held_item.name == obj.name:
                    self.displayed_text = "You put back the potion."
                    self.player.held_item = None
                else:
                    self.player.held_item = obj # for potion, we set the held item
                    self.displayed_text = f"You picked up the {obj.name.upper()} potion."
                    self.displayed_icon = obj.name
                    event_type = Event.ITEM_OBTAINED
                    details = obj.name
            else:
                res = obj.interact()
                self.telemetry.log_event(Event.ITEM_INTERACTED, obj.name)
                # if res:
                #     self.displayed_text = res

                if obj.item_text:
                    self.text_queue = deque(obj.item_text)
                    return self._handle_interact()

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
    def load(cls, filename="save"):
        filename = filename + ".pkl"
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
        
            new_obj = Object(obj_name, obj_type, new_obj_dict["position"], obj_id, item_text=obj_text)
            objects[room][obj_name] = new_obj

    for room in all_entities["npcs"]:
        room_objs = all_entities["npcs"][room]
        for obj_name in room_objs:
            new_obj_dict = room_objs[obj_name]

            if "conditional_interacts" in new_obj_dict:
                conditional_interact_data = new_obj_dict["conditional_interacts"]
            else:
                conditional_interact_data = {}

            if "held_item_interact_data" in new_obj_dict:
                # if held_item_interact_data is specified, use it
                held_item_interact_data = new_obj_dict["held_item_interact_data"]
            else:
                # otherwise default to empty dict
                held_item_interact_data = {}

            if "player2_interact_data" in new_obj_dict:
                # if held_item_interact_data is specified, use it
                player2_interact_data = new_obj_dict["player2_interact_data"]
            else:
                # otherwise default to empty dict
                player2_interact_data = {}

            new_obj = NPC(obj_name, new_obj_dict["position"], new_obj_dict["facing"], new_obj_dict["interact_data"], 
                          held_item_interact_data, conditional_interact_data, player2_interact_data)
            objects[room][obj_name] = new_obj

    return objects

def update_start_state(state, object_filename):
    with open(object_filename, 'r') as f:
        all_entities = json.load(f)
    
        for room in all_entities["npcs"]:
            room_objs = all_entities["npcs"][room]
            for obj_name in room_objs:
                new_obj_dict = room_objs[obj_name]

                if "conditional_interacts" in new_obj_dict:
                    conditional_interact_data = new_obj_dict["conditional_interacts"]
                else:
                    conditional_interact_data = {}

                if "held_item_interact_data" in new_obj_dict:
                    # if held_item_interact_data is specified, use it
                    held_item_interact_data = new_obj_dict["held_item_interact_data"]
                else:
                    # otherwise default to empty dict
                    held_item_interact_data = {}

                if "player2_interact_data" in new_obj_dict:
                    # if held_item_interact_data is specified, use it
                    player2_interact_data = new_obj_dict["player2_interact_data"]
                else:
                    # otherwise default to empty dict
                    player2_interact_data = {}

                npc = state._get_object_by_name(room, obj_name)
                if npc:
                    # Update the NPC's interact data
                    npc.interact_data = new_obj_dict["interact_data"]
                    npc.held_item_interact_data = held_item_interact_data
                    npc.conditional_interact_data = conditional_interact_data
                    npc.player2_held_item_interact_data = player2_interact_data