#!/usr/bin/env python3
"""UV-PRO BLE Discovery & Monitor

Scans for BLE devices, connects to the UV-PRO, enumerates all GATT
services/characteristics, and subscribes to all notify-capable
characteristics to display everything the radio sends.

Usage:
    source .venv/bin/activate
    python ble_monitor.py              # scan and auto-connect to UV-PRO
    python ble_monitor.py --scan       # scan only, list all BLE devices
    python ble_monitor.py --addr XX:XX:XX:XX:XX:XX   # connect by address

Press Ctrl+C to stop.
"""
import asyncio
import argparse
import sys
from datetime import datetime

from bleak import BleakScanner, BleakClient

# --- Colors ---
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
RED = "\033[31m"
DIM = "\033[2m"
MAGENTA = "\033[35m"

# KISS constants (for attempted decode)
FEND = 0xC0
FESC = 0xDB
TFEND = 0xDC
TFESC = 0xDD


def printable_ascii(data):
    return "".join(chr(b) if 32 <= b < 127 else "." for b in data)


def kiss_destuff(data):
    result = bytearray()
    i = 0
    while i < len(data):
        if data[i] == FESC and i + 1 < len(data):
            if data[i + 1] == TFEND:
                result.append(FEND)
            elif data[i + 1] == TFESC:
                result.append(FESC)
            else:
                result.append(data[i + 1])
            i += 2
        else:
            result.append(data[i])
            i += 1
    return bytes(result)


def decode_ax25(frame):
    if len(frame) < 16:
        return None
    try:
        dest = "".join(chr(b >> 1) for b in frame[0:6]).rstrip()
        dest_ssid = (frame[6] >> 1) & 0x0F
        src = "".join(chr(b >> 1) for b in frame[7:13]).rstrip()
        src_ssid = (frame[13] >> 1) & 0x0F
        src_last = bool(frame[13] & 0x01)
        digis = []
        offset = 14
        last = src_last
        while not last and offset + 7 <= len(frame):
            dc = "".join(chr(b >> 1) for b in frame[offset : offset + 6]).rstrip()
            ds = (frame[offset + 6] >> 1) & 0x0F
            last = bool(frame[offset + 6] & 0x01)
            h = bool(frame[offset + 6] & 0x80)
            d = f"{dc}-{ds}" if ds else dc
            if h:
                d += "*"
            digis.append(d)
            offset += 7
        if offset + 2 > len(frame):
            return None
        info = frame[offset + 2 :]
        s = f"{src}-{src_ssid}" if src_ssid else src
        d = f"{dest}-{dest_ssid}" if dest_ssid else dest
        path = ",".join([d] + digis)
        return f"{s}>{path}:{info.decode('latin-1')}"
    except Exception:
        return None


async def scan_devices(timeout=10.0):
    """Scan for all BLE devices and display them."""
    print(f"{BOLD}Scanning for BLE devices ({timeout}s)...{RESET}\n")

    # Try with adv data first, fall back to simple list
    try:
        devices = await BleakScanner.discover(timeout=timeout, return_adv=True)
    except Exception:
        # Fallback: simple device list
        dev_list = await BleakScanner.discover(timeout=timeout)
        devices = {d: (d, None) for d in dev_list} if dev_list else {}

    if not devices:
        print(f"{RED}No BLE devices found.{RESET}")
        return None

    # Build a flat list of (name, address, rssi, service_uuids) regardless of bleak version
    entries = []
    for key, value in devices.items():
        # return_adv=True gives {BLEDevice: (BLEDevice, AdvertisementData)} or
        # on some macOS bleak versions: {str: (BLEDevice, AdvertisementData)}
        if isinstance(value, tuple) and len(value) == 2:
            dev_obj, adv = value
        else:
            dev_obj, adv = value, None

        # Handle both BLEDevice objects and raw strings (macOS Swift bridge)
        if hasattr(dev_obj, "name"):
            name = dev_obj.name or "(unknown)"
            address = dev_obj.address
        elif hasattr(key, "name"):
            name = key.name or "(unknown)"
            address = key.address if hasattr(key, "address") else str(key)
        else:
            name = "(unknown)"
            address = str(key)

        rssi = adv.rssi if adv and hasattr(adv, "rssi") else 0
        svcs = adv.service_uuids if adv and hasattr(adv, "service_uuids") else []
        entries.append((name, address, rssi or 0, svcs or []))

    # Sort by signal strength
    entries.sort(key=lambda x: x[2], reverse=True)

    print(f"{'Name':<30} {'Address':<20} {'RSSI':>5}  Services")
    print(f"{'-' * 30} {'-' * 20} {'-' * 5}  {'-' * 30}")

    uv_pro = None
    for name, address, rssi, svcs in entries:
        svcs_str = ", ".join(str(s) for s in svcs)[:50]

        # Highlight UV-PRO
        is_uvpro = "uv" in name.lower() or "btech" in name.lower() or "pro" in name.lower()
        if is_uvpro:
            print(f"{GREEN}{BOLD}{name:<30} {address:<20} {rssi:>5}  {svcs_str}{RESET}")
            uv_pro = address
        else:
            print(f"{name:<30} {address:<20} {rssi:>5}  {svcs_str}")

    print(f"\n{len(entries)} device(s) found.\n")
    return uv_pro


