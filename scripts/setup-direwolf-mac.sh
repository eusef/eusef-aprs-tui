#!/bin/bash
# setup-direwolf-mac.sh — Configure Direwolf for DigiRig on macOS
#
# What this does:
#   - Ensures Direwolf is installed (via Homebrew, if needed)
#   - Detects your DigiRig audio device and serial port
#   - Generates a direwolf.conf in the app folder (not system-wide)
#   - The APRS TUI app will start/stop Direwolf automatically
#
# What this does NOT do:
#   - Install system services or launch agents
#   - Modify any system configuration
#   - Create files outside the app folder
#
# Signal chain:
#   Radio ↔ DigiRig (USB audio) ↔ Direwolf (software TNC) ↔ APRS TUI
#
# Usage:
#   ./scripts/setup-direwolf-mac.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
DIREWOLF_CONF="$APP_DIR/direwolf.conf"
KISS_PORT=8001

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
DIM='\033[2m'
BOLD='\033[1m'
NC='\033[0m'

info()  { echo -e "${GREEN}✓${NC} $*"; }
warn()  { echo -e "${YELLOW}!${NC} $*"; }
err()   { echo -e "${RED}✗${NC} $*"; }
step()  { echo -e "\n${BOLD}${BLUE}▸ $*${NC}"; }

echo -e "${BOLD}APRS TUI — DigiRig Setup for macOS${NC}"
echo -e "${DIM}Configures Direwolf as a local software TNC.${NC}"
echo -e "${DIM}Direwolf will start/stop automatically with the app.${NC}"

# ─────────────────────────────────────────────
# 1. Pre-flight
# ─────────────────────────────────────────────
step "Checking prerequisites"

if [[ "$(uname)" != "Darwin" ]]; then
    err "This script is for macOS only."
    exit 1
fi
info "macOS $(sw_vers -productVersion) ($(uname -m))"

# ─────────────────────────────────────────────
# 2. Find or install Direwolf
# ─────────────────────────────────────────────
step "Locating Direwolf"

DW_BIN=""
# Check common locations
for candidate in \
    "$(which direwolf 2>/dev/null || true)" \
    "/opt/local/bin/direwolf" \
    "/opt/homebrew/bin/direwolf" \
    "/usr/local/bin/direwolf"; do
    if [[ -n "$candidate" && -x "$candidate" ]]; then
        DW_BIN="$candidate"
        break
    fi
done

if [[ -n "$DW_BIN" ]]; then
    info "Found Direwolf: $DW_BIN"
else
    echo "Direwolf is not installed."
    if command -v brew &>/dev/null; then
        echo -n "Install via Homebrew? [Y/n]: "
        read -r INSTALL_DW
        if [[ ! "$INSTALL_DW" =~ ^[Nn] ]]; then
            brew install direwolf
            DW_BIN="$(which direwolf 2>/dev/null || true)"
            if [[ -z "$DW_BIN" ]]; then
                err "Installation failed"
                exit 1
            fi
            info "Installed: $DW_BIN"
        else
            err "Direwolf is required. Install manually: brew install direwolf"
            exit 1
        fi
    else
        err "Direwolf not found and Homebrew not available."
        echo "  Install Homebrew: https://brew.sh"
        echo "  Then run: brew install direwolf"
        exit 1
    fi
fi

# ─────────────────────────────────────────────
# 3. Detect DigiRig audio device
# ─────────────────────────────────────────────
step "Detecting DigiRig audio device"

echo -e "${DIM}Looking for USB audio devices...${NC}"

AUDIO_DEVICE=""
if system_profiler SPAudioDataType 2>/dev/null | grep -q "USB PnP Sound Device"; then
    AUDIO_DEVICE="USB PnP Sound Device"
    info "Found: \"$AUDIO_DEVICE\" (C-Media CM108)"
else
    warn "\"USB PnP Sound Device\" not detected."
    echo ""
    echo "  Is your DigiRig plugged in?"
    echo ""
    echo "  Available audio devices:"
    system_profiler SPAudioDataType 2>/dev/null \
        | grep -E "^\s+\S" \
        | grep -v "^\s*$" \
        | sed 's/:$//' \
        | sed 's/^  */    /' \
        || true
    echo ""
    echo -n "Enter audio device name (or press Enter for \"USB PnP Sound Device\"): "
    read -r AUDIO_DEVICE
    AUDIO_DEVICE="${AUDIO_DEVICE:-USB PnP Sound Device}"
