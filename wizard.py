#!/usr/bin/env python3
"""APRS TUI Setup Wizard - Interactive configuration for the APRS TUI application."""
from __future__ import annotations

import argparse
import platform
import shutil
import socket
import subprocess
import sys
from pathlib import Path

import questionary
from rich.console import Console
from rich.panel import Panel

from aprs_tui.config import (
    AppConfig,
    APRSISConfig,
    BeaconConfig,
    MapConfig,
    ServerConfig,
    StationConfig,
    default_config_path,
)

console = Console()

# Section map per PRD 6.2
SECTION_MAP = {
    "all": ["deps", "connection", "station", "beacon", "aprs_is", "map", "write"],
    "server": ["deps", "connection", "write"],
    "bt": ["deps", "bluetooth", "write"],
    "station": ["station", "write"],
    "beacon": ["beacon", "write"],
    "aprs-is": ["aprs_is", "write"],
    "map": ["map", "write"],
    "test": ["connection_test"],
}

SECTION_MENU = [
    ("Full setup (all sections)", "all"),
    ("Server / connection", "server"),
    ("Bluetooth pairing", "bt"),
    ("Station identity (callsign, SSID, position)", "station"),
    ("Beacon settings", "beacon"),
    ("APRS-IS gateway", "aprs-is"),
    ("Map / offline tiles", "map"),
    ("Connection test", "test"),
]


def detect_platform() -> dict:
    """Detect the current platform and its capabilities."""
    system = platform.system()
    is_wsl = False

    if system == "Linux":
        try:
            with open("/proc/version") as f:
                if "microsoft" in f.read().lower():
                    is_wsl = True
        except FileNotFoundError:
            pass

    return {
        "system": system,
        "is_wsl": is_wsl,
        "has_bluetooth": system in ("Linux", "Darwin") and not is_wsl,
        "has_serial": system in ("Linux", "Darwin"),
        "bt_device_prefix": "/dev/cu." if system == "Darwin" else "/dev/rfcomm",
        "serial_device_prefix": "/dev/cu." if system == "Darwin" else "/dev/tty",
    }


def step_deps_check() -> None:
    """OS detection and dependency check."""
    plat = detect_platform()
    os_name = plat["system"]
    console.print(f"\n[bold]Platform:[/bold] {os_name}")

    if plat["is_wsl"]:
        console.print("  [yellow]![/yellow] WSL2 detected")
        console.print("  [dim]Bluetooth is not available under WSL2.[/dim]")
        console.print("  [dim]Serial device passthrough requires usbipd-win.[/dim]")

    if os_name == "Linux":
        # Check for socat, rfcomm, bluetoothctl, avahi-browse
        for cmd, purpose in [
            ("socat", "Bluetooth serial bridge"),
            ("bluetoothctl", "Bluetooth pairing"),
            ("avahi-browse", "mDNS discovery"),
        ]:
            if shutil.which(cmd):
                console.print(f"  [green]\u2713[/green] {cmd} found")
            else:
                console.print(f"  [yellow]![/yellow] {cmd} not found ({purpose})")
    elif os_name == "Darwin":
        console.print("  [green]\u2713[/green] macOS detected (dns-sd available)")

    if plat["has_serial"]:
        serial_prefix = plat["serial_device_prefix"]
        console.print(f"  [green]\u2713[/green] Serial support (prefix: {serial_prefix})")
    if plat["has_bluetooth"]:
        bt_prefix = plat["bt_device_prefix"]
        console.print(f"  [green]\u2713[/green] Bluetooth support (prefix: {bt_prefix})")
    console.print()


def step_serial_device() -> str | None:
    """Detect and select a USB serial device."""
    from serial.tools import list_ports

    console.print("\n[bold]Scanning for serial devices...[/bold]")
    ports = list(list_ports.comports())

    if not ports:
        console.print("  [yellow]No serial devices found.[/yellow]")
        manual = questionary.text(
            "Enter device path manually (or leave blank to skip):"
        ).ask()
        return manual if manual else None

    choices = []
    for p in ports:
        desc = f"{p.device} - {p.description}"
        if p.manufacturer:
            desc += f" ({p.manufacturer})"
        choices.append(questionary.Choice(desc, value=p.device))
    choices.append(questionary.Choice("Enter manually", value="__manual__"))

    selected = questionary.select("Select serial device:", choices=choices).ask()
    if selected is None:
        raise KeyboardInterrupt

    if selected == "__manual__":
        device = questionary.text("Device path:").ask()
        if device is None:
            raise KeyboardInterrupt
        return device

    return selected


def _step_ble_setup(plat: dict, device_hint: str = "") -> tuple[str | None, int]:
    """BLE KISS TNC setup (Mobilinkd TNC4, BTECH UV-PRO, VGC VR-N76, etc.).

    Returns (address_or_name, 0) for kiss-ble protocol.
    The 'port' field is unused for BLE but we return 0.
    """
    device_label = device_hint or "BLE TNC"
    console.print(f"\n[bold]{device_label} \u2014 BLE Setup[/bold]")
    console.print(
        "[dim]Make sure your device is powered on and NOT connected to another app "
        "(e.g., phone).[/dim]"
    )
    console.print(
        "[dim yellow]Note: Some devices may not appear on the first scan \u2014 "
        "try scanning again if needed.[/dim yellow]\n"
    )

    # Scan loop - allow re-scanning
    device_address = None
    while device_address is None:
        scan = questionary.confirm("Scan for BLE TNC devices? (20 seconds)", default=True).ask()
        if scan is None:
            raise KeyboardInterrupt

        if scan:
            console.print("  Scanning for BLE devices (this may take a moment)...")
            try:
                import asyncio

                from aprs_tui.transport.kiss_ble import scan_for_tnc

                loop = asyncio.new_event_loop()
                devices = loop.run_until_complete(scan_for_tnc(timeout=20.0))
                loop.close()

                if devices:
                    console.print(f"  [green]Found {len(devices)} TNC device(s):[/green]")
                    choices = []
                    for d in devices:
                        choices.append(questionary.Choice(
                            f"{d['name']} ({d['address']})", value=d['address']
                        ))
                    choices.append(questionary.Choice("Scan again", value="__rescan__"))
                    choices.append(questionary.Choice("Enter manually", value="__manual__"))

                    selected = questionary.select("Select your TNC:", choices=choices).ask()
                    if selected is None:
                        raise KeyboardInterrupt
                    if selected == "__rescan__":
                        continue
                    elif selected != "__manual__":
                        device_address = selected
                        break
                else:
                    console.print("  [yellow]No BLE TNC devices found.[/yellow]")
                    console.print(
                        "  [dim]Make sure your device is powered on "
                        "and not connected to another app.[/dim]"
                    )
                    console.print("  [dim]Some radios need a second scan to be discovered.[/dim]\n")
                    action = questionary.select(
                        "What would you like to do?",
                        choices=["Scan again", "Enter manually"],
                    ).ask()
                    if action is None:
                        raise KeyboardInterrupt
                    if action == "Scan again":
                        continue
            except ImportError:
                console.print("  [yellow]BLE scanning requires 'bleak' library.[/yellow]")
            except Exception as e:
                console.print(f"  [yellow]BLE scan error: {e}[/yellow]")

        # Manual entry fallback
        if device_address is None and not scan:
            console.print("\n  [dim]Enter the device name or BLE address/UUID.[/dim]")
            console.print("  [dim]You can find it by running: python ble_monitor.py --scan[/dim]")
            default_name = device_hint or "TNC4 Mobilinkd"
            entry = questionary.text(
                "BLE device name or address:",
                default=default_name,
            ).ask()
            if entry is None:
                raise KeyboardInterrupt
            device_address = entry

    console.print(f"\n  [green]\u2713[/green] Will connect via BLE to: {device_address}")
    # Return address and 0 (port unused for BLE)
    # The caller needs to know this is BLE, so we use a special return
    return f"ble:{device_address}", 0


