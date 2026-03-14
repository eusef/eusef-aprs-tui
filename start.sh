#!/bin/bash
# start.sh - Launch the APRS TUI application
# Uses the config written by the wizard at the default platform path.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"

# Activate venv
if [ ! -d "$VENV_DIR" ]; then
    echo "Virtual environment not found. Setting up..."
    python3 -m venv "$VENV_DIR"
    source "$VENV_DIR/bin/activate"
    pip install -r "$SCRIPT_DIR/requirements.txt"
else
    source "$VENV_DIR/bin/activate"
fi

# Launch TUI (uses default config path, or run wizard if none exists)
python -m aprs_tui "$@"
