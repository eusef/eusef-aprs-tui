# APRS-TUI: Social Media & Forum Posts

---

## Reddit: r/amateurradio (Launch Post)

**Title:** I built the first terminal-based APRS client. Runs on a headless Pi, over SSH, in tmux. No GUI needed.

**Body:**

Hey all,

I've been working on something I've wanted for a long time: a proper APRS client that runs entirely in the terminal.

**The problem:** Every APRS client out there (Xastir, YAAC, PinPoint) needs a graphical desktop. If you want to monitor APRS on a headless Pi in your shack, you're stuck with raw text output or VNC. Want to check on your station from your phone over SSH? Tough luck.

**APRS-TUI** is a full-featured terminal APRS client built with Python and Textual. Here's what it does:

- Real-time color-coded packet stream with filtering
- **Text-message-style chat**: open a conversation with any station and message back and forth like you're texting. Per-station threads, delivery checkmarks, auto-retries, and persistent history that's saved to disk and survives restarts. Stations with chat history get a 💬 badge so you can pick up where you left off.
- Station tracking with distance and bearing
- Position beaconing
- Connects to Direwolf (KISS TCP), Bluetooth HTs (Kenwood TH-D74/D75, BTECH UV-PRO), USB TNCs (Mobilinkd, NinoTNC), and APRS-IS
- **Mobilinkd TNC4 connects out of the box over BLE** (tested and verified)
- Includes scripts to set up **Direwolf on demand on macOS** with a DigiRig
- Guided setup wizard (`wizard.sh`) that handles Bluetooth pairing and generates bridge scripts
- Auto-discovers Direwolf on your network via mDNS
- Switch between home and field configs without restarting
- Launch with `./start.sh` and you're monitoring

It's designed to run on a Pi in tmux and just stay up. SSH in from wherever, and your APRS station is right there. Open a chat with a station and it feels like iMessage over RF.

It's also built with accessibility in mind. Color-blind-safe text prefixes on every packet type and message state, WCAG AA contrast ratios, a high contrast mode (`APRS_TUI_HIGH_CONTRAST=1`), monochrome fallback for basic terminals, and screen reader compatibility. Nothing depends on color alone.

Still approaching beta, but core features are solid. Happy to take feedback.

[GitHub link]

73 de [callsign]

---

## Reddit: r/amateurradio (Short / Follow-up)

**Title:** APRS-TUI: terminal APRS client that runs over SSH on a headless Pi

**Body:**

Quick update on a project I've been working on. APRS-TUI is a terminal-based APRS client. Think of it as what you'd want if you have a Pi + Direwolf in your shack and you just want to SSH in and see what's on the air.

Supports KISS TCP, Bluetooth radios (Mobilinkd TNC4 connects over BLE out of the box), USB TNCs, and APRS-IS. Has a setup wizard (`wizard.sh`) so you don't have to hand-edit config files. On Mac with a DigiRig, included scripts get Direwolf running on demand. The chat feature works like texting: per-station conversations with delivery confirmation and history saved to disk.

Link in comments. Feedback welcome.

73

---

## Reddit: r/RTLSDR or r/raspberry_pi (Cross-post angle)

**Title:** Terminal-based APRS client for your Pi + SDR setup. No desktop environment needed.

**Body:**

If you're running Direwolf with an RTL-SDR on a Raspberry Pi, you probably know the pain of trying to monitor APRS without a full desktop. APRS-TUI is a terminal client that connects to Direwolf over KISS TCP and gives you a proper packet display, text-message-style chat with persistent history, station tracking, and beaconing, all in the terminal.

Runs great in tmux over SSH. Setup wizard auto-discovers Direwolf on your network.

[GitHub link]

---

## Twitter/X Thread

**Post 1:**
Introducing APRS-TUI: the first terminal-based APRS client for amateur radio.

No GUI. No mouse. No X11. Just APRS in your terminal.

Runs on a headless Pi, over SSH, in tmux. Connects to Direwolf, Bluetooth radios, USB TNCs, and APRS-IS.

[screenshot]

