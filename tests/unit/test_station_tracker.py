"""Tests for station tracking (core/station_tracker.py).

Covers: Issue #14 - Station Tracker (heard table, distance calc)
Sprint: 3 (Station List + Beaconing)
PRD refs: Station panel shows heard stations with distance.

Module under test: aprs_tui.core.station_tracker
Estimated implementation: ~100-150 lines

The station tracker maintains a table of all heard stations with:
- Callsign
- Last-heard timestamp
- Last-known position (lat/lon)
- Distance from own station (Haversine)
- Packet count
- Last info type (position, mic-e, etc.)
"""
from __future__ import annotations

import pytest


# ==========================================================================
# Station add and update
# ==========================================================================

class TestStationAddUpdate:
    """Adding and updating stations in the heard table."""

    @pytest.mark.skip(reason="Sprint 3: Not implemented yet")
    def test_add_new_station(self):
        """A position packet from a new callsign creates a new station entry."""
        pass

    @pytest.mark.skip(reason="Sprint 3: Not implemented yet")
    def test_update_existing_station(self):
        """A second position packet from a known callsign updates position
        and last-heard timestamp."""
        pass

    @pytest.mark.skip(reason="Sprint 3: Not implemented yet")
    def test_packet_count_incremented(self):
        """Each packet from a station increments its packet count."""
        pass

    @pytest.mark.skip(reason="Sprint 3: Not implemented yet")
    def test_non_position_packet_updates_last_heard(self):
        """A status or message packet from a known station updates last-heard
        but does not change the position."""
        pass

    @pytest.mark.skip(reason="Sprint 3: Not implemented yet")
    def test_mic_e_packet_updates_position(self):
        """A Mic-E packet is treated as a position source."""
        pass

    @pytest.mark.skip(reason="Sprint 3: Not implemented yet")
    def test_station_list_returns_all_stations(self):
        """get_stations() returns all tracked stations."""
        pass

    @pytest.mark.skip(reason="Sprint 3: Not implemented yet")
    def test_station_list_sortable_by_last_heard(self):
        """Stations can be sorted by last-heard timestamp."""
        pass

    @pytest.mark.skip(reason="Sprint 3: Not implemented yet")
    def test_station_list_sortable_by_distance(self):
        """Stations can be sorted by distance from own station."""
        pass

    @pytest.mark.skip(reason="Sprint 3: Not implemented yet")
    def test_station_list_sortable_by_callsign(self):
        """Stations can be sorted alphabetically by callsign."""
        pass


# ==========================================================================
# Distance calculation
# ==========================================================================

class TestDistanceCalc:
    """Haversine distance calculation between own station and heard stations."""

    @pytest.mark.skip(reason="Sprint 3: Not implemented yet")
    def test_distance_same_point(self):
        """Distance from a point to itself is 0."""
        pass

    @pytest.mark.skip(reason="Sprint 3: Not implemented yet")
    def test_distance_known_points(self):
        """Distance between two known coordinates matches expected value
        (within 1% tolerance for Haversine approximation)."""
        pass

    @pytest.mark.skip(reason="Sprint 3: Not implemented yet")
    def test_distance_antipodal_points(self):
        """Distance between antipodal points is approximately 20,000 km."""
        pass

    @pytest.mark.skip(reason="Sprint 3: Not implemented yet")
    def test_distance_returns_none_without_own_position(self):
        """If own station position is not configured, distance is None."""
        pass

    @pytest.mark.skip(reason="Sprint 3: Not implemented yet")
    def test_distance_returns_none_without_station_position(self):
        """If a heard station has no position, distance is None."""
        pass

    @pytest.mark.skip(reason="Sprint 3: Not implemented yet")
    def test_distance_updates_on_position_change(self):
        """When a station's position changes, distance is recalculated."""
        pass

    @pytest.mark.skip(reason="Sprint 3: Not implemented yet")
    def test_distance_units_kilometers(self):
        """Distance is returned in kilometers."""
        pass


# ==========================================================================
# Edge cases
# ==========================================================================

class TestStationTrackerEdgeCases:
    """Edge cases for station tracking."""

    @pytest.mark.skip(reason="Sprint 3: Not implemented yet")
    def test_parse_error_packet_still_tracks_callsign(self):
        """A packet with parse_error still registers the source callsign
        in the heard table (just without position)."""
        pass

    @pytest.mark.skip(reason="Sprint 3: Not implemented yet")
    def test_zero_lat_lon_treated_as_valid(self):
        """Position 0,0 (null island) is treated as a valid position."""
        pass

    @pytest.mark.skip(reason="Sprint 3: Not implemented yet")
    def test_station_timeout_optional(self):
        """Stations can optionally be removed after not being heard for N minutes."""
        pass
