"""Beacon timer for periodic position transmission."""
from __future__ import annotations

import asyncio
import logging
from typing import Callable, Awaitable

from aprs_tui.protocol.encoder import encode_position, build_packet
from aprs_tui.protocol.ax25 import ax25_encode
from aprs_tui.protocol.kiss import kiss_frame

logger = logging.getLogger(__name__)


class BeaconManager:
    """Manages periodic position beacon transmission.

    Args:
        callsign: Station callsign with SSID (e.g., "W3ADO-9")
        latitude: Station latitude
        longitude: Station longitude
        symbol_table: APRS symbol table char
        symbol_code: APRS symbol code char
        comment: Beacon comment text
        interval: Beacon interval in seconds (min 60)
        destination: AX.25 destination (default "APRS")
        path: Digipeater path (default ["WIDE1-1", "WIDE2-1"])
        send_func: Async callable that sends bytes (e.g., transport.write_frame)
        on_beacon_sent: Optional callback when beacon fires
    """

    def __init__(
        self,
        callsign: str,
        latitude: float,
        longitude: float,
        symbol_table: str = "/",
        symbol_code: str = ">",
        comment: str = "",
        interval: int = 600,
        destination: str = "APRS",
        path: list[str] | None = None,
        send_func: Callable[[bytes], Awaitable[None]] | None = None,
        on_beacon_sent: Callable[[], None] | None = None,
    ) -> None:
        self._callsign = callsign
        self._lat = latitude
        self._lon = longitude
        self._symbol_table = symbol_table
        self._symbol_code = symbol_code
        self._comment = comment
        self._interval = max(interval, 60)  # Minimum 60 seconds
        self._destination = destination
        self._path = path or ["WIDE1-1", "WIDE2-1"]
        self._send_func = send_func
        self._on_beacon_sent = on_beacon_sent
        self._enabled = False
        self._task: asyncio.Task | None = None
        self._beacon_count = 0

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def interval(self) -> int:
        return self._interval

    @property
    def beacon_count(self) -> int:
        return self._beacon_count

    def enable(self) -> None:
        """Enable beaconing. Starts the timer loop."""
        if self._enabled:
            return
        self._enabled = True
        self._task = asyncio.create_task(self._beacon_loop())
        logger.info("Beacon enabled, interval=%ds", self._interval)

    def disable(self) -> None:
        """Disable beaconing. Stops the timer."""
        self._enabled = False
        if self._task and not self._task.done():
            self._task.cancel()
        self._task = None
        logger.info("Beacon disabled")

    def build_position_packet(self) -> str:
        """Build the APRS position text line for this beacon."""
        info = encode_position(
            self._lat, self._lon,
            self._symbol_table, self._symbol_code,
            self._comment,
        )
        return build_packet(self._callsign, self._destination, info, self._path)

    def build_kiss_frame(self) -> bytes:
        """Build the full KISS-framed AX.25 packet for transmission."""
        info = encode_position(
            self._lat, self._lon,
            self._symbol_table, self._symbol_code,
            self._comment,
        )
        ax25_data = ax25_encode(
            self._callsign, self._destination,
            self._path, info.encode("latin-1"),
        )
        return kiss_frame(ax25_data)

    async def _beacon_loop(self) -> None:
        """Timer loop that sends beacons at the configured interval."""
        try:
            # Send first beacon immediately
            await self._send_beacon()
            while self._enabled:
                await asyncio.sleep(self._interval)
                if not self._enabled:
                    break
                await self._send_beacon()
        except asyncio.CancelledError:
            pass

    def _build_ax25(self) -> bytes:
        """Build raw AX.25 frame (no KISS wrapping - transport handles that)."""
        info = encode_position(
            self._lat, self._lon,
            self._symbol_table, self._symbol_code,
            self._comment,
        )
        return ax25_encode(
            self._callsign, self._destination,
            self._path, info.encode("latin-1"),
        )

    async def _send_beacon(self) -> None:
        """Build and send one beacon packet."""
        if self._send_func is None:
            logger.warning("Beacon fired but no send function configured")
            return

        try:
            ax25_data = self._build_ax25()
            await self._send_func(ax25_data)
            self._beacon_count += 1
            logger.info("Beacon #%d sent", self._beacon_count)
            if self._on_beacon_sent:
                self._on_beacon_sent()
        except Exception as e:
            logger.error("Beacon send failed: %s", e)
