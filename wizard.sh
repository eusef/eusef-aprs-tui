#!/bin/bash
# wizard.sh - Run the APRS TUI setup wizard

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"

if [ ! -d "$VENV_DIR" ]; then
    echo "Run ./setup.sh first to install dependencies."
    exit 1
fi

source "$VENV_DIR/bin/activate"
python "$SCRIPT_DIR/wizard.py" "$@"
