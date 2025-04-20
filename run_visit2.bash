#!/bin/bash

# Check if participant ID and save file to use as base was provided
# Usage check
if [ $# -lt 2 ]; then
  echo "Usage: $0 <participant_id> <pid_to_load>"
  echo "Modes: 0 or 1" # 0 for control, 1 for experimental
  exit 1
fi

PARTICIPANT_ID="$1"
LOAD_FILE="$2"

SAVE_DIR="/media/cairo/T7/handover_project/participant_data"
export SAVE_DIR

VENV_PATH="./venv"

# Check if the virtual environment exists
if [ ! -d "$VENV_PATH" ]; then
  echo "Error: virtual environment not found at $VENV_PATH"
  exit 1
fi

# Activate the virtual environment
source "$VENV_PATH/bin/activate"

# Load environment variables from .env file if it exists
if [ -f ".env" ]; then
  export $(grep -v '^#' .env | xargs)
fi


# Run the main task (no distractor)
python3 evaluation/treasure_hunt_py/treasure_hunt/scripts/main.py --reset-held-items --is_player2 --reset-time --load "$LOAD_FILE" --save "$PARTICIPANT_ID" >> $SAVE_DIR/$PARTICIPANT_ID.log

if [ $? -ne 0 ]; then
  echo "Error: main.py failed"
  deactivate
  exit 1
fi

# Open a Google form (prefilled with participant ID)
FORM_URL="https://docs.google.com/forms/d/e/1FAIpQLScqlXf9X_mkWfBeR7Jh84ONj2LxNPN4Q65zBiQjjNsquBOH3Q/viewform?usp=pp_url"
FORM_URL+="&entry.526348217=$PARTICIPANT_ID"

xdg-open "$FORM_URL" &

# Deactivate the virtual environment
deactivate

echo "All scripts completed successfully for participant ID: $PARTICIPANT_ID"