#!/usr/bin/env python3
"""Test the actual AprsIsTransport + ConnectionManager pipeline."""
import asyncio
import sys

sys.path.insert(0, ".")

from aprs_tui.core.connection import ConnectionManager
from aprs_tui.transport.aprs_is import AprsIsTransport

count = 0

def on_packet(pkt):
    global count
    count += 1
    print(f"[{count}] {pkt.info_type}: {pkt.source} - {pkt.raw[:80]}")

def on_state(state):
    print(f"STATE: {state.value}")

async def main():
    transport = AprsIsTransport(
        host="rotate.aprs2.net",
        port=14580,
        callsign="W7PDJ",
        passcode=16017,
        filter_str="r/47.6/-122.3/200",
    )

    mgr = ConnectionManager(
        transport,
        on_state_change=on_state,
        on_packet=on_packet,
    )

    print("Connecting to APRS-IS...")
    await mgr.connect()
    print(f"Connected: {mgr.state.value}")
    print("Waiting 20 seconds for packets...\n")

    await asyncio.sleep(20)

    print(f"\nTotal packets: {count}")
    await mgr.disconnect()

asyncio.run(main())
