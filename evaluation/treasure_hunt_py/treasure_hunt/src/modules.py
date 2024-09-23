from numpy import random
class Object:
    def __init__(self, name, type, position, id=None):
        self.name = name
        self.type = type
        self.position = position
        self._sprite = id if id is not None else name
        self._is_passable = True
        self.is_visible = True

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
    def __init__(self, linked_object, name, type, position, id=None):
        super().__init__(name, type, position, id)
        self.interact_count = 0
        self.linked_object = linked_object
        self.linked_object.make_invisible()

    def interact(self):
        self.interact_count += 1
        if self.interact_count >= 3:
            self.linked_object.make_visible()
            return True
        return None
    
class WireModule(Object):
    def __init__(self, position, serial_no="1234", wires=None):
        super().__init__("wire_module", "module", position)

        self.wires = wires if wires is not None else self.random()
        self.num_wires = len(self.wires)
        self.serial_no = serial_no
        self.defused = False
        self._sprite = "module"
    
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
            
    def on_keypress(self, key):
        # import pdb; pdb.set_trace()
        if key.isdigit() and int(key) < self.num_wires:
            return self.check_defuse(int(key))