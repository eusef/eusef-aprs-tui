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

from aprs_tui.core.station_tracker import (
    StationTracker,
    haversine,
    is_rf_station,
    is_is_only_station,
)
from aprs_tui.protocol.types import APRSPacket

# ==========================================================================
# Station add and update
# ==========================================================================


class TestStationAddUpdate:
    """Adding and updating stations in the heard table."""

    def test_add_new_station(self):
        """A position packet from a new callsign creates a new station entry."""
        tracker = StationTracker(own_lat=40.0, own_lon=-75.0)
        pkt = APRSPacket(
            raw="W3ADO-1>APRS:!4000.00N/07500.00W#",
            source="W3ADO-1",
            info_type="position",
            latitude=40.0,
            longitude=-75.0,
        )
        tracker.update(pkt)
        assert tracker.count == 1
        stn = tracker.get_station("W3ADO-1")
        assert stn is not None
        assert stn.callsign == "W3ADO-1"
        assert stn.latitude == 40.0
        assert stn.longitude == -75.0

    def test_update_existing_station(self):
        """A second position packet from a known callsign updates position
        and last-heard timestamp."""
        tracker = StationTracker(own_lat=40.0, own_lon=-75.0)
        pkt1 = APRSPacket(
            raw="W3ADO-1>APRS:!4000.00N/07500.00W#",
            source="W3ADO-1",
            info_type="position",
            latitude=40.0,
            longitude=-75.0,
        )
        tracker.update(pkt1)
        first_heard = tracker.get_station("W3ADO-1").last_heard

        pkt2 = APRSPacket(
            raw="W3ADO-1>APRS:!4010.00N/07510.00W#",
            source="W3ADO-1",
            info_type="position",
            latitude=40.1,
            longitude=-75.1,
        )
        tracker.update(pkt2)
        assert tracker.count == 1  # still one station
        stn = tracker.get_station("W3ADO-1")
        assert stn.latitude == 40.1
        assert stn.longitude == -75.1
        assert stn.last_heard >= first_heard

    def test_packet_count_incremented(self):
        """Each packet from a station increments its packet count."""
        tracker = StationTracker()
        for i in range(5):
            pkt = APRSPacket(
                raw=f"W3ADO-1>APRS:packet{i}",
                source="W3ADO-1",
                info_type="status",
            )
            tracker.update(pkt)
        stn = tracker.get_station("W3ADO-1")
        assert stn.packet_count == 5

    def test_non_position_packet_updates_last_heard(self):
        """A status or message packet from a known station updates last-heard
        but does not change the position."""
        tracker = StationTracker(own_lat=40.0, own_lon=-75.0)
        # First send a position packet
        pkt_pos = APRSPacket(
            raw="W3ADO-1>APRS:!4000.00N/07500.00W#",
            source="W3ADO-1",
            info_type="position",
            latitude=40.0,
            longitude=-75.0,
        )
        tracker.update(pkt_pos)

        # Then a status packet
        pkt_status = APRSPacket(
            raw="W3ADO-1>APRS:>status text",
            source="W3ADO-1",
            info_type="status",
            status_text="status text",
        )
        tracker.update(pkt_status)

        stn = tracker.get_station("W3ADO-1")
        assert stn.latitude == 40.0  # position unchanged
        assert stn.longitude == -75.0
        assert stn.packet_count == 2
        assert stn.last_info_type == "status"

    def test_mic_e_packet_updates_position(self):
        """A Mic-E packet is treated as a position source."""
        tracker = StationTracker(own_lat=40.0, own_lon=-75.0)
        pkt = APRSPacket(
            raw="W3ADO-1>T2SP0W:`...",
            source="W3ADO-1",
            info_type="mic-e",
            latitude=41.0,
            longitude=-76.0,
        )
        tracker.update(pkt)
        stn = tracker.get_station("W3ADO-1")
        assert stn.latitude == 41.0
        assert stn.longitude == -76.0
        assert stn.distance_km is not None

    def test_station_list_returns_all_stations(self):
        """get_stations() returns all tracked stations."""
        tracker = StationTracker()
        for call in ["W3ADO-1", "N3LLO-5", "KB3HTS-9"]:
            pkt = APRSPacket(raw=f"{call}>APRS:test", source=call, info_type="status")
            tracker.update(pkt)
        stations = tracker.get_stations()
        assert len(stations) == 3
        callsigns = {s.callsign for s in stations}
        assert callsigns == {"W3ADO-1", "N3LLO-5", "KB3HTS-9"}

    def test_station_list_sortable_by_last_heard(self):
        """Stations can be sorted by last-heard timestamp."""
        tracker = StationTracker()
        # Insert stations in order
        for call in ["FIRST", "SECOND", "THIRD"]:
            pkt = APRSPacket(raw=f"{call}>APRS:test", source=call, info_type="status")
            tracker.update(pkt)

        stations = tracker.get_stations(sort_by="last_heard")
        # Most recently heard first
        assert stations[0].callsign == "THIRD"
        assert stations[-1].callsign == "FIRST"

    def test_station_list_sortable_by_distance(self):
        """Stations can be sorted by distance from own station."""
        tracker = StationTracker(own_lat=40.0, own_lon=-75.0)
        # Close station
        pkt_close = APRSPacket(
            raw="CLOSE>APRS:pos",
            source="CLOSE",
            info_type="position",
            latitude=40.01,
            longitude=-75.01,
        )
        # Far station
        pkt_far = APRSPacket(
            raw="FAR>APRS:pos",
            source="FAR",
            info_type="position",
            latitude=42.0,
            longitude=-78.0,
        )
        tracker.update(pkt_far)
        tracker.update(pkt_close)

        stations = tracker.get_stations(sort_by="distance")
        assert stations[0].callsign == "CLOSE"
        assert stations[1].callsign == "FAR"

    def test_station_list_sortable_by_callsign(self):
        """Stations can be sorted alphabetically by callsign."""
        tracker = StationTracker()
        for call in ["ZULU", "ALPHA", "MIKE"]:
            pkt = APRSPacket(raw=f"{call}>APRS:test", source=call, info_type="status")
            tracker.update(pkt)

        stations = tracker.get_stations(sort_by="callsign")
        assert stations[0].callsign == "ALPHA"
        assert stations[1].callsign == "MIKE"
        assert stations[2].callsign == "ZULU"


