#!/usr/bin/env python3
"""Quick test: read raw bytes from Mobilinkd BT serial."""
import serial
import time

DEVICE = "/dev/cu.TNC4Mobilinkd"

s = serial.Serial(DEVICE, 9600, timeout=2)
print(f"Opened: {s.name}")

# Send KISS init - exit KISS then re-enter (reset)
FEND = b"\xc0"
# Some TNCs need a FEND to wake up
s.write(FEND + FEND)
s.flush()
print("Sent KISS FEND wake-up")

print("Listening for KISS data (20 seconds)...")
print("Make sure your radio is on 144.390 MHz")
print("Make sure Mobilinkd phone app is CLOSED\n")

total = 0
start = time.time()
while time.time() - start < 20:
    data = s.read(s.in_waiting or 1)
    if data:
        total += len(data)
        preview = data[:32].hex(" ")
        print(f"  [{len(data)} bytes] {preview}")
        if 0xC0 in data:
            print("  ^ KISS FEND detected!")

print(f"\nTotal: {total} bytes")
s.close()