**Post 2:**
Why build this? Because every APRS client out there requires a graphical desktop. If you run a Pi + Direwolf headless, your only option was raw text dumps.

APRS-TUI gives you a real interface: color-coded packets, text-message-style chat with delivery confirmation and persistent history, station list, beaconing.

**Post 3:**
The chat feature is my favorite part. Open a conversation with any heard station and it works like texting:

- Per-station threaded conversations
- Delivery checkmarks (✓ delivered, ⏳ pending)
- Auto-retry if no ack
- History saved to disk, survives restarts
- 💬 badge on stations you've chatted with

APRS messaging the way it should feel.

**Post 4:**
Getting started is simple. The setup wizard (wizard.sh) handles the hard parts:

- Detects your hardware
- Pairs Bluetooth radios
- Finds Direwolf on your network via mDNS
- Generates config and bridge scripts

Mobilinkd TNC4 connects over BLE out of the box. On Mac with a DigiRig, included scripts set up Direwolf on demand.

Run ./start.sh and you're on the air.

**Post 5:**
Accessibility was a priority from day one:

- Color-blind safe: every state uses unique text prefixes, not just color
- WCAG AA contrast (primary text at 15:1)
- High contrast mode for low vision
- Monochrome fallback for basic terminals
- Screen reader friendly: keyboard-only, plain ASCII, BEL alerts

Ham radio software should be usable by everyone.

**Post 6:**
Open source, Python 3.11+, approaching beta. Looking for field testers.

GitHub: [link]

73 de [callsign]

---

## QRZ Forums Post

**Title:** APRS-TUI: Terminal-Based APRS Client for Headless / SSH Operation

**Body:**

Fellow hams,

I'd like to share a project I've been developing: APRS-TUI, a terminal-based APRS client designed specifically for headless operation.

**The gap it fills:** All current APRS clients (Xastir, YAAC, PinPoint APRS) require a graphical desktop environment. This means you can't run them on a headless Raspberry Pi, over SSH, or in a tmux session. APRS-TUI solves this by providing a full-featured APRS interface that runs entirely in the terminal.

**Key capabilities:**
- Real-time packet decoding with color-coded display
- Text-message-style chat: per-station threaded conversations with delivery confirmation (✓/⏳), auto-retries, and persistent history saved to disk
- Station tracking with distance and bearing from your QTH
- Position beaconing
- Supports Direwolf (KISS TCP), Bluetooth HTs (TH-D74/D75, UV-PRO), USB TNCs (Mobilinkd, NinoTNC), and APRS-IS
- Mobilinkd TNC4 connects out of the box over BLE (tested and verified)
- Includes scripts to set up Direwolf on demand on macOS with a DigiRig
- Interactive setup wizard (`wizard.sh`) with automatic Bluetooth pairing
- mDNS auto-discovery of Direwolf instances
- Launch with `./start.sh`

**Accessibility:** This was a priority. The interface is designed for operators with low vision or color blindness. Every packet type and message state has a unique text prefix so nothing depends on color alone. All text meets WCAG AA contrast ratios (primary text at 15:1). There's a high contrast mode, a monochrome fallback for basic terminals, and screen reader support with keyboard-only operation, plain ASCII labels, and BEL alerts for incoming messages.

**Typical setup:** Raspberry Pi running Direwolf with a sound card or SDR, APRS-TUI running in tmux. SSH in from anywhere and you have full access to your APRS station.

Also works well for field portable (SOTA/POTA) with a laptop and Bluetooth-capable HT.

The project is open source (Python) and approaching beta. I'm actively looking for feedback from the community, especially from operators running different hardware configurations.

GitHub: [link]

73 de [callsign]

---

## Mastodon / Fediverse

APRS-TUI: a terminal APRS client for amateur radio.

Runs headless on a Pi, works over SSH, stays up in tmux. Connects to Direwolf, Bluetooth radios, USB TNCs, or APRS-IS.

Chat with stations like you're texting. Per-station threads, delivery checkmarks, persistent history. Every other APRS client needs a GUI. This one doesn't.

Open source, Python, approaching beta. Looking for testers.

[link]

#amateurradio #hamradio #APRS #raspberrypi #opensource
