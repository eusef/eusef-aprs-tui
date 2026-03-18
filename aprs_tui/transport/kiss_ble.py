"""KISS transport over Bluetooth Low Energy (BLE).

Supports devices that expose KISS data via BLE GATT:
  - Mobilinkd TNC4
  - BTECH UV-PRO
  - VGC VR-N76 (same hardware as UV-PRO)

Uses the `bleak` library for cross-platform BLE support.

BLE Service UUIDs (shared across all supported devices):
  Service:  00000001-ba2a-46c9-ae49-01b0961f68bb
  TX (Device→App): 00000003-ba2a-46c9-ae49-01b0961f68bb  (notify)
  RX (App→Device): 00000002-ba2a-46c9-ae49-01b0961f68bb  (write)

Some devices (e.g., UV-PRO on macOS) require BLE bonding for write-with-response,
which macOS Core Bluetooth cannot initiate programmatically. For these devices,
KissBleHybridTransport uses BLE for RX and classic BT serial for TX.
"""
from __future__ import annotations

import asyncio
import contextlib
import logging
from functools import partial

from .base import ConnectionState, Transport

logger = logging.getLogger(__name__)

# BLE KISS UUIDs (shared by Mobilinkd TNC4, BTECH UV-PRO, VGC VR-N76)
KISS_SERVICE_UUID = "00000001-ba2a-46c9-ae49-01b0961f68bb"
KISS_TX_CHAR_UUID = "00000003-ba2a-46c9-ae49-01b0961f68bb"  # Device → App (notify)
KISS_RX_CHAR_UUID = "00000002-ba2a-46c9-ae49-01b0961f68bb"  # App → Device (write)

# KISS constants
FEND = 0xC0
FESC = 0xDB
TFEND = 0xDC
TFESC = 0xDD
KISS_DATA_CMD = 0x00


async def scan_for_tnc(timeout: float = 10.0) -> list[dict]:
    """Scan for BLE KISS TNC devices (Mobilinkd TNC4, BTECH UV-PRO, etc.).

    Matches by device name or by advertising the known KISS BLE service UUID.
    Returns list of dicts with 'name', 'address' keys.
    """
    from bleak import BleakScanner

    _KNOWN_NAMES = ("mobilinkd", "tnc", "uv-pro", "uvpro", "btech", "vr-n76", "vrn76", "vgc")  # noqa: N806

    devices = []
    discovered = await BleakScanner.discover(timeout=timeout, return_adv=True)
    for dev, adv in discovered.values():
        name = (dev.name or "") if hasattr(dev, "name") else ""
        address = dev.address if hasattr(dev, "address") else str(dev)
        name_lower = name.lower()

        # Match by name
        name_match = any(n in name_lower for n in _KNOWN_NAMES)

        # Match by KISS service UUID in advertisement
        svc_uuids = adv.service_uuids if adv and hasattr(adv, "service_uuids") else []
        uuid_match = KISS_SERVICE_UUID in svc_uuids

        if name_match or uuid_match:
            devices.append({"name": name or address, "address": address})
    return devices


