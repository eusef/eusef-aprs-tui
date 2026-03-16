#!/usr/bin/env python3
"""UV-PRO Bluetooth Serial Monitor

Monitors the UV-PRO Bluetooth serial port and displays everything
that comes across -- raw hex, ASCII, and decoded KISS/AX.25 frames
if detected.

Usage:
    source .venv/bin/activate
    python bt_monitor.py [device] [baudrate]

Defaults: /dev/cu.UV-PRO  9600

Press Ctrl+C to stop.
"""
import serial
import sys
import time
from datetime import datetime

# --- Config ---
DEVICE = sys.argv[1] if len(sys.argv) > 1 else "/dev/cu.UV-PRO"
BAUD = int(sys.argv[2]) if len(sys.argv) > 2 else 9600

# --- KISS constants ---
FEND = 0xC0
FESC = 0xDB
TFEND = 0xDC
TFESC = 0xDD

# --- Colors ---
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
RED = "\033[31m"
DIM = "\033[2m"


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


def printable_ascii(data):
    """Show printable ASCII or dots for non-printable bytes."""
    return "".join(chr(b) if 32 <= b < 127 else "." for b in data)


def main():
    print(f"{BOLD}{'=' * 60}{RESET}")
    print(f"{BOLD}  UV-PRO Bluetooth Monitor{RESET}")
    print(f"{BOLD}{'=' * 60}{RESET}")
    print(f"  Device:   {CYAN}{DEVICE}{RESET}")
    print(f"  Baud:     {CYAN}{BAUD}{RESET}")
    print(f"  Started:  {datetime.now().strftime('%H:%M:%S')}")
    print(f"  Stop:     {YELLOW}Ctrl+C{RESET}")
    print(f"{'=' * 60}")
    print()

    try:
        ser = serial.Serial(DEVICE, BAUD, timeout=2.0)
    except serial.SerialException as e:
        print(f"{RED}FAILED to open {DEVICE}: {e}{RESET}")
        print()
        print("Troubleshooting:")
        print("  - Is the UV-PRO powered on and paired?")
        print("  - Check: ls /dev/cu.UV*")
        print("  - Is another app using the port?")
        sys.exit(1)

    print(f"{GREEN}CONNECTED{RESET} to {ser.name}")
    print(f"Waiting for data... everything received will be displayed.\n")

    buf = bytearray()
    total_bytes = 0
    frame_count = 0
    start = time.time()
    last_data_time = None

    try:
        while True:
            chunk = ser.read(ser.in_waiting or 1)
            if not chunk:
                continue

            now = time.time()
            total_bytes += len(chunk)
            elapsed = now - start

            # Timestamp + separator if gap > 1 second
            if last_data_time and (now - last_data_time) > 1.0:
                print(f"{DIM}  --- {now - last_data_time:.1f}s gap ---{RESET}")

            last_data_time = now
            ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]

            # Raw hex
            hex_str = chunk.hex(" ")
            ascii_str = printable_ascii(chunk)
            print(f"{DIM}[{ts}]{RESET} {CYAN}+{len(chunk):>3}B{RESET}  hex: {hex_str}")
            print(f"{'':>17}ascii: {ascii_str}")

            # Accumulate and try to extract KISS frames
            buf.extend(chunk)

            while True:
                try:
                    s = buf.index(FEND)
                except ValueError:
                    # No FEND found -- show as non-KISS data if buffer is large
                    if len(buf) > 256:
                        print(
                            f"  {YELLOW}(non-KISS data, {len(buf)}B cleared){RESET}"
                        )
                        buf.clear()
                    break

                if s > 0:
                    pre = bytes(buf[:s])
                    print(
                        f"  {DIM}(pre-FEND data: {pre.hex(' ')} "
                        f'= "{printable_ascii(pre)}"){RESET}'
                    )
                    del buf[:s]

                # Skip leading FENDs
                pos = 0
                while pos < len(buf) and buf[pos] == FEND:
                    pos += 1
                if pos >= len(buf):
                    break

                try:
                    end = buf.index(FEND, pos)
                except ValueError:
                    break  # Incomplete frame, wait for more data

                raw = buf[pos:end]
                del buf[: end + 1]

                cmd_type = raw[0] if raw else None
                frame_count += 1

                print()
                print(
                    f"  {GREEN}{BOLD}*** KISS FRAME #{frame_count} "
                    f"({len(raw)}B, cmd=0x{cmd_type:02X}) ***{RESET}"
                )
                print(f"  {DIM}Raw: {raw.hex(' ')}{RESET}")

                if cmd_type == 0x00 and len(raw) > 1:
                    # Data frame -- try AX.25 decode
                    payload = kiss_destuff(bytes(raw[1:]))
                    print(f"  Payload ({len(payload)}B): {payload.hex(' ')}")
                    decoded = decode_ax25(payload)
                    if decoded:
                        print(f"  {GREEN}{BOLD}APRS: {decoded}{RESET}")
                    else:
                        print(
                            f"  {YELLOW}(payload not AX.25 or too short){RESET}"
                        )
                        print(f'  ASCII: "{printable_ascii(payload)}"')
                elif cmd_type is not None:
                    print(
                        f"  {YELLOW}KISS command 0x{cmd_type:02X} "
                        f"(not a data frame){RESET}"
                    )
                print()

    except KeyboardInterrupt:
        pass
    finally:
        ser.close()
        elapsed = time.time() - start
        print()
        print(f"{'=' * 60}")
        print(f"  Session:  {elapsed:.0f} seconds")
        print(f"  Received: {total_bytes} bytes, {frame_count} KISS frame(s)")
        print(f"  Closed:   {datetime.now().strftime('%H:%M:%S')}")
        print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
