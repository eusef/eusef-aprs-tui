"""Shared test fixtures for the APRS TUI test suite.

Provides reusable fixtures for:
- Mock transports (in-memory byte streams for unit tests)
- Local TCP servers simulating KISS and APRS-IS protocols
- Sample APRS packets of every supported type
- Pre-framed KISS and AX.25 binary payloads
- Config factory for generating valid AppConfig instances
- Temporary config file creation

Used by: unit/, integration/, acceptance/
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Sample APRS packets - real-world examples covering every packet type
# the decoder must handle.  Keys match info_type values in APRSPacket.
# ---------------------------------------------------------------------------

# FEND byte used as KISS frame delimiter
FEND = 0xC0
# KISS data-frame command byte
KISS_DATA_CMD = 0x00
# FESC / TFEND / TFESC for byte-stuffing
FESC = 0xDB
TFEND = 0xDC
TFESC = 0xDD


@pytest.fixture()
def sample_packets() -> dict[str, str]:
    """Dict of real APRS packet strings keyed by packet type.

    These are text-format lines as aprslib.parse() expects them - i.e., the
    format produced *after* AX.25 decoding for KISS transports, or read
    directly from an APRS-IS TCP stream.

    Types: position, mic-e, message, weather, object, status, telemetry.
    """
    return {
        # Uncompressed position with symbol and comment
        "position": "W3ADO-1>APRS,WIDE1-1,WIDE2-1:!4903.50N/07201.75W-PHG2360/Test station",
        # Compressed position
        "position_compressed": "W3ADO-1>APRS:!/5L!!<*e7>7P[",
        # Mic-E encoded position (Kenwood TH-D74 style)
        "mic-e": "KJ4ERJ-9>T2SP0W:`c5Il!<>/`\"4V}_%",
        # APRS message with message number
        "message": "W3ADO-1>APRS::N0CALL   :Hello from APRS TUI{001",
        # APRS message ack
        "message_ack": "N0CALL>APRS::W3ADO-1  :ack001",
        # APRS message reject
        "message_rej": "N0CALL>APRS::W3ADO-1  :rej001",
        # Weather report (positionless)
        "weather": "FW0727>APRS,TCPIP*:_10090556c220s004g005t077r000p000P000h50b09900",
        # Object
        "object": "W3ADO-1>APRS:;LEADER   *092345z4903.50N/07201.75W-Test Object",
        # Status report
        "status": "W3ADO-1>APRS:>Monitoring 144.390MHz",
        # Telemetry
        "telemetry": "W3ADO-1>APRS:T#005,199,000,255,073,123,01100001",
        # Unparseable / malformed packet (should trigger ParseError)
        "malformed": "NOCALL>APRS:!!!THIS_IS_NOT_VALID!!!",
    }


@pytest.fixture()
def sample_ax25_frames() -> dict[str, bytes]:
    """Raw AX.25 binary frames corresponding to sample packets.

    Each value is the binary payload that would appear *inside* a KISS frame
    (after KISS deframing, before AX.25 decoding).

    Structure per frame:
      [Dest addr 7B][Src addr 7B][Digi addrs 0-8x7B][Ctrl 0x03][PID 0xF0][Info]

    Address encoding: each ASCII char left-shifted by 1 bit, SSID in byte 6.
    """
    def _encode_address(callsign: str, ssid: int = 0, last: bool = False) -> bytes:
        """Encode a single AX.25 address field (7 bytes)."""
        call = callsign.ljust(6)[:6]
        encoded = bytes([ord(c) << 1 for c in call])
        ssid_byte = 0b01100000 | ((ssid & 0x0F) << 1)
        if last:
            ssid_byte |= 0x01  # end-of-address marker
        return encoded + bytes([ssid_byte])

    # Build a simple position packet: W3ADO-1>APRS:!4903.50N/07201.75W-
    info_field = b"!4903.50N/07201.75W-"
    dest_raw = bytearray(_encode_address("APRS", ssid=0))
    dest_raw[6] |= 0x80  # Set command bit on destination (UI command frame)
    dest = bytes(dest_raw)
    src = _encode_address("W3ADO", ssid=1, last=True)
    control = bytes([0x03])
    pid = bytes([0xF0])

    position_frame = dest + src + control + pid + info_field

    # Build a message packet: W3ADO-1>APRS::N0CALL   :Hello{001
    msg_info = b":N0CALL   :Hello{001"
    msg_src = _encode_address("W3ADO", ssid=1, last=True)
    message_frame = dest + msg_src + control + pid + msg_info

    return {
        "position": position_frame,
        "message": message_frame,
    }


@pytest.fixture()
def sample_kiss_frames(sample_ax25_frames: dict[str, bytes]) -> dict[str, bytes]:
    """KISS-framed versions of the sample AX.25 frames.

    Each value is a complete KISS frame:
      FEND + CMD_BYTE + (byte-stuffed AX.25 payload) + FEND

    Byte stuffing rules:
      0xC0 in payload -> 0xDB 0xDC
      0xDB in payload -> 0xDB 0xDD
    """
    def _kiss_frame(ax25_payload: bytes) -> bytes:
        stuffed = bytearray()
        for b in ax25_payload:
            if b == FEND:
                stuffed.extend([FESC, TFEND])
            elif b == FESC:
                stuffed.extend([FESC, TFESC])
            else:
                stuffed.append(b)
        return bytes([FEND, KISS_DATA_CMD]) + bytes(stuffed) + bytes([FEND])

    return {key: _kiss_frame(val) for key, val in sample_ax25_frames.items()}


# ---------------------------------------------------------------------------
# Mock transport - in-memory byte stream for unit tests
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_transport():
    """In-memory transport that yields bytes without real I/O.

    Returns a factory that produces (reader, writer) pairs. The writer is
    used by test code to inject raw bytes; the reader simulates what a
    real transport's read_frame() would return.

    Usage in tests:
        rx_queue, tx_queue = mock_transport()
        await rx_queue.put(kiss_frame_bytes)  # simulate incoming data
        frame = await tx_queue.get()          # capture outgoing data
    """
    def _factory():
        rx_queue: asyncio.Queue[bytes] = asyncio.Queue()
        tx_queue: asyncio.Queue[bytes] = asyncio.Queue()
        return rx_queue, tx_queue

    return _factory


# ---------------------------------------------------------------------------
# Local TCP server fixtures for integration tests
# ---------------------------------------------------------------------------

@pytest.fixture()
async def kiss_tcp_server():
    """Local TCP server fixture that speaks KISS protocol.

    Starts a TCP server on a random available port. Accepts one client
    connection. Provides methods to send KISS-framed data to the client
    and read data the client sends.

    Yields a dict with:
        - host: str
        - port: int
        - send(data: bytes): coroutine to send raw bytes to client
        - receive() -> bytes: coroutine to read bytes from client
        - close(): coroutine to shut down the server

    The server automatically cleans up on fixture teardown.
    """
    clients: list[tuple[asyncio.StreamReader, asyncio.StreamWriter]] = []

    async def _handle_client(reader, writer):
        clients.append((reader, writer))

    server = await asyncio.start_server(_handle_client, "127.0.0.1", 0)
    addr = server.sockets[0].getsockname()

    async def _send(data: bytes):
        # Wait for a client to connect, then send
        while not clients:
            await asyncio.sleep(0.01)
        _, writer = clients[-1]
        writer.write(data)
        await writer.drain()

    async def _receive(nbytes: int = 4096) -> bytes:
        while not clients:
            await asyncio.sleep(0.01)
        reader, _ = clients[-1]
        return await reader.read(nbytes)

    async def _close():
        for _, writer in clients:
            writer.close()
        server.close()
        await server.wait_closed()

    yield {
        "host": addr[0],
        "port": addr[1],
        "send": _send,
        "receive": _receive,
        "close": _close,
    }

    await _close()


@pytest.fixture()
async def aprs_is_server():
    """Local TCP server fixture that speaks APRS-IS protocol.

    Simulates an APRS-IS server: sends a greeting banner on connect,
    expects a login line, responds with a login ack, and then sends
    APRS packet lines.

    Yields a dict with:
        - host: str
        - port: int
        - send_packet(line: str): coroutine to send an APRS-IS line
        - get_login() -> str: coroutine to read the login line from client
        - close(): coroutine to shut down the server

    The server automatically cleans up on fixture teardown.
    """
    clients: list[tuple[asyncio.StreamReader, asyncio.StreamWriter]] = []
    login_received: asyncio.Queue[str] = asyncio.Queue()

    async def _handle_client(reader, writer):
        clients.append((reader, writer))
        # Send APRS-IS greeting banner
        writer.write(b"# javAPRSSrvr 4.2.0b05 13 Mar 2026\r\n")
        await writer.drain()
        # Read login line
        try:
            line = await reader.readline()
            await login_received.put(line.decode().strip())
            # Send login ack
            writer.write(b"# logresp CALL verified, server T2TEST\r\n")
            await writer.drain()
        except Exception:
            pass

    server = await asyncio.start_server(_handle_client, "127.0.0.1", 0)
    addr = server.sockets[0].getsockname()

    async def _send_packet(line: str):
        while not clients:
            await asyncio.sleep(0.01)
        _, writer = clients[-1]
        writer.write(f"{line}\r\n".encode())
        await writer.drain()

    async def _get_login() -> str:
        return await asyncio.wait_for(login_received.get(), timeout=5.0)

    async def _close():
        for _, writer in clients:
            writer.close()
        server.close()
        await server.wait_closed()

    yield {
        "host": addr[0],
        "port": addr[1],
        "send_packet": _send_packet,
        "get_login": _get_login,
        "close": _close,
    }

    await _close()


# ---------------------------------------------------------------------------
# Config fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def config_factory():
    """Factory function to generate valid AppConfig-compatible dicts with overrides.

    Returns a callable that produces a config dict matching the Pydantic
    AppConfig model structure.  Pass keyword arguments to override any
    top-level or nested field.

    Example:
        cfg = config_factory(callsign="N0CALL-5", server_host="10.0.0.1")
    """
    _defaults: dict[str, Any] = {
        "station": {
            "callsign": "N0CALL",
            "ssid": 0,
            "symbol_table": "/",
            "symbol_code": "-",
        },
        "server": {
            "protocol": "kiss-tcp",
            "host": "127.0.0.1",
            "port": 8001,
        },
        "beacon": {
            "enabled": False,
            "interval": 600,
            "latitude": 49.0583,
            "longitude": -72.0292,
            "comment": "APRS TUI",
        },
        "aprs_is": {
            "enabled": False,
            "host": "rotate.aprs2.net",
            "port": 14580,
            "filter": "r/49.05/-72.03/100",
            "passcode": -1,
        },
        "connection": {
            "reconnect_interval": 10,
            "max_reconnect_attempts": 0,
            "health_timeout": 60,
        },
    }

    def _build(**overrides: Any) -> dict[str, Any]:
        import copy
        cfg = copy.deepcopy(_defaults)
        for key, value in overrides.items():
            if isinstance(value, dict) and key in cfg:
                cfg[key].update(value)
            else:
                # Allow flat overrides like callsign="X" to update station.callsign
                for section in cfg.values():
                    if isinstance(section, dict) and key in section:
                        section[key] = value
                        break
                else:
                    cfg[key] = value
        return cfg

    return _build


@pytest.fixture()
def tmp_config_file(config_factory, tmp_path: Path):
    """Writes a temporary config.toml and returns its path.

    Returns a callable: pass keyword overrides to config_factory,
    and the resulting config dict is written as TOML to a temp file.

    Example:
        path = tmp_config_file(callsign="W3ADO-1")
        # path is a Path pointing to a valid config.toml in tmp_path
    """
    def _write(**overrides: Any) -> Path:
        cfg = config_factory(**overrides)
        config_path = tmp_path / "config.toml"
        # Write a minimal TOML representation
        lines = []
        for section, values in cfg.items():
            if isinstance(values, dict):
                lines.append(f"[{section}]")
                for k, v in values.items():
                    if isinstance(v, str):
                        lines.append(f'{k} = "{v}"')
                    elif isinstance(v, bool):
                        lines.append(f"{k} = {'true' if v else 'false'}")
                    elif isinstance(v, (int, float)):
                        lines.append(f"{k} = {v}")
                    else:
                        lines.append(f'{k} = "{v}"')
                lines.append("")
        config_path.write_text("\n".join(lines))
        return config_path

    return _write