def _step_hybrid_serial(plat: dict, device_name: str) -> str | None:
    """Find or ask for the classic BT serial device for hybrid BLE+Serial TX.

    The UV-PRO / VR-N76 need classic BT serial for TX since macOS cannot
    negotiate BLE bonding for encrypted writes.
    """
    console.print("\n[bold]Transmit Setup (Classic Bluetooth Pairing)[/bold]")
    console.print(
        f"[bold yellow]Important:[/bold yellow] To send messages and beacons, "
        f"the {device_name} must also be paired to your computer over classic Bluetooth."
    )
    console.print(
        "[dim]The BLE connection handles receiving packets, but transmitting requires\n"
        "a separate classic Bluetooth serial link.[/dim]\n"
    )

    if plat["system"] == "Darwin":
        console.print("[bold]Steps to pair:[/bold]")
        console.print("  1. Open [bold]System Settings > Bluetooth[/bold]")
        console.print(f"  2. Make sure the {device_name} is powered on")
        console.print(
            f"  3. Find the {device_name} in the device list and click [bold]Connect[/bold]"
        )
        console.print(
            f"  4. Once paired, a serial device (e.g., /dev/cu.{device_name}) will appear\n"
        )

        import glob
        # Auto-detect likely serial devices
        bt_devices = []
        for pattern in ["/dev/cu.UV-PRO*", "/dev/cu.VR-N76*", "/dev/cu.BTECH*",
                        "/dev/cu.VGC*", "/dev/cu.BT*"]:
            bt_devices.extend(glob.glob(pattern))
        # Also check generic cu.* devices
        for dev in glob.glob("/dev/cu.*"):
            if dev not in bt_devices and dev not in (
                "/dev/cu.Bluetooth-Incoming-Port", "/dev/cu.debug-console",
                "/dev/cu.wlan-debug",
            ):
                bt_devices.append(dev)

        if bt_devices:
            console.print(f"  [green]Found {len(bt_devices)} serial device(s):[/green]")
            choices = [questionary.Choice(dev, value=dev) for dev in bt_devices]
            choices.append(questionary.Choice("Enter manually", value="__manual__"))
            selected = questionary.select("Select the TX serial device:", choices=choices).ask()
            if selected is None:
                raise KeyboardInterrupt
            if selected != "__manual__":
                console.print(f"  [green]\u2713[/green] TX via: {selected}")
                return selected

        console.print("  [yellow]No BT serial devices found.[/yellow]")
        console.print(f"  The {device_name} may not be paired yet.")
        console.print(
            "  [bold]Pair it in System Settings > Bluetooth[/bold], then re-run the wizard."
        )
        console.print(
            "  [dim]You can continue without TX \u2014 receiving will still work over BLE.[/dim]"
        )

    device = questionary.text(
        "Enter serial device path for TX:",
        default=f"/dev/cu.{device_name}",
    ).ask()
    if device is None:
        raise KeyboardInterrupt
    console.print(f"  [green]\u2713[/green] TX via: {device}")
    return device


