import time

class Telemetry:
    def __init__(self, log_file="telemetry_log.txt", overwrite=False):
        self.log_file = log_file
        print("Telemetry initialized")

        if overwrite:
            self.file = open(self.log_file, "w")
        else:
            self.file = open(self.log_file, "a")
        self.log_event("Telemetry started")

    def log_event(self, event_name, details=""):
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        log_entry = f"{timestamp} - {event_name}: {details}\n"
        self.file.write(log_entry)

    def cleanup(self):
        print("Stopping telemetry...")
        self.log_event("Telemetry stopped", "Game closed")
        self.file.close()