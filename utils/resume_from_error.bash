#!/bin/bash

# Check if participant ID and condition was provided
# Usage check
if [ $# -lt 2 ]; then
  echo "Usage: $0 <participant_id> <mode>"
  echo "Modes: 0 or 1" # 0 for control, 1 for experimental
  exit 1
fi

PARTICIPANT_ID="$1"
MODE="$2"

SAVE_DIR="/media/cairo/T7/handover_project/participant_data"
# SAVE_DIR="$MAIN_S_DIR/$PARTICIPANT_ID"

# mkdir $SAVE_DIR
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

# Run the tutorial
# python3 evaluation/treasure_hunt_py/treasure_hunt/scripts/tutorial.py
# if [ $? -ne 0 ]; then
#   echo "Error: tutorial.py failed"
#   deactivate
#   exit 1
# fi

# Run the main task (with distractor enabled by default)
python3 evaluation/treasure_hunt_py/treasure_hunt/scripts/main.py --load "$PARTICIPANT_ID" --save "$PARTICIPANT_ID" >> $SAVE_DIR/$PARTICIPANT_ID.log

if [ $? -ne 0 ]; then
  echo "Error: main.py failed"
  deactivate
  exit 1
fi

# Run the report script
if [ "$MODE" = "0" ]; then
  # Run the control task
  python3 src/control_chat.py --pid "$PARTICIPANT_ID"
  if [ $? -ne 0 ]; then
    echo "Error: chat.py failed"
    deactivate
    exit 1
  fi

elif [ "$MODE" = "1" ]; then
  # Run the experimental task
  python3 src/chat.py --pid "$PARTICIPANT_ID"
  if [ $? -ne 0 ]; then
    echo "Error: chat.py failed"
    deactivate
    exit 1
  fi
fi

# Open a Google form (prefilled with participant ID)
FORM_URL="https://docs.google.com/forms/d/e/1FAIpQLSfPgIEZrhDuRiT05bJwh8mTntwEoBOcxFgZJbiCqXsBOAx6Hw/viewform?usp=pp_url"
FORM_URL+="&entry.2058389802=$PARTICIPANT_ID"

xdg-open "$FORM_URL"

# Deactivate the virtual environment
deactivate

echo "All scripts completed successfully for participant ID: $PARTICIPANT_ID"