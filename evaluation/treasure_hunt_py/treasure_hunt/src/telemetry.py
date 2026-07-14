import time

class Event:
    # define implemented event types
    NPC_INTERACT = "NPC interact"
    GAVE_ITEM_TO_NPC = "Gave item to NPC"
    DOOR_UNLOCKED = "Door unlocked"
    DOOR_LOCKED = "Tried locked door"
    ITEM_OBTAINED = "Item obtained"
    ITEM_INTERACTED = "Item interacted"
    ITEM_LOST = "Item lost"
    ROOM_ENTERED = "Room entered"
    PLAYER_MOVED = "Player moved"
    TREASURE_FOUND = "Treasure collected"
    # MODULE_DEFUSED = "Module defused"
    # MODULE_ATTEMPTED = "Module attempted"
    # MODULE_INTERACTED = "Module interacted"
    GAVE_WRONG_ITEM = "Gave wrong item to NPC"

    def __init__(self, event_type, details=""):
        self.event_type = event_type
        self.details = details
        self.timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

    def __str__(self):
        return f"{self.timestamp} - {self.event_type}: {self.details}"

class Telemetry:
    def __init__(self, log_file="telemetry_log.txt", overwrite=False):
        self.log_file = log_file
        print("Telemetry initialized")

        if overwrite:
            self.file = open(self.log_file, "w")
        else:
            self.file = open(self.log_file, "a")
        # self.log_event("Telemetry started")

    def log_event(self, event_type, details=""):
        if event_type is not None:
            ev = Event(event_type, details)
            self.file.write(str(ev) + "\n")

    def cleanup(self):
        print("Stopping telemetry...")
        # self.log_event("Telemetry stopped", "Game closed")
        self.file.close()

class DummyTelemetry(Telemetry):
    def __init__(self):
        pass
    def log_event(self, event_type, details=""):
        # print("Telemetry:", event_type, details)
        pass
    def cleanup(self):
        pass
