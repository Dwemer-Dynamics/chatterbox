#!/bin/bash

BASE_DIR="/home/dwemer"
REPO_URL="https://github.com/Dwemer-Dynamics/chatterbox"
REPO_DIR="$BASE_DIR/chatterbox"
VENV_DIR="$REPO_DIR/venv"

cd "$REPO_DIR"

# Create virtual environment if it doesn't exist
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

if [ -f /etc/dwemerdistro_services.conf ]; then
    # shellcheck disable=SC1091
    source /etc/dwemerdistro_services.conf
fi
export CHATTERBOX_HOST="${CHATTERBOX_HOST:-0.0.0.0}"
export CHATTERBOX_PORT="${CHATTERBOX_PORT:-8023}"

# Launch the service
python3 restapi.py &> log.txt &