async def connect_and_enumerate(address):
    """Connect to a BLE device and list all services/characteristics."""
    print(f"\n{BOLD}Connecting to {address}...{RESET}")

    client = BleakClient(address)
    await client.connect(timeout=15.0)

    if not client.is_connected:
        print(f"{RED}Failed to connect.{RESET}")
        return None, []

    print(f"{GREEN}CONNECTED{RESET}\n")

    notify_chars = []

    print(f"{BOLD}{'=' * 60}")
    print(f"  GATT Services & Characteristics")
    print(f"{'=' * 60}{RESET}\n")

    for service in client.services:
        print(f"{CYAN}{BOLD}Service: {service.uuid}{RESET}")
        if service.description:
            print(f"  Description: {service.description}")

        for char in service.characteristics:
            props = ", ".join(char.properties)
            print(f"  {YELLOW}Char: {char.uuid}{RESET}")
            print(f"    Handle: {char.handle}")
            print(f"    Properties: {props}")
            if char.description:
                print(f"    Description: {char.description}")

            # Try reading if readable
            if "read" in char.properties:
                try:
                    val = await client.read_gatt_char(char.uuid)
                    print(f"    {GREEN}Value: {val.hex(' ')}{RESET}")
                    print(f"    {GREEN}ASCII: {printable_ascii(val)}{RESET}")
                except Exception as e:
                    print(f"    {DIM}(read failed: {e}){RESET}")

            # Track notify-capable characteristics
            if "notify" in char.properties or "indicate" in char.properties:
                notify_chars.append(char)
                print(f"    {MAGENTA}>>> SUBSCRIBABLE (will monitor){RESET}")

            # List descriptors
            for desc in char.descriptors:
                print(f"    {DIM}Descriptor: {desc.uuid} = {desc.description}{RESET}")

        print()

    print(f"{BOLD}Found {len(notify_chars)} notify/indicate characteristic(s){RESET}\n")
    return client, notify_chars