class KissBleTransport(Transport):
    """KISS transport over BLE (Mobilinkd TNC4, BTECH UV-PRO, VGC VR-N76).

    Connects via BLE GATT, subscribes to KISS TX notifications,
    and writes KISS frames to the RX characteristic.

    Args:
        address: BLE device address/UUID (e.g., "DA78B460-FC42-AF4C-975D-0505B8BDE531")
                 or device name (e.g., "UV-PRO", "TNC4 Mobilinkd")
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

        # Clean up any previous connection first
        await self._cleanup()

        max_attempts = 3
        last_error = None

        for attempt in range(1, max_attempts + 1):
            try:
                addr = self._address
                logger.info("BLE connecting to %s (attempt %d/%d)", addr, attempt, max_attempts)

                # Create a fresh client each attempt
                self._client = BleakClient(
                    addr,
                    disconnected_callback=self._on_disconnect,
                )
                await self._client.connect(timeout=15.0)

                if not self._client.is_connected:
                    raise ConnectionError("BLE connection failed")

                # Small delay to let BLE stabilize
                await asyncio.sleep(0.5)

                mtu = getattr(self._client, "mtu_size", 23)
                logger.info("BLE MTU: %d (write chunk size: %d)", mtu, max(mtu - 3, 20))

                # Trigger BLE encryption/pairing by attempting an encrypted read.
                # Some devices (e.g., BTECH UV-PRO) require bonding for TX writes.
                # On macOS Core Bluetooth, accessing an encrypted characteristic
                # prompts the OS to negotiate encryption automatically.
                _ENCRYPTED_CHAR = "00001103-d102-11e1-9b23-00025b00a5a5"  # noqa: N806
                try:
                    await self._client.read_gatt_char(_ENCRYPTED_CHAR)
                    logger.info("BLE encryption negotiated via encrypted char read")
                except Exception as enc_err:
                    logger.debug(
                        "BLE encrypted char read (expected to fail or trigger pairing): %s",
                        enc_err,
                    )

                await asyncio.sleep(0.5)

                # Subscribe to KISS TX notifications (TNC → App)
                await self._client.start_notify(
                    KISS_TX_CHAR_UUID, self._on_ble_notify
                )

                self._state = ConnectionState.CONNECTED
                self._buffer.clear()
                while not self._frame_queue.empty():
                    self._frame_queue.get_nowait()

                logger.info("BLE connected to %s", self.display_name)
                return  # Success

            except Exception as exc:
                last_error = exc
                logger.warning("BLE connect attempt %d failed: %s", attempt, exc)
                await self._cleanup()
                if attempt < max_attempts:
                    await asyncio.sleep(2.0)  # Wait before retry

        self._state = ConnectionState.FAILED
        raise ConnectionError(f"BLE connect failed after {max_attempts} attempts: {last_error}")

    def _on_disconnect(self, client) -> None:
        """Called by bleak when BLE connection drops."""
        logger.warning("BLE disconnected (callback)")
        self._state = ConnectionState.DISCONNECTED

    async def _cleanup(self) -> None:
        """Clean up any existing BLE connection."""
        if self._client:
            try:
                if self._client.is_connected:
                    with contextlib.suppress(Exception):
                        await self._client.stop_notify(KISS_TX_CHAR_UUID)
                    with contextlib.suppress(Exception):
                        await asyncio.wait_for(self._client.disconnect(), timeout=3.0)
            except Exception:
                pass
            self._client = None

    async def disconnect(self) -> None:
        await self._cleanup()
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

        # Use negotiated MTU minus 3 bytes for ATT overhead (default 20 if unknown)
        mtu = getattr(self._client, "mtu_size", 23)
        chunk_size = max(mtu - 3, 20)
        logger.debug("BLE TX: %d bytes (KISS), MTU=%d, chunk=%d", len(kiss_data), mtu, chunk_size)

        for i in range(0, len(kiss_data), chunk_size):
            chunk = kiss_data[i:i + chunk_size]
            logger.debug("BLE TX chunk %d: %s", i // chunk_size, chunk.hex())
            # Try write-with-response first (works if BLE encryption was
            # negotiated during connect). Fall back to write-without-response
            # for devices that don't require bonding.
            try:
                await self._client.write_gatt_char(KISS_RX_CHAR_UUID, chunk, response=True)
            except Exception:
                await self._client.write_gatt_char(KISS_RX_CHAR_UUID, chunk, response=False)
            if i + chunk_size < len(kiss_data):
                await asyncio.sleep(0.05)  # Small delay between chunks

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


class KissBleHybridTransport(Transport):
    """Hybrid BLE+Serial transport for devices that require bonding for BLE writes.

    Uses BLE GATT for RX (notifications) and classic Bluetooth serial for TX.
    This works around macOS Core Bluetooth's inability to programmatically
    initiate BLE bonding, which some devices (BTECH UV-PRO, VGC VR-N76) require
    for write-with-response.

    Args:
        ble_address: BLE device address/UUID for RX
        serial_device: Classic BT serial device path for TX (e.g., /dev/cu.UV-PRO)
        baudrate: Baud rate for serial TX (default 9600)
    """

    def __init__(self, ble_address: str, serial_device: str, baudrate: int = 9600) -> None:
        self._ble_address = ble_address
        self._serial_device = serial_device
        self._baudrate = baudrate
        # BLE side (RX)
        self._ble = KissBleTransport(address=ble_address)
        # Serial side (TX) - lazy init
        self._serial = None  # serial.Serial instance
        self._state = ConnectionState.DISCONNECTED

    async def connect(self) -> None:
        import serial

        self._state = ConnectionState.CONNECTING

        # Connect BLE for RX
        await self._ble.connect()

        # Open classic BT serial for TX
        loop = asyncio.get_event_loop()
        try:
            self._serial = await loop.run_in_executor(
                None,
                partial(serial.Serial, self._serial_device, self._baudrate, timeout=5.0),
            )
            logger.info("Hybrid TX serial opened: %s@%d", self._serial_device, self._baudrate)
        except Exception as exc:
            logger.warning("Hybrid TX serial failed (TX disabled): %s", exc)
            # Continue with RX-only -- don't fail the whole connection
            self._serial = None

        self._state = ConnectionState.CONNECTED
        logger.info("Hybrid BLE+Serial connected (RX=%s, TX=%s)",
                     self._ble_address, self._serial_device if self._serial else "DISABLED")

    async def disconnect(self) -> None:
        await self._ble.disconnect()
        if self._serial:
            loop = asyncio.get_event_loop()
            with contextlib.suppress(Exception):
                await loop.run_in_executor(None, self._serial.close)
            self._serial = None
        self._state = ConnectionState.DISCONNECTED

    async def read_frame(self) -> bytes:
        """Read from BLE (notifications)."""
        return await self._ble.read_frame()

    async def write_frame(self, data: bytes) -> None:
        """Write via classic BT serial."""
        if self._serial is None or not self._serial.is_open:
            raise ConnectionError("TX serial not connected")

        kiss_data = KissBleTransport._kiss_encode(data)
        logger.debug("Hybrid TX: %d bytes via serial", len(kiss_data))

        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(None, self._serial.write, kiss_data)
        except Exception as exc:
            raise ConnectionError(f"Serial TX error: {exc}") from exc

    @property
    def state(self) -> ConnectionState:
        # If BLE disconnects, we're disconnected
        if (
            self._ble.state == ConnectionState.DISCONNECTED
            and self._state == ConnectionState.CONNECTED
        ):
            self._state = ConnectionState.DISCONNECTED
        return self._state

    @property
    def display_name(self) -> str:
        tx_status = self._serial_device if self._serial else "TX disabled"
        return f"BLE+Serial {self._ble_address[:8]}... ({tx_status})"
