"""Tests for packet deduplication filter (core/dedup.py).

Covers: Issue #36 - Packet deduplication (source + info hash, 30s window)
Sprint: 7 (APRS-IS + Discovery + Polish)
PRD refs: R-06 (dedup for dual radio + APRS-IS), Architecture 10.5

Module under test: aprs_tui.core.dedup
Estimated implementation: ~50-80 lines

Dedup filter drops duplicate packets received within a 30-second window.
This is essential for dual mode (simultaneous radio + APRS-IS) where the
same packet may arrive on both transports. Dedup key is source callsign +
info field hash.
"""
from __future__ import annotations

import time

from aprs_tui.core.dedup import DeduplicationFilter
from aprs_tui.protocol.types import APRSPacket

# ==========================================================================
# Basic dedup logic
# ==========================================================================

class TestDedupFilter:
    """Core deduplication logic: drop duplicates within time window."""

    def test_first_packet_passes(self):
        """The first occurrence of a packet always passes the filter."""
        dedup = DeduplicationFilter(window=30.0)
        pkt = APRSPacket(
            raw="W3ADO-1>APRS:!4903.50N/07201.75W-",
            source="W3ADO-1",
            info_type="position",
        )
        assert not dedup.is_duplicate(pkt)

    def test_duplicate_within_window_dropped(self):
        """An identical packet (same source + info) within 30s is dropped."""
        dedup = DeduplicationFilter(window=30.0)
        pkt = APRSPacket(
            raw="W3ADO-1>APRS:!4903.50N/07201.75W-",
            source="W3ADO-1",
            info_type="position",
        )
        assert not dedup.is_duplicate(pkt)  # First time = passes
        assert dedup.is_duplicate(pkt)       # Same packet = duplicate

    def test_duplicate_after_window_passes(self):
        """An identical packet after the 30s window has elapsed passes through."""
        dedup = DeduplicationFilter(window=0.1)  # 100ms window
        pkt = APRSPacket(
            raw="W3ADO-1>APRS:!4903.50N/07201.75W-",
            source="W3ADO-1",
            info_type="position",
        )
        assert not dedup.is_duplicate(pkt)
        time.sleep(0.15)
        assert not dedup.is_duplicate(pkt)  # Window expired, passes again

    def test_different_source_same_info_passes(self):
        """Same info field from different source callsigns both pass."""
        dedup = DeduplicationFilter(window=30.0)
        pkt1 = APRSPacket(
            raw="W3ADO-1>APRS:!4903.50N/07201.75W-",
            source="W3ADO-1",
            info_type="position",
        )
        pkt2 = APRSPacket(
            raw="W3ADO-1>APRS:!4903.50N/07201.75W-",
            source="N0CALL",
            info_type="position",
        )
        assert not dedup.is_duplicate(pkt1)
        assert not dedup.is_duplicate(pkt2)

    def test_same_source_different_info_passes(self):
        """Different info fields from the same source both pass."""
        dedup = DeduplicationFilter(window=30.0)
        pkt1 = APRSPacket(
            raw="W3ADO-1>APRS:!4903.50N/07201.75W-",
            source="W3ADO-1",
            info_type="position",
        )
        pkt2 = APRSPacket(
            raw="W3ADO-1>APRS:>Monitoring 144.390MHz",
            source="W3ADO-1",
            info_type="status",
        )
        assert not dedup.is_duplicate(pkt1)
        assert not dedup.is_duplicate(pkt2)


# ==========================================================================
# Window behavior
# ==========================================================================

class TestDedupWindow:
    """30-second sliding window behavior."""

    def test_window_is_30_seconds(self):
        """The dedup window is exactly 30 seconds (configurable)."""
        dedup = DeduplicationFilter()
        assert dedup.window == 30.0

        dedup2 = DeduplicationFilter(window=60.0)
        assert dedup2.window == 60.0

    def test_expired_entries_cleaned_up(self):
        """Old entries are purged to prevent unbounded memory growth."""
        dedup = DeduplicationFilter(window=0.05)  # 50ms window
        # Add more than 1000 entries to trigger cleanup
        for i in range(1100):
            pkt = APRSPacket(raw=f"TEST>APRS:packet{i}", source="TEST")
            dedup.is_duplicate(pkt)
        # Wait for entries to expire
        time.sleep(0.1)
        # Trigger cleanup by adding one more (over the 1000 threshold)
        pkt = APRSPacket(raw="TEST>APRS:trigger", source="TEST")
        dedup.is_duplicate(pkt)
        # After cleanup, the _seen dict should have only unexpired entries
        assert len(dedup._seen) < 1100

    def test_window_boundary_exact(self):
        """A packet arriving at exactly 30.0 seconds after the first should pass."""
        dedup = DeduplicationFilter(window=0.1)  # Use short window for testing
        pkt = APRSPacket(raw="TEST>APRS:boundary", source="TEST")
        assert not dedup.is_duplicate(pkt)

        # Manipulate the timestamp to be exactly at the window boundary
        key = dedup._make_key(pkt)
        now = time.monotonic()
        dedup._seen[key] = now - 0.1  # Exactly at window boundary

        # At exactly the window boundary (now - seen == window), should pass
        assert not dedup.is_duplicate(pkt)


