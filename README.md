# aprs-tui

[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/philj2)

A keyboard-driven terminal interface for [APRS](https://en.wikipedia.org/wiki/Automatic_Packet_Reporting_System) — monitor stations, send messages, and beacon your position, all from the command line.

Connects to any KISS TCP endpoint: a local [Direwolf](https://github.com/wb2osz/direwolf) instance, a Bluetooth TNC (Kenwood TH-D74/D75, Mobilinkd, UV-Pro), a remote server over your LAN, or the APRS-IS internet gateway — with no code changes. A companion setup wizard handles all hardware configuration interactively.

![aprs-tui screenshot](eusef-aprs-tui-demo.gif)

## Features

- **Multi-transport** — KISS TCP, Bluetooth SPP, KISS serial, and APRS-IS in one app
- **mDNS auto-discovery** — finds Direwolf servers on your LAN automatically
- **Full APRS decode** — position (uncompressed + compressed + Mic-E), messages, objects, weather, status, telemetry
- **Send messages** — with automatic ack tracking and retry
- **Position beaconing** — fixed interval or smart beacon; configurable symbol and comment
- **F2 field switch** — swap from home Direwolf to Bluetooth radio at a park without restarting
- **Setup wizard** — interactive configuration for every hardware path, with live connection tests
- **SSH-safe** — keyboard-only navigation, no mouse dependency
- **tmux/screen friendly** — no terminal ownership assumptions
- **Terminal map** — braille-rendered map with tile downloads, station overlay, and movement tracks
- **Chat** — peer-to-peer messaging with compose, ack tracking, and retry
- **Command palette** — `?` key opens searchable command list
- **Direwolf management** — optionally manage a local Direwolf subprocess

## Requirements

- Python **3.11+**
- Linux, macOS, or Raspberry Pi OS (WSL2 supported; Windows native not supported)
- A KISS TCP endpoint — Direwolf, a Bluetooth TNC bridge, or APRS-IS

Direwolf can run standalone or be managed as a subprocess by the TUI. For standalone use, install and configure Direwolf separately with `KISSPORT 8001` set in `direwolf.conf`. See [wb2osz/direwolf](https://github.com/wb2osz/direwolf).

## Installation

### Recommended (one command)

```bash
git clone https://github.com/eusef/eusef-aprs-tui.git
cd eusef-aprs-tui
./setup.sh
```

`setup.sh` detects your OS, installs system dependencies (`socat`, `python3`), creates a virtualenv, and installs all Python packages.

### Manual

```bash
git clone https://github.com/eusef/eusef-aprs-tui.git
cd eusef-aprs-tui
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Quick Start

First run - the TUI detects no config and launches the wizard automatically:

```bash
./start.sh
```

Or without the wrapper:

```bash
source .venv/bin/activate
python -m aprs_tui
```

Run the wizard standalone:

```bash
./wizard.sh                        # or: python wizard.py
./wizard.sh --section server       # change just the connection
```

### CLI flags

| Flag | Description |
|---|---|
| `--config PATH` | Use a custom config file |
| `--log-level LEVEL` | `DEBUG`, `INFO`, `WARNING` (default), or `ERROR` |

## Setup Wizard

The wizard handles all hardware setup interactively. Run it standalone or from inside the TUI.

```bash
python wizard.py                    # Full guided setup
python wizard.py --section server   # Change server / connection only
python wizard.py --section bt       # Re-pair Bluetooth TNC
python wizard.py --section station  # Update callsign or SSID
python wizard.py --section beacon   # Adjust beacon settings
python wizard.py --section aprs-is  # Configure internet gateway
python wizard.py --test             # Connection tests only
```

The wizard:
- Detects your OS and checks dependencies (`socat`, `rfcomm`, `avahi-browse`)
- Scans for KISS TNC servers on your LAN via mDNS
- Guides Bluetooth pairing and generates a `start-bt-bridge.sh` socat script
- Offers to install a systemd/launchd unit for automatic bridge startup
- Runs a live connection test at every hardware step
- Backs up your existing `config.toml` before overwriting

## Configuration

Config is written by the wizard to `~/.config/aprs-tui/config.toml`. Override the path with `--config`.

```toml
[station]
callsign = "W7XXX-9"
ssid = 9
symbol = "/>"          # Car symbol (APRS symbol table + code)
comment = "Field portable"

[server]
host = "raspberrypi.local"
port = 8001
protocol = "kiss"
reconnect_interval_sec = 10
reconnect_max_attempts = 0   # 0 = infinite

[beacon]
enabled = true
interval_sec = 600
smart_beacon = false
lat = 45.4215
lon = -122.6819

[aprs_is]
enabled = false
server = "rotate.aprs2.net"
port = 14580
passcode = ""          # Leave blank for receive-only
filter = "r/45.4/-122.6/50"
```

## Hardware Support

| Connection type | Path | Notes |
|---|---|---|
| Direwolf (USB / SDR) | KISS TCP | Set `KISSPORT 8001` in `direwolf.conf` |
| Kenwood TH-D74 / TH-D75 | Bluetooth SPP | Enable BT KISS TNC in radio menu |
| Mobilinkd TNC | Bluetooth SPP | Hold button to enter pairing mode |
| Radioddity UV-Pro | Bluetooth SPP | Confirm KISS mode in device settings |
| Generic HW TNC | Serial / socat | Wizard generates bridge script |
| APRS-IS | TCP (internet) | Receive-only without a validated passcode |
| Remote headless | KISS TCP over LAN | Radio + Direwolf on Pi, TUI on laptop |

### Bluetooth on Linux

The wizard uses `rfcomm` and `socat` to bridge your Bluetooth radio to a local KISS TCP port. A generated `start-bt-bridge.sh` script and optional systemd unit handle reconnection automatically.

```bash
# Example generated bridge script
rfcomm bind /dev/rfcomm0 AA:BB:CC:DD:EE:FF
socat TCP-LISTEN:8001,reuseaddr,fork FILE:/dev/rfcomm0,b9600,raw,echo=0
```

If `rfcomm bind` returns permission denied, add yourself to the `dialout` group:

```bash
sudo usermod -aG dialout $USER   # then log out and back in
```

### mDNS Auto-Discovery

To enable automatic server discovery, add one line to your Direwolf startup script on the host machine:

```bash
# Linux (Avahi)
avahi-publish-service "Direwolf KISS" _kiss-tnc._tcp 8001 &

# macOS (Bonjour)
dns-sd -R "Direwolf KISS" _kiss-tnc._tcp . 8001 &
```

The wizard will find the server automatically on future runs. Service type: `_kiss-tnc._tcp`.

## Keyboard Reference

### General

| Key | Action |
|---|---|
| `q` | Quit |
| `?` | Command palette |
| `Ctrl+W` | Config wizard |
| `Tab` | Next panel |
| `j` / `k` | Scroll up / down |
| `:` | Command mode |
| `F2` | Quick-switch server (field switch) |

### Messages

| Key | Action |
|---|---|
| `c` | Compose message |
| `Enter` | Open chat (from station list) |
| `x` | Cancel message retries |
| `y` | Copy last packet |

### Map

| Key | Action |
|---|---|
| `m` / `M` | Toggle map (large / small) |
| `+` / `-` | Zoom in / out |
| Arrow keys | Pan (Shift = fast) |
| `a` | Auto-zoom toggle |
| `0` | Reset zoom |
| `n` / `N` | Next / prev station |
| `f` | Fullscreen map |
| `g` | Legend toggle |

### Map Filters

| Key | Action |
|---|---|
| `i` | APRS-IS stations |
| `R` | RF stations |
| `w` | Weather |
| `d` | Digipeaters |
| `t` | Tracks |

### Other

| Key | Action |
|---|---|
| `b` | Beacon on / off |
| `r` | Raw packets |
| `Esc` | Close overlay |

### Commands

| Command | Action |
|---|---|
| `:config` | Full reconfigure (launches wizard) |
| `:config server` | Switch server / connection type |
| `:config bt` | Re-pair Bluetooth device |
| `:config station` | Change callsign or SSID |
| `:config beacon` | Adjust beacon interval or position |
| `:config aprs-is` | Toggle internet gateway |
| `:connect` | Reconnect to current server |
| `:disconnect` | Drop connection, stay in TUI |

## Field Switching

Press `F2` or type `:config server` from inside the running TUI. The app suspends cleanly, the wizard runs in the same terminal, and the TUI reconnects automatically with the new configuration when you're done. No restart needed.

## APRS-IS Passcode

Transmitting to APRS-IS requires a validated callsign passcode. Receive-only mode works without one. Generate your passcode at [apps.magicbug.co.uk/passcode](https://apps.magicbug.co.uk/passcode/).

## Common SSID Conventions

| SSID | Use |
|---|---|
| -0 | Fixed home station |
| -1 | Digipeater |
| -5 | Handheld |
| -7 | Walkie-talkie (low power) |
| -9 | Mobile / vehicle |
| -14 | Netbook / tablet |

## Troubleshooting

Logs are written to a platform-specific data directory:

| Platform | Path |
|---|---|
| Linux | `~/.local/share/aprs-tui/aprs-tui.log` |
| macOS | `~/Library/Application Support/aprs-tui/aprs-tui.log` |

Increase verbosity:

```bash
python -m aprs_tui --log-level DEBUG
```

## Development

```bash
./setup.sh                           # or: pip install -r requirements-dev.txt
```

### Tests

Three tiers, all run in CI:

| Tier | Command | Timeout |
|---|---|---|
| Unit | `pytest tests/unit/ -v` | 30s |
| Integration | `pytest tests/integration/ -v` | 60s |
| Acceptance | `pytest tests/acceptance/ -v` | 120s |

Skip hardware-dependent tests:

```bash
pytest -m "not slow"
pytest -m "not bluetooth"
pytest -m "not serial"
```

### Code quality

- **Linter:** Ruff (rules: E, F, W, I, N, UP, B, A, SIM)
- **Line length:** 100
- **Coverage floor:** 80% (enforced in CI)
- **CI matrix:** Python 3.11 / 3.12 / 3.13 on Ubuntu + macOS

## Support This Project

If aprs-tui saves you time at a park activation or helps you get on APRS, consider buying me a coffee.

[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/philj2)

## License

MIT — see [LICENSE](LICENSE).
