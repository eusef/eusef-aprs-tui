#!/bin/bash
# setup.sh - One-time setup for APRS TUI
# Installs system dependencies, creates venv, installs Python packages.

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"

echo "==================================="
echo "  APRS TUI - Setup"
echo "==================================="
echo

# Detect platform
OS="$(uname -s)"
echo "Platform: $OS"

# --- System dependencies ---
echo
echo "Checking system dependencies..."

if [ "$OS" = "Darwin" ]; then
    # macOS
    if ! command -v brew &>/dev/null; then
        echo "[!] Homebrew not found. Install it from https://brew.sh"
        echo "    Then re-run this script."
        exit 1
    fi

    MISSING=()
    command -v socat &>/dev/null || MISSING+=("socat")
    command -v python3 &>/dev/null || MISSING+=("python3")

    if [ ${#MISSING[@]} -gt 0 ]; then
        echo "Installing: ${MISSING[*]}"
        brew install "${MISSING[@]}"
    else
        echo "  All system dependencies installed."
    fi

elif [ "$OS" = "Linux" ]; then
    MISSING=()
    command -v socat &>/dev/null || MISSING+=("socat")
    command -v python3 &>/dev/null || MISSING+=("python3")

    if [ ${#MISSING[@]} -gt 0 ]; then
        echo "Installing: ${MISSING[*]}"
        if command -v apt-get &>/dev/null; then
            sudo apt-get update && sudo apt-get install -y "${MISSING[@]}" python3-venv
        elif command -v dnf &>/dev/null; then
            sudo dnf install -y "${MISSING[@]}" python3-venv
        elif command -v pacman &>/dev/null; then
            sudo pacman -S --noconfirm "${MISSING[@]}" python
        else
            echo "[!] Unknown package manager. Please install manually: ${MISSING[*]}"
            exit 1
        fi
    else
        echo "  All system dependencies installed."
    fi
fi

# --- Python version check ---
echo
PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PYTHON_MAJOR=$(python3 -c "import sys; print(sys.version_info.major)")
PYTHON_MINOR=$(python3 -c "import sys; print(sys.version_info.minor)")

if [ "$PYTHON_MAJOR" -lt 3 ] || [ "$PYTHON_MINOR" -lt 11 ]; then
    echo "[!] Python 3.11+ required (found $PYTHON_VERSION)"
    exit 1
fi
echo "Python $PYTHON_VERSION OK"

# --- Virtual environment ---
echo
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
else
    echo "Virtual environment exists."
fi

source "$VENV_DIR/bin/activate"

# --- Python packages ---
echo
echo "Installing Python packages..."
pip install --quiet --upgrade pip
pip install --quiet -r "$SCRIPT_DIR/requirements.txt"

echo
echo "==================================="
echo "  Setup complete!"
echo "==================================="
echo
echo "Next steps:"
echo "  1. Run the wizard:     ./wizard.sh"
echo "  2. Start the TUI:      ./start.sh"
echo
echo "If using Bluetooth TNC:"
echo "  1. Pair your device in system Bluetooth settings"
echo "  2. Run the bridge:     ./start-bt-bridge.sh  (in a separate terminal)"
echo "  3. Then start the TUI: ./start.sh"
