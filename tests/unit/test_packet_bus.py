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

import asyncio

from aprs_tui.core.packet_bus import PacketBus
from aprs_tui.protocol.types import APRSPacket


def _make_packet(label: str = "test") -> APRSPacket:
    """Helper to create a simple APRSPacket for testing."""
    return APRSPacket(raw=f"TEST>APRS:{label}", source="TEST", info_type="status")


# ==========================================================================
# Subscribe
# ==========================================================================

class TestPacketBusSubscribe:
    """Subscribing to the packet bus."""

    def test_subscribe_returns_queue(self):
        """subscribe() returns an asyncio.Queue that receives published packets."""
        bus = PacketBus()
        queue = bus.subscribe()
        assert isinstance(queue, asyncio.Queue)

    def test_multiple_subscribers(self):
        """Multiple subscribers each get their own queue and all receive the same packets."""
        bus = PacketBus()
        q1 = bus.subscribe()
        q2 = bus.subscribe()
        q3 = bus.subscribe()
        assert q1 is not q2
        assert q2 is not q3
        assert bus.subscriber_count == 3

        pkt = _make_packet("multi")
        bus.publish(pkt)
        assert q1.get_nowait() is pkt
        assert q2.get_nowait() is pkt
        assert q3.get_nowait() is pkt

    def test_subscriber_queue_bounded(self):
        """Subscriber queues have a max size of 1000 to prevent unbounded growth."""
        bus = PacketBus()
        queue = bus.subscribe()
        assert queue.maxsize == 1000


# ==========================================================================
# Publish
# ==========================================================================

class TestPacketBusPublish:
    """Publishing packets to all subscribers."""

    def test_publish_delivers_to_subscriber(self):
        """A published packet appears in the subscriber's queue."""
        bus = PacketBus()
        queue = bus.subscribe()
        pkt = _make_packet("deliver")
        bus.publish(pkt)
        assert not queue.empty()
        assert queue.get_nowait() is pkt

    def test_publish_delivers_to_all_subscribers(self):
        """A published packet is delivered to every active subscriber."""
        bus = PacketBus()
        queues = [bus.subscribe() for _ in range(5)]
        pkt = _make_packet("all")
        bus.publish(pkt)
        for q in queues:
            assert q.get_nowait() is pkt

    def test_publish_order_preserved(self):
        """Packets are delivered in the order they were published (FIFO)."""
        bus = PacketBus()
        queue = bus.subscribe()
        packets = [_make_packet(f"order-{i}") for i in range(10)]
        for pkt in packets:
            bus.publish(pkt)
        received = []
        while not queue.empty():
            received.append(queue.get_nowait())
        assert received == packets

    def test_publish_no_subscribers_no_error(self):
        """Publishing with zero subscribers does not raise an error."""
        bus = PacketBus()
        assert bus.subscriber_count == 0
        # Should not raise
        bus.publish(_make_packet("nobody"))


# ==========================================================================
# Backpressure (slow consumer)
# ==========================================================================

