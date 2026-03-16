# APRS-TUI: README / Landing Page Copy

*Use this as the basis for your GitHub README or a project landing page.*

---

# APRS-TUI

**APRS in your terminal. Finally.**

A full-featured APRS client that runs entirely in the terminal. Monitor packets, chat with other operators like you're texting, track stations, and beacon your position from a headless Raspberry Pi, an SSH session, or any machine with a terminal. No GUI. No mouse. No X11.

<!-- screenshot placeholder: add a terminal screenshot or asciinema recording here -->

---

## Why APRS-TUI?

Every existing APRS client (Xastir, YAAC, PinPoint APRS) requires a graphical desktop. That means you can't run them headless, you can't use them over SSH, and you can't leave them running in tmux on a Pi in your shack while you're away.

APRS-TUI changes that. It's built for the terminal from day one, so it works anywhere a terminal does.

---

## What It Does

- **Decode and display APRS packets** in a real-time, color-coded stream with filtering and raw packet view
- **Chat like you're texting** with per-station threaded conversations. Open a chat with any heard station and message back and forth in a familiar text-message-style interface. Delivery confirmation (checkmarks, pending indicators), automatic retries, and persistent history that survives app restarts. A 💬 badge on stations with chat history makes it easy to pick up where you left off.
- **Track heard stations** with distance, bearing, and last-heard timestamps
- **Beacon your position** on a configurable interval
- **Connect to multiple sources** simultaneously: Direwolf (KISS TCP), Bluetooth radios (SPP and BLE), USB TNCs, and APRS-IS internet feeds
- **Auto-discover** Direwolf instances on your network via mDNS
- **Switch configurations on the fly** between your home rig and field setup without restarting

---

## Getting Started

### What You Need

- Python 3.11+
- A packet radio setup (Direwolf + sound card, Bluetooth HT, USB TNC) OR just an internet connection for APRS-IS

### Install

```bash
git clone https://github.com/[your-repo]/aprs-tui.git
cd aprs-tui
pip install -r requirements.txt
```

### Run the Setup Wizard

```bash
./wizard.sh
```

The wizard walks you through everything: detecting your hardware, pairing Bluetooth radios, configuring Direwolf connections, and setting your callsign and SSID. It generates your `config.toml` and any bridge scripts you need.

### Launch

```bash
./start.sh
```

That's it. You're monitoring APRS.

---

## Supported Hardware

| Device | Connection | Notes |
|--------|-----------|-------|
| Direwolf | KISS TCP (:8001) | Auto-discovered via mDNS |
| Kenwood TH-D74/D75 | Bluetooth SPP | Wizard handles pairing + socat bridge |
| BTECH UV-PRO | Bluetooth SPP | Wizard handles pairing + socat bridge |
| Mobilinkd TNC3 | USB serial | Standard KISS serial |
| Mobilinkd TNC4 | Bluetooth LE | Connects out of the box over BLE (tested) |
| NinoTNC, MFJ-1270X | USB serial | Standard KISS serial |
| DigiRig + Mac | Direwolf (KISS TCP) | Included scripts set up Direwolf on demand |
| No radio | APRS-IS | Internet-only monitoring, no hardware needed |

---

## Runs Anywhere a Terminal Does

- **Raspberry Pi** in your shack, running headless 24/7
- **SSH** into your home station from anywhere
- **tmux/screen** sessions that persist when you disconnect
- **Your laptop** in the field for SOTA/POTA activations
- **Linux, macOS**, and WSL2 on Windows

---

## Accessible by Design

APRS-TUI was built from the start to be usable by operators with low vision, color blindness, or who rely on screen readers.

- **Color-blind safe**: Every packet type and message state uses a unique text prefix (`[POS]`, `[MSG]`, `[WX]`, etc.) so nothing depends on color alone. Tested against protanopia, deuteranopia, and tritanopia.
- **WCAG AA contrast**: All text meets a minimum 4.5:1 contrast ratio. Primary text hits 15:1 (WCAG AAA).
- **High contrast mode**: Set `APRS_TUI_HIGH_CONTRAST=1` for pure black/white with no dim text and ratios at 7:1 or above.
- **Monochrome fallback**: Works on `vt100`, `dumb`, or `NO_COLOR=1` terminals using bold, reverse, and underline attributes instead of color.
- **Screen reader friendly**: Keyboard-only operation, plain ASCII panel titles, predictable column layouts, BEL alerts on incoming messages, and no decorative Unicode.
- **No blinking, no animations**: Nothing flashes or moves unexpectedly.

---

## Built With

- [Textual](https://textual.textualize.io/) for the terminal UI
- [aprslib](https://github.com/rossengeorgiev/aprs-lib) for packet decoding
- Python asyncio for non-blocking I/O across all transports
- [Pydantic](https://docs.pydantic.dev/) for configuration validation

---

## Status

APRS-TUI is in active development approaching beta. Core functionality (packet decoding, messaging, beaconing, multi-transport support) is working. Field testing is ongoing across multiple hardware configurations.

Bug reports and feedback welcome. See [CONTRIBUTING.md] for details.

---

## License

[Your license here]

---

*73 de [Your Callsign]*