def step_bluetooth_setup(plat: dict) -> tuple[str | None, int]:
    """Bluetooth TNC setup.

    On macOS: connects directly to /dev/cu.* serial device (no socat needed).
    On Linux: uses rfcomm or socat bridge.

    Returns (device_path, baud_rate) or (None, 0) if cancelled.
    """
    if not plat["has_bluetooth"]:
        console.print("[yellow]Bluetooth is not available on this platform.[/yellow]")
        if plat["is_wsl"]:
            console.print("[dim]WSL2 does not support Bluetooth natively.[/dim]")
            console.print("[dim]Use KISS TCP or APRS-IS instead.[/dim]")
        return None, 0

    console.print("\n[bold]Bluetooth TNC Setup[/bold]")
    console.print(
        "[dim]Verified devices are marked with \u2713. "
        "Others may work but have not been tested.[/dim]"
    )
    console.print(
        "[dim]Want to help verify a device or add support for one not listed?[/dim]"
    )
    console.print(
        "[dim]Reach out on Ko-fi or GitHub and we can coordinate testing together![/dim]\n"
    )

    # --- Check TNC type: BLE vs classic SPP ---
    tnc_type = questionary.select(
        "Which device are you connecting?",
        choices=[
            questionary.Choice("\u2713 BTECH UV-PRO (BLE)", value="ble-uvpro"),
            questionary.Choice("\u2713 Mobilinkd TNC4 (BLE)", value="ble-tnc4"),
            questionary.Choice("  VGC VR-N76 (BLE) — unverified", value="ble-vrn76"),
            questionary.Choice("  Mobilinkd TNC3 (Classic BT) — unverified", value="classic"),
            questionary.Choice("  Kenwood TH-D74/D75 (Classic BT) — unverified", value="classic"),
            questionary.Choice("  Other Bluetooth TNC — unverified", value="classic"),
            questionary.Choice("  My device isn't listed", value="__not_listed__"),
        ],
    ).ask()
    if tnc_type is None:
        raise KeyboardInterrupt

    if tnc_type == "__not_listed__":
        console.print("\n[bold]We'd love to add support for your device![/bold]")
        console.print(
            "  Reach out on Ko-fi or GitHub and we can coordinate testing together."
        )
        console.print("  In the meantime, you can try one of these options:\n")
        console.print("  [dim]- If your device uses BLE, try 'Other Bluetooth TNC' above[/dim]")
        console.print(
            "  [dim]- If your device has a USB/serial port, "
            "try 'USB Serial TNC' from the main menu[/dim]"
        )
        console.print(
            "  [dim]- If your device works with Direwolf, try 'KISS TCP' from the main menu[/dim]\n"
        )
        proceed = questionary.confirm("Go back to the device list?", default=True).ask()
        if proceed:
            return step_bluetooth_setup(plat)
        return None, 0

    _VERIFIED_BLE = ("ble-uvpro", "ble-tnc4")  # noqa: N806
    _VERIFIED_CLASSIC = ()  # none verified yet  # noqa: N806

    if tnc_type.startswith("ble"):
        hints = {
            "ble-uvpro": "UV-PRO",
            "ble-vrn76": "VR-N76",
            "ble-tnc4": "TNC4 Mobilinkd",
        }

        if tnc_type not in _VERIFIED_BLE:
            device_label = hints.get(tnc_type, "selected device")
            console.print(
                f"\n[yellow]Note:[/yellow] The {device_label} has not been "
                "verified with this app."
            )
            console.print(
                "[dim]It may work, but if you run into issues please report them on GitHub.[/dim]"
            )
            console.print(
                "[dim]If you'd like to send a device for testing, "
                "reach out on Ko-fi or GitHub.[/dim]\n"
            )

        ble_result, _ = _step_ble_setup(plat, device_hint=hints.get(tnc_type, ""))
        if ble_result is None:
            return None, 0

        # UV-PRO / VR-N76 work with pure BLE for both RX and TX.
        # The write-with-response → write-without-response fallback in
        # KissBleTransport handles the macOS bonding limitation.
        return ble_result, 0

    if tnc_type == "classic" and tnc_type not in _VERIFIED_CLASSIC:
        console.print(
            "\n[yellow]Note:[/yellow] Classic Bluetooth TNC support has not been fully verified."
        )
        console.print(
            "[dim]If you run into issues, please report them on GitHub.[/dim]"
        )
        console.print(
            "[dim]If you'd like to send a device for testing, reach out on Ko-fi or GitHub.[/dim]\n"
        )

    if plat["system"] == "Darwin":
        # --- macOS classic BT: direct serial connection ---
        console.print(
            "\n[bold]Step 1:[/bold] Make sure your TNC is paired in System Settings > Bluetooth"
        )
        console.print(
            "[bold]Step 2:[/bold] Close any other apps connected to the TNC "
            "(only one BT connection at a time)\n"
        )

        # Auto-detect BT serial devices
        import glob
        bt_devices = []
        for pattern in ["/dev/cu.TNC*", "/dev/cu.Mobilinkd*", "/dev/cu.Kenwood*",
                        "/dev/cu.BT*", "/dev/cu.Bluetooth*"]:
            bt_devices.extend(glob.glob(pattern))
        # Also include any non-standard cu.* devices (exclude system ones)
        for dev in glob.glob("/dev/cu.*"):
            if dev not in bt_devices and dev not in (
                "/dev/cu.Bluetooth-Incoming-Port", "/dev/cu.debug-console",
                "/dev/cu.wlan-debug",
            ):
                bt_devices.append(dev)

        if bt_devices:
            console.print(f"  [green]Found {len(bt_devices)} serial device(s):[/green]")
            choices = [questionary.Choice(dev, value=dev) for dev in bt_devices]
            choices.append(questionary.Choice("Enter manually", value="__manual__"))

            selected = questionary.select("Select your TNC device:", choices=choices).ask()
            if selected is None:
                raise KeyboardInterrupt
            if selected == "__manual__":
                device = questionary.text("Device path:", default="/dev/cu.").ask()
                if device is None:
                    raise KeyboardInterrupt
            else:
                device = selected
        else:
            console.print("  [yellow]No BT TNC devices found.[/yellow]")
            console.print(
                "  [dim]Make sure your TNC is paired in System Settings > Bluetooth[/dim]"
            )
            device = questionary.text("Enter device path:", default="/dev/cu.").ask()
            if device is None:
                raise KeyboardInterrupt

        # Test the connection
        console.print(f"\n  Testing {device}...")
        try:
            import serial
            s = serial.Serial(device, 9600, timeout=2)
            s.close()
            console.print("  [green]\u2713[/green] Device opened successfully!")
        except Exception as e:
            console.print(f"  [yellow]![/yellow] Could not open device: {e}")
            console.print("  [dim]The TNC may not be powered on or paired.[/dim]")
            proceed = questionary.confirm("Save this config anyway?", default=True).ask()
            if not proceed:
                raise KeyboardInterrupt from None

        baud = 9600
        return device, baud

    else:
        # --- Linux: rfcomm or socat bridge ---
        console.print("\n[bold]Tips before scanning:[/bold]")
        console.print(
            "  Kenwood TH-D74/D75: Menu > APRS > Bluetooth > BT KISS TNC > ON"
        )
        console.print("  Mobilinkd TNC: Hold button until LED flashes blue")
        console.print("  Default PINs: Kenwood=0000, Mobilinkd=1234\n")

        if not shutil.which("bluetoothctl"):
            console.print(
                "[yellow]bluetoothctl not found. Enter device path manually.[/yellow]"
            )
            device = questionary.text(
                "BT device path:", default="/dev/rfcomm0"
            ).ask()
            if device is None:
                raise KeyboardInterrupt
        else:
            console.print("Scanning for Bluetooth devices (10 seconds)...")
            try:
                subprocess.run(
                    ["bluetoothctl", "--timeout", "10", "scan", "on"],
                    capture_output=True, text=True, timeout=15,
                )
                console.print("[dim]Scan complete.[/dim]")
            except (subprocess.TimeoutExpired, FileNotFoundError):
                console.print("[yellow]BT scan failed or timed out.[/yellow]")

            device = questionary.text(
                "BT device path:", default="/dev/rfcomm0"
            ).ask()
            if device is None:
                raise KeyboardInterrupt

        # Linux needs socat bridge
        console.print("\n[bold]socat Bridge Configuration[/bold]")
        console.print(
            "[dim]socat forwards BT serial to KISS TCP so the TUI can connect.[/dim]"
        )

        port_str = questionary.text("KISS TCP port for bridge:", default="8001").ask()
        if port_str is None:
            raise KeyboardInterrupt
        port = int(port_str)

        generate = questionary.confirm(
            "Generate start-bt-bridge.sh?", default=True
        ).ask()
        if generate:
            script_content = f"""#!/bin/bash
# start-bt-bridge.sh - generated by aprs-tui wizard
# Bridges BT serial to KISS TCP port {port}
DEVICE="{device}"
PORT={port}
echo "Starting BT bridge: $DEVICE -> TCP port $PORT"
while true; do
    socat TCP-LISTEN:$PORT,reuseaddr,fork OPEN:$DEVICE,rawer
    echo "Bridge disconnected, restarting in 3s..."
    sleep 3
done
"""
            script_path = Path("start-bt-bridge.sh")
            script_path.write_text(script_content)
            script_path.chmod(0o755)
            console.print(f"  [green]\u2713[/green] Bridge script written to {script_path}")

        # On Linux, TUI connects via TCP to the socat bridge
        return "localhost", port


# --- Platform-specific DigiRig detection helpers ---


