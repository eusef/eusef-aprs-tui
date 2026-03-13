"""Tests for beacon timer and position generation (core/beacon.py).

Covers: Issue #17 - Beacon timer + position transmission
Sprint: 3 (Station List + Beaconing)
PRD refs: AC-09 (beaconing - interval, format, toggle without restart)

Module under test: aprs_tui.core.beacon
Estimated implementation: ~80-120 lines

The beacon module:
- Fires a position beacon at the configured interval
- Uses the encoder to build the position packet
- Supports runtime toggle (on/off) without app restart
- Respects minimum interval of 60 seconds (APRS courtesy)
"""
from __future__ import annotations

import pytest


# ==========================================================================
# Beacon interval
# ==========================================================================

class TestBeaconInterval:
    """Beacon fires at the configured interval."""

    @pytest.mark.skip(reason="Sprint 3: Not implemented yet")
    def test_beacon_fires_at_interval(self):
        """Beacon fires after the configured number of seconds."""
        pass

    @pytest.mark.skip(reason="Sprint 3: Not implemented yet")
    def test_beacon_fires_repeatedly(self):
        """Beacon continues to fire at each interval, not just once."""
        pass

    @pytest.mark.skip(reason="Sprint 3: Not implemented yet")
    def test_beacon_default_interval_600(self):
        """Default beacon interval is 600 seconds (10 minutes)."""
        pass

    @pytest.mark.skip(reason="Sprint 3: Not implemented yet")
    def test_beacon_minimum_interval_60(self):
        """Beacon interval cannot be set below 60 seconds."""
        pass

    @pytest.mark.skip(reason="Sprint 3: Not implemented yet")
    def test_beacon_first_fires_immediately_option(self):
        """Beacon optionally fires immediately on start (before first interval)."""
        pass


# ==========================================================================
# Beacon position format (AC-09)
# ==========================================================================

class TestBeaconPositionFormat:
    """The beacon transmits correctly formatted position packets."""

    @pytest.mark.skip(reason="Sprint 3: Not implemented yet")
    def test_beacon_uses_configured_callsign(self):
        """Beacon source callsign matches station config."""
        pass

    @pytest.mark.skip(reason="Sprint 3: Not implemented yet")
    def test_beacon_uses_configured_position(self):
        """Beacon lat/lon matches the configured beacon position."""
        pass

    @pytest.mark.skip(reason="Sprint 3: Not implemented yet")
    def test_beacon_uses_configured_symbol(self):
        """Beacon symbol table and code match config."""
        pass

    @pytest.mark.skip(reason="Sprint 3: Not implemented yet")
    def test_beacon_uses_configured_comment(self):
        """Beacon comment text matches config."""
        pass

    @pytest.mark.skip(reason="Sprint 3: Not implemented yet")
    def test_beacon_packet_parseable(self):
        """The generated beacon packet can be parsed by aprslib.parse()."""
        pass


# ==========================================================================
# Toggle behavior (AC-09: toggle without restart)
# ==========================================================================

class TestBeaconToggle:
    """Runtime beacon enable/disable without restarting the app."""

    @pytest.mark.skip(reason="Sprint 3: Not implemented yet")
    def test_beacon_disabled_by_default(self):
        """When beacon.enabled=false, no beacons are transmitted."""
        pass

    @pytest.mark.skip(reason="Sprint 3: Not implemented yet")
    def test_beacon_enable_at_runtime(self):
        """Enabling beacon at runtime starts the beacon timer."""
        pass

    @pytest.mark.skip(reason="Sprint 3: Not implemented yet")
    def test_beacon_disable_at_runtime(self):
        """Disabling beacon at runtime stops the timer; no more beacons sent."""
        pass

    @pytest.mark.skip(reason="Sprint 3: Not implemented yet")
    def test_beacon_re_enable_resets_timer(self):
        """Re-enabling beacon after disable starts a fresh interval."""
        pass


# ==========================================================================
# Transport interaction
# ==========================================================================

class TestBeaconTransport:
    """Beacon sends packets through the correct transport."""

    @pytest.mark.skip(reason="Sprint 3: Not implemented yet")
    def test_beacon_sends_via_kiss_transport(self):
        """When connected via KISS, beacon sends as AX.25 KISS frame."""
        pass

    @pytest.mark.skip(reason="Sprint 3: Not implemented yet")
    def test_beacon_sends_via_aprs_is(self):
        """When connected via APRS-IS, beacon sends as text line."""
        pass

    @pytest.mark.skip(reason="Sprint 3: Not implemented yet")
    def test_beacon_not_sent_when_disconnected(self):
        """Beacon timer fires but no packet is sent if not connected."""
        pass

    @pytest.mark.skip(reason="Sprint 3: Not implemented yet")
    def test_beacon_increments_tx_counter(self):
        """Each beacon transmission increments the TX packet counter."""
        pass
