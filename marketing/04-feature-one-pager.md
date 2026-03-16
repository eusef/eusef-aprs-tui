# APRS-TUI Feature One-Pager

## APRS-TUI

### APRS in your terminal. Finally.

The first and only terminal-based APRS client for amateur radio. Monitor packets, chat with other operators like you're texting, track stations, and beacon your position from any terminal, including headless systems, SSH sessions, and tmux.

---

### The Problem

Every APRS client available today requires a graphical desktop environment:

| Client | GUI Required | Headless | SSH | tmux | Threaded Chat | Persistent History | WCAG Contrast | Color-Blind Safe |
|--------|-------------|----------|-----|------|--------------|-------------------|--------------|-----------------|
| Xastir | Yes | No | No | No | No | No | No | No |
| YAAC | Yes (Java) | No | No | No | No | No | No | No |
| PinPoint APRS | Yes (Windows) | No | No | No | No | No | No | No |
| **APRS-TUI** | **No** | **Yes** | **Yes** | **Yes** | **Yes** | **Yes** | **Yes (AA+)** | **Yes** |

If you run a Raspberry Pi with Direwolf in your shack, you currently have no way to get a proper APRS interface without a monitor, keyboard, and desktop environment. APRS-TUI fixes that.

---

### Core Features

**Packet Monitoring**
Real-time color-coded packet stream. Filter by packet type. Toggle raw packet view. All keyboard-driven.

**Chat / Messaging**
Text-message-style conversations with any station. Select a station from the heard list, press Enter, and you're in a threaded chat. Messages show delivery status in real time: ✓ delivered, ⏳ pending, ✗ failed. Automatic retries follow the APRS standard schedule (30s, 60s, 120s). Chat history is saved to disk and persists across restarts. Stations with chat history display a 💬 badge so you can pick up right where you left off. Toast notifications alert you to new incoming messages.

**Station Tracking**
Live list of heard stations with callsign, distance from your QTH, bearing, and last-heard timestamp.

**Position Beaconing**
Transmit your position on a configurable interval. Set your symbol, comment, and coordinates.

**Multi-Transport**
Connect to any combination of these simultaneously:

| Transport | Example Hardware |
|-----------|-----------------|
| KISS TCP | Direwolf (auto-discovered via mDNS) |
| Bluetooth SPP | Kenwood TH-D74, TH-D75, BTECH UV-PRO |
| Bluetooth LE | Mobilinkd TNC4 (connects out of the box, tested) |
| USB Serial | Mobilinkd TNC3, NinoTNC, MFJ-1270X |
| DigiRig + Mac | Direwolf via included on-demand setup scripts |
| APRS-IS | Internet feed (no radio required) |

**Guided Setup Wizard**
Run `./wizard.sh` and it detects your hardware, handles Bluetooth pairing, discovers Direwolf on your network, and generates all config files and bridge scripts. No hand-editing required.

**Field Switching**
Open the command palette (Ctrl+W) to reconfigure on the fly. Switch between your home Direwolf rig and a field Bluetooth radio without restarting the application.

---

### Ideal Setups

**Home Station (24/7 monitoring)**
Raspberry Pi + Direwolf + sound card or SDR. APRS-TUI in tmux. SSH in from anywhere.

**Mac + DigiRig**
macOS with a DigiRig audio interface. Included scripts set up Direwolf on demand. Run `./wizard.sh`, then `./start.sh`.

**Field Portable (SOTA/POTA)**
Laptop + Bluetooth HT (TH-D74, UV-PRO) or Mobilinkd TNC4 (connects over BLE out of the box). Pair via wizard, monitor and message from the summit.

**Internet Monitor (no radio)**
Any computer with a terminal. Connect to APRS-IS and watch the feed. Great entry point for new hams.

**Dual Mode**
Run KISS and APRS-IS simultaneously. APRS-TUI deduplicates packets automatically so you see both local RF and the wider network in one view.

---

### Accessible by Design

APRS-TUI was built from the start to be usable by all operators, including those with low vision, color blindness, or who use screen readers.

| Feature | Implementation |
|---------|---------------|
| Color blindness | Every packet type and message state uses a unique text prefix (`[POS]`, `[MSG]`, `[WX]`, `>>`, `✓`). Nothing depends on color alone. Tested against protanopia, deuteranopia, and tritanopia. |
| Low vision | WCAG AA contrast minimum (4.5:1). Primary text at 15:1 (AAA). High contrast mode via `APRS_TUI_HIGH_CONTRAST=1` with 7:1+ ratios and no dim text. |
| Screen readers | Keyboard-only operation. Plain ASCII panel titles. Predictable column layouts. BEL alerts (`\a`) on incoming messages. No decorative Unicode. |
| Basic terminals | Monochrome fallback for `vt100`, `dumb`, or `NO_COLOR=1`. Uses bold, reverse, and underline instead of color. ASCII box drawing instead of Unicode. |
| Graceful degradation | Three-tier color support: 24-bit true color, 256-color, 16-color ANSI, monochrome. Auto-detected from terminal capabilities. |
| Safety | No blinking, no animations, no flashing content anywhere in the interface. |

---

### Technical Details

- **Language:** Python 3.11+
- **UI Framework:** Textual (SSH-safe, no X11)
- **Architecture:** Async-first (asyncio), non-blocking I/O on all transports
- **Config:** TOML with Pydantic validation, shared between wizard and TUI
- **Responsive:** 5 layout breakpoints (XL/LG/MD/SM/XS) for different terminal sizes
- **Platforms:** Linux, macOS, Raspberry Pi OS, WSL2

---

### Status

Approaching beta. 8 development sprints completed. Core features are functional and undergoing field testing across multiple hardware configurations.

**Get started:** `git clone` > `pip install` > `./wizard.sh` > `./start.sh`

---

*Open source. Built for the amateur radio community.*

*73 de [Your Callsign]*