# ==========================================================================
# Distance calculation
# ==========================================================================


class TestDistanceCalc:
    """Haversine distance calculation between own station and heard stations."""

    def test_distance_same_point(self):
        """Distance from a point to itself is 0."""
        dist = haversine(40.0, -75.0, 40.0, -75.0)
        assert dist == 0.0

    def test_distance_known_points(self):
        """Distance between two known coordinates matches expected value
        (within 1% tolerance for Haversine approximation)."""
        # New York to Los Angeles
        dist = haversine(40.7128, -74.0060, 34.0522, -118.2437)
        assert abs(dist - 3944) < 3944 * 0.01  # within 1%

    def test_distance_antipodal_points(self):
        """Distance between antipodal points is approximately 20,000 km."""
        # North pole to south pole
        dist = haversine(90.0, 0.0, -90.0, 0.0)
        assert abs(dist - 20015) < 20015 * 0.01  # within 1%

    def test_distance_returns_none_without_own_position(self):
        """If own station position is not configured, distance is None."""
        tracker = StationTracker()  # no own position
        pkt = APRSPacket(
            raw="W3ADO-1>APRS:pos",
            source="W3ADO-1",
            info_type="position",
            latitude=40.0,
            longitude=-75.0,
        )
        tracker.update(pkt)
        stn = tracker.get_station("W3ADO-1")
        assert stn.distance_km is None
        assert stn.bearing is None

    def test_distance_returns_none_without_station_position(self):
        """If a heard station has no position, distance is None."""
        tracker = StationTracker(own_lat=40.0, own_lon=-75.0)
        pkt = APRSPacket(
            raw="W3ADO-1>APRS:>status",
            source="W3ADO-1",
            info_type="status",
        )
        tracker.update(pkt)
        stn = tracker.get_station("W3ADO-1")
        assert stn.distance_km is None
        assert stn.bearing is None

    def test_distance_updates_on_position_change(self):
        """When a station's position changes, distance is recalculated."""
        tracker = StationTracker(own_lat=40.0, own_lon=-75.0)
        pkt1 = APRSPacket(
            raw="W3ADO-1>APRS:pos1",
            source="W3ADO-1",
            info_type="position",
            latitude=40.1,
            longitude=-75.1,
        )
        tracker.update(pkt1)
        dist1 = tracker.get_station("W3ADO-1").distance_km

        pkt2 = APRSPacket(
            raw="W3ADO-1>APRS:pos2",
            source="W3ADO-1",
            info_type="position",
            latitude=41.0,
            longitude=-76.0,
        )
        tracker.update(pkt2)
        dist2 = tracker.get_station("W3ADO-1").distance_km

        assert dist1 is not None
        assert dist2 is not None
        assert dist2 > dist1  # second position is farther away

    def test_distance_units_kilometers(self):
        """Distance is returned in kilometers."""
        tracker = StationTracker(own_lat=40.0, own_lon=-75.0)
        pkt = APRSPacket(
            raw="W3ADO-1>APRS:pos",
            source="W3ADO-1",
            info_type="position",
            latitude=40.1,
            longitude=-75.1,
        )
        tracker.update(pkt)
        stn = tracker.get_station("W3ADO-1")
        # ~13 km for 0.1 degrees at this latitude
        assert stn.distance_km is not None
        assert 10 < stn.distance_km < 20