def _detect_digirig_audio(plat: dict) -> tuple[str, str]:
    """Detect DigiRig audio device per platform.

    Returns (display_name, adevice_config_block) where adevice_config_block
    is the ADEVICE line (and optional ARATE) for direwolf.conf.
    """
    system = plat["system"]

    if system == "Darwin":
        audio_device = "USB PnP Sound Device"
        try:
            result = subprocess.run(
                ["system_profiler", "SPAudioDataType"],
                capture_output=True, text=True, timeout=5,
            )
            if "USB PnP Sound Device" in result.stdout:
                console.print(f'  [green]\u2713[/green] Found: "{audio_device}" (C-Media CM108)')
                return audio_device, f'ADEVICE "{audio_device}" "{audio_device}"\nARATE 44100'
        except Exception:
            pass
        console.print(f'  [yellow]![/yellow] "{audio_device}" not detected.')
        console.print("  [dim]Is the DigiRig plugged in?[/dim]")
        custom = questionary.text("Audio device name:", default=audio_device).ask()
        if custom is None:
            raise KeyboardInterrupt
        return custom, f'ADEVICE "{custom}" "{custom}"\nARATE 44100'

    elif system == "Linux":
        console.print("  [dim]Scanning ALSA devices (arecord -l)...[/dim]")
        try:
            result = subprocess.run(
                ["arecord", "-l"], capture_output=True, text=True, timeout=5,
            )
            import re
            for line in result.stdout.splitlines():
                if any(kw in line for kw in ("USB PnP", "C-Media", "CM108")):
                    match = re.search(r"card\s+(\d+).*device\s+(\d+)", line)
                    card_match = re.search(r"card\s+\d+:\s+(\w+)", line)
                    if match:
                        card_name = card_match.group(1) if card_match else match.group(1)
                        dev = match.group(2)
                        adevice = f"plughw:CARD={card_name},DEV={dev}"
                        console.print(f"  [green]\u2713[/green] Found: {adevice}")
                        console.print(f"  [dim]{line.strip()}[/dim]")
                        return adevice, f"ADEVICE {adevice}"
            if result.stdout.strip():
                console.print("  [yellow]![/yellow] DigiRig not auto-detected. Devices found:")
                for line in result.stdout.splitlines():
                    if line.strip().startswith("card"):
                        console.print(f"  [dim]  {line.strip()}[/dim]")
            else:
                console.print("  [yellow]![/yellow] No ALSA recording devices found.")
        except FileNotFoundError:
            console.print("  [yellow]![/yellow] 'arecord' not found (install alsa-utils).")
        except Exception as e:
            console.print(f"  [yellow]![/yellow] Audio scan error: {e}")
        custom = questionary.text(
            "ALSA device (run 'arecord -l'):", default="plughw:CARD=Set,DEV=0",
        ).ask()
        if custom is None:
            raise KeyboardInterrupt
        return custom, f"ADEVICE {custom}"

    else:  # Windows
        console.print("  [dim]Run 'direwolf -h' to list audio device indices.[/dim]")
        console.print("  [dim]Look for 'USB PnP Sound Device' or 'C-Media'.[/dim]")
        try:
            result = subprocess.run(
                ["direwolf", "-h"], capture_output=True, text=True, timeout=10,
            )
            for line in (result.stdout + result.stderr).splitlines():
                if any(kw in line for kw in ("Sound", "Audio", "USB", "C-Media")):
                    console.print(f"  [dim]  {line.strip()}[/dim]")
        except Exception:
            pass
        idx = questionary.text("Audio device index:", default="1").ask()
        if idx is None:
            raise KeyboardInterrupt
        return f"Device {idx}", f"ADEVICE {idx}"


def _detect_digirig_ptt(plat: dict) -> str:
    """Detect DigiRig serial port for PTT per platform. Returns PTT config line."""
    import glob as glob_mod

    system = plat["system"]

    if system == "Darwin":
        serial_devs = (
            glob_mod.glob("/dev/cu.usbserial-*")
            + glob_mod.glob("/dev/cu.SLAB_USBtoUART*")
        )
    elif system == "Linux":
        serial_devs = (
            glob_mod.glob("/dev/ttyUSB*")
            + glob_mod.glob("/dev/ttyACM*")
        )
    else:  # Windows
        serial_devs = []
        try:
            from serial.tools import list_ports
            serial_devs = [
                p.device for p in list_ports.comports()
                if any(kw in (p.description or "") for kw in ("USB", "Serial", "DigiRig"))
            ]
        except ImportError:
            pass

    if serial_devs:
        if len(serial_devs) == 1:
            ptt_dev = serial_devs[0]
            console.print(f"  [green]\u2713[/green] Serial port: {ptt_dev}")
        else:
            choices = [questionary.Choice(d, value=d) for d in serial_devs]
            ptt_dev = questionary.select(
                "Select DigiRig serial port:", choices=choices,
            ).ask()
            if ptt_dev is None:
                raise KeyboardInterrupt
        console.print(f"  [green]\u2713[/green] PTT: RTS via {ptt_dev}")
        return f"PTT {ptt_dev} RTS"

    console.print("  [yellow]![/yellow] No USB serial port found.")
    model = questionary.select(
        "Which DigiRig model?",
        choices=[
            questionary.Choice("DigiRig Mobile (has serial port)", value="mobile"),
            questionary.Choice("DigiRig Lite (VOX only)", value="lite"),
        ],
    ).ask()
    if model is None:
        raise KeyboardInterrupt
    if model == "mobile":
        console.print("  [dim]Make sure the DigiRig is plugged in.[/dim]")
        if system == "Windows":
            default_dev = "COM3"
        elif system == "Linux":
            default_dev = "/dev/ttyUSB0"
        else:
            default_dev = "/dev/cu.usbserial-0001"
        manual = questionary.text(
            "Enter serial port (or Enter for VOX):", default=default_dev,
        ).ask()
        if manual:
            return f"PTT {manual} RTS"
    console.print("  [dim]Make sure VOX is enabled on your radio.[/dim]")
    return "PTT VOX"


