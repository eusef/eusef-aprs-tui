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

import pytest


# ==========================================================================
# Outbound message tracking
# ==========================================================================

class TestMessageSend:
    """Tracking outbound messages awaiting acknowledgement."""

    @pytest.mark.skip(reason="Sprint 4: Not implemented yet")
    def test_send_message_creates_pending(self):
        """Sending a message adds it to the pending ack queue."""
        pass

    @pytest.mark.skip(reason="Sprint 4: Not implemented yet")
    def test_send_assigns_sequence_number(self):
        """Each sent message gets a unique, incrementing sequence number."""
        pass

    @pytest.mark.skip(reason="Sprint 4: Not implemented yet")
    def test_send_returns_message_number(self):
        """send_message() returns the assigned msgno for UI display."""
        pass

    @pytest.mark.skip(reason="Sprint 4: Not implemented yet")
    def test_multiple_pending_messages(self):
        """Multiple messages to different callsigns can be pending simultaneously."""
        pass


# ==========================================================================
# Ack handling
# ==========================================================================

class TestAckHandling:
    """Processing received message acknowledgements."""

    @pytest.mark.skip(reason="Sprint 4: Not implemented yet")
    def test_ack_removes_from_pending(self):
        """Receiving an ack for a pending message removes it from the queue."""
        pass

    @pytest.mark.skip(reason="Sprint 4: Not implemented yet")
    def test_ack_stops_retries(self):
        """After ack is received, no more retries are scheduled for that message."""
        pass

    @pytest.mark.skip(reason="Sprint 4: Not implemented yet")
    def test_ack_for_unknown_msgno_ignored(self):
        """An ack for a message number not in pending is silently ignored."""
        pass

    @pytest.mark.skip(reason="Sprint 4: Not implemented yet")
    def test_ack_notifies_callback(self):
        """On ack receipt, a registered callback/event is fired for UI update."""
        pass

    @pytest.mark.skip(reason="Sprint 4: Not implemented yet")
    def test_reject_removes_from_pending(self):
        """Receiving a reject for a pending message removes it and notifies failure."""
        pass


# ==========================================================================
# Retry schedule
# ==========================================================================

class TestRetrySchedule:
    """Retry timing per APRS spec: 30s, 60s, 120s, 120s, 120s."""

    @pytest.mark.skip(reason="Sprint 4: Not implemented yet")
    def test_first_retry_at_30_seconds(self):
        """First retry fires 30 seconds after initial send."""
        pass

    @pytest.mark.skip(reason="Sprint 4: Not implemented yet")
    def test_second_retry_at_60_seconds(self):
        """Second retry fires 60 seconds after first retry."""
        pass

    @pytest.mark.skip(reason="Sprint 4: Not implemented yet")
    def test_third_retry_at_120_seconds(self):
        """Third retry fires 120 seconds after second retry (plateau)."""
        pass

    @pytest.mark.skip(reason="Sprint 4: Not implemented yet")
    def test_subsequent_retries_stay_at_120_seconds(self):
        """Fourth and fifth retries remain at 120-second intervals."""
        pass

    @pytest.mark.skip(reason="Sprint 4: Not implemented yet")
    def test_max_retries_configurable(self):
        """Number of retry attempts is configurable (default 5)."""
        pass


# ==========================================================================
# Timeout and failure
# ==========================================================================

class TestMessageTimeout:
    """Timeout after max retries exhausted."""

    @pytest.mark.skip(reason="Sprint 4: Not implemented yet")
    def test_timeout_after_max_retries(self):
        """After all retries are exhausted, the message is marked as failed."""
        pass

    @pytest.mark.skip(reason="Sprint 4: Not implemented yet")
    def test_timeout_notifies_callback(self):
        """On timeout, a registered callback/event is fired to notify the UI."""
        pass

    @pytest.mark.skip(reason="Sprint 4: Not implemented yet")
    def test_timeout_removes_from_pending(self):
        """A timed-out message is removed from the pending queue."""
        pass

    @pytest.mark.skip(reason="Sprint 4: Not implemented yet")
    def test_total_timeout_duration(self):
        """Total time from first send to final timeout:
        30 + 60 + 120 + 120 + 120 = 450 seconds (~7.5 minutes)."""
        pass


# ==========================================================================
# Inbound message filtering (Issue #22)
# ==========================================================================

class TestInboundMessageFilter:
    """Filtering inbound messages addressed to my callsign."""

    @pytest.mark.skip(reason="Sprint 4: Not implemented yet")
    def test_message_to_my_callsign_passes(self):
        """A message addressed to our configured callsign is delivered."""
        pass

    @pytest.mark.skip(reason="Sprint 4: Not implemented yet")
    def test_message_to_other_callsign_filtered(self):
        """A message addressed to someone else is not delivered to message panel."""
        pass

    @pytest.mark.skip(reason="Sprint 4: Not implemented yet")
    def test_message_addressee_case_insensitive(self):
        """Addressee matching is case-insensitive."""
        pass

    @pytest.mark.skip(reason="Sprint 4: Not implemented yet")
    def test_message_addressee_ignores_padding(self):
        """Trailing spaces in the 9-char addressee field are stripped before matching."""
        pass

    @pytest.mark.skip(reason="Sprint 4: Not implemented yet")
    def test_bulletin_messages_pass(self):
        """Messages to BLN* (bulletins) are always delivered regardless of callsign."""
        pass
