#!/usr/bin/env python3
"""Quick test: connect to APRS-IS and print raw packets."""
import socket

HOST = "rotate.aprs2.net"
PORT = 14580
CALLSIGN = "W7PDJ"
PASSCODE = "16017"

sock = socket.create_connection((HOST, PORT), timeout=10)
sock.settimeout(5)

# Read greeting
greeting = sock.recv(1024).decode().strip()
print(f"Server: {greeting}")

# Send login
login = f"user {CALLSIGN} pass {PASSCODE} vers aprs-tui 0.1 filter r/47.6/-122.3/200\r\n"
print(f"Login:  {login.strip()}")
sock.send(login.encode())

# Read login response
response = sock.recv(1024).decode().strip()
print(f"Server: {response}")
print()
print("Listening for packets (20 seconds)...")
print()

import time
start = time.time()
count = 0
while time.time() - start < 20:
    try:
        data = sock.recv(4096).decode("latin-1", errors="replace")
        for line in data.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            if line.startswith("#"):
                print(f"  [comment] {line}")
            else:
                count += 1
                print(f"  [{count}] {line[:100]}")
    except socket.timeout:
        pass

print(f"\nReceived {count} packets in 20 seconds")
sock.close()