def _step_digirig_setup(config: AppConfig) -> AppConfig:
    """Set up DigiRig with local Direwolf — generates direwolf.conf in app folder."""
    plat = detect_platform()
    system = plat["system"]

    console.print("\n[bold]DigiRig Setup[/bold]")
    console.print("[dim]This will configure Direwolf as a local software TNC.[/dim]")
    console.print("[dim]Direwolf will start/stop automatically with the app.[/dim]\n")

    app_dir = Path(__file__).parent
    dw_conf_path = app_dir / "direwolf.conf"

    # Check Direwolf installation (platform-specific install hints)
    dw_bin = shutil.which("direwolf")
    if not dw_bin:
        if system == "Darwin":
            candidates = [
                "/opt/local/bin/direwolf", "/opt/homebrew/bin/direwolf", "/usr/local/bin/direwolf"
            ]
        elif system == "Linux":
            candidates = ["/usr/bin/direwolf", "/usr/local/bin/direwolf"]
        else:
            candidates = []
        for candidate in candidates:
            if Path(candidate).exists():
                dw_bin = candidate
                break
    if dw_bin:
        console.print(f"  [green]\u2713[/green] Direwolf found: {dw_bin}")
    else:
        console.print("  [red]\u2717[/red] Direwolf not found.")
        if system == "Darwin":
            console.print("  [dim]Install with: brew install direwolf[/dim]")
        elif system == "Linux":
            console.print("  [dim]Install with: sudo apt install direwolf[/dim]")
        else:
            console.print("  [dim]Download from: github.com/wb2osz/direwolf/releases[/dim]")
        proceed = questionary.confirm("Continue setup anyway?", default=False).ask()
        if not proceed:
            raise KeyboardInterrupt

    # Detect audio device (platform-aware)
    console.print("\n[bold]Audio Device[/bold]")
    _audio_name, adevice_block = _detect_digirig_audio(plat)

    # Detect PTT serial port (platform-aware)
    console.print("\n[bold]PTT Control[/bold]")
    ptt_line = _detect_digirig_ptt(plat)

    # Get callsign from config
    callsign = f"{config.station.callsign}-{config.station.ssid}"

    # Platform label for config header
    platform_label = {"Darwin": "macOS", "Linux": "Linux", "Windows": "Windows"}.get(system, system)

    # Write direwolf.conf
    if dw_conf_path.exists():
        shutil.copy2(dw_conf_path, str(dw_conf_path) + ".bak")
        console.print("\n  [dim]Backed up existing direwolf.conf[/dim]")

    dw_conf_path.write_text(f"""\
# Direwolf config for {platform_label} + DigiRig
# Generated by APRS TUI wizard
# Direwolf is started/stopped automatically with the app.

{adevice_block}

CHANNEL 0
MYCALL {callsign}
MODEM 1200

{ptt_line}
TXDELAY 40
TXTAIL 10

KISSPORT 8001
AGWPORT 0
""")

    console.print(f"\n  [green]\u2713[/green] Direwolf config written: {dw_conf_path}")
    console.print("  [dim]Direwolf will start automatically when you launch the app.[/dim]")

    return config.model_copy(
        update={
            "server": ServerConfig(protocol="kiss-tcp", host="127.0.0.1", port=8001),
        }
    )


def step_connection_type(config: AppConfig) -> AppConfig:
    """Select connection type and configure server."""
    plat = detect_platform()

    choices = [
        "DigiRig (local Direwolf — auto-managed)",
        "Direwolf / KISS TCP (remote or manual)",
    ]
    if plat["has_serial"]:
        choices.append("USB Serial TNC (direct serial connection)")
    if plat["has_bluetooth"]:
        choices.append("Bluetooth TNC (UV-PRO, VR-N76, Mobilinkd, Kenwood)")
    choices.append("APRS-IS only (internet gateway, no radio)")

    conn_type = questionary.select(
        "How is your TNC or radio connected?", choices=choices
    ).ask()

    if conn_type is None:  # User cancelled
        raise KeyboardInterrupt

    if "DigiRig" in conn_type:
        return _step_digirig_setup(config)

    if "Serial" in conn_type:
        device = step_serial_device()
        if device:
            baud_str = questionary.text("Baud rate:", default="9600").ask()
            if baud_str is None:
                raise KeyboardInterrupt
            return config.model_copy(
                update={
                    "server": ServerConfig(
                        protocol="kiss-serial", host=device, port=int(baud_str)
                    ),
                }
            )

    if "Bluetooth" in conn_type:
        device_or_host, port_or_baud = step_bluetooth_setup(plat)
        if device_or_host:
            # Hybrid BLE+Serial (UV-PRO / VR-N76): "hybrid:ble_address|serial_device"
            if isinstance(device_or_host, str) and device_or_host.startswith("hybrid:"):
                parts = device_or_host[7:].split("|", 1)
                ble_address = parts[0]
                serial_device = parts[1] if len(parts) > 1 else ""
                return config.model_copy(
                    update={
                        "server": ServerConfig(
                            protocol="kiss-ble-hybrid",
                            host=ble_address,
                            port=port_or_baud or 9600,
                            serial_device=serial_device,
                        ),
                    }
                )
            # Pure BLE (returned from _step_ble_setup as "ble:address")
            if isinstance(device_or_host, str) and device_or_host.startswith("ble:"):
                ble_address = device_or_host[4:]  # strip "ble:" prefix
                return config.model_copy(
                    update={
                        "server": ServerConfig(
                            protocol="kiss-ble", host=ble_address, port=0
                        ),
                    }
                )
            # Classic BT:
            # On macOS: device_or_host is /dev/cu.*, port_or_baud is baud rate
            # On Linux: device_or_host is "localhost", port_or_baud is TCP port
            return config.model_copy(
                update={
                    "server": ServerConfig(
                        protocol="kiss-bt", host=device_or_host, port=port_or_baud
                    ),
                }
            )

    if "APRS-IS" in conn_type:
        return config.model_copy(
            update={
                "server": ServerConfig(
                    protocol="aprs-is", host="rotate.aprs2.net", port=14580
                ),
                "aprs_is": APRSISConfig(enabled=True),
            }
        )

    # KISS TCP setup (default / fallback for Direwolf selection)
    # Try mDNS discovery first
    console.print("\nScanning for KISS TNC servers on your network (3s)...")

    import asyncio

    from aprs_tui.discovery.mdns import discover_kiss_servers

    try:
        loop = asyncio.new_event_loop()
        servers = loop.run_until_complete(discover_kiss_servers(timeout=3.0))
        loop.close()
    except Exception:
        servers = []

    host = None
    port = None

    if servers:
        console.print(f"  [green]Found {len(servers)} server(s):[/green]")
        choices = []
        for s in servers:
            status = "[green]\u2713[/green]" if s.reachable else "[red]\u2717[/red]"
            label = f"{status} {s.name} ({s.host}:{s.port})"
            choices.append(questionary.Choice(label, value=(s.host, s.port)))
        choices.append(questionary.Choice("Enter manually", value=None))

        selected = questionary.select("Select server:", choices=choices).ask()
        if selected is not None:
            host, port = selected
    else:
        console.print("  [dim]No KISS TNC servers found via mDNS.[/dim]")
        console.print("  [dim]To enable auto-discovery, on your Direwolf host run:[/dim]")
        console.print(
            "  [dim]  Linux: avahi-publish-service \"Direwolf KISS\" _kiss-tnc._tcp 8001 &[/dim]"
        )
        console.print("  [dim]  macOS: dns-sd -R \"Direwolf KISS\" _kiss-tnc._tcp . 8001 &[/dim]\n")

    # Manual entry if no server was selected via mDNS
    if host is None:
        host = questionary.text("KISS TCP host:", default=config.server.host).ask()
        if host is None:
            raise KeyboardInterrupt

        port_str = questionary.text(
            "KISS TCP port:", default=str(config.server.port)
        ).ask()
        if port_str is None:
            raise KeyboardInterrupt

        port = int(port_str)

    # Connection test
    console.print(f"\nTesting connection to {host}:{port}...")
    try:
        sock = socket.create_connection((host, port), timeout=5)
        sock.close()
        console.print("  [green]\u2713[/green] Connected successfully!")
    except (ConnectionRefusedError, OSError, TimeoutError) as e:
        console.print(f"  [red]\u2717[/red] Could not connect: {e}")
        console.print(
            f"  [dim]Verify Direwolf is running and KISSPORT {port} is set[/dim]"
        )
        proceed = questionary.confirm(
            "Save this configuration anyway?", default=True
        ).ask()
        if not proceed:
            raise KeyboardInterrupt from None

    return config.model_copy(
        update={
            "server": ServerConfig(protocol="kiss-tcp", host=host, port=port),
        }
    )


