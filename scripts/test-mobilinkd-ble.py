#!/usr/bin/env python3
"""Test Mobilinkd TNC4 BLE connection and KISS data."""
import asyncio
from bleak import BleakScanner, BleakClient

KISS_SERVICE = "00000001-ba2a-46c9-ae49-01b0961f68bb"
KISS_TX_CHAR = "00000003-ba2a-46c9-ae49-01b0961f68bb"  # TNC→App (notify)
KISS_RX_CHAR = "00000002-ba2a-46c9-ae49-01b0961f68bb"  # App→TNC (write)


async def main():
    # Step 1: Scan
    print("Scanning for BLE devices (10 seconds)...")
    devices = await BleakScanner.discover(timeout=10.0)

    tnc = None
    for d in devices:
        name = d.name or ""
        print(f"  Found: {name} ({d.address})")
        if "mobilinkd" in name.lower() or "tnc" in name.lower():
            tnc = d
            print(f"  ^^^ TNC detected!")

    if not tnc:
        print("\nNo TNC found. Make sure Mobilinkd is powered on and phone app is closed.")
        return

    # Step 2: Connect
    print(f"\nConnecting to {tnc.name} ({tnc.address})...")
    client = BleakClient(tnc.address)
    await client.connect(timeout=15.0)
    print(f"Connected: {client.is_connected}")

    # Step 3: List services
    print("\nServices:")
    for service in client.services:
        print(f"  {service.uuid}: {service.description}")
        for char in service.characteristics:
            props = ", ".join(char.properties)
            print(f"    {char.uuid}: {props}")

    # Step 4: Subscribe to KISS TX and listen
    packet_count = 0

    def on_notify(sender, data):
        nonlocal packet_count
        packet_count += 1
        hex_str = data.hex(" ")
        print(f"  [{packet_count}] {len(data)} bytes: {hex_str}")
        if 0xC0 in data:
            print(f"       ^^^ KISS FEND detected!")

    print(f"\nSubscribing to KISS TX notifications...")
    await client.start_notify(KISS_TX_CHAR, on_notify)

    print("Listening for 30 seconds... (transmit from your other radio)")
    print()
    await asyncio.sleep(30)

    print(f"\nTotal notifications: {packet_count}")
    await client.stop_notify(KISS_TX_CHAR)
    await client.disconnect()

asyncio.run(main())
