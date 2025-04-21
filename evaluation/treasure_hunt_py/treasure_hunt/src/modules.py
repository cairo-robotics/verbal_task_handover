from numpy import random
import pygame
from treasure_hunt.visualization.utils import *

# random.seed(0)

class InteractiveDialogue:
    def __init__(self, options, text, title=None):
        self.type = "interactive_dialogue"
        self.on_cooldown = False
        self.options = options
        self.display_text = text
        self.title = title
        self.selected_option = 0

    def on_keypress(self, key):
        # import pdb; pdb.set_trace()
        key = pygame.key.name(key)
        if not label_in_list(key):
            return None
        key_index = label_to_index(key)
        if 0 <= key_index < len(self.options):
            return self.options[key_index]
        else:
            return None

class Object:
    def __init__(self, name, type, position, id=None, item_text=None):
        self.name = name
        self.type = type
        self.position = position
        self._sprite = id if id is not None else name
        self._is_passable = True
        self.is_visible = True

        self.item_text = item_text if item_text is not None else []

    @property
    def sprite(self):
        return self._sprite

    @property
    def is_passable(self):
        return self._is_passable

    def interact(self):
        return None

    def on_update(self):
        pass

    def make_invisible(self):
        self.is_visible = False
    def make_visible(self):
        self.is_visible = True

class KeyObject(Object):
    def __init__(self, linked_object, name, type, position, id=None, item_text=None):
        super().__init__(name, type, position, id, item_text)
        self.interact_count = 0
        self.linked_object = linked_object
        self.linked_object.make_invisible()

    # @property
    # def __dict__(self):
    #     d = super().__dict__.copy()
    #     print(d)
    #     d["linked_object"] = self.linked_object.__dict__

    def interact(self):
        self.interact_count += 1
        if self.interact_count >= 3:
            self.linked_object.make_visible()
            return True
        return None
    

    
class WireModule(Object):
    def __init__(self, position, contains, serial_no="1234", wires=None):
        super().__init__("wire_module", "wire_module", position)

        self.wires = wires if wires is not None else self.random()
        self.num_wires = len(self.wires)
        self.serial_no = serial_no
        self.defused = False
        self._sprite = "module"
        self.cut_wire = None
        self.contains = contains

        self.COOLDOWN = 30000 # 30 seconds
        self.cooldown_start = None

        self.item_text = "[Press the number key of the correct wire to defuse the panel. Press ESC to exit.]"

    @property
    def on_cooldown(self):
        if self.cooldown_start is not None:
            return pygame.time.get_ticks() - self.cooldown_start < self.COOLDOWN
        return False
    
    def random(self):
        COLOR_OPTIONS = ["red", "blue", "yellow", "black", "green"]
        WIRE_COUNT    = [3, 4]

        wire_count = random.choice(WIRE_COUNT)
        wires = random.choice(COLOR_OPTIONS, wire_count, replace=True)

        return list(wires)
    
    def check_defuse(self, cut_wire_index):
        serial_no = self.serial_no
        serial_last_digit_is_odd = int(serial_no[-1]) % 2 == 1
        print("cut wire: ", cut_wire_index)

        if self.num_wires == 3:
            if "red" not in self.wires:
                # cut the second wire
                return cut_wire_index == 1
            elif self.wires.count("blue") > 1:
                # cut the last blue wire
                last_blue_wire = self.wires[::-1].index("blue")
                return cut_wire_index == self.num_wires - last_blue_wire - 1
            else:
                # cut the last wire
                return cut_wire_index == self.num_wires - 1
            
        elif self.num_wires == 4:
            if self.wires.count("red") > 1 and serial_last_digit_is_odd:
                # cut the last red wire
                last_red_wire = self.wires[::-1].index("red")
                return cut_wire_index == self.num_wires - last_red_wire - 1
            elif self.wires.count("blue") == 1:
                # cut the first wire
                return cut_wire_index == 0
            elif self.wires.count("yellow") > 1:
                # cut the last wire
                return cut_wire_index == self.num_wires - 1
            else:
                # cut the second wire
                return cut_wire_index == 1
            
    def interact(self, *args):
        return not self.defused
            
    def on_keypress(self, key):
        # import pdb; pdb.set_trace()
        key = pygame.key.name(key)
        if not self.defused and key.isdigit() and int(key) < self.num_wires:
            if self.check_defuse(int(key)-1):
                self.defused = True
                self.cut_wire = int(key) - 1
                return True
            else:
                self.cooldown_start = pygame.time.get_ticks()
                return False
        return None
            
class PasswordModule(Object):
    def __init__(self, position, contains, password="asdf"):
        super().__init__("password_module", "password_module", position)
        self.password = password
        self._sprite = "module"
        self.input = ""
        self.defused = False
        self.contains = contains

        self.COOLDOWN = 5000 # 5 seconds
        self.cooldown_start = None

        self.item_text = "[Type the correct password and press ENTER to defuse the panel. Press ESC to exit.]"

    @property
    def on_cooldown(self):
        if self.cooldown_start is not None:
            return pygame.time.get_ticks() - self.cooldown_start < self.COOLDOWN
        return False

    def interact(self, *args):
        return not self.defused
    
    def on_keypress(self, key):
        if key == pygame.K_BACKSPACE:
            self.input = self.input[:-1]
        elif key == pygame.K_RETURN:
            if self.input == self.password:
                self.defused = True
                return True
            else:
                self.input = ""
                return False
        elif pygame.key.name(key) in "abcdefghijklmnopqrstuvwxyz0123456789":
            self.input += pygame.key.name(key)
        
        return None