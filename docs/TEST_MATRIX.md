# APRS TUI - Hardware/Software Test Matrix

## Test Environments

| # | Environment | Status |
|---|-------------|--------|
| E1 | macOS (your Mac) | Available |
| E2 | Raspberry Pi 4 (direwolf.local) | Available |
| E3 | SSH session (Mac → Pi) | Available |
| E4 | tmux session | Not tested |

## Connection Configurations

| # | Config | Transport | Source | Environment |
|---|--------|-----------|--------|-------------|
| C1 | KISS TCP → Direwolf on Pi | kiss-tcp | DigiRig + radio | E1 → E2 |
| C2 | BT Serial → Mobilinkd TNC4 | kiss-bt | Mobilinkd + radio | E1 |
| C3 | APRS-IS (receive only) | aprs-is | Internet | E1 |
| C4 | APRS-IS (TX/RX with passcode) | aprs-is | Internet | E1 |
| C5 | USB Serial → Mobilinkd (if supported) | kiss-serial | Mobilinkd USB | E1 |
| C6 | KISS TCP → Direwolf on Pi | kiss-tcp | DigiRig + radio | E2 (local) |

## Manual QA Scenarios

### First Run & Config

| # | Scenario | Steps | Expected | Status |
|---|----------|-------|----------|--------|
| T01 | Fresh first run | Delete config, run `./start.sh` | Wizard auto-launches | |
| T02 | Wizard full flow | `./wizard.sh` → complete all sections | Config written, summary shown | |
| T03 | Wizard section run | `./wizard.sh --section station` | Only callsign/SSID prompted | |
| T04 | Wizard re-run | Run wizard twice | `config.toml.bak` created | |
| T05 | Invalid config | Edit config with bad callsign | Clear error on TUI launch | |
| T06 | F2 inline wizard | Press Ctrl+W in TUI | TUI suspends, wizard runs, TUI resumes | |

### KISS TCP (Direwolf on Pi)

| # | Scenario | Steps | Expected | Status |
|---|----------|-------|----------|--------|
| T07 | Connect to Direwolf | Config: kiss-tcp, direwolf.local:8001 | Status bar: CONNECTED | BLOCKED (TCP issue) |
| T08 | Receive packets | Wait for RF traffic | Packets appear in stream, color-coded | |
| T09 | Station tracking | Receive position packets | Station panel populates with distance/bearing | |
| T10 | Auto-reconnect | Kill Direwolf, restart it | Status: RECONNECTING → CONNECTED | |
| T11 | Health watchdog | Connect, no traffic for 60s | Warning indicator in status bar | |

### Bluetooth Serial (Mobilinkd TNC4 on Mac)

| # | Scenario | Steps | Expected | Status |
|---|----------|-------|----------|--------|
| T12 | Wizard BT detect | `./wizard.sh --section server` → BT | `/dev/cu.TNC4Mobilinkd` auto-detected | |
| T13 | BT connect | Config: kiss-bt, /dev/cu.TNC4Mobilinkd | Status bar: CONNECTED (BT KISS) | |
| T14 | Receive packets | Radio on 144.390, wait for traffic | Packets in stream panel | |
| T15 | BT disconnect | Power off Mobilinkd | TUI detects disconnect, RECONNECTING | |
| T16 | BT reconnect | Power Mobilinkd back on | TUI reconnects automatically | |
| T17 | Phone app conflict | Open Mobilinkd app on phone | TUI loses connection (expected) | |

### APRS-IS (Internet)

| # | Scenario | Steps | Expected | Status |
|---|----------|-------|----------|--------|
| T18 | APRS-IS connect | Config: aprs-is, rotate.aprs2.net | Status: CONNECTED (APRS-IS RX only) | |
| T19 | Receive packets | Wait | Global APRS traffic streams in | |
| T20 | Filter | Set filter: r/45.4/-122.6/100 | Only local packets shown | |
| T21 | RX-only blocks TX | Try to send message | Blocked (no passcode) | |

### Messaging

| # | Scenario | Steps | Expected | Status |
|---|----------|-------|----------|--------|
| T22 | Compose message | Press `c`, enter callsign + text | Message sent, shows PENDING | |
| T23 | Ack received | Other station acks | Status changes to ACKED | |
| T24 | Retry on no ack | Wait 30s | Retry sent (30s, 60s, 120s schedule) | |
| T25 | Message timeout | No ack after 5 retries | Status: FAILED | |
| T26 | Receive message | Other station sends to you | Appears in inbox, auto-ack sent | |

### Beaconing

| # | Scenario | Steps | Expected | Status |
|---|----------|-------|----------|--------|
| T27 | Enable beacon | Press `b` | Beacon timer starts, status bar shows BCN | |
| T28 | Beacon transmits | Wait for interval | Position packet sent via transport | |
| T29 | Disable beacon | Press `b` again | Timer stops, no more beacons | |
| T30 | Beacon parseable | Capture beacon with another station | Valid APRS position packet | |

### UI & Navigation

| # | Scenario | Steps | Expected | Status |
|---|----------|-------|----------|--------|
| T31 | Vim scrolling | Press j/k in stream panel | Scrolls up/down | |
| T32 | Panel switching | Press Tab | Focus cycles between panels | |
| T33 | Command palette | Press `:` or Ctrl+P | Command palette opens, fuzzy search works | |
| T34 | Raw toggle | Press `r` | Raw packet text shown below decoded | |
| T35 | Help | Press `?` | Key hints notification shown | |
| T36 | Quit | Press `q` | App exits cleanly, transport disconnected | |
| T37 | SSH session | SSH to Mac/Pi, run TUI | All keyboard nav works, no mouse needed | |
| T38 | tmux session | Run TUI inside tmux | No terminal conflicts, resize works | |

### Platform-Specific

| # | Scenario | Steps | Expected | Status |
|---|----------|-------|----------|--------|
| T39 | Pi Direwolf setup | Run `setup-direwolf-pi.sh` | Direwolf installs, DigiRig detected, service running | Partial |
| T40 | Pi mDNS discovery | Run wizard on Mac | Direwolf on Pi auto-discovered | |
| T41 | Pi firewall | Connect to Pi:8001 from Mac | TCP connection succeeds | BLOCKED |
| T42 | Mac BT auto-detect | Run wizard BT section | Lists /dev/cu.* BT devices | |

### Edge Cases

| # | Scenario | Steps | Expected | Status |
|---|----------|-------|----------|--------|
| T43 | Malformed packet | Send garbage to KISS port | Raw displayed with warning, no crash | |
| T44 | Dual mode dedup | KISS + APRS-IS same packet | Only shown once in stream | |
| T45 | Packet logging | Enable logging, receive packets | Daily log file created in data dir | |
| T46 | Config hot-reload | Ctrl+W → change server → save | TUI reconnects to new server | |

## Known Issues

1. **TCP to Pi blocked** - Port 8001 on Pi unreachable from Mac despite firewall flushed. SSH works. Likely Firewalla Gold SE router rule. Workaround: SSH tunnel `ssh -L 8001:127.0.0.1:8001 phil@direwolf.local -N`
2. **Mobilinkd phone app conflict** - TNC4 only allows one BT connection. Close phone app before using TUI.
