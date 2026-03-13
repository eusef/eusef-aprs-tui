"""KISS transport over USB serial devices using pyserial."""
from __future__ import annotations

import asyncio
import logging
from functools import partial

import serial

from .base import ConnectionState, Transport

logger = logging.getLogger(__name__)

# KISS constants
FEND = 0xC0
FESC = 0xDB
TFEND = 0xDC
TFESC = 0xDD
KISS_DATA_CMD = 0x00

SUPPORTED_BAUD_RATES = [1200, 9600, 19200, 38400, 57600, 115200]


class KissSerialTransport(Transport):
    """KISS transport over a serial port.

    Uses pyserial for I/O with asyncio thread executor for non-blocking reads (ADR-3).

    Args:
        device: Serial device path (e.g., /dev/ttyUSB0)
        baudrate: Baud rate (default 9600)
        timeout: Read timeout in seconds (default 1.0)
    """

    def __init__(self, device: str, baudrate: int = 9600, timeout: float = 1.0) -> None:
        self._device = device
        self._baudrate = baudrate
        self._timeout = timeout
        self._serial: serial.Serial | None = None
        self._state = ConnectionState.DISCONNECTED
        self._buffer = bytearray()
        self._frame_queue: asyncio.Queue[bytes] = asyncio.Queue()

    async def connect(self) -> None:
        self._state = ConnectionState.CONNECTING
        loop = asyncio.get_event_loop()
        try:
            self._serial = await loop.run_in_executor(
                None,
                partial(serial.Serial, self._device, self._baudrate, timeout=self._timeout),
            )
            self._state = ConnectionState.CONNECTED
            self._buffer.clear()
            while not self._frame_queue.empty():
                self._frame_queue.get_nowait()
            logger.info("Connected to %s", self.display_name)
        except serial.SerialException as exc:
            self._state = ConnectionState.FAILED
            raise ConnectionError(f"Failed to open {self._device}: {exc}") from exc

    async def disconnect(self) -> None:
        if self._serial is not None:
            try:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, self._serial.close)
            except Exception:
                pass
        self._serial = None
        self._state = ConnectionState.DISCONNECTED

    async def read_frame(self) -> bytes:
        if self._serial is None:
            raise ConnectionError("Not connected")

        if not self._frame_queue.empty():
            return self._frame_queue.get_nowait()

        loop = asyncio.get_event_loop()
        while True:
            try:
                chunk = await loop.run_in_executor(None, self._read_chunk)
            except (serial.SerialException, OSError) as exc:
                self._state = ConnectionState.DISCONNECTED
                raise ConnectionError(f"Serial read error on {self._device}: {exc}") from exc

            if not chunk:
                # Timeout with no data - keep trying
                continue

            self._buffer.extend(chunk)
            self._extract_frames()

            if not self._frame_queue.empty():
                return self._frame_queue.get_nowait()

    def _read_chunk(self) -> bytes:
        """Blocking serial read - called via executor."""
        if self._serial is None or not self._serial.is_open:
            raise serial.SerialException("Port closed")
        return self._serial.read(self._serial.in_waiting or 1)

    async def write_frame(self, data: bytes) -> None:
        if self._serial is None or self._state != ConnectionState.CONNECTED:
            raise ConnectionError("Not connected")

        kiss_data = self._kiss_encode(data)
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(None, self._serial.write, kiss_data)
        except (serial.SerialException, OSError) as exc:
            self._state = ConnectionState.DISCONNECTED
            raise ConnectionError(f"Serial write error: {exc}") from exc

    @property
    def state(self) -> ConnectionState:
        return self._state

    @property
    def display_name(self) -> str:
        return f"Serial {self._device}@{self._baudrate}"

    # KISS framing methods (same as TCP transport)
    def _extract_frames(self) -> None:
        while True:
            try:
                start = self._buffer.index(FEND)
            except ValueError:
                self._buffer.clear()
                return
            if start > 0:
                del self._buffer[:start]
            pos = 0
            while pos < len(self._buffer) and self._buffer[pos] == FEND:
                pos += 1
            if pos >= len(self._buffer):
                return
            try:
                end = self._buffer.index(FEND, pos)
            except ValueError:
                return
            raw = self._buffer[pos:end]
            del self._buffer[:end + 1]
            if len(raw) < 1:
                continue
            if raw[0] != KISS_DATA_CMD:
                continue
            payload = self._kiss_destuff(bytes(raw[1:]))
            if payload:
                self._frame_queue.put_nowait(payload)

    @staticmethod
    def _kiss_destuff(data: bytes) -> bytes:
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

    @staticmethod
    def _kiss_encode(data: bytes) -> bytes:
        stuffed = bytearray()
        for b in data:
            if b == FEND:
                stuffed.extend([FESC, TFEND])
            elif b == FESC:
                stuffed.extend([FESC, TFESC])
            else:
                stuffed.append(b)
        return bytes([FEND, KISS_DATA_CMD]) + bytes(stuffed) + bytes([FEND])
