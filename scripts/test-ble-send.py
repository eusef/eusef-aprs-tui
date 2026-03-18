#!/usr/bin/env python3
"""Test sending a KISS frame to Mobilinkd TNC4 via BLE."""
import asyncio
import sys

sys.path.insert(0, ".")

from bleak import BleakClient

BLE_ADDRESS = "F8A81515-6061-CA30-2B45-E33A75516D3E"
KISS_TX_CHAR = "00000003-ba2a-46c9-ae49-01b0961f68bb"  # TNC→App (notify)
KISS_RX_CHAR = "00000002-ba2a-46c9-ae49-01b0961f68bb"  # App→TNC (write)

# Build a test APRS message packet
from aprs_tui.protocol.ax25 import ax25_encode  # noqa: E402
from aprs_tui.protocol.encoder import encode_message  # noqa: E402
from aprs_tui.protocol.kiss import kiss_frame  # noqa: E402

CALLSIGN = "W7PDJ-14"
DEST_CALL = "W7PDJ-7"
MSG_TEXT = "BLE test 73"
MSG_ID = "99"

info = encode_message(DEST_CALL, MSG_TEXT, MSG_ID)
print(f"APRS info: {info}")

ax25_data = ax25_encode(CALLSIGN, "APRS", ["WIDE1-1", "WIDE2-1"], info.encode("latin-1"))
print(f"AX.25 frame: {len(ax25_data)} bytes")

kiss_data = kiss_frame(ax25_data)
print(f"KISS frame: {len(kiss_data)} bytes: {kiss_data.hex(' ')}")


async def main():
    print(f"\nConnecting to {BLE_ADDRESS}...")
    client = BleakClient(BLE_ADDRESS)
    await client.connect(timeout=15.0)
    print(f"Connected: {client.is_connected}")

    # Subscribe to TX to see any response
    responses = []
    def on_notify(sender, data):
        responses.append(data)
        print(f"  RX: {len(data)} bytes: {data.hex(' ')}")

    await client.start_notify(KISS_TX_CHAR, on_notify)
    print("Subscribed to notifications")

    # Send the KISS frame
    print(f"\nSending KISS frame ({len(kiss_data)} bytes)...")

    # Try writing in chunks (BLE max ~20 bytes per write)
    chunk_size = 20
    for i in range(0, len(kiss_data), chunk_size):
        chunk = kiss_data[i:i + chunk_size]
        print(f"  Writing chunk {i//chunk_size + 1}: {len(chunk)} bytes: {chunk.hex(' ')}")
        await client.write_gatt_char(KISS_RX_CHAR, chunk)
        await asyncio.sleep(0.05)

    print("\nSent! Waiting 5 seconds for response/TX...")
    await asyncio.sleep(5)

    print(f"\nResponses received: {len(responses)}")
    await client.stop_notify(KISS_TX_CHAR)
    await client.disconnect()
    print("Done.")

asyncio.run(main())