def step_station(config: AppConfig) -> AppConfig:
    """Configure station identity."""
    console.print("\n[bold]Station Configuration[/bold]")

    callsign = questionary.text(
        "Your callsign (e.g., W7XXX):",
        default=config.station.callsign if config.station.callsign != "N0CALL" else "",
        validate=lambda x: (
            True if len(x) >= 3 and x.isalnum() else "3-7 alphanumeric characters required"
        ),
    ).ask()
    if callsign is None:
        raise KeyboardInterrupt

    console.print("\n  [dim]Common SSID conventions:[/dim]")
    console.print("  [dim]  0=Fixed  5=Handheld  7=Walkie  9=Mobile  14=Laptop[/dim]")

    ssid_str = questionary.text("SSID (0-15):", default=str(config.station.ssid)).ask()
    if ssid_str is None:
        raise KeyboardInterrupt
    ssid = int(ssid_str)

    symbol_choice = questionary.select(
        "APRS symbol:",
        choices=[
            questionary.Choice("/> Car (mobile)", value="/>"),
            questionary.Choice("/[ Walker/pedestrian", value="/["),
            questionary.Choice("/- House (fixed)", value="/-"),
            questionary.Choice("/k Truck", value="/k"),
            questionary.Choice("Custom", value=None),
        ],
    ).ask()
    if symbol_choice is None:
        sym_table = questionary.text("Symbol table (/ or \\):", default="/").ask()
        if sym_table is None:
            raise KeyboardInterrupt
        sym_code = questionary.text("Symbol code:", default=">").ask()
        if sym_code is None:
            raise KeyboardInterrupt
    else:
        sym_table, sym_code = symbol_choice[0], symbol_choice[1]

    # Station position
    console.print("\n[bold]Station Position[/bold]")
    console.print("[dim]Your coordinates are used for:[/dim]")
    console.print("[dim]  - APRS-IS server filtering (receive packets near you)[/dim]")
    console.print("[dim]  - Distance/bearing to other stations[/dim]")
    console.print("[dim]  - Position beaconing (if enabled later)[/dim]")
    console.print("[dim]Tip: search your address at latlong.net[/dim]\n")

    default_lat = (
        config.station.latitude if config.station.latitude != 0.0 else config.beacon.latitude
    )
    default_lon = (
        config.station.longitude if config.station.longitude != 0.0 else config.beacon.longitude
    )

    lat_str = questionary.text(
        "Latitude (decimal degrees, e.g. 45.5):",
        default=str(default_lat) if default_lat != 0.0 else "",
    ).ask()
    if lat_str is None:
        raise KeyboardInterrupt
    lat = float(lat_str) if lat_str else 0.0

    lon_str = questionary.text(
        "Longitude (decimal degrees, e.g. -122.6):",
        default=str(default_lon) if default_lon != 0.0 else "",
    ).ask()
    if lon_str is None:
        raise KeyboardInterrupt
    lon = float(lon_str) if lon_str else 0.0

    return config.model_copy(
        update={
            "station": StationConfig(
                callsign=callsign.upper(),
                ssid=ssid,
                latitude=lat,
                longitude=lon,
                symbol_table=sym_table,
                symbol_code=sym_code,
            ),
        }
    )


def step_beacon(config: AppConfig) -> AppConfig:
    """Configure position beaconing."""
    console.print("\n[bold]Beacon Settings[/bold]")

    enabled = questionary.confirm(
        "Enable position beaconing?", default=config.beacon.enabled
    ).ask()
    if enabled is None:
        raise KeyboardInterrupt

    interval = config.beacon.interval
    lat = config.beacon.latitude
    lon = config.beacon.longitude
    comment = config.beacon.comment

    if enabled:
        interval_str = questionary.text(
            "Beacon interval in seconds (min 60):", default=str(config.beacon.interval)
        ).ask()
        if interval_str is None:
            raise KeyboardInterrupt
        interval = max(int(interval_str), 60)

        # Default to station position, allow override for beacon
        default_lat = (
            config.beacon.latitude if config.beacon.latitude != 0.0 else config.station.latitude
        )
        default_lon = (
            config.beacon.longitude if config.beacon.longitude != 0.0 else config.station.longitude
        )

        if default_lat != 0.0 and default_lon != 0.0:
            console.print(f"  [dim]Using station position: {default_lat}, {default_lon}[/dim]")
            use_station = questionary.confirm(
                "Use your station position for beaconing?", default=True
            ).ask()
            if use_station is None:
                raise KeyboardInterrupt
            if use_station:
                lat = default_lat
                lon = default_lon
            else:
                lat_str = questionary.text("Beacon latitude:", default=str(default_lat)).ask()
                if lat_str is None:
                    raise KeyboardInterrupt
                lat = float(lat_str)
                lon_str = questionary.text("Beacon longitude:", default=str(default_lon)).ask()
                if lon_str is None:
                    raise KeyboardInterrupt
                lon = float(lon_str)
        else:
            console.print("  [yellow]No station position set. Enter beacon coordinates.[/yellow]")
            lat_str = questionary.text("Beacon latitude (decimal degrees):").ask()
            if lat_str is None:
                raise KeyboardInterrupt
            lat = float(lat_str) if lat_str else 0.0
            lon_str = questionary.text("Beacon longitude (decimal degrees):").ask()
            if lon_str is None:
                raise KeyboardInterrupt
            lon = float(lon_str) if lon_str else 0.0

        comment = (
            questionary.text(
                "Station comment (max 43 chars):", default=config.beacon.comment
            ).ask()
            or ""
        )
        comment = comment[:43]

    return config.model_copy(
        update={
            "beacon": BeaconConfig(
                enabled=enabled,
                interval=interval,
                latitude=lat,
                longitude=lon,
                comment=comment,
            ),
        }
    )


