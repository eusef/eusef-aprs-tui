"""Tests for the async packet bus (core/packet_bus.py).

Covers: Issue #9 - Packet Bus (async pub/sub queue)
Sprint: 2 (TUI Shell + Stream Panel)
PRD refs: ADR-2 (packet bus as central decoupler)

Module under test: aprs_tui.core.packet_bus
Estimated implementation: ~40-60 lines

The PacketBus is a central async pub/sub queue that decouples transport
from UI. Transport publishes decoded APRSPackets; UI panels subscribe.
Bounded queues (maxsize=1000) provide backpressure. Slow consumers get
oldest packets dropped to prevent memory issues.
"""
from __future__ import annotations

import pytest


# ==========================================================================
# Subscribe
# ==========================================================================

class TestPacketBusSubscribe:
    """Subscribing to the packet bus."""

    @pytest.mark.skip(reason="Sprint 2: Not implemented yet")
    def test_subscribe_returns_queue(self):
        """subscribe() returns an asyncio.Queue that receives published packets."""
        pass

    @pytest.mark.skip(reason="Sprint 2: Not implemented yet")
    def test_multiple_subscribers(self):
        """Multiple subscribers each get their own queue and all receive the same packets."""
        pass

    @pytest.mark.skip(reason="Sprint 2: Not implemented yet")
    def test_subscriber_queue_bounded(self):
        """Subscriber queues have a max size of 1000 to prevent unbounded growth."""
        pass


# ==========================================================================
# Publish
# ==========================================================================

class TestPacketBusPublish:
    """Publishing packets to all subscribers."""

    @pytest.mark.skip(reason="Sprint 2: Not implemented yet")
    def test_publish_delivers_to_subscriber(self):
        """A published packet appears in the subscriber's queue."""
        pass

    @pytest.mark.skip(reason="Sprint 2: Not implemented yet")
    def test_publish_delivers_to_all_subscribers(self):
        """A published packet is delivered to every active subscriber."""
        pass

    @pytest.mark.skip(reason="Sprint 2: Not implemented yet")
    def test_publish_order_preserved(self):
        """Packets are delivered in the order they were published (FIFO)."""
        pass

    @pytest.mark.skip(reason="Sprint 2: Not implemented yet")
    def test_publish_no_subscribers_no_error(self):
        """Publishing with zero subscribers does not raise an error."""
        pass


# ==========================================================================
# Backpressure (slow consumer)
# ==========================================================================

class TestPacketBusBackpressure:
    """Backpressure handling when a subscriber is slow."""

    @pytest.mark.skip(reason="Sprint 2: Not implemented yet")
    def test_full_queue_drops_oldest(self):
        """When a subscriber's queue is full (1000 items), publishing drops
        the oldest packet and adds the new one."""
        pass

    @pytest.mark.skip(reason="Sprint 2: Not implemented yet")
    def test_full_queue_does_not_block_publisher(self):
        """A full subscriber queue never blocks the publish() call."""
        pass

    @pytest.mark.skip(reason="Sprint 2: Not implemented yet")
    def test_slow_subscriber_does_not_affect_fast_subscriber(self):
        """One subscriber with a full queue does not delay delivery to
        other subscribers."""
        pass

    @pytest.mark.skip(reason="Sprint 2: Not implemented yet")
    def test_dropped_packet_count_trackable(self):
        """The number of dropped packets per subscriber can be queried
        for monitoring/display."""
        pass


# ==========================================================================
# Edge cases
# ==========================================================================

class TestPacketBusEdgeCases:
    """Edge cases for the packet bus."""

    @pytest.mark.skip(reason="Sprint 2: Not implemented yet")
    def test_publish_after_subscriber_removed(self):
        """If a subscriber queue is removed/closed, publishing does not crash."""
        pass

    @pytest.mark.skip(reason="Sprint 2: Not implemented yet")
    def test_concurrent_publish_safe(self):
        """Multiple concurrent publish() calls do not corrupt state."""
        pass

    @pytest.mark.skip(reason="Sprint 2: Not implemented yet")
    def test_subscribe_during_publish(self):
        """A new subscriber added during a publish() call does not crash."""
        pass