# ==========================================================================
# Edge cases
# ==========================================================================


class TestStationTrackerEdgeCases:
    """Edge cases for station tracking."""

    def test_parse_error_packet_still_tracks_callsign(self):
        """A packet with parse_error still registers the source callsign
        in the heard table (just without position)."""
        tracker = StationTracker()
        pkt = APRSPacket(
            raw="W3ADO-1>APRS:garbled",
            source="W3ADO-1",
            info_type="unknown",
            parse_error="Could not parse",
        )
        tracker.update(pkt)
        assert tracker.count == 1
        stn = tracker.get_station("W3ADO-1")
        assert stn is not None
        assert stn.latitude is None
        assert stn.longitude is None

    def test_zero_lat_lon_treated_as_valid(self):
        """Position 0,0 (null island) is treated as a valid position."""
        tracker = StationTracker(own_lat=40.0, own_lon=-75.0)
        pkt = APRSPacket(
            raw="W3ADO-1>APRS:pos",
            source="W3ADO-1",
            info_type="position",
            latitude=0.0,
            longitude=0.0,
        )
        tracker.update(pkt)
        stn = tracker.get_station("W3ADO-1")
        assert stn.latitude == 0.0
        assert stn.longitude == 0.0
        assert stn.distance_km is not None

    def test_station_timeout_optional(self):
        """Stations can optionally be removed after not being heard for N minutes.
        Since timeout is not yet implemented, just verify that stations persist
        indefinitely by default."""
        tracker = StationTracker()
        pkt = APRSPacket(
            raw="W3ADO-1>APRS:test",
            source="W3ADO-1",
            info_type="status",
        )
        tracker.update(pkt)
        # Station should still be there (no timeout implemented)
        assert tracker.count == 1
        assert tracker.get_station("W3ADO-1") is not None


# ==========================================================================
# Transport source tracking
# ==========================================================================


class TestTransportSourceTracking:
    """Issue #54: Track transport source and position history."""

    def test_rf_source_recorded(self):
        """Station heard via RF transport has source recorded."""
        tracker = StationTracker()
        pkt = APRSPacket(
            raw="W3ADO-1>APRS:pos",
            source="W3ADO-1",
            info_type="position",
            latitude=40.0,
            longitude=-75.0,
            transport="KISS TCP",
        )
        tracker.update(pkt)
        stn = tracker.get_station("W3ADO-1")
        assert "KISS TCP" in stn.sources

    def test_is_source_recorded(self):
        """Station heard via APRS-IS has source recorded."""
        tracker = StationTracker()
        pkt = APRSPacket(
            raw="W3ADO-1>APRS:pos",
            source="W3ADO-1",
            info_type="position",
            latitude=40.0,
            longitude=-75.0,
            transport="APRS-IS",
        )
        tracker.update(pkt)
        stn = tracker.get_station("W3ADO-1")
        assert "APRS-IS" in stn.sources

    def test_both_sources_recorded(self):
        """Station heard via both RF and IS has both sources."""
        tracker = StationTracker()
        pkt_rf = APRSPacket(
            raw="W3ADO-1>APRS:pos",
            source="W3ADO-1",
            info_type="position",
            latitude=40.0,
            longitude=-75.0,
            transport="KISS TCP",
        )
        pkt_is = APRSPacket(
            raw="W3ADO-1>APRS:pos",
            source="W3ADO-1",
            info_type="position",
            latitude=40.0,
            longitude=-75.0,
            transport="APRS-IS",
        )
        tracker.update(pkt_rf)
        tracker.update(pkt_is)
        stn = tracker.get_station("W3ADO-1")
        assert stn.sources == {"KISS TCP", "APRS-IS"}

    def test_empty_transport_not_added(self):
        """Packets with empty transport string don't add empty string to sources."""
        tracker = StationTracker()
        pkt = APRSPacket(
            raw="W3ADO-1>APRS:test",
            source="W3ADO-1",
            info_type="status",
            transport="",
        )
        tracker.update(pkt)
        stn = tracker.get_station("W3ADO-1")
        assert len(stn.sources) == 0

    def test_is_rf_station(self):
        """is_rf_station returns True for RF-heard stations."""
        tracker = StationTracker()
        pkt = APRSPacket(
            raw="W3ADO-1>APRS:pos",
            source="W3ADO-1",
            info_type="position",
            latitude=40.0,
            longitude=-75.0,
            transport="KISS TCP",
        )
        tracker.update(pkt)
        stn = tracker.get_station("W3ADO-1")
        assert is_rf_station(stn) is True
        assert is_is_only_station(stn) is False

    def test_is_is_only_station(self):
        """is_is_only_station returns True for IS-only stations."""
        tracker = StationTracker()
        pkt = APRSPacket(
            raw="W3ADO-1>APRS:pos",
            source="W3ADO-1",
            info_type="position",
            latitude=40.0,
            longitude=-75.0,
            transport="APRS-IS",
        )
        tracker.update(pkt)
        stn = tracker.get_station("W3ADO-1")
        assert is_rf_station(stn) is False
        assert is_is_only_station(stn) is True

    def test_both_sources_classified_as_rf(self):
        """Station heard on both RF and IS is classified as RF."""
        tracker = StationTracker()
        for transport in ("KISS TCP", "APRS-IS"):
            pkt = APRSPacket(
                raw="W3ADO-1>APRS:pos",
                source="W3ADO-1",
                info_type="position",
                latitude=40.0,
                longitude=-75.0,
                transport=transport,
            )
            tracker.update(pkt)
        stn = tracker.get_station("W3ADO-1")
        assert is_rf_station(stn) is True
        assert is_is_only_station(stn) is False


