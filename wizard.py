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
    APRSISConfig,
    AppConfig,
    BeaconConfig,
    ConnectionConfig,
    ServerConfig,
    StationConfig,
    default_config_path,
)

console = Console()

# Section map per PRD 6.2
SECTION_MAP = {
    "all": ["deps", "connection", "station", "beacon", "aprs_is", "write"],
    "server": ["deps", "connection", "write"],
    "bt": ["deps", "bluetooth", "write"],
    "station": ["station", "write"],
    "beacon": ["beacon", "write"],
    "aprs-is": ["aprs_is", "write"],
    "test": ["connection_test"],
}


def detect_platform() -> dict:
    """Detect the current platform and its capabilities."""
    system = platform.system()
    is_wsl = False

    if system == "Linux":
        try:
            with open("/proc/version", "r") as f:
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
        console.print(f"  [green]\u2713[/green] Serial support (prefix: {plat['serial_device_prefix']})")
    if plat["has_bluetooth"]:
        console.print(f"  [green]\u2713[/green] Bluetooth support (prefix: {plat['bt_device_prefix']})")

    console.print("\n[dim]This wizard assumes Direwolf (or equivalent KISS TCP server)\nis already installed and configured on your target host.[/dim]")
    console.print("[dim]If not, see: https://github.com/wb2osz/direwolf[/dim]\n")


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


