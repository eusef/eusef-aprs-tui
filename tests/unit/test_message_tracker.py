"""Tests for outbound message ack tracking and retry (core/message_tracker.py).

Covers: Issue #19 - Message Tracker (ack tracking, retry 30s/60s/120s, timeout)
        Issue #22 - Inbound message filtering (to my callsign)
Sprint: 4 (Messaging)
PRD refs: AC-08 (messaging - send, ack tracking, retry, failure notification)

Module under test: aprs_tui.core.message_tracker
Estimated implementation: ~150-200 lines

APRS message retry schedule per spec:
  First retry: 30s
  Second retry: 60s
  Third and subsequent: 120s (plateau)
  Max retries: configurable (default 5)
  On ack: remove from pending, notify UI
  On timeout: notify UI of delivery failure

Inbound message filtering: only messages addressed to my callsign are
delivered to the message panel.
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

from aprs_tui.core.message_tracker import (
    RETRY_DELAYS,
    InboundMessage,
    MessageState,
    MessageTracker,
    TrackedMessage,
)
from aprs_tui.protocol.types import APRSPacket

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_tracker(
    callsign: str = "N0CALL-9",
    max_retries: int = 5,
    send_func=None,
    on_state_change=None,
    on_inbound=None,
) -> MessageTracker:
    """Create a MessageTracker suitable for synchronous unit tests.

    By default send_func is a no-op async mock so that asyncio.create_task
    inside send_message does not blow up when an event loop is running.
    """
    if send_func is None:
        send_func = AsyncMock()
    return MessageTracker(
        own_callsign=callsign,
        max_retries=max_retries,
        send_func=send_func,
        on_state_change=on_state_change,
        on_inbound=on_inbound,
    )


def _ack_packet(source: str, msg_id: str) -> APRSPacket:
    return APRSPacket(
        raw=f"{source}>APRS::N0CALL-9 :ack{msg_id}",
        source=source,
        info_type="message",
        is_ack=True,
        message_id=msg_id,
    )


def _rej_packet(source: str, msg_id: str) -> APRSPacket:
    return APRSPacket(
        raw=f"{source}>APRS::N0CALL-9 :rej{msg_id}",
        source=source,
        info_type="message",
        is_rej=True,
        message_id=msg_id,
    )


def _msg_packet(
    source: str,
    addressee: str,
    text: str,
    msg_id: str | None = None,
) -> APRSPacket:
    return APRSPacket(
        raw=f"{source}>APRS::{addressee}:{text}",
        source=source,
        info_type="message",
        addressee=addressee,
        message_text=text,
        message_id=msg_id,
    )


# ==========================================================================
# Outbound message tracking
# ==========================================================================

class TestMessageSend:
    """Tracking outbound messages awaiting acknowledgement."""

    async def test_send_message_creates_pending(self):
        """Sending a message adds it to the pending ack queue."""
        tracker = _make_tracker()
        tracker.send_message("W3ADO-1", "Hello")
        assert tracker.pending_count == 1
        tracker.stop()

    async def test_send_assigns_sequence_number(self):
        """Each sent message gets a unique, incrementing sequence number."""
        tracker = _make_tracker()
        id1 = tracker.send_message("W3ADO-1", "First")
        id2 = tracker.send_message("W3ADO-1", "Second")
        id3 = tracker.send_message("K3ABC", "Third")
        assert id1 == "1"
        assert id2 == "2"
        assert id3 == "3"
        tracker.stop()

    async def test_send_returns_message_number(self):
        """send_message() returns the assigned msgno for UI display."""
        tracker = _make_tracker()
        msg_id = tracker.send_message("W3ADO-1", "Hello")
        assert msg_id == "1"
        tracker.stop()

    async def test_multiple_pending_messages(self):
        """Multiple messages to different callsigns can be pending simultaneously."""
        tracker = _make_tracker()
        tracker.send_message("W3ADO-1", "Hello A")
        tracker.send_message("K3ABC", "Hello B")
        tracker.send_message("N3XYZ", "Hello C")
        assert tracker.pending_count == 3
        tracker.stop()


# ==========================================================================
# Ack handling
# ==========================================================================

class TestAckHandling:
    """Processing received message acknowledgements."""

    async def test_ack_removes_from_pending(self):
        """Receiving an ack for a pending message removes it from the queue."""
        tracker = _make_tracker()
        msg_id = tracker.send_message("W3ADO-1", "Hello")
        assert tracker.pending_count == 1

        tracker.handle_packet(_ack_packet("W3ADO-1", msg_id))
        assert tracker.pending_count == 0
        tracker.stop()

    async def test_ack_stops_retries(self):
        """After ack is received, no more retries are scheduled for that message."""
        tracker = _make_tracker()
        msg_id = tracker.send_message("W3ADO-1", "Hello")
        tracker.start_retry_loop(msg_id)

        # Verify retry task exists
        assert msg_id in tracker._retry_tasks

        tracker.handle_packet(_ack_packet("W3ADO-1", msg_id))

        # Retry task should be cleaned up
        assert msg_id not in tracker._retry_tasks
        tracker.stop()

    async def test_ack_for_unknown_msgno_ignored(self):
        """An ack for a message number not in pending is silently ignored."""
        tracker = _make_tracker()
        tracker.send_message("W3ADO-1", "Hello")
        assert tracker.pending_count == 1

        # Ack for a non-existent message
        tracker.handle_packet(_ack_packet("W3ADO-1", "999"))
        assert tracker.pending_count == 1  # unchanged
        tracker.stop()

    async def test_ack_notifies_callback(self):
        """On ack receipt, a registered callback/event is fired for UI update."""
        state_changes: list[TrackedMessage] = []
        tracker = _make_tracker(on_state_change=state_changes.append)
        msg_id = tracker.send_message("W3ADO-1", "Test")

        tracker.handle_packet(_ack_packet("W3ADO-1", msg_id))
        assert len(state_changes) == 1
        assert state_changes[0].state == MessageState.ACKED
        tracker.stop()

    async def test_reject_removes_from_pending(self):
        """Receiving a reject for a pending message removes it and notifies failure."""
        state_changes: list[TrackedMessage] = []
        tracker = _make_tracker(on_state_change=state_changes.append)
        msg_id = tracker.send_message("W3ADO-1", "Test")

        tracker.handle_packet(_rej_packet("W3ADO-1", msg_id))
        assert tracker.pending_count == 0
        assert len(state_changes) == 1
        assert state_changes[0].state == MessageState.REJECTED
        tracker.stop()


# ==========================================================================
# Retry schedule
# ==========================================================================

class TestRetrySchedule:
    """Retry timing per APRS spec: 30s, 60s, 120s, 120s, 120s."""

    def test_first_retry_at_30_seconds(self):
        """First retry fires 30 seconds after initial send."""
        assert RETRY_DELAYS[0] == 30

    def test_second_retry_at_60_seconds(self):
        """Second retry fires 60 seconds after first retry."""
        assert RETRY_DELAYS[1] == 60

    def test_third_retry_at_120_seconds(self):
        """Third retry fires 120 seconds after second retry (plateau)."""
        assert RETRY_DELAYS[2] == 120

    def test_subsequent_retries_stay_at_120_seconds(self):
        """Fourth and fifth retries remain at 120-second intervals."""
        assert RETRY_DELAYS[3] == 120
        assert RETRY_DELAYS[4] == 120

    def test_max_retries_configurable(self):
        """Number of retry attempts is configurable (default 5)."""
        tracker = MessageTracker(own_callsign="N0CALL-9", max_retries=3)
        assert tracker.max_retries == 3

        default_tracker = MessageTracker(own_callsign="N0CALL-9")
        assert default_tracker.max_retries == 5


# ==========================================================================
# Timeout and failure
# ==========================================================================

class TestMessageTimeout:
    """Timeout after max retries exhausted."""

    async def test_timeout_after_max_retries(self):
        """After all retries are exhausted, the message is marked as failed."""
        send_mock = AsyncMock()
        state_changes: list[TrackedMessage] = []
        tracker = _make_tracker(
            max_retries=1,
            send_func=send_mock,
            on_state_change=state_changes.append,
        )
        msg_id = tracker.send_message("W3ADO-1", "Hello")
        tracker.start_retry_loop(msg_id)

        # Let the retry loop complete (max_retries=1 means one send, no sleep)
        await asyncio.sleep(0.1)

        assert len(state_changes) == 1
        assert state_changes[0].state == MessageState.FAILED
        tracker.stop()

    async def test_timeout_notifies_callback(self):
        """On timeout, a registered callback/event is fired to notify the UI."""
        state_changes: list[TrackedMessage] = []
        tracker = _make_tracker(
            max_retries=1,
            on_state_change=state_changes.append,
        )
        msg_id = tracker.send_message("W3ADO-1", "Hello")
        tracker.start_retry_loop(msg_id)

        # Let the retry loop complete
        await asyncio.sleep(0.1)

        assert len(state_changes) == 1
        assert state_changes[0].state == MessageState.FAILED
        tracker.stop()

    async def test_timeout_removes_from_pending(self):
        """A timed-out message is removed from the pending queue."""
        tracker = _make_tracker(max_retries=1)
        msg_id = tracker.send_message("W3ADO-1", "Hello")
        tracker.start_retry_loop(msg_id)

        # Let the retry loop complete
        await asyncio.sleep(0.1)

        assert tracker.pending_count == 0
        tracker.stop()

    def test_total_timeout_duration(self):
        """Total time from first send to final timeout:
        30 + 60 + 120 + 120 + 120 = 450 seconds (~7.5 minutes)."""
        assert sum(RETRY_DELAYS) == 450
        assert RETRY_DELAYS == [30, 60, 120, 120, 120]


# ==========================================================================
# Inbound message filtering (Issue #22)
# ==========================================================================

class TestInboundMessageFilter:
    """Filtering inbound messages addressed to my callsign."""

    def test_message_to_my_callsign_passes(self):
        """A message addressed to our configured callsign is delivered."""
        tracker = MessageTracker(own_callsign="N0CALL-9")
        pkt = _msg_packet("W3ADO-1", "N0CALL-9", "Hello", msg_id="42")
        tracker.handle_packet(pkt)
        assert len(tracker.inbound_messages) == 1
        assert tracker.inbound_messages[0].source == "W3ADO-1"
        assert tracker.inbound_messages[0].text == "Hello"

    def test_message_to_other_callsign_filtered(self):
        """A message addressed to someone else is not delivered to message panel."""
        tracker = MessageTracker(own_callsign="N0CALL-9")
        pkt = _msg_packet("W3ADO-1", "K3ABC", "Hi", msg_id="43")
        tracker.handle_packet(pkt)
        assert len(tracker.inbound_messages) == 0

    def test_message_addressee_case_insensitive(self):
        """Addressee matching is case-insensitive."""
        tracker = MessageTracker(own_callsign="N0CALL-9")

        # Lowercase addressee should still match
        pkt = _msg_packet("W3ADO-1", "n0call-9", "Hi", msg_id="44")
        tracker.handle_packet(pkt)
        assert len(tracker.inbound_messages) == 1

    def test_message_addressee_ignores_padding(self):
        """Trailing spaces in the 9-char addressee field are stripped before matching."""
        tracker = MessageTracker(own_callsign="N0CALL-9")

        # Padded addressee (9-char field with trailing spaces)
        pkt = _msg_packet("W3ADO-1", "N0CALL-9 ", "Hi")
        tracker.handle_packet(pkt)
        assert len(tracker.inbound_messages) == 1

    def test_bulletin_messages_pass(self):
        """Messages to BLN* (bulletins) are always delivered regardless of callsign."""
        tracker = MessageTracker(own_callsign="N0CALL-9")
        pkt = _msg_packet("W3ADO-1", "BLN1", "Bulletin text")
        tracker.handle_packet(pkt)
        assert len(tracker.inbound_messages) == 1
        assert tracker.inbound_messages[0].text == "Bulletin text"

    def test_inbound_callback_fires(self):
        """The on_inbound callback is called for messages addressed to us."""
        received: list[InboundMessage] = []
        tracker = MessageTracker(
            own_callsign="N0CALL-9",
            on_inbound=received.append,
        )
        pkt = _msg_packet("W3ADO-1", "N0CALL-9", "Test msg", msg_id="10")
        tracker.handle_packet(pkt)
        assert len(received) == 1
        assert received[0].source == "W3ADO-1"
        assert received[0].text == "Test msg"
        assert received[0].msg_id == "10"

    def test_non_message_packets_ignored(self):
        """Packets with info_type != 'message' are ignored by the tracker."""
        tracker = MessageTracker(own_callsign="N0CALL-9")
        pkt = APRSPacket(
            raw="W3ADO-1>APRS:!4000.00N/07500.00W>",
            source="W3ADO-1",
            info_type="position",
        )
        tracker.handle_packet(pkt)
        assert len(tracker.inbound_messages) == 0
        assert tracker.pending_count == 0

    def test_multiple_inbound_filters_correctly(self):
        """Verify a mix of messages to us and others filters correctly."""
        tracker = MessageTracker(own_callsign="N0CALL-9")

        # Message to us
        tracker.handle_packet(_msg_packet("W3ADO-1", "N0CALL-9", "Hello", "42"))
        assert len(tracker.inbound_messages) == 1

        # Message to someone else
        tracker.handle_packet(_msg_packet("W3ADO-1", "K3ABC", "Hi", "43"))
        assert len(tracker.inbound_messages) == 1  # still 1

        # Case insensitive match
        tracker.handle_packet(_msg_packet("W3ADO-1", "n0call-9", "Hi", "44"))
        assert len(tracker.inbound_messages) == 2

        # Padded addressee
        tracker.handle_packet(_msg_packet("W3ADO-1", "N0CALL-9 ", "Hi"))
        assert len(tracker.inbound_messages) == 3

        # Bulletin
        tracker.handle_packet(_msg_packet("W3ADO-1", "BLN1", "Bulletin text"))
        assert len(tracker.inbound_messages) == 4
