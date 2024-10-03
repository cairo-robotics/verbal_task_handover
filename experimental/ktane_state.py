from numpy import random

class WireModule:
    def __init__(self, wires):
        self.wires = list(wires)

    @classmethod
    def random(cls):
        COLOR_OPTIONS = ["red", "blue", "yellow", "black", "white"]
        WIRE_COUNT    = [3, 4, 5, 6]

        wire_count = random.choice(WIRE_COUNT)
        wires = random.choice(COLOR_OPTIONS, wire_count, replace=True)

        return cls(wires)
    
    def __str__(self):
        return f"Wires: {self.wires}"

    def _solution(self, serial_no, *args):
        num_wires = len(self.wires)
        serial_last_digit_is_odd = int(serial_no[-1]) % 2 == 1

        if num_wires == 3:
            if "red" not in self.wires:
                return "Cut the second wire."
            elif self.wires[-1] == "white":
                return "Cut the last wire."
            elif self.wires.count("blue") > 1:
                return "Cut the last blue wire."
            else:
                return "Cut the last wire."
        elif num_wires == 4:
            if self.wires.count("red") > 1 and serial_last_digit_is_odd:
                return "Cut the last red wire."
            elif self.wires[-1] == "yellow" and "red" not in self.wires:
                return "Cut the first wire."
            elif self.wires.count("blue") == 1:
                return "Cut the first wire."
            elif self.wires.count("yellow") > 1:
                return "Cut the last wire."
            else:
                return "Cut the second wire."
        elif num_wires == 5:
            if self.wires[-1] == "black" and serial_last_digit_is_odd:
                return "Cut the fourth wire."
            elif self.wires.count("red") == 1 and self.wires.count("yellow") > 1:
                return "Cut the first wire."
            elif self.wires.count("black") > 1:
                return "Cut the first black wire."
            else:
                return "Cut the second wire."
        elif num_wires == 6:
            if "yellow" not in self.wires and serial_last_digit_is_odd:
                return "Cut the third wire."
            elif self.wires.count("yellow") == 1 and self.wires.count("white") > 1:
                return "Cut the fourth wire."
            elif self.wires.count("red") == 0:
                return "Cut the last wire."
            else:
                return "Cut the fourth wire."
            
class ButtonModule:
    def __init__(self, color, text, indicator):
        self.color = color
        self.text = text
        self.indicator = indicator

    @classmethod
    def random(cls):
        COLOR_OPTIONS = ["red", "blue", "yellow", "black", "white"]
        TEXT_OPTIONS  = ["Abort", "Detonate", "Hold"]
        INDICATOR_OPTIONS = ["CAR", "FRK"]

        color = random.choice(COLOR_OPTIONS)
        text = random.choice(TEXT_OPTIONS)
        indicator = random.choice(INDICATOR_OPTIONS)

        return cls(color, text, indicator)
    
    def __str__(self):
        return f"Color: {self.color}\nText: {self.text}\nIndicator: {self.indicator}"

    def _solution(self, serial_no, batteries):
        serial_no_contains_vowel = any(char in "AEIOU" for char in serial_no)

        if self.color == "blue" and self.text == "Abort":
            return "Hold the button and refer to the release timer."
        elif serial_no and batteries > 1 and self.text == "Detonate":
            return "Press and immediately release the button."
        elif self.color == "white" and self.indicator == "CAR":
            return "Hold the button and refer to the release timer."
        elif batteries > 2 and self.indicator == "FRK":
            return "Press and immediately release the button."
        elif self.color == "yellow":
            return "Hold the button and refer to the release timer."
        elif self.color == "red" and self.text == "Hold":
            return "Press and immediately release the button."
        else:
            return "Hold the button and refer to the release timer."


class KeepTalkingState:
    def __init__(self, serial_no, batteries, modules):
        self.serial_no = serial_no
        self.batteries = batteries
        self.modules = modules

    @classmethod
    def random(cls, seed=None):
        SERIAL_NO_LENGTH = 6
        BATTERY_COUNT = [0, 1, 2, 3, 4, 5]

        if seed is not None:
            random.seed(seed)

        serial_no = "".join(random.choice(list("ABCDEFGHIJKLMNOPQRSTUVWXYZ"), SERIAL_NO_LENGTH // 2))
        serial_no += "".join(random.choice(list("0123456789"), SERIAL_NO_LENGTH // 2))
        batteries = random.choice(BATTERY_COUNT)
        modules = [WireModule.random(), ButtonModule.random()]

        return cls(serial_no, batteries, modules)
    
    def __str__(self):
        return f"Serial No: {self.serial_no}\nBatteries: {self.batteries}\nModules: {self.modules}"
    
if __name__ == "__main__":
    seed = 0
    ktane_state = KeepTalkingState.random(seed)
    print(ktane_state)
    print()
    for module in ktane_state.modules:
        print(module)
        print(module._solution(ktane_state.serial_no, ktane_state.batteries))
        print()