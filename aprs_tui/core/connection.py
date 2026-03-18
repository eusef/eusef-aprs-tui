"""Connection lifecycle manager with state machine and auto-reconnect."""
from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable

from aprs_tui.protocol.ax25 import ax25_decode, ax25_to_text
from aprs_tui.protocol.decoder import decode_packet
from aprs_tui.protocol.types import APRSPacket
from aprs_tui.transport.base import ConnectionState, Transport

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages transport connection lifecycle with auto-reconnect.

    State machine: DISCONNECTED -> CONNECTING -> CONNECTED -> RECONNECTING -> FAILED

    Args:
        transport: The transport to manage
        reconnect_interval: Base delay between reconnect attempts (seconds)
        max_reconnect_attempts: Max retry count (0 = infinite)
        health_timeout: Seconds of silence before health warning
        on_state_change: Callback when connection state changes
        on_packet: Callback when a decoded packet is received
        on_health_warning: Callback when health timeout fires
    """

    def __init__(
        self,
        transport: Transport,
        reconnect_interval: float = 10.0,
        max_reconnect_attempts: int = 0,
        health_timeout: float = 60.0,
        on_state_change: Callable[[ConnectionState], None] | None = None,
        on_packet: Callable[[APRSPacket], None] | None = None,
        on_health_warning: Callable[[bool], None] | None = None,
    ) -> None:
        self._transport = transport
        self._reconnect_interval = reconnect_interval
        self._max_attempts = max_reconnect_attempts
        self._health_timeout = health_timeout
        self._on_state_change = on_state_change
        self._on_packet = on_packet
        self._on_health_warning = on_health_warning

        self._state = ConnectionState.DISCONNECTED
        self._attempt_count = 0
        self._last_packet_time: float = 0.0
        self._read_task: asyncio.Task | None = None
        self._health_task: asyncio.Task | None = None
        self._reconnect_task: asyncio.Task | None = None
        self._running = False
        self._health_warned = False
        self._rx_count = 0
        self._tx_count = 0

    @property
    def state(self) -> ConnectionState:
        return self._state

    @property
    def rx_count(self) -> int:
        return self._rx_count

    @property
    def tx_count(self) -> int:
        return self._tx_count

    @property
    def transport(self) -> Transport:
        return self._transport

    def _set_state(self, new_state: ConnectionState) -> None:
        if new_state != self._state:
            old = self._state
            self._state = new_state
            logger.info("Connection state: %s -> %s", old.value, new_state.value)
            if self._on_state_change:
                self._on_state_change(new_state)

    async def connect(self) -> None:
        """Start the connection and begin reading packets."""
        self._running = True
        self._set_state(ConnectionState.CONNECTING)
        try:
            await self._transport.connect()
            self._set_state(ConnectionState.CONNECTED)
            self._attempt_count = 0
            self._last_packet_time = time.monotonic()
            self._health_warned = False
            self._start_read_loop()
            self._start_health_check()
        except ConnectionError:
            await self._handle_connection_failure()

    async def disconnect(self) -> None:
        """Stop reading and disconnect the transport."""
        self._running = False
        self._stop_tasks()
        await self._transport.disconnect()
        self._set_state(ConnectionState.DISCONNECTED)

    async def send_frame(self, data: bytes) -> None:
        """Send a frame via the transport. Increments TX count."""
        await self._transport.write_frame(data)
        self._tx_count += 1

    def _start_read_loop(self) -> None:
        if self._read_task and not self._read_task.done():
            self._read_task.cancel()
        self._read_task = asyncio.create_task(self._read_loop())

    def _start_health_check(self) -> None:
        if self._health_task and not self._health_task.done():
            self._health_task.cancel()
        self._health_task = asyncio.create_task(self._health_loop())

    def _stop_tasks(self) -> None:
        for task in (self._read_task, self._health_task, self._reconnect_task):
            if task and not task.done():
                task.cancel()
        self._read_task = None
        self._health_task = None
        self._reconnect_task = None

    async def _read_loop(self) -> None:
        """Read frames from transport, decode, and publish."""
        try:
            while self._running:
                try:
                    raw_frame = await self._transport.read_frame()
                except ConnectionError:
                    if self._running:
                        await self._handle_connection_failure()
                    return

                self._last_packet_time = time.monotonic()
                self._rx_count += 1

                # Clear health warning on packet receipt
                if self._health_warned:
                    self._health_warned = False
                    if self._on_health_warning:
                        self._on_health_warning(False)

                # Decode and publish
                # APRS-IS returns text lines; KISS returns binary AX.25 frames
                try:
                    from aprs_tui.transport.aprs_is import AprsIsTransport
                    is_text_transport = isinstance(self._transport, AprsIsTransport)
                except ImportError:
                    is_text_transport = False

                try:
                    if is_text_transport:
                        # APRS-IS: raw_frame is already a text line encoded as bytes
                        text_line = raw_frame.decode("latin-1", errors="replace")
                        pkt = decode_packet(text_line, transport=self._transport.display_name)
                    else:
                        # KISS: raw_frame is binary AX.25
                        ax25 = ax25_decode(raw_frame)
                        text_line = ax25_to_text(ax25)
                        pkt = decode_packet(text_line, transport=self._transport.display_name)
                except Exception:
                    raw_display = (
                        raw_frame.decode("latin-1", errors="replace")
                        if is_text_transport
                        else raw_frame.hex()
                    )
                    pkt = APRSPacket(
                        raw=raw_display,
                        parse_error="Decode failed",
                        transport=self._transport.display_name,
                    )

                if self._on_packet:
                    self._on_packet(pkt)
        except asyncio.CancelledError:
            pass

    async def _health_loop(self) -> None:
        """Monitor for silence (no packets received)."""
        try:
            while self._running and self._state == ConnectionState.CONNECTED:
                # Check interval is 1/4 of health timeout, capped at 5s
                check_interval = min(self._health_timeout / 4, 5.0)
                await asyncio.sleep(check_interval)
                if not self._running or self._state != ConnectionState.CONNECTED:
                    break
                elapsed = time.monotonic() - self._last_packet_time
                if elapsed > self._health_timeout and not self._health_warned:
                    self._health_warned = True
                    logger.warning("No packets received for %.0fs", elapsed)
                    if self._on_health_warning:
                        self._on_health_warning(True)
        except asyncio.CancelledError:
            pass

    async def _handle_connection_failure(self) -> None:
        """Handle a connection failure - attempt reconnect or fail."""
        if not self._running:
            return

        self._attempt_count += 1

        if self._max_attempts > 0 and self._attempt_count > self._max_attempts:
            self._set_state(ConnectionState.FAILED)
            return

        self._set_state(ConnectionState.RECONNECTING)

        # Exponential backoff: 1s, 2s, 4s, 8s, ..., capped at 30s
        delay = min(2 ** (self._attempt_count - 1), 30)
        logger.info("Reconnecting in %ds (attempt %d)", delay, self._attempt_count)

        await asyncio.sleep(delay)

        if not self._running:
            return

        self._set_state(ConnectionState.CONNECTING)
        try:
            await self._transport.connect()
            self._set_state(ConnectionState.CONNECTED)
            self._attempt_count = 0
            self._last_packet_time = time.monotonic()
            self._health_warned = False
            self._start_read_loop()
            self._start_health_check()
        except ConnectionError:
            await self._handle_connection_failure()