class TestPacketBusBackpressure:
    """Backpressure handling when a subscriber is slow."""

    def test_full_queue_drops_oldest(self):
        """When a subscriber's queue is full (1000 items), publishing drops
        the oldest packet and adds the new one."""
        bus = PacketBus(maxsize=3)
        queue = bus.subscribe()

        pkt1 = _make_packet("first")
        pkt2 = _make_packet("second")
        pkt3 = _make_packet("third")
        pkt4 = _make_packet("fourth")

        bus.publish(pkt1)
        bus.publish(pkt2)
        bus.publish(pkt3)
        # Queue is now full (3 items)
        assert queue.qsize() == 3

        # Publishing a 4th should drop the oldest (pkt1) and add pkt4
        bus.publish(pkt4)
        assert queue.qsize() == 3
        assert queue.get_nowait() is pkt2  # pkt1 was dropped
        assert queue.get_nowait() is pkt3
        assert queue.get_nowait() is pkt4

    def test_full_queue_does_not_block_publisher(self):
        """A full subscriber queue never blocks the publish() call."""
        bus = PacketBus(maxsize=2)
        queue = bus.subscribe()

        # Fill the queue
        bus.publish(_make_packet("a"))
        bus.publish(_make_packet("b"))
        assert queue.full()

        # This must not block -- it should return immediately
        bus.publish(_make_packet("c"))
        # If we get here, it didn't block
        assert queue.qsize() == 2

    def test_slow_subscriber_does_not_affect_fast_subscriber(self):
        """One subscriber with a full queue does not delay delivery to
        other subscribers."""
        bus = PacketBus(maxsize=2)
        slow_q = bus.subscribe()
        fast_q = bus.subscribe()

        # Fill only the slow queue
        bus.publish(_make_packet("x"))
        bus.publish(_make_packet("y"))
        # Both queues are full now
        # Drain the fast queue to make it "fast"
        fast_q.get_nowait()
        fast_q.get_nowait()

        # Now publish more -- slow_q is full, fast_q has room
        pkt = _make_packet("new")
        bus.publish(pkt)

        # fast_q should have received the new packet
        assert fast_q.get_nowait() is pkt
        # slow_q should also have it (oldest was dropped)
        # slow_q had [x, y], now after drop oldest it's [y, new]
        assert slow_q.get_nowait().raw == "TEST>APRS:y"
        assert slow_q.get_nowait() is pkt

    def test_dropped_packet_count_trackable(self):
        """The number of dropped packets per subscriber can be queried
        for monitoring/display."""
        bus = PacketBus(maxsize=2)
        queue = bus.subscribe()

        assert bus.dropped_count(queue) == 0

        bus.publish(_make_packet("1"))
        bus.publish(_make_packet("2"))
        assert bus.dropped_count(queue) == 0

        # This causes a drop
        bus.publish(_make_packet("3"))
        assert bus.dropped_count(queue) == 1

        # Another drop
        bus.publish(_make_packet("4"))
        assert bus.dropped_count(queue) == 2


# ==========================================================================
# Edge cases
# ==========================================================================

class TestPacketBusEdgeCases:
    """Edge cases for the packet bus."""

    def test_publish_after_subscriber_removed(self):
        """If a subscriber queue is removed/closed, publishing does not crash."""
        bus = PacketBus()
        queue = bus.subscribe()
        bus.unsubscribe(queue)
        assert bus.subscriber_count == 0
        # Should not raise
        bus.publish(_make_packet("orphan"))

    def test_concurrent_publish_safe(self):
        """Multiple concurrent publish() calls do not corrupt state."""
        bus = PacketBus()
        queue = bus.subscribe()

        # Simulate rapid sequential publishes (sync context -- truly concurrent
        # publish is only possible with async, but since publish() is sync and
        # non-blocking, sequential rapid calls should be safe)
        for i in range(100):
            bus.publish(_make_packet(f"rapid-{i}"))

        assert queue.qsize() == 100
        # Verify ordering
        for i in range(100):
            pkt = queue.get_nowait()
            assert pkt.raw == f"TEST>APRS:rapid-{i}"

    def test_subscribe_during_publish(self):
        """A new subscriber added during a publish() call does not crash."""
        bus = PacketBus()
        q1 = bus.subscribe()

        # publish() iterates over list(self._subscribers), so adding a new
        # subscriber during iteration is safe. We can't truly interleave in
        # sync code, but we can verify that subscribing right after publish
        # works and the new subscriber does not receive the earlier packet.
        pkt1 = _make_packet("before")
        bus.publish(pkt1)

        q2 = bus.subscribe()

        pkt2 = _make_packet("after")
        bus.publish(pkt2)

        # q1 got both packets
        assert q1.get_nowait() is pkt1
        assert q1.get_nowait() is pkt2

        # q2 only got the second packet (subscribed after first publish)
        assert q2.get_nowait() is pkt2
        assert q2.empty()