async def monitor(client, notify_chars):
    """Subscribe to all notify characteristics and display incoming data."""
    print(f"{BOLD}{'=' * 60}")
    print(f"  Monitoring all BLE notifications")
    print(f"  Press Ctrl+C to stop")
    print(f"{'=' * 60}{RESET}\n")

    notification_count = 0
    kiss_buffer = bytearray()
    frame_count = 0

    def make_handler(char_uuid):
        def handler(sender, data):
            nonlocal notification_count, kiss_buffer, frame_count
            notification_count += 1
            ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            hex_str = data.hex(" ") if len(data) <= 40 else data[:40].hex(" ") + "..."
            ascii_str = printable_ascii(data)

            print(f"{DIM}[{ts}]{RESET} {CYAN}Char {str(char_uuid)[:8]}...{RESET} {MAGENTA}+{len(data)}B{RESET}")
            print(f"  hex:   {hex_str}")
            print(f"  ascii: {ascii_str}")

            # Try KISS decode
            kiss_buffer.extend(data)
            while True:
                try:
                    s = kiss_buffer.index(FEND)
                except ValueError:
                    if len(kiss_buffer) > 512:
                        kiss_buffer.clear()
                    break
                if s > 0:
                    del kiss_buffer[:s]
                pos = 0
                while pos < len(kiss_buffer) and kiss_buffer[pos] == FEND:
                    pos += 1
                if pos >= len(kiss_buffer):
                    break
                try:
                    end = kiss_buffer.index(FEND, pos)
                except ValueError:
                    break
                raw = kiss_buffer[pos:end]
                del kiss_buffer[: end + 1]
                if len(raw) < 1:
                    continue
                frame_count += 1
                cmd = raw[0]
                print(f"\n  {GREEN}{BOLD}*** KISS FRAME #{frame_count} (cmd=0x{cmd:02X}, {len(raw)}B) ***{RESET}")
                if cmd == 0x00 and len(raw) > 1:
                    payload = kiss_destuff(bytes(raw[1:]))
                    decoded = decode_ax25(payload)
                    if decoded:
                        print(f"  {GREEN}{BOLD}APRS: {decoded}{RESET}")
                    else:
                        print(f"  Payload: {payload.hex(' ')}")
                        print(f"  ASCII:   {printable_ascii(payload)}")
                print()

        return handler

    # Subscribe to each notify characteristic
    for char in notify_chars:
        try:
            await client.start_notify(char.uuid, make_handler(char.uuid))
            print(f"{GREEN}Subscribed to {char.uuid}{RESET}")
        except Exception as e:
            print(f"{RED}Failed to subscribe to {char.uuid}: {e}{RESET}")

    print(f"\nListening...\n")

    # Keep running until Ctrl+C
    try:
        while client.is_connected:
            await asyncio.sleep(0.5)
        print(f"\n{RED}BLE connection lost.{RESET}")
    except asyncio.CancelledError:
        pass

    return notification_count, frame_count


async def main():
    parser = argparse.ArgumentParser(description="UV-PRO BLE Monitor")
    parser.add_argument("--scan", action="store_true", help="Scan only, don't connect")
    parser.add_argument("--addr", type=str, help="BLE address to connect to directly")
    parser.add_argument("--timeout", type=float, default=10.0, help="Scan timeout (default 10s)")
    args = parser.parse_args()

    print(f"{BOLD}{'=' * 60}")
    print(f"  UV-PRO BLE Monitor")
    print(f"{'=' * 60}{RESET}")
    print(f"  Started: {datetime.now().strftime('%H:%M:%S')}")
    print()

    address = args.addr

    if not address:
        # Scan first
        uv_pro = await scan_devices(timeout=args.timeout)

        if args.scan:
            return

        if uv_pro:
            address = uv_pro
            print(f"{GREEN}Found UV-PRO candidate: {address}{RESET}")
        else:
            # Ask user to pick
            addr = input(f"\n{YELLOW}Enter BLE address to connect to (or 'q' to quit): {RESET}").strip()
            if addr.lower() == "q":
                return
            address = addr

    # Connect and enumerate services
    client, notify_chars = await connect_and_enumerate(address)
    if client is None:
        return

    if not notify_chars:
        print(f"{YELLOW}No notify characteristics found -- nothing to monitor.{RESET}")
        print(f"The service list above shows what the device exposes.")
        await client.disconnect()
        return

    # Monitor
    try:
        notif_count, frame_count = await monitor(client, notify_chars)
    except KeyboardInterrupt:
        notif_count, frame_count = 0, 0
    finally:
        if client.is_connected:
            await client.disconnect()
        print(f"\n{'=' * 60}")
        print(f"  Notifications: {notif_count}")
        print(f"  KISS frames:   {frame_count}")
        print(f"  Closed:        {datetime.now().strftime('%H:%M:%S')}")
        print(f"{'=' * 60}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n{DIM}Stopped.{RESET}")