def step_bluetooth_setup(plat: dict) -> tuple[str | None, int]:
    """Bluetooth TNC pairing and socat bridge setup.

    Returns (device_path, kiss_port) or (None, 0) if cancelled.
    """
    if not plat["has_bluetooth"]:
        console.print("[yellow]Bluetooth is not available on this platform.[/yellow]")
        if plat["is_wsl"]:
            console.print("[dim]WSL2 does not support Bluetooth natively.[/dim]")
            console.print("[dim]Use KISS TCP or APRS-IS instead.[/dim]")
        return None, 0

    console.print("\n[bold]Bluetooth TNC Setup[/bold]")
    console.print("[dim]Supported: Kenwood TH-D74/D75, Mobilinkd, UV-Pro[/dim]")

    if plat["system"] == "Darwin":
        console.print(
            "\n[dim]On macOS, pair your device via System Preferences > Bluetooth first.[/dim]"
        )
        console.print("[dim]The device will appear as /dev/cu.DeviceName[/dim]")

        device = questionary.text(
            "Enter BT serial device path:",
            default="/dev/cu.",
        ).ask()
        if device is None:
            raise KeyboardInterrupt

    else:  # Linux
        console.print("\n[bold]Tips before scanning:[/bold]")
        console.print(
            "  Kenwood TH-D74/D75: Menu > APRS > Bluetooth > BT KISS TNC > ON"
        )
        console.print("  Mobilinkd TNC: Hold button until LED flashes blue")
        console.print("  Default PINs: Kenwood=0000, Mobilinkd=1234\n")

        # Check for bluetoothctl
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
            # Attempt BT scan
            console.print("Scanning for Bluetooth devices (10 seconds)...")
            try:
                subprocess.run(
                    ["bluetoothctl", "--timeout", "10", "scan", "on"],
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
                # Parse devices - simplified
                console.print(
                    "[dim]Scan complete. Enter the device MAC or path.[/dim]"
                )
            except (subprocess.TimeoutExpired, FileNotFoundError):
                console.print("[yellow]BT scan failed or timed out.[/yellow]")

            device = questionary.text(
                "BT device path:", default="/dev/rfcomm0"
            ).ask()
            if device is None:
                raise KeyboardInterrupt

    # socat bridge setup
    console.print("\n[bold]socat Bridge Configuration[/bold]")
    console.print(
        "[dim]socat forwards BT serial to KISS TCP so the TUI can connect.[/dim]"
    )

    port_str = questionary.text("KISS TCP port for bridge:", default="8001").ask()
    if port_str is None:
        raise KeyboardInterrupt
    port = int(port_str)

    # Generate bridge script
    generate = questionary.confirm(
        "Generate start-bt-bridge.sh?", default=True
    ).ask()
    if generate:
        script_content = f"""#!/bin/bash
# start-bt-bridge.sh - generated by aprs-tui wizard
# Bridges BT serial to KISS TCP port {port}
# Usage: ./start-bt-bridge.sh

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

    return device, port


def step_connection_type(config: AppConfig) -> AppConfig:
    """Select connection type and configure server."""
    plat = detect_platform()

    choices = [
        "Direwolf / KISS TCP (USB/SDR, network)",
    ]
    if plat["has_serial"]:
        choices.append("USB Serial TNC (direct serial connection)")
    if plat["has_bluetooth"]:
        choices.append("Bluetooth TNC (Kenwood, Mobilinkd, UV-Pro)")
    choices.append("APRS-IS only (internet gateway, no radio)")

    conn_type = questionary.select(
        "How is your TNC or radio connected?", choices=choices
    ).ask()

    if conn_type is None:  # User cancelled
        raise KeyboardInterrupt

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
        device, port = step_bluetooth_setup(plat)
        if device:
            return config.model_copy(
                update={
                    "server": ServerConfig(
                        protocol="kiss-bt", host="localhost", port=port
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
        console.print("  [dim]  Linux: avahi-publish-service \"Direwolf KISS\" _kiss-tnc._tcp 8001 &[/dim]")
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
            raise KeyboardInterrupt

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

    return config.model_copy(
        update={
            "station": StationConfig(
                callsign=callsign.upper(),
                ssid=ssid,
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

        lat_str = questionary.text(
            "Latitude (decimal degrees):", default=str(config.beacon.latitude)
        ).ask()
        if lat_str is None:
            raise KeyboardInterrupt
        lat = float(lat_str)

        lon_str = questionary.text(
            "Longitude (decimal degrees):", default=str(config.beacon.longitude)
        ).ask()
        if lon_str is None:
            raise KeyboardInterrupt
        lon = float(lon_str)

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

    console.print("\n  [dim]Leave passcode blank for receive-only mode.[/dim]")
    console.print("  [dim]Passcode generator: https://apps.magicbug.co.uk/passcode/[/dim]")

    passcode_str = questionary.text(
        "Passcode (-1 for receive-only):", default=str(config.aprs_is.passcode)
    ).ask()
    if passcode_str is None:
        raise KeyboardInterrupt

    filter_str = (
        questionary.text("Filter (blank=none):", default=config.aprs_is.filter).ask() or ""
    )

    console.print("\n  [dim]Example filters: r/45.4/-122.6/100  b/W7XXX*  t/m[/dim]")

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


def step_write_config(config: AppConfig, config_path: Path) -> None:
    """Display summary and write config."""
    callsign = f"{config.station.callsign}-{config.station.ssid}"

    beacon_status = (
        f"ON, every {config.beacon.interval}s" if config.beacon.enabled else "OFF"
    )
    aprs_is_status = (
        f"ON, {config.aprs_is.host}" if config.aprs_is.enabled else "OFF"
    )

    summary = f"""[bold]Configuration Summary[/bold]

Callsign:  {callsign}
Symbol:    {config.station.symbol_table}{config.station.symbol_code}
Server:    {config.server.host}:{config.server.port} ({config.server.protocol})
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
    parser.add_argument("--section", default="all", choices=list(SECTION_MAP.keys()))
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

    steps = SECTION_MAP[args.section]

    try:
        if "deps" in steps:
            step_deps_check()
        if "bluetooth" in steps:
            plat = detect_platform()
            device, port = step_bluetooth_setup(plat)
            if device:
                config = config.model_copy(
                    update={
                        "server": ServerConfig(
                            protocol="kiss-bt", host="localhost", port=port
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
        if "write" in steps:
            step_write_config(config, config_path)
    except KeyboardInterrupt:
        console.print("\n[yellow]Wizard cancelled.[/yellow]")
        sys.exit(1)


if __name__ == "__main__":
    main()