fi

# ─────────────────────────────────────────────
# 4. Detect serial port (PTT)
# ─────────────────────────────────────────────
step "Detecting DigiRig serial port (for PTT)"

SERIAL_DEVICES=()
for dev in /dev/cu.usbserial-* /dev/cu.SLAB_USBtoUART*; do
    [[ -e "$dev" ]] && SERIAL_DEVICES+=("$dev")
done

PTT_MODE=""
PTT_DEVICE=""

if [[ ${#SERIAL_DEVICES[@]} -eq 0 ]]; then
    echo "  No USB serial ports found."
    echo ""
    echo "  Which DigiRig do you have?"
    echo "    1) DigiRig Mobile  (has serial port for hardware PTT)"
    echo "    2) DigiRig Lite    (no serial port — uses VOX for PTT)"
    echo -n "  Choice [1/2]: "
    read -r DIGIRIG_MODEL
    if [[ "$DIGIRIG_MODEL" == "1" ]]; then
        warn "DigiRig Mobile not detected. Make sure it's plugged in."
        echo -n "  Enter serial port manually, or press Enter for VOX: "
        read -r PTT_DEVICE
        if [[ -n "$PTT_DEVICE" ]]; then
            PTT_MODE="RTS"
        else
            PTT_MODE="VOX"
        fi
    else
        PTT_MODE="VOX"
    fi
elif [[ ${#SERIAL_DEVICES[@]} -eq 1 ]]; then
    PTT_DEVICE="${SERIAL_DEVICES[0]}"
    PTT_MODE="RTS"
    info "Found serial port: $PTT_DEVICE"
else
    echo "  Multiple serial ports found:"
    for i in "${!SERIAL_DEVICES[@]}"; do
        echo "    $((i+1))) ${SERIAL_DEVICES[$i]}"
    done
    echo -n "  Select DigiRig serial port [1-${#SERIAL_DEVICES[@]}]: "
    read -r CHOICE
    IDX=$((CHOICE - 1))
    if [[ $IDX -ge 0 && $IDX -lt ${#SERIAL_DEVICES[@]} ]]; then
        PTT_DEVICE="${SERIAL_DEVICES[$IDX]}"
        PTT_MODE="RTS"
        info "Selected: $PTT_DEVICE"
    else
        err "Invalid choice"
        exit 1
    fi
fi

if [[ "$PTT_MODE" == "VOX" ]]; then
    info "PTT mode: VOX (make sure VOX is enabled on your radio)"
else
    info "PTT mode: RTS via $PTT_DEVICE"
fi

# ─────────────────────────────────────────────
# 5. Get callsign
# ─────────────────────────────────────────────
step "Station callsign"

CALLSIGN=""
APRS_CONFIG="$HOME/Library/Application Support/aprs-tui/config.toml"
if [[ -f "$APRS_CONFIG" ]]; then
    EXISTING_CALL=$(grep -E '^callsign' "$APRS_CONFIG" | head -1 | sed 's/.*= *"//' | sed 's/".*//')
    EXISTING_SSID=$(grep -E '^ssid' "$APRS_CONFIG" | head -1 | sed 's/.*= *//')
    if [[ -n "$EXISTING_CALL" ]]; then
        CALLSIGN="${EXISTING_CALL}-${EXISTING_SSID:-0}"
        info "From APRS TUI config: $CALLSIGN"
    fi
fi

if [[ -z "$CALLSIGN" ]]; then
    echo -n "Your callsign with SSID (e.g., W7PDJ-14): "
    read -r CALLSIGN
    if [[ -z "$CALLSIGN" ]]; then
        err "Callsign is required"
        exit 1
    fi
fi

# ─────────────────────────────────────────────
# 6. Build PTT config line
# ─────────────────────────────────────────────
PTT_LINE="PTT VOX"
if [[ "$PTT_MODE" == "RTS" && -n "$PTT_DEVICE" ]]; then
    PTT_LINE="PTT $PTT_DEVICE RTS"
fi

# ─────────────────────────────────────────────
# 7. Write direwolf.conf in the app folder
# ─────────────────────────────────────────────
step "Writing Direwolf configuration"

if [[ -f "$DIREWOLF_CONF" ]]; then
    cp "$DIREWOLF_CONF" "${DIREWOLF_CONF}.bak"
    warn "Backed up existing config to direwolf.conf.bak"
fi

cat > "$DIREWOLF_CONF" << DWEOF
# ─────────────────────────────────────────────────────
# Direwolf config for macOS + DigiRig
# Generated by APRS TUI: $(date)
# This file lives in the app folder — not system-wide.
# Direwolf is started/stopped by the APRS TUI app.
# ─────────────────────────────────────────────────────

# ── Audio ─────────────────────────────────────────────
# DigiRig uses C-Media CM108 ("USB PnP Sound Device")
# macOS: PortAudio device names (run 'direwolf' to list)
ADEVICE "${AUDIO_DEVICE}" "${AUDIO_DEVICE}"
ARATE 44100

# ── Channel 0 — APRS 1200 baud ───────────────────────
CHANNEL 0
MYCALL ${CALLSIGN}
MODEM 1200

# ── PTT ───────────────────────────────────────────────
# DigiRig Mobile: RTS on CP2102 serial port
# DigiRig Lite:   VOX (enable VOX on radio)
${PTT_LINE}

# ── KISS TCP ──────────────────────────────────────────
# APRS TUI connects to this port
KISSPORT ${KISS_PORT}

# Disable AGW (not needed)
AGWPORT 0

# ── Audio Level Notes ─────────────────────────────────
# "Audio input level is too high":
#   macOS can't adjust CM108 gain. Lower your radio's
#   data/audio output level instead.
# "Audio input level is too low":
#   Increase radio's audio output level.
DWEOF

info "Written: $DIREWOLF_CONF"

# ─────────────────────────────────────────────
# 8. Update APRS TUI config to kiss-tcp
# ─────────────────────────────────────────────
step "Updating APRS TUI config"

if [[ -f "$APRS_CONFIG" ]]; then
    echo "  Set APRS TUI to use KISS TCP (127.0.0.1:$KISS_PORT)?"
    echo -n "  [Y/n]: "
    read -r UPDATE_TUI

    if [[ ! "$UPDATE_TUI" =~ ^[Nn] ]]; then
        if [[ -d "$APP_DIR/.venv" ]]; then
            source "$APP_DIR/.venv/bin/activate" 2>/dev/null || true
        fi

        python3 -c "
import tomllib
from pathlib import Path
import shutil

config_path = Path('''$APRS_CONFIG''')
data = tomllib.loads(config_path.read_bytes().decode())
data['server']['protocol'] = 'kiss-tcp'
data['server']['host'] = '127.0.0.1'
data['server']['port'] = $KISS_PORT

import tomli_w
shutil.copy2(config_path, str(config_path) + '.bak')
config_path.write_bytes(tomli_w.dumps(data).encode())
" 2>/dev/null && info "Config updated: kiss-tcp → 127.0.0.1:$KISS_PORT" \
              || warn "Could not update config automatically. Run: ./wizard.sh --section server"
    fi
else
    warn "No APRS TUI config found. Run ./wizard.sh after setup."
fi

# ─────────────────────────────────────────────
# Done
# ─────────────────────────────────────────────
echo ""
echo -e "${BOLD}${GREEN}━━━ Setup Complete ━━━${NC}"
echo ""
echo -e "  Audio:     \"$AUDIO_DEVICE\""
echo -e "  PTT:       $PTT_MODE ${PTT_DEVICE:+($PTT_DEVICE)}"
echo -e "  Callsign:  $CALLSIGN"
echo -e "  KISS TCP:  127.0.0.1:$KISS_PORT"
echo -e "  Config:    $DIREWOLF_CONF"
echo ""
echo "How it works:"
echo "  - When you run ./start.sh, the app detects direwolf.conf"
echo "  - It starts Direwolf automatically and waits for it to be ready"
echo "  - When you quit the app, Direwolf stops too"
echo ""
echo "Troubleshooting:"
echo "  - Check direwolf.log in the app folder for audio/PTT issues"
echo "  - 'Audio level too high': Lower radio's data output level"
echo "  - Run 'direwolf' alone to see available audio devices"
echo "  - DigiRig Lite: Make sure VOX is enabled on your radio"
echo ""
