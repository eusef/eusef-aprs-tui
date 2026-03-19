#!/usr/bin/env python3
"""Test sending an APRS message to UV-PRO via BLE with bonding.

Attempts to negotiate BLE encryption/bonding on macOS and then
write a KISS frame to the UV-PRO's RX characteristic.

Usage: .venv/bin/python scripts/test-uvpro-ble-send.py
"""
import asyncio
import sys

sys.path.insert(0, ".")

from bleak import BleakClient

from aprs_tui.protocol.ax25 import ax25_encode
from aprs_tui.protocol.encoder import encode_message

# UV-PRO BLE address from config
BLE_ADDRESS = "DA78B460-FC42-AF4C-975D-0505B8BDE531"

# KISS BLE UUIDs
KISS_SERVICE = "00000001-ba2a-46c9-ae49-01b0961f68bb"
KISS_TX_CHAR = "00000003-ba2a-46c9-ae49-01b0961f68bb"  # Device→App (notify)
KISS_RX_CHAR = "00000002-ba2a-46c9-ae49-01b0961f68bb"  # App→Device (write)

# Encrypted characteristic that triggers macOS bonding dialog
ENCRYPTED_CHAR = "00001103-d102-11e1-9b23-00025b00a5a5"

CALLSIGN = "W7PDJ-14"
DEST_CALL = "W7PDJ-7"
MSG_TEXT = "BLE bond test 73"
MSG_ID = "97"


def kiss_encode(data: bytes) -> bytes:
    fend, fesc, tfend, tfesc = 0xC0, 0xDB, 0xDC, 0xDD  # noqa: N806
    stuffed = bytearray()
    for b in data:
        if b == fend:
            stuffed.extend([fesc, tfend])
        elif b == fesc:
            stuffed.extend([fesc, tfesc])
        else:
            stuffed.append(b)
    return bytes([fend, 0x00]) + bytes(stuffed) + bytes([fend])


async def main():
    print("=== UV-PRO BLE TX Test (with bonding) ===")
    print(f"BLE Address: {BLE_ADDRESS}")
    print(f"Message: {CALLSIGN} -> {DEST_CALL}: {MSG_TEXT}")
    print()

    # Build the APRS frame
    info = encode_message(DEST_CALL, MSG_TEXT, MSG_ID)
    ax25 = ax25_encode(CALLSIGN, "APRS", ["WIDE1-1", "WIDE2-1"], info.encode("latin-1"))
    kiss_data = kiss_encode(ax25)
    print(f"APRS info: {info}")
    print(f"AX.25: {len(ax25)} bytes")
    print(f"KISS:  {len(kiss_data)} bytes: {kiss_data.hex(' ')}")
    print()

    # Step 1: Connect
    print("[1] Connecting to UV-PRO via BLE...")
    client = BleakClient(BLE_ADDRESS)
    try:
        await client.connect(timeout=15.0)
    except Exception as e:
        print(f"    FAILED to connect: {e}")
        return
    print(f"    Connected: {client.is_connected}")

    mtu = getattr(client, "mtu_size", 23)
    print(f"    MTU: {mtu}")

    # Step 2: List services and characteristics
    print("\n[2] Enumerating services...")
    kiss_svc_found = False
    for service in client.services:
        is_kiss = KISS_SERVICE.lower() in service.uuid.lower()
        marker = " <<< KISS" if is_kiss else ""
        print(f"    {service.uuid}{marker}")
        if is_kiss:
            kiss_svc_found = True
        for char in service.characteristics:
            props = ", ".join(char.properties)
            print(f"      {char.uuid}: [{props}]")

    if not kiss_svc_found:
        print("    WARNING: KISS service not found!")

    # Step 3: Try to trigger BLE encryption/bonding
    print("\n[3] Attempting BLE encryption negotiation...")
    print("    (On macOS, this may trigger a pairing dialog in System Settings)")
    try:
        val = await client.read_gatt_char(ENCRYPTED_CHAR)
        print(f"    Encrypted char read OK: {val.hex(' ') if val else 'empty'}")
    except Exception as e:
        print(f"    Encrypted char read failed: {e}")
        print("    This is expected if the device needs bonding that hasn't been done yet.")

    # Also try reading paired status if available
    try:
        paired = getattr(client, "is_paired", None)
        if paired is not None:
            print(f"    Paired: {paired}")
    except Exception:
        pass

    await asyncio.sleep(1.0)

    # Step 4: Subscribe to notifications (to see any response)
    print("\n[4] Subscribing to KISS TX notifications...")
    responses = []

    def on_notify(sender, data):
        responses.append(data)
        print(f"    RX notification: {len(data)} bytes: {data.hex(' ')}")

    try:
        await client.start_notify(KISS_TX_CHAR, on_notify)
        print("    Subscribed OK")
    except Exception as e:
        print(f"    Subscribe failed: {e}")

    await asyncio.sleep(0.5)

    # Step 5: Try write-with-response (requires bonding)
    print("\n[5] Attempting write-WITH-response (requires bonding)...")
    chunk_size = max(mtu - 3, 20)
    write_with_resp_ok = False

    try:
        for i in range(0, len(kiss_data), chunk_size):
            chunk = kiss_data[i:i + chunk_size]
            print(f"    Writing chunk {i // chunk_size + 1}: {len(chunk)}B: {chunk.hex(' ')}")
            await client.write_gatt_char(KISS_RX_CHAR, chunk, response=True)
            if i + chunk_size < len(kiss_data):
                await asyncio.sleep(0.05)
        print("    Write-with-response SUCCEEDED!")
        print("    >>> Watch UV-PRO: does LED turn RED (PTT)? <<<")
        write_with_resp_ok = True
    except Exception as e:
        print(f"    Write-with-response FAILED: {e}")

    await asyncio.sleep(3)

    # Step 6: If write-with-response failed, try write-without-response
    if not write_with_resp_ok:
        print("\n[6] Attempting write-WITHOUT-response (no bonding needed)...")
        try:
            for i in range(0, len(kiss_data), chunk_size):
                chunk = kiss_data[i:i + chunk_size]
                print(f"    Writing chunk {i // chunk_size + 1}: {len(chunk)}B: {chunk.hex(' ')}")
                await client.write_gatt_char(KISS_RX_CHAR, chunk, response=False)
                if i + chunk_size < len(kiss_data):
                    await asyncio.sleep(0.05)
            print("    Write-without-response completed (no error).")
            print("    >>> Watch UV-PRO: does LED turn RED (PTT)? <<<")
        except Exception as e:
            print(f"    Write-without-response FAILED: {e}")

        await asyncio.sleep(3)
    else:
        print("\n[6] Skipped (write-with-response worked)")

    # Step 7: Check for any RX notifications
    print(f"\n[7] Notifications received: {len(responses)}")
    for i, r in enumerate(responses):
        print(f"    [{i+1}] {r.hex(' ')}")

    # Cleanup
    import contextlib

    with contextlib.suppress(Exception):
        await client.stop_notify(KISS_TX_CHAR)
    await client.disconnect()
    print("\n[Done] Disconnected.")
    print()
    print("Interpretation:")
    print("  - Write-with-response succeeded + PTT: bonding works! We can use pure BLE for TX.")
    print("  - Write-without-response succeeded + PTT: UV-PRO accepts unencrypted writes.")
    print("  - No PTT at all: the UV-PRO may need to be in APRS mode, or on 144.390 MHz.")
    print("  - Write failed with 'not paired': macOS needs to bond first. Check System")
    print("    Settings > Bluetooth and pair the UV-PRO manually, then re-run this script.")


asyncio.run(main())
