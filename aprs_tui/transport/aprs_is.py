"""Lightweight async APRS-IS client transport (ADR-8)."""
from __future__ import annotations

import asyncio
import logging

from .base import ConnectionState, Transport

logger = logging.getLogger(__name__)


class AprsIsTransport(Transport):
    """APRS-IS transport using native asyncio TCP.

    Protocol: text line-oriented. Login, then read/write APRS packet lines.
    Lines starting with '#' are server comments (skipped).

    Args:
        host: APRS-IS server hostname
        port: APRS-IS port (default 14580)
        callsign: Login callsign
        passcode: APRS-IS passcode (-1 = receive only)
        filter_str: Server-side filter (e.g., "r/45.4/-122.6/100")
    """

    def __init__(
        self,
        host: str,
        port: int = 14580,
        callsign: str = "N0CALL",
        passcode: int = -1,
        filter_str: str = "",
    ) -> None:
        self._host = host
        self._port = port
        self._callsign = callsign
        self._passcode = passcode
        self._filter = filter_str
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._state = ConnectionState.DISCONNECTED

    async def connect(self) -> None:
        self._state = ConnectionState.CONNECTING
        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(self._host, self._port), timeout=10.0
            )
            # Read server greeting (# comment line)
            greeting = await asyncio.wait_for(self._reader.readline(), timeout=5.0)
            logger.debug("APRS-IS greeting: %s", greeting.decode().strip())
            # Send login
            login = f"user {self._callsign} pass {self._passcode} vers aprs-tui 0.1"
            if self._filter:
                login += f" filter {self._filter}"
            self._writer.write(f"{login}\r\n".encode())
            await self._writer.drain()
            # Read login ack
            ack = await asyncio.wait_for(self._reader.readline(), timeout=5.0)
            logger.debug("APRS-IS login ack: %s", ack.decode().strip())
            self._state = ConnectionState.CONNECTED
        except (ConnectionRefusedError, OSError, TimeoutError) as exc:
            self._state = ConnectionState.FAILED
            raise ConnectionError(f"APRS-IS connect failed: {exc}") from exc

    async def disconnect(self) -> None:
        if self._writer:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except Exception:
                pass
        self._reader = None
        self._writer = None
        self._state = ConnectionState.DISCONNECTED

    async def read_frame(self) -> bytes:
        """Read one APRS packet line (skipping # comments). Returns line as bytes."""
        if self._reader is None:
            raise ConnectionError("Not connected")
        while True:
            try:
                line = await self._reader.readline()
            except (ConnectionResetError, BrokenPipeError, OSError) as exc:
                self._state = ConnectionState.DISCONNECTED
                raise ConnectionError(f"APRS-IS read error: {exc}") from exc
            if not line:
                self._state = ConnectionState.DISCONNECTED
                raise ConnectionError("APRS-IS connection closed")
            decoded = line.decode("latin-1", errors="replace").strip()
            if not decoded:
                continue
            if decoded.startswith("#"):
                continue  # Skip server comments
            return decoded.encode("latin-1")

    async def write_frame(self, data: bytes) -> None:
        """Send an APRS packet line to APRS-IS. Blocked in read-only mode."""
        if self._writer is None or self._state != ConnectionState.CONNECTED:
            raise ConnectionError("Not connected")
        if self._passcode == -1:
            raise PermissionError("Cannot transmit in read-only mode (passcode=-1)")
        line = data.decode("latin-1", errors="replace").strip()
        self._writer.write(f"{line}\r\n".encode())
        await self._writer.drain()

    @property
    def state(self) -> ConnectionState:
        return self._state

    @property
    def display_name(self) -> str:
        mode = "RX only" if self._passcode == -1 else "TX/RX"
        return f"APRS-IS {self._host}:{self._port} ({mode})"

    @property
    def is_read_only(self) -> bool:
        return self._passcode == -1
