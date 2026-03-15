"""KISS transport over Bluetooth Low Energy (BLE) for Mobilinkd TNC4.

The TNC4 uses BLE GATT for KISS data instead of classic BT SPP serial.
Uses the `bleak` library for cross-platform BLE support.

BLE Service UUIDs (Mobilinkd TNC4):
  Service:  00000001-ba2a-46c9-ae49-01b0961f68bb
  TX (TNC→App): 00000002-ba2a-46c9-ae49-01b0961f68bb  (notify)
  RX (App→TNC): 00000003-ba2a-46c9-ae49-01b0961f68bb  (write)
"""
from __future__ import annotations

import asyncio
import logging

from .base import ConnectionState, Transport

logger = logging.getLogger(__name__)

# Mobilinkd TNC4 BLE UUIDs
KISS_SERVICE_UUID = "00000001-ba2a-46c9-ae49-01b0961f68bb"
KISS_TX_CHAR_UUID = "00000003-ba2a-46c9-ae49-01b0961f68bb"  # TNC → App (notify)
KISS_RX_CHAR_UUID = "00000002-ba2a-46c9-ae49-01b0961f68bb"  # App → TNC (write)

# KISS constants
FEND = 0xC0
FESC = 0xDB
TFEND = 0xDC
TFESC = 0xDD
KISS_DATA_CMD = 0x00


async def scan_for_tnc(timeout: float = 10.0) -> list[dict]:
    """Scan for Mobilinkd TNC BLE devices.

    Returns list of dicts with 'name', 'address' keys.
    """
    from bleak import BleakScanner

    devices = []
    discovered = await BleakScanner.discover(timeout=timeout)
    for d in discovered:
        name = d.name or ""
        if "mobilinkd" in name.lower() or "tnc" in name.lower():
            devices.append({"name": name, "address": d.address})
    return devices


class KissBleTransport(Transport):
    """KISS transport over BLE for Mobilinkd TNC4.

    Connects to the TNC via BLE GATT, subscribes to KISS TX notifications,
    and writes KISS frames to the RX characteristic.

    Args:
        address: BLE device address (e.g., "34:81:F4:F6:0D:9B")
                 or device name (e.g., "TNC4 Mobilinkd")
    """

    def __init__(self, address: str) -> None:
        self._address = address
        self._client = None
        self._state = ConnectionState.DISCONNECTED
        self._buffer = bytearray()
        self._frame_queue: asyncio.Queue[bytes] = asyncio.Queue()

    async def connect(self) -> None:
        from bleak import BleakClient

        self._state = ConnectionState.CONNECTING
        try:
            # Use address directly - on macOS this is a CoreBluetooth UUID
            # (e.g., "F8A81515-6061-CA30-2B45-E33A75516D3E")
            # On Linux this is a MAC address (e.g., "34:81:F4:F6:0D:9B")
            addr = self._address
            logger.info("BLE connecting to: %s", addr)

            self._client = BleakClient(addr)
            await self._client.connect(timeout=15.0)

            if not self._client.is_connected:
                raise ConnectionError("BLE connection failed")

            # Subscribe to KISS TX notifications (TNC → App)
            await self._client.start_notify(
                KISS_TX_CHAR_UUID, self._on_ble_notify
            )

            self._state = ConnectionState.CONNECTED
            self._buffer.clear()
            while not self._frame_queue.empty():
                self._frame_queue.get_nowait()

            logger.info("BLE connected to %s", self.display_name)

        except Exception as exc:
            self._state = ConnectionState.FAILED
            raise ConnectionError(f"BLE connect failed: {exc}") from exc

    async def disconnect(self) -> None:
        if self._client and self._client.is_connected:
            try:
                await self._client.stop_notify(KISS_TX_CHAR_UUID)
            except Exception:
                pass
            try:
                await self._client.disconnect()
            except Exception:
                pass
        self._client = None
        self._state = ConnectionState.DISCONNECTED
        logger.info("BLE disconnected")

    async def read_frame(self) -> bytes:
        """Read one deframed AX.25 payload from the KISS BLE stream."""
        if self._client is None or not self._client.is_connected:
            raise ConnectionError("BLE not connected")

        # Wait for a complete frame
        while True:
            if not self._frame_queue.empty():
                return self._frame_queue.get_nowait()

            # Check if still connected
            if self._client is None or not self._client.is_connected:
                self._state = ConnectionState.DISCONNECTED
                raise ConnectionError("BLE connection lost")

            # Wait a bit for notifications to arrive
            await asyncio.sleep(0.05)

    async def write_frame(self, data: bytes) -> None:
        """Write a KISS frame to the TNC via BLE."""
        if self._client is None or not self._client.is_connected:
            raise ConnectionError("BLE not connected")

        kiss_data = self._kiss_encode(data)

        # BLE has a max write size (~20 bytes default, can be negotiated higher)
        # Send in chunks if needed
        chunk_size = 20
        for i in range(0, len(kiss_data), chunk_size):
            chunk = kiss_data[i:i + chunk_size]
            await self._client.write_gatt_char(KISS_RX_CHAR_UUID, chunk)

    @property
    def state(self) -> ConnectionState:
        return self._state

    @property
    def display_name(self) -> str:
        return f"BLE KISS {self._address}"

    # ------------------------------------------------------------------
    # BLE notification handler
    # ------------------------------------------------------------------

    def _on_ble_notify(self, sender, data: bytearray) -> None:
        """Called by bleak when BLE notification arrives from TNC."""
        self._buffer.extend(data)
        self._extract_frames()

    # ------------------------------------------------------------------
    # KISS framing
    # ------------------------------------------------------------------

    def _extract_frames(self) -> None:
        """Parse complete KISS frames from the internal buffer."""
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
                logger.debug("Ignoring BLE KISS cmd 0x%02X", raw[0])
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

    @staticmethod
    def _looks_like_mac(address: str) -> bool:
        """Check if address looks like a MAC address."""
        parts = address.replace("-", ":").split(":")
        return len(parts) == 6 and all(len(p) == 2 for p in parts)