def step_aprs_is(config: AppConfig) -> AppConfig:
    """Configure APRS-IS gateway."""
    console.print("\n[bold]APRS-IS Internet Gateway[/bold]")
    console.print("[dim]APRS-IS streams live APRS packets from the internet.[/dim]")
    console.print("[dim]Can run alongside radio (dual mode) or standalone.[/dim]\n")

    enabled = questionary.confirm(
        "Connect to APRS-IS?", default=config.aprs_is.enabled
    ).ask()
    if enabled is None:
        raise KeyboardInterrupt

    if not enabled:
        return config.model_copy(update={"aprs_is": APRSISConfig(enabled=False)})

    server = questionary.text("Server:", default=config.aprs_is.host).ask()
    if server is None:
        raise KeyboardInterrupt

    port_str = questionary.text("Port:", default=str(config.aprs_is.port)).ask()
    if port_str is None:
        raise KeyboardInterrupt

    console.print("\n  [dim]Passcode is required for transmitting via APRS-IS.[/dim]")
    console.print("  [dim]For receive-only, enter -1.[/dim]")
    console.print("  [dim]Passcode generator: https://apps.magicbug.co.uk/passcode/[/dim]")

    passcode_str = questionary.text(
        "Passcode (-1 for receive-only):", default=str(config.aprs_is.passcode)
    ).ask()
    if passcode_str is None:
        raise KeyboardInterrupt

    # --- Filter configuration ---
    console.print("\n[bold]APRS-IS Filter[/bold]")
    console.print("[dim]A filter tells the server what packets to send you.[/dim]")
    console.print("[dim]Without a filter, you may receive no packets.[/dim]\n")

    # Auto-generate filter from station position
    stn_lat = (
        config.station.latitude if config.station.latitude != 0.0 else config.beacon.latitude
    )
    stn_lon = (
        config.station.longitude if config.station.longitude != 0.0 else config.beacon.longitude
    )
    existing_filter = config.aprs_is.filter
    # Regenerate if no filter, or if it references 0.0/0.0 (stale coords)
    if stn_lat != 0.0 and (not existing_filter or "0.0/0.0" in existing_filter):
        default_filter = f"r/{stn_lat}/{stn_lon}/100"
        console.print(
            f"  [green]Auto-generated from your station position:[/green] {default_filter}"
        )
    else:
        default_filter = existing_filter

    filter_choice = questionary.select(
        "How would you like to set the filter?",
        choices=[
            questionary.Choice(
                "Radius from my position (100km)",
                value="radius_100",
            ),
            questionary.Choice(
                "Radius from my position (200km)",
                value="radius_200",
            ),
            questionary.Choice(
                "Radius from my position (500km)",
                value="radius_500",
            ),
            questionary.Choice(
                "Only my callsign traffic",
                value="mycall",
            ),
            questionary.Choice(
                "Messages only",
                value="messages",
            ),
            questionary.Choice(
                "Enter custom filter",
                value="custom",
            ),
        ],
    ).ask()
    if filter_choice is None:
        raise KeyboardInterrupt

    lat = stn_lat
    lon = stn_lon
    callsign = config.station.callsign

    if filter_choice == "radius_100":
        filter_str = f"r/{lat}/{lon}/100"
    elif filter_choice == "radius_200":
        filter_str = f"r/{lat}/{lon}/200"
    elif filter_choice == "radius_500":
        filter_str = f"r/{lat}/{lon}/500"
    elif filter_choice == "mycall":
        filter_str = f"b/{callsign}*"
    elif filter_choice == "messages":
        filter_str = "t/m"
    else:
        console.print("\n  [dim]Filter syntax examples:[/dim]")
        console.print("  [dim]  r/45.5/-122.2/100  Radius 100km from coordinates[/dim]")
        console.print("  [dim]  b/W7PDJ*           Only your callsign traffic[/dim]")
        console.print("  [dim]  t/m                Messages only[/dim]")
        console.print("  [dim]  t/poimqstunw       All packet types[/dim]")
        console.print("  [dim]  r/45/-122/200 t/m  Combine: radius + messages[/dim]")
        filter_str = questionary.text(
            "Enter APRS-IS filter:", default=default_filter
        ).ask() or ""

    if lat == 0.0 and lon == 0.0 and filter_choice.startswith("radius"):
        console.print(
            "\n  [yellow]Warning: Your position is 0,0. "
            "Set your position in station config first.[/yellow]"
        )
        console.print(
            "  [dim]The radius filter won't work correctly without a valid position.[/dim]"
        )

    console.print(f"\n  Filter: [bold]{filter_str}[/bold]")

    return config.model_copy(
        update={
            "aprs_is": APRSISConfig(
                enabled=True,
                host=server,
                port=int(port_str),
                passcode=int(passcode_str),
                filter=filter_str,
            ),
        }
    )


def step_map_setup(config: AppConfig) -> AppConfig:
    """Configure offline map panel and optionally download tiles."""
    console.print("\n[bold]Map Panel Setup[/bold]")

    enabled = questionary.confirm(
        "Enable map panel?", default=True
    ).ask()
    if enabled is None:
        raise KeyboardInterrupt

    if not enabled:
        return config.model_copy(
            update={"map": config.map.model_copy(update={"enabled": False})}
        )

    download_now = questionary.confirm(
        "Download offline maps now?", default=True
    ).ask()
    if download_now is None:
        raise KeyboardInterrupt

    if not download_now:
        console.print("  [dim]You can download maps later with: python -m aprs_tui.map.downloader[/dim]")
        return config.model_copy(
            update={"map": config.map.model_copy(update={"enabled": True})}
        )

    # --- Region specification ---
    stn_lat = (
        config.station.latitude if config.station.latitude != 0.0 else config.beacon.latitude
    )
    stn_lon = (
        config.station.longitude if config.station.longitude != 0.0 else config.beacon.longitude
    )

    region_choices = []
    if stn_lat != 0.0 and stn_lon != 0.0:
        region_choices.append(
            questionary.Choice(
                f"Use current station position ({stn_lat}, {stn_lon}) + radius",
                value="center",
            )
        )
    region_choices.append(
        questionary.Choice("Enter bounding box coordinates manually", value="bbox")
    )

    region_mode = questionary.select(
        "How would you like to specify the map region?",
        choices=region_choices,
    ).ask()
    if region_mode is None:
        raise KeyboardInterrupt

    if region_mode == "center":
        radius_str = questionary.text(
            "Radius in km:", default="200"
        ).ask()
        if radius_str is None:
            raise KeyboardInterrupt
        radius_km = float(radius_str)

        from aprs_tui.map.downloader import bounding_box_from_center

        min_lat, max_lat, min_lon, max_lon = bounding_box_from_center(
            stn_lat, stn_lon, radius_km
        )
        console.print(
            f"  [dim]Bounding box: {min_lat:.2f},{min_lon:.2f} to {max_lat:.2f},{max_lon:.2f}[/dim]"
        )
    else:
        min_lat_str = questionary.text("Min latitude (south):").ask()
        if min_lat_str is None:
            raise KeyboardInterrupt
        max_lat_str = questionary.text("Max latitude (north):").ask()
        if max_lat_str is None:
            raise KeyboardInterrupt
        min_lon_str = questionary.text("Min longitude (west):").ask()
        if min_lon_str is None:
            raise KeyboardInterrupt
        max_lon_str = questionary.text("Max longitude (east):").ask()
        if max_lon_str is None:
            raise KeyboardInterrupt
        min_lat = float(min_lat_str)
        max_lat = float(max_lat_str)
        min_lon = float(min_lon_str)
        max_lon = float(max_lon_str)

    # --- Max zoom level ---
    zoom_choice = questionary.select(
        "Max zoom level:",
        choices=[
            questionary.Choice("10 - Regional overview (~5 MB)", value=10),
            questionary.Choice("14 - City detail (~80 MB)", value=14),
            questionary.Choice("16 - Street detail (~500 MB)", value=16),
        ],
    ).ask()
    if zoom_choice is None:
        raise KeyboardInterrupt
    max_zoom = zoom_choice

    # --- Estimate and confirm ---
    from aprs_tui.map.downloader import (
        TileDownloader,
        calculate_tile_count,
        estimate_size_mb,
    )

    tile_count = calculate_tile_count(min_lat, max_lat, min_lon, max_lon, 0, max_zoom)
    size_mb = estimate_size_mb(tile_count)

    console.print(f"\n  Tiles to download: [bold]{tile_count:,}[/bold]")
    console.print(f"  Estimated size:    [bold]{size_mb:.1f} MB[/bold]")

    proceed = questionary.confirm("Proceed with download?", default=True).ask()
    if proceed is None:
        raise KeyboardInterrupt

    if not proceed:
        console.print("  [dim]Download skipped. You can download maps later.[/dim]")
        return config.model_copy(
            update={"map": config.map.model_copy(update={"enabled": True})}
        )

    # --- Download with progress ---
    from aprs_tui.map.registry import MapRegistry, default_maps_dir

    maps_dir = default_maps_dir()
    region_name = f"{config.station.callsign.lower()}-region"
    output_path = maps_dir / f"{region_name}.mbtiles"

    from rich.progress import BarColumn, Progress, TextColumn, TimeRemainingColumn

    progress = Progress(
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        TextColumn("{task.percentage:>3.0f}%"),
        TimeRemainingColumn(),
        console=console,
    )

    task_id = None

    def on_progress(p):  # noqa: ANN001
        nonlocal task_id
        if task_id is None:
            task_id = progress.add_task("Downloading tiles", total=p.total_tiles)
        progress.update(
            task_id,
            completed=p.downloaded_tiles + p.skipped_tiles,
        )
        progress.refresh()

    downloader = TileDownloader(progress_callback=on_progress)

    console.print(f"\n  Downloading to: {output_path}")
    with progress:
        downloader.download(
            output_path=output_path,
            min_lat=min_lat,
            max_lat=max_lat,
            min_lon=min_lon,
            max_lon=max_lon,
            min_zoom=0,
            max_zoom=max_zoom,
            map_name=region_name,
        )

    console.print(f"  [green]\u2713[/green] Map downloaded: {output_path}")

    # Register in map registry
    import datetime

    registry = MapRegistry(maps_dir)
    from aprs_tui.map.registry import MapEntry

    registry.register(
        region_name,
        MapEntry(
            file=output_path.name,
            name=f"{config.station.callsign} region",
            bounds=(min_lon, min_lat, max_lon, max_lat),
            min_zoom=0,
            max_zoom=max_zoom,
            size_mb=round(output_path.stat().st_size / (1024 * 1024), 1),
            downloaded=datetime.datetime.now(tz=datetime.timezone.utc).isoformat(),
        ),
    )
    console.print("  [green]\u2713[/green] Map registered in maps.toml")

    updated_map = config.map.model_copy(
        update={"enabled": True, "maps_dir": str(maps_dir)}
    )
    return config.model_copy(update={"map": updated_map})