# ==========================================================================
# Dual-transport scenarios
# ==========================================================================

class TestDedupDualMode:
    """Dedup with packets arriving on different transports."""

    def test_same_packet_two_transports_deduped(self):
        """The same packet arriving on KISS and APRS-IS within 30s is deduplicated;
        only the first arrival passes."""
        dedup = DeduplicationFilter(window=30.0)
        # Same raw content, different transport tags
        pkt_kiss = APRSPacket(
            raw="W3ADO-1>APRS:!4903.50N/07201.75W-",
            source="W3ADO-1",
            info_type="position",
            transport="KISS",
        )
        pkt_aprs_is = APRSPacket(
            raw="W3ADO-1>APRS:!4903.50N/07201.75W-",
            source="W3ADO-1",
            info_type="position",
            transport="APRS-IS",
        )
        assert not dedup.is_duplicate(pkt_kiss)   # First arrival passes
        assert dedup.is_duplicate(pkt_aprs_is)     # Same content = duplicate

    def test_dedup_records_first_transport(self):
        """The packet that passes retains the transport tag of its first arrival."""
        dedup = DeduplicationFilter(window=30.0)
        pkt_kiss = APRSPacket(
            raw="W3ADO-1>APRS:!4903.50N/07201.75W-",
            source="W3ADO-1",
            info_type="position",
            transport="KISS",
        )
        pkt_aprs_is = APRSPacket(
            raw="W3ADO-1>APRS:!4903.50N/07201.75W-",
            source="W3ADO-1",
            info_type="position",
            transport="APRS-IS",
        )
        # First one passes - it retains its transport tag
        assert not dedup.is_duplicate(pkt_kiss)
        assert pkt_kiss.transport == "KISS"
        # Second one is dropped
        assert dedup.is_duplicate(pkt_aprs_is)

    def test_high_volume_dedup_performance(self):
        """Dedup handles 100 unique packets/sec without measurable latency."""
        dedup = DeduplicationFilter(window=30.0)
        start = time.monotonic()
        for i in range(1000):
            pkt = APRSPacket(
                raw=f"W3ADO-{i}>APRS:!4903.50N/07201.75W-packet{i}",
                source=f"W3ADO-{i}",
                info_type="position",
            )
            dedup.is_duplicate(pkt)
        elapsed = time.monotonic() - start
        # 1000 packets should complete well under 1 second
        assert elapsed < 1.0


# ==========================================================================
# Edge cases
# ==========================================================================

class TestDedupEdgeCases:
    """Edge cases for dedup filter."""

    def test_empty_info_field(self):
        """Packets with empty info fields are still deduped by source."""
        dedup = DeduplicationFilter(window=30.0)
        pkt1 = APRSPacket(raw="", source="W3ADO-1")
        pkt2 = APRSPacket(raw="", source="W3ADO-1")
        assert not dedup.is_duplicate(pkt1)
        assert dedup.is_duplicate(pkt2)

    def test_parse_error_packets_not_deduped(self):
        """Packets with parse errors are not deduped (always pass through),
        since we can't reliably extract a dedup key."""
        dedup = DeduplicationFilter(window=30.0)
        pkt = APRSPacket(
            raw="INVALID>APRS:!!!BAD!!!",
            source="INVALID",
            parse_error="Unable to parse",
        )
        assert not dedup.is_duplicate(pkt)
        assert not dedup.is_duplicate(pkt)  # Should still pass (never deduped)
        assert not dedup.is_duplicate(pkt)  # Always passes

    def test_filter_reset(self):
        """Calling reset() clears all state; previously-seen packets pass again."""
        dedup = DeduplicationFilter(window=30.0)
        pkt = APRSPacket(
            raw="W3ADO-1>APRS:!4903.50N/07201.75W-",
            source="W3ADO-1",
            info_type="position",
        )
        assert not dedup.is_duplicate(pkt)
        assert dedup.is_duplicate(pkt)  # Duplicate
        dedup.reset()
        assert not dedup.is_duplicate(pkt)  # Passes again after reset
