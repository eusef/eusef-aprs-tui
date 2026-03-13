"""KISS-over-TCP transport implementation.

Connects to a KISS TNC via TCP, handles KISS framing/deframing, and
delivers raw AX.25 payloads to the caller.
"""
from __future__ import annotations

import asyncio
import logging

from .base import ConnectionState, Transport

logger = logging.getLogger(__name__)

# KISS protocol constants
FEND = 0xC0
FESC = 0xDB
TFEND = 0xDC
TFESC = 0xDD
KISS_DATA_CMD = 0x00

# Connection timeout in seconds
CONNECT_TIMEOUT = 10.0


class KissTcpTransport(Transport):
    """KISS transport over a TCP socket.

    Uses ``asyncio.open_connection()`` to connect to a KISS TNC.
    Incoming TCP data is buffered and KISS-deframed; each call to
    ``read_frame()`` returns exactly one AX.25 payload.

    Parameters
    ----------
    host:
        Hostname or IP address of the KISS TNC.
    port:
        TCP port of the KISS TNC.
    """

    def __init__(self, host: str, port: int) -> None:
        self._host = host
        self._port = port
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._state = ConnectionState.DISCONNECTED
        self._buffer = bytearray()
        self._frame_queue: asyncio.Queue[bytes] = asyncio.Queue()

    # ------------------------------------------------------------------
    # Transport ABC
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        """Connect to the KISS TNC via TCP."""
        self._state = ConnectionState.CONNECTING
        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(self._host, self._port),
                timeout=CONNECT_TIMEOUT,
            )
            self._state = ConnectionState.CONNECTED
            self._buffer.clear()
            # Drain any leftover frames from a previous session
            while not self._frame_queue.empty():
                self._frame_queue.get_nowait()
            logger.info("Connected to %s", self.display_name)
        except (ConnectionRefusedError, OSError) as exc:
            self._state = ConnectionState.FAILED
            raise ConnectionError(
                f"Failed to connect to {self.display_name}: {exc}"
            ) from exc
        except TimeoutError as exc:
            self._state = ConnectionState.FAILED
            raise ConnectionError(
                f"Connection to {self.display_name} timed out"
            ) from exc

    async def disconnect(self) -> None:
        """Close the TCP connection."""
        if self._writer is not None:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except Exception:  # noqa: BLE001
                pass
        self._reader = None
        self._writer = None
        self._state = ConnectionState.DISCONNECTED
        logger.info("Disconnected from %s", self.display_name)

    async def read_frame(self) -> bytes:
        """Read one deframed AX.25 payload from the KISS stream.

        Blocks until a complete frame is available. Raises
        ``ConnectionError`` if the connection is lost.
        """
        if self._reader is None:
            raise ConnectionError("Not connected")

        # Return buffered frames first
        if not self._frame_queue.empty():
            return self._frame_queue.get_nowait()

        while True:
            try:
                chunk = await self._reader.read(4096)
            except (ConnectionResetError, BrokenPipeError, OSError) as exc:
                self._state = ConnectionState.DISCONNECTED
                raise ConnectionError(
                    f"Connection lost to {self.display_name}: {exc}"
                ) from exc

            if not chunk:
                # EOF - remote closed the connection
                self._state = ConnectionState.DISCONNECTED
                raise ConnectionError(
                    f"Connection closed by {self.display_name}"
                )

            self._buffer.extend(chunk)
            self._extract_frames()

            if not self._frame_queue.empty():
                return self._frame_queue.get_nowait()

    async def write_frame(self, data: bytes) -> None:
        """Write an AX.25 frame wrapped in KISS framing.

        Parameters
        ----------
        data:
            Raw AX.25 payload bytes to send.
        """
        if self._writer is None or self._state != ConnectionState.CONNECTED:
            raise ConnectionError("Not connected")

        kiss_frame = self._kiss_encode(data)
        try:
            self._writer.write(kiss_frame)
            await self._writer.drain()
        except (ConnectionResetError, BrokenPipeError, OSError) as exc:
            self._state = ConnectionState.DISCONNECTED
            raise ConnectionError(
                f"Failed to send to {self.display_name}: {exc}"
            ) from exc

    @property
    def state(self) -> ConnectionState:
        """Current connection state."""
        return self._state

    @property
    def display_name(self) -> str:
        """Human-readable transport identifier."""
        return f"KISS TCP {self._host}:{self._port}"

    # ------------------------------------------------------------------
    # KISS framing internals
    # ------------------------------------------------------------------

    def _extract_frames(self) -> None:
        """Parse complete KISS frames from the internal buffer.

        Handles FEND delimiters and byte-stuffing (FESC sequences).
        Extracted AX.25 payloads are placed on ``_frame_queue``.
        """
        while True:
            # Find start FEND
            try:
                start = self._buffer.index(FEND)
            except ValueError:
                # No FEND at all - discard noise before any frame
                self._buffer.clear()
                return

            # Discard bytes before the first FEND
            if start > 0:
                del self._buffer[:start]

            # Skip consecutive FENDs to find start of frame data
            pos = 0
            while pos < len(self._buffer) and self._buffer[pos] == FEND:
                pos += 1

            if pos >= len(self._buffer):
                # Only FENDs in buffer, no data yet
                return

            # Find end FEND after the data
            try:
                end = self._buffer.index(FEND, pos)
            except ValueError:
                # Incomplete frame - wait for more data
                return

            # Extract the raw frame content (between FENDs)
            raw = self._buffer[pos:end]

            # Remove the consumed bytes (including the closing FEND)
            del self._buffer[: end + 1]

            if len(raw) < 1:
                # Empty frame, skip
                continue

            # First byte is the command/port byte; 0x00 = data frame
            cmd_byte = raw[0]
            if cmd_byte != KISS_DATA_CMD:
                logger.debug("Ignoring KISS frame with command byte 0x%02X", cmd_byte)
                continue

            # De-stuff the payload
            payload = self._kiss_destuff(bytes(raw[1:]))
            if payload:
                self._frame_queue.put_nowait(payload)

    @staticmethod
    def _kiss_destuff(data: bytes) -> bytes:
        """Remove KISS byte-stuffing from a frame payload.

        FESC TFEND -> FEND (0xC0)
        FESC TFESC -> FESC (0xDB)
        """
        result = bytearray()
        i = 0
        while i < len(data):
            if data[i] == FESC:
                if i + 1 < len(data):
                    next_byte = data[i + 1]
                    if next_byte == TFEND:
                        result.append(FEND)
                    elif next_byte == TFESC:
                        result.append(FESC)
                    else:
                        # Invalid escape sequence - pass through
                        result.append(FESC)
                        result.append(next_byte)
                    i += 2
                else:
                    # FESC at end of data - pass through
                    result.append(FESC)
                    i += 1
            else:
                result.append(data[i])
                i += 1
        return bytes(result)

    @staticmethod
    def _kiss_encode(data: bytes) -> bytes:
        """Wrap an AX.25 payload in KISS framing.

        Returns FEND + CMD(0x00) + byte-stuffed data + FEND.
        """
        stuffed = bytearray()
        for b in data:
            if b == FEND:
                stuffed.extend([FESC, TFEND])
            elif b == FESC:
                stuffed.extend([FESC, TFESC])
            else:
                stuffed.append(b)
        return bytes([FEND, KISS_DATA_CMD]) + bytes(stuffed) + bytes([FEND])