def step_write_config(config: AppConfig, config_path: Path) -> None:
    """Display summary and write config."""
    callsign = f"{config.station.callsign}-{config.station.ssid}"

    beacon_status = (
        f"ON, every {config.beacon.interval}s" if config.beacon.enabled else "OFF"
    )
    aprs_is_status = (
        f"ON, {config.aprs_is.host}" if config.aprs_is.enabled else "OFF"
    )

    if config.station.latitude != 0.0:
        position_str = f"{config.station.latitude}, {config.station.longitude}"
    else:
        position_str = "Not set"

    tx_serial_line = (
        f"\nTX Serial: {config.server.serial_device}" if config.server.serial_device else ""
    )
    summary = f"""[bold]Configuration Summary[/bold]

Callsign:  {callsign}
Position:  {position_str}
Symbol:    {config.station.symbol_table}{config.station.symbol_code}
Server:    {config.server.host}:{config.server.port} ({config.server.protocol}){tx_serial_line}
Beacon:    {beacon_status}
APRS-IS:   {aprs_is_status}"""

    console.print(Panel(summary))

    confirm = questionary.confirm(
        f"Write config to {config_path}?", default=True
    ).ask()

    if confirm:
        config.save(config_path)
        console.print(f"\n[green]\u2713[/green] Config written to {config_path}")
    else:
        console.print("\n[yellow]Config not saved.[/yellow]")


def main() -> None:
    """Run the APRS TUI Setup Wizard."""
    parser = argparse.ArgumentParser(description="APRS TUI Setup Wizard")
    parser.add_argument(
        "--section",
        default=None,
        choices=list(SECTION_MAP.keys()),
        help="Jump directly to a section (skip menu)",
    )
    parser.add_argument("--config", type=Path, default=None)
    args = parser.parse_args()

    config_path = args.config or default_config_path()

    # Load existing config or create default
    try:
        config = AppConfig.load(config_path)
        console.print(f"[dim]Loaded existing config from {config_path}[/dim]")
    except (FileNotFoundError, Exception):
        config = AppConfig(station=StationConfig(callsign="N0CALL"))
        console.print("[dim]No existing config found, using defaults[/dim]")

    # If no --section given, show interactive menu
    section = args.section
    if section is None:
        console.print("\n[bold blue]APRS TUI Setup Wizard[/bold blue]\n")
        choices = [label for label, _ in SECTION_MENU]
        answer = questionary.select(
            "What would you like to configure?",
            choices=choices,
        ).ask()
        if answer is None:
            console.print("[dim]Cancelled.[/dim]")
            return
        # Find the section key for the selected label
        section = next(key for label, key in SECTION_MENU if label == answer)

    steps = SECTION_MAP[section]

    try:
        if "deps" in steps:
            step_deps_check()
        if "bluetooth" in steps:
            plat = detect_platform()
            device, port = step_bluetooth_setup(plat)
            if device:
                if isinstance(device, str) and device.startswith("hybrid:"):
                    parts = device[7:].split("|", 1)
                    config = config.model_copy(
                        update={
                            "server": ServerConfig(
                                protocol="kiss-ble-hybrid",
                                host=parts[0],
                                port=port or 9600,
                                serial_device=parts[1] if len(parts) > 1 else "",
                            ),
                        }
                    )
                elif isinstance(device, str) and device.startswith("ble:"):
                    config = config.model_copy(
                        update={
                            "server": ServerConfig(
                                protocol="kiss-ble", host=device[4:], port=0
                            ),
                        }
                    )
                else:
                    config = config.model_copy(
                        update={
                            "server": ServerConfig(
                                protocol="kiss-bt", host=device, port=port
                            ),
                        }
                    )
        if "connection" in steps:
            config = step_connection_type(config)
        if "connection_test" in steps:
            # Quick test only
            step_connection_type(config)
            return
        if "station" in steps:
            config = step_station(config)
        if "beacon" in steps:
            config = step_beacon(config)
        if "aprs_is" in steps:
            config = step_aprs_is(config)
        if "map" in steps:
            config = step_map_setup(config)
        if "write" in steps:
            step_write_config(config, config_path)
    except KeyboardInterrupt:
        console.print("\n[yellow]Wizard cancelled.[/yellow]")
        sys.exit(1)


if __name__ == "__main__":
    main()
