#!/usr/bin/env python3
"""Diagnostic: test UV-PRO classic BT serial port for KISS TX.

Tests whether the UV-PRO's classic Bluetooth serial port accepts KISS
frames for transmission. Run with the UV-PRO paired and connected.

Usage: python scripts/test-uvpro-serial.py [/dev/cu.UV-PRO]
"""
import sys
import time

import serial

DEVICE = sys.argv[1] if len(sys.argv) > 1 else "/dev/cu.UV-PRO"
BAUDRATE = 9600

# KISS constants
FEND = 0xC0
KISS_DATA_CMD = 0x00

# Build a minimal APRS beacon as AX.25 + KISS
# This avoids importing project code so the script is self-contained
sys.path.insert(0, ".")
from aprs_tui.protocol.ax25 import ax25_encode  # noqa: E402
from aprs_tui.protocol.encoder import encode_message  # noqa: E402


def kiss_encode(data: bytes) -> bytes:
    """Wrap raw AX.25 frame in KISS framing."""
    fesc, tfend, tfesc = 0xDB, 0xDC, 0xDD
    stuffed = bytearray()
    for b in data:
        if b == FEND:
            stuffed.extend([fesc, tfend])
        elif b == fesc:
            stuffed.extend([fesc, tfesc])
        else:
            stuffed.append(b)
    return bytes([FEND, KISS_DATA_CMD]) + bytes(stuffed) + bytes([FEND])


def main():
    print("=== UV-PRO Serial TX Diagnostic ===")
    print(f"Device: {DEVICE}")
    print(f"Baud:   {BAUDRATE}")
    print()

    # Step 1: Open serial port
    print("[1] Opening serial port...")
    try:
        ser = serial.Serial(DEVICE, BAUDRATE, timeout=2.0, write_timeout=5.0)
        print(f"    OK - port open: {ser.name}")
        print(f"    DSR={ser.dsr}, CTS={ser.cts}, CD={ser.cd}")
    except Exception as e:
        print(f"    FAILED: {e}")
        return

    # Step 2: Check if anything comes in on the serial port (data from radio?)
    print("\n[2] Reading from serial port (2 seconds)...")
    data = ser.read(256)
    if data:
        print(f"    Received {len(data)} bytes: {data.hex(' ')}")
        print(f"    ASCII: {data.decode('latin-1', errors='replace')}")
    else:
        print("    No data received (normal if radio is idle)")

    # Step 3: Try sending KISS "return to command mode" (0xC0 0xFF 0xC0)
    # Some TNCs respond to this
    print("\n[3] Sending KISS return-to-cmd (C0 FF C0)...")
    try:
        ser.write(bytes([FEND, 0xFF, FEND]))
        ser.flush()
        time.sleep(1)
        resp = ser.read(256)
        if resp:
            print(f"    Response: {resp.hex(' ')}")
            print(f"    ASCII: {resp.decode('latin-1', errors='replace')}")
        else:
            print("    No response")
    except Exception as e:
        print(f"    Write error: {e}")

    # Step 4: Send a test APRS message via KISS
    print("\n[4] Sending test KISS frame (APRS message)...")
    info = encode_message("W7PDJ-7", "serial test", "98")
    ax25 = ax25_encode("W7PDJ-14", "APRS", ["WIDE1-1", "WIDE2-1"], info.encode("latin-1"))
    kiss_data = kiss_encode(ax25)
    print(f"    AX.25: {len(ax25)} bytes")
    print(f"    KISS:  {len(kiss_data)} bytes: {kiss_data.hex(' ')}")

    try:
        written = ser.write(kiss_data)
        ser.flush()
        print(f"    Wrote {written} bytes")
        print("    >>> Watch the UV-PRO: does the LED turn RED (PTT)? <<<")
        time.sleep(3)
        resp = ser.read(256)
        if resp:
            print(f"    Response: {resp.hex(' ')}")
        else:
            print("    No response from radio")
    except Exception as e:
        print(f"    Write error: {e}")

    # Step 5: Try different baud rates
    print("\n[5] Trying alternate baud rates...")
    for baud in [19200, 38400, 57600, 115200]:
        try:
            ser.baudrate = baud
            time.sleep(0.2)
            ser.write(kiss_data)
            ser.flush()
            print(f"    {baud}: wrote OK - watch for PTT!")
            time.sleep(2)
            resp = ser.read(256)
            if resp:
                print(f"    {baud}: response: {resp.hex(' ')}")
        except Exception as e:
            print(f"    {baud}: error: {e}")

    # Reset to original baud
    ser.baudrate = BAUDRATE

    # Step 6: Try raw FEND bytes (KISS keepalive / port detection)
    print(f"\n[6] Sending bare FEND bytes at {BAUDRATE} baud...")
    try:
        ser.write(bytes([FEND, FEND, FEND]))
        ser.flush()
        time.sleep(1)
        resp = ser.read(256)
        if resp:
            print(f"    Response: {resp.hex(' ')}")
        else:
            print("    No response")
    except Exception as e:
        print(f"    Error: {e}")

    ser.close()
    print("\n[Done] Serial port closed.")
    print()
    print("Results:")
    print("  - If no PTT at any baud rate: the UV-PRO SPP port likely does NOT")
    print("    accept KISS. TX may need to go through BLE with bonding, or the")
    print("    SPP port uses a different protocol (AT commands, proprietary, etc.)")
    print("  - If PTT fired at a specific baud rate: update config.toml with that baud.")
    print("  - If you got readable responses: the radio may need initialization first.")


if __name__ == "__main__":
    main()
