import tkinter as tk
from tkinter import scrolledtext
import os
import argparse

CHAT_SAVE_FILE = "chat_save.txt"
CHAT_SAVE_DIR = os.environ.get("SAVE_DIR", os.getcwd())


class ReportOnlyGUI(tk.Tk):
    def __init__(self, report_filename):
        super().__init__()

        self.report_filename = os.path.join(CHAT_SAVE_DIR, report_filename) # where the user's final report will be stored

        report_text_area = scrolledtext.ScrolledText(self, wrap=tk.WORD)
        report_text_area.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

        save_button = tk.Button(self, text="Save Report", command=lambda: self.save_report(report_text_area))
        save_button.pack(pady=5)

    def save_report(self, text_area):
        with open(self.report_filename, "w") as file:
            file.write(text_area.get("1.0", tk.END).strip())

def main(args):
    report_filename = "{}_user_report.txt".format(args.pid)
    gui = ReportOnlyGUI(report_filename)
    gui.title("Report for Handover Support Project")
    gui.mainloop()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Chatbot for handover support project")
    parser.add_argument('--pid', type=str, help='participant ID for telemetry and chat logs')
    args = parser.parse_args()

    main(args)
