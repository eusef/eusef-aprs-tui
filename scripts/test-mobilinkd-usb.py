#!/usr/bin/env python3
"""Test Mobilinkd TNC4 USB - try various protocols to get a response."""
import time

import serial

DEVICE = "/dev/cu.usbmodem2082336543461"

s = serial.Serial(DEVICE, 9600, timeout=2)
print(f"Opened: {s.name}")

# Try KISS FEND
print("\n1. Sending KISS FEND bytes...")
s.write(b"\xc0\xc0")
s.flush()
time.sleep(1)
data = s.read(s.in_waiting or 0)
print(f"   Response: {len(data)} bytes {data.hex(' ') if data else '(none)'}")

# Try newline (maybe it's a command interface)
print("\n2. Sending newline...")
s.write(b"\r\n")
s.flush()
time.sleep(1)
data = s.read(s.in_waiting or 0)
print(f"   Response: {len(data)} bytes {data[:80] if data else b'(none)'}")

# Try Mobilinkd TNC protocol - hardware info request
# TNC4 uses KISS extended commands: FEND + 0x06 + 0x01 + FEND
print("\n3. Sending TNC hardware info request (KISS ext cmd)...")
s.write(b"\xc0\x06\x01\xc0")
s.flush()
time.sleep(1)
data = s.read(s.in_waiting or 0)
print(f"   Response: {len(data)} bytes {data.hex(' ') if data else '(none)'}")

# Try at different baud rates
for baud in [38400, 57600, 115200]:
    s.close()
    s = serial.Serial(DEVICE, baud, timeout=1)
    print(f"\n4. Trying baud {baud}, sending FEND...")
    s.write(b"\xc0\xc0")
    s.flush()
    time.sleep(1)
    data = s.read(s.in_waiting or 0)
    print(f"   Response: {len(data)} bytes {data.hex(' ') if data else '(none)'}")

s.close()
print("\nDone.")