# ==========================================================================
# Position history
# ==========================================================================


class TestPositionHistory:
    """Issue #54: Position history for track/trail rendering."""

    def test_position_history_appended_on_change(self):
        """Position history appends when lat/lon changes."""
        tracker = StationTracker()
        positions = [(40.0, -75.0), (40.1, -75.1), (40.2, -75.2)]
        for lat, lon in positions:
            pkt = APRSPacket(
                raw="W3ADO-1>APRS:pos",
                source="W3ADO-1",
                info_type="position",
                latitude=lat,
                longitude=lon,
            )
            tracker.update(pkt)
        stn = tracker.get_station("W3ADO-1")
        assert len(stn.position_history) == 3
        assert stn.position_history[0][0] == 40.0
        assert stn.position_history[2][0] == 40.2

    def test_position_history_not_appended_when_same(self):
        """Position history does NOT append when position stays the same."""
        tracker = StationTracker()
        for _ in range(5):
            pkt = APRSPacket(
                raw="W3ADO-1>APRS:pos",
                source="W3ADO-1",
                info_type="position",
                latitude=40.0,
                longitude=-75.0,
            )
            tracker.update(pkt)
        stn = tracker.get_station("W3ADO-1")
        # First packet creates history entry (lat/lon was None -> 40.0),
        # subsequent same-position packets do not
        assert len(stn.position_history) == 1

    def test_position_history_capped(self):
        """Position history respects max_track_points."""
        tracker = StationTracker(max_track_points=5)
        for i in range(10):
            pkt = APRSPacket(
                raw="W3ADO-1>APRS:pos",
                source="W3ADO-1",
                info_type="position",
                latitude=40.0 + i * 0.01,
                longitude=-75.0,
            )
            tracker.update(pkt)
        stn = tracker.get_station("W3ADO-1")
        assert len(stn.position_history) == 5
        # Should have the 5 most recent positions
        assert stn.position_history[0][0] == 40.05

    def test_position_history_has_timestamps(self):
        """Position history entries contain timestamps."""
        tracker = StationTracker()
        pkt = APRSPacket(
            raw="W3ADO-1>APRS:pos",
            source="W3ADO-1",
            info_type="position",
            latitude=40.0,
            longitude=-75.0,
        )
        tracker.update(pkt)
        stn = tracker.get_station("W3ADO-1")
        assert len(stn.position_history) == 1
        lat, lon, ts = stn.position_history[0]
        assert lat == 40.0
        assert lon == -75.0
        assert ts > 0  # valid timestamp

    def test_non_position_packet_no_history(self):
        """Status packets do not create position history entries."""
        tracker = StationTracker()
        pkt = APRSPacket(
            raw="W3ADO-1>APRS:>status",
            source="W3ADO-1",
            info_type="status",
        )
        tracker.update(pkt)
        stn = tracker.get_station("W3ADO-1")
        assert len(stn.position_history) == 0
