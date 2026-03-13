"""APRS message tracking with ack/retry logic and inbound filtering."""
from __future__ import annotations
import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Awaitable

from aprs_tui.protocol.encoder import encode_message, encode_ack
from aprs_tui.protocol.types import APRSPacket

logger = logging.getLogger(__name__)


class MessageState(Enum):
    PENDING = "pending"
    ACKED = "acked"
    REJECTED = "rejected"
    FAILED = "failed"


# APRS retry schedule: 30s, 60s, 120s, 120s, 120s
RETRY_DELAYS = [30, 60, 120, 120, 120]


@dataclass
class TrackedMessage:
    """A message being tracked for ack."""
    msg_id: str
    addressee: str
    text: str
    state: MessageState = MessageState.PENDING
    send_count: int = 0
    created_at: float = field(default_factory=time.monotonic)
    acked_at: float | None = None


@dataclass
class InboundMessage:
    """A received message addressed to us."""
    source: str
    text: str
    msg_id: str | None = None
    timestamp: float = field(default_factory=time.monotonic)


class MessageTracker:
    """Tracks outbound messages for ack and filters inbound messages.

    Args:
        own_callsign: Our callsign (e.g., "N0CALL-9") for inbound filtering
        max_retries: Maximum retry attempts (default 5)
        send_func: Async callable to send encoded message bytes
        on_state_change: Callback when a tracked message state changes
        on_inbound: Callback when an inbound message to us is received
    """

    def __init__(
        self,
        own_callsign: str,
        max_retries: int = 5,
        send_func: Callable[[str], Awaitable[None]] | None = None,
        on_state_change: Callable[[TrackedMessage], None] | None = None,
        on_inbound: Callable[[InboundMessage], None] | None = None,
    ) -> None:
        self._own_callsign = own_callsign.upper().strip()
        self._max_retries = max_retries
        self._send_func = send_func
        self._on_state_change = on_state_change
        self._on_inbound = on_inbound
        self._next_id = 1
        self._pending: dict[str, TrackedMessage] = {}
        self._history: list[TrackedMessage] = []
        self._inbound: list[InboundMessage] = []
        self._retry_tasks: dict[str, asyncio.Task] = {}

    @property
    def max_retries(self) -> int:
        return self._max_retries

    @property
    def pending_count(self) -> int:
        return len(self._pending)

    @property
    def inbound_messages(self) -> list[InboundMessage]:
        return list(self._inbound)

    @property
    def history(self) -> list[TrackedMessage]:
        return list(self._history)

    def send_message(self, addressee: str, text: str) -> str:
        """Queue a message for sending. Returns the assigned message ID."""
        msg_id = str(self._next_id)
        self._next_id += 1

        tracked = TrackedMessage(msg_id=msg_id, addressee=addressee.upper(), text=text)
        self._pending[msg_id] = tracked
        self._history.append(tracked)

        # Start retry loop
        self._retry_tasks[msg_id] = asyncio.create_task(self._retry_loop(tracked))

        return msg_id

    def handle_packet(self, pkt: APRSPacket) -> None:
        """Process an incoming packet for ack matching or inbound message filtering."""
        if pkt.info_type != "message":
            return

        # Handle ack/rej for our outbound messages
        if pkt.is_ack and pkt.message_id:
            self._handle_ack(pkt.message_id)
            return

        if pkt.is_rej and pkt.message_id:
            self._handle_rej(pkt.message_id)
            return

        # Inbound message filtering (Issue #22)
        addressee = (pkt.addressee or "").upper().strip()

        # Check if message is for us or is a bulletin
        is_for_us = addressee == self._own_callsign
        is_bulletin = addressee.startswith("BLN")

        if is_for_us or is_bulletin:
            msg = InboundMessage(
                source=pkt.source or "",
                text=pkt.message_text or "",
                msg_id=pkt.message_id,
            )
            self._inbound.append(msg)

            if self._on_inbound:
                self._on_inbound(msg)

            # Auto-ack if message has an ID
            if pkt.message_id and is_for_us and self._send_func:
                asyncio.create_task(self._send_ack(pkt.source or "", pkt.message_id))

    def _handle_ack(self, msg_id: str) -> None:
        if msg_id not in self._pending:
            return
        tracked = self._pending.pop(msg_id)
        tracked.state = MessageState.ACKED
        tracked.acked_at = time.monotonic()
        # Cancel retry task
        if msg_id in self._retry_tasks:
            self._retry_tasks[msg_id].cancel()
            del self._retry_tasks[msg_id]
        if self._on_state_change:
            self._on_state_change(tracked)

    def _handle_rej(self, msg_id: str) -> None:
        if msg_id not in self._pending:
            return
        tracked = self._pending.pop(msg_id)
        tracked.state = MessageState.REJECTED
        if msg_id in self._retry_tasks:
            self._retry_tasks[msg_id].cancel()
            del self._retry_tasks[msg_id]
        if self._on_state_change:
            self._on_state_change(tracked)

    async def _retry_loop(self, tracked: TrackedMessage) -> None:
        """Send message and retry per APRS schedule."""
        try:
            for attempt in range(self._max_retries):
                if tracked.state != MessageState.PENDING:
                    return

                tracked.send_count += 1

                if self._send_func:
                    info = encode_message(tracked.addressee, tracked.text, tracked.msg_id)
                    await self._send_func(info)

                if attempt < self._max_retries - 1:
                    delay = RETRY_DELAYS[min(attempt, len(RETRY_DELAYS) - 1)]
                    await asyncio.sleep(delay)

            # Max retries exhausted
            if tracked.state == MessageState.PENDING:
                self._pending.pop(tracked.msg_id, None)
                tracked.state = MessageState.FAILED
                if self._on_state_change:
                    self._on_state_change(tracked)
        except asyncio.CancelledError:
            pass

    async def _send_ack(self, source: str, msg_id: str) -> None:
        """Send an ack for a received message."""
        if self._send_func:
            info = encode_ack(source, msg_id)
            await self._send_func(info)

    def stop(self) -> None:
        """Cancel all retry tasks."""
        for task in self._retry_tasks.values():
            if not task.done():
                task.cancel()
        self._retry_tasks.clear()
