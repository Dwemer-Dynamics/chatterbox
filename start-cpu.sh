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

export CHATTERBOX_HOST="${CHATTERBOX_HOST:-0.0.0.0}"
if [ -z "${CHATTERBOX_PORT:-}" ] && [ -f "$REPO_DIR/.dwemerdistro-port" ]; then
    CHATTERBOX_PORT="$(tr -d '[:space:]' < "$REPO_DIR/.dwemerdistro-port")"
fi
case "${CHATTERBOX_PORT:-}" in
    ''|*[!0-9]*) CHATTERBOX_PORT=8020 ;;
esac
export CHATTERBOX_PORT

# Launch the service
python3 restapi.py &> log.txt &
