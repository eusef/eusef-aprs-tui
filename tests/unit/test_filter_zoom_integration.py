"""Integration tests: MapFilters + AutoZoomController.

Proves that filtering stations changes the auto-zoom viewport —
i.e., the caller (MapPanel) can pass filters.filter_stations(all_stations)
to controller.update() and get a viewport scoped to the visible set.

GitHub issue #61.
"""
from __future__ import annotations

import time

from aprs_tui.core.station_tracker import StationRecord
from aprs_tui.map.auto_zoom import AutoZoomController, calculate_auto_zoom
from aprs_tui.map.filters import MapFilters

OWN_LAT = 45.0
OWN_LON = -122.0
WIDTH = 160
HEIGHT = 80


def _make_station(
    callsign: str,
    lat: float,
    lon: float,
    *,
    sources: set[str] | None = None,
    symbol_table: str | None = None,
    symbol_code: str | None = None,
) -> StationRecord:
    """Build a positioned StationRecord with sensible defaults."""
    stn = StationRecord(callsign=callsign)
    stn.latitude = lat
    stn.longitude = lon
    stn.last_heard = time.monotonic()
    stn.position_history = [(lat, lon, time.time())]
    if sources is not None:
        stn.sources = sources
    if symbol_table is not None:
        stn.symbol_table = symbol_table
    if symbol_code is not None:
        stn.symbol_code = symbol_code
    return stn


def _fresh_controller() -> AutoZoomController:
    """Create a fresh controller with no smoothing history."""
    return AutoZoomController(
        own_lat=OWN_LAT,
        own_lon=OWN_LON,
        panel_width_dots=WIDTH,
        panel_height_dots=HEIGHT,
    )


# ---------------------------------------------------------------------------
# Core integration: hiding IS stations contracts the viewport
# ---------------------------------------------------------------------------


class TestHidingISStationsContractsViewport:
    """When far-away IS-only stations are hidden, the viewport should zoom in."""

    def test_hiding_is_stations_contracts_viewport(self) -> None:
        # RF station nearby, IS station far away
        rf_station = _make_station(
            "RF1", 45.5, -121.5, sources={"KISS TCP"},
        )
        is_station = _make_station(
            "IS1", 35.0, -118.0, sources={"APRS-IS"},
        )
        all_stations = [rf_station, is_station]

        filters = MapFilters()

        # All stations visible — viewport must cover the distant IS station
        ctrl_all = _fresh_controller()
        all_result = ctrl_all.update(filters.filter_stations(all_stations))
        assert all_result is not None

        # Hide IS stations
        filters.toggle_is()
        rf_only = filters.filter_stations(all_stations)
        assert len(rf_only) == 1  # only RF station passes

        # Fresh controller (no smoothing carry-over) with RF-only list
        ctrl_rf = _fresh_controller()
        rf_result = ctrl_rf.update(rf_only)
        assert rf_result is not None

        # With only the nearby RF station, zoom should be higher (more zoomed in)
        assert rf_result[2] >= all_result[2], (
            f"Expected RF-only zoom ({rf_result[2]}) >= all-stations zoom ({all_result[2]})"
        )


# ---------------------------------------------------------------------------
# Hiding RF stations shows only IS stations
# ---------------------------------------------------------------------------


class TestHidingRFStationsShowsOnlyIS:
    """When RF stations are hidden, the viewport adjusts to IS-only stations."""

    def test_hiding_rf_stations_shows_only_is(self) -> None:
        # RF station far away, IS station nearby
        rf_station = _make_station(
            "RF1", 55.0, -130.0, sources={"KISS TCP"},
        )
        is_station = _make_station(
            "IS1", 45.2, -121.8, sources={"APRS-IS"},
        )
        all_stations = [rf_station, is_station]

        filters = MapFilters()

        # All stations visible
        ctrl_all = _fresh_controller()
        all_result = ctrl_all.update(filters.filter_stations(all_stations))
        assert all_result is not None

        # Hide RF stations
        filters.toggle_rf()
        is_only = filters.filter_stations(all_stations)
        assert len(is_only) == 1  # only IS station passes

        # Fresh controller with IS-only list
        ctrl_is = _fresh_controller()
        is_result = ctrl_is.update(is_only)
        assert is_result is not None

        # IS station is nearby, so zoom should be higher (more zoomed in)
        assert is_result[2] >= all_result[2], (
            f"Expected IS-only zoom ({is_result[2]}) >= all-stations zoom ({all_result[2]})"
        )


# ---------------------------------------------------------------------------
# filter_stations then update — uses the filtered list
# ---------------------------------------------------------------------------


class TestFilterThenAutoZoomUsesFilteredList:
    """Passing filter_stations() output to update() gives the same result
    as calling calculate_auto_zoom() with the same filtered list."""

    def test_filter_then_autozoom_uses_filtered_list(self) -> None:
        rf1 = _make_station("RF1", 45.5, -121.5, sources={"KISS TCP"})
        rf2 = _make_station("RF2", 46.0, -121.0, sources={"KISS TCP"})
        is1 = _make_station("IS1", 35.0, -118.0, sources={"APRS-IS"})
        all_stations = [rf1, rf2, is1]

        filters = MapFilters()
        filters.toggle_is()  # hide IS
        filtered = filters.filter_stations(all_stations)

        # Via controller
        ctrl = _fresh_controller()
        ctrl_result = ctrl.update(filtered)
        assert ctrl_result is not None

        # Via raw function with the same filtered list
        raw_result = calculate_auto_zoom(
            filtered, OWN_LAT, OWN_LON, WIDTH, HEIGHT,
        )

        # First update on a fresh controller has no smoothing, so results match
        assert ctrl_result[0] == raw_result[0]
        assert ctrl_result[1] == raw_result[1]
        assert ctrl_result[2] == raw_result[2]


# ---------------------------------------------------------------------------
# All stations filtered out → default zoom
# ---------------------------------------------------------------------------


class TestAllStationsFilteredReturnsDefaultZoom:
    """When every station is filtered out, the controller returns the default
    viewport centered on own position."""

    def test_all_stations_filtered_returns_default_zoom(self) -> None:
        # Only IS stations, then hide IS
        is1 = _make_station("IS1", 35.0, -118.0, sources={"APRS-IS"})
        is2 = _make_station("IS2", 40.0, -100.0, sources={"APRS-IS"})
        all_stations = [is1, is2]

        filters = MapFilters()
        filters.toggle_is()  # hide all IS
        filtered = filters.filter_stations(all_stations)
        assert len(filtered) == 0

        ctrl = _fresh_controller()
        result = ctrl.update(filtered)
        assert result is not None

        # Empty filtered list → own position, default zoom
        assert result[0] == OWN_LAT
        assert result[1] == OWN_LON
        assert result[2] == 10.0  # default_zoom

    def test_hide_both_rf_and_is_returns_default(self) -> None:
        rf1 = _make_station("RF1", 46.0, -121.0, sources={"KISS TCP"})
        is1 = _make_station("IS1", 35.0, -118.0, sources={"APRS-IS"})
        all_stations = [rf1, is1]

        filters = MapFilters()
        filters.toggle_is()
        filters.toggle_rf()
        filtered = filters.filter_stations(all_stations)
        assert len(filtered) == 0

        ctrl = _fresh_controller()
        result = ctrl.update(filtered)
        assert result is not None
        assert result[0] == OWN_LAT
        assert result[1] == OWN_LON
        assert result[2] == 10.0


# ---------------------------------------------------------------------------
# Filter status text reflects counts after filter
# ---------------------------------------------------------------------------


class TestFilterStatusTextReflectsCountsAfterFilter:
    """status_text() shows accurate counts matching what filter_stations() returns."""

    def test_filter_status_text_reflects_counts_after_filter(self) -> None:
        rf1 = _make_station("RF1", 45.5, -121.5, sources={"KISS TCP"})
        rf2 = _make_station("RF2", 46.0, -121.0, sources={"KISS TCP"})
        is1 = _make_station("IS1", 35.0, -118.0, sources={"APRS-IS"})
        is2 = _make_station("IS2", 40.0, -100.0, sources={"APRS-IS"})
        all_stations = [rf1, rf2, is1, is2]

        filters = MapFilters()

        # All visible
        text = filters.status_text(all_stations)
        assert "RF:2" in text
        assert "IS:2" in text

        # Hide IS
        filters.toggle_is()
        text = filters.status_text(all_stations)
        assert "IS:hidden" in text
        assert "RF:2" in text

        # Also hide RF
        filters.toggle_rf()
        text = filters.status_text(all_stations)
        assert "RF:hidden" in text
        assert "IS:hidden" in text

    def test_status_counts_match_filtered_station_count(self) -> None:
        """The counts in status_text should match len(filter_stations())."""
        rf1 = _make_station("RF1", 45.5, -121.5, sources={"KISS TCP"})
        is1 = _make_station("IS1", 35.0, -118.0, sources={"APRS-IS"})
        all_stations = [rf1, is1]

        filters = MapFilters()
        filtered = filters.filter_stations(all_stations)
        assert len(filtered) == 2

        filters.toggle_is()
        filtered = filters.filter_stations(all_stations)
        assert len(filtered) == 1

        # The remaining station should be RF
        text = filters.status_text(all_stations)
        assert "RF:1" in text
        assert "IS:hidden" in text


# ---------------------------------------------------------------------------
# WX and Digi filters interact with auto-zoom
# ---------------------------------------------------------------------------


class TestWXAndDigiFiltersAffectZoom:
    """Hiding weather or digipeater stations also affects the auto-zoom viewport."""

    def test_hiding_wx_station_changes_viewport(self) -> None:
        # WX station far away, regular station nearby
        wx_station = _make_station(
            "WX1", 30.0, -110.0,
            sources={"APRS-IS"},
            symbol_table="/",
            symbol_code="_",
        )
        regular = _make_station("REG1", 45.2, -121.8, sources={"APRS-IS"})
        all_stations = [wx_station, regular]

        filters = MapFilters()

        ctrl_all = _fresh_controller()
        all_result = ctrl_all.update(filters.filter_stations(all_stations))
        assert all_result is not None

        filters.toggle_wx()
        filtered = filters.filter_stations(all_stations)
        assert len(filtered) == 1  # only regular passes

        ctrl_filtered = _fresh_controller()
        filtered_result = ctrl_filtered.update(filtered)
        assert filtered_result is not None

        # Without distant WX station, should zoom in more
        assert filtered_result[2] >= all_result[2]

    def test_hiding_digi_station_changes_viewport(self) -> None:
        # Digi station far away, regular station nearby
        digi_station = _make_station(
            "DIGI1", 30.0, -110.0,
            sources={"APRS-IS"},
            symbol_table="/",
            symbol_code="#",  # digipeater symbol
        )
        regular = _make_station("REG1", 45.2, -121.8, sources={"APRS-IS"})
        all_stations = [digi_station, regular]

        filters = MapFilters()

        ctrl_all = _fresh_controller()
        all_result = ctrl_all.update(filters.filter_stations(all_stations))
        assert all_result is not None

        filters.toggle_digi()
        filtered = filters.filter_stations(all_stations)
        assert len(filtered) == 1

        ctrl_filtered = _fresh_controller()
        filtered_result = ctrl_filtered.update(filtered)
        assert filtered_result is not None

        assert filtered_result[2] >= all_result[2]


# ---------------------------------------------------------------------------
# Re-enabling a filter expands the viewport back
# ---------------------------------------------------------------------------


class TestReEnablingFilterExpandsViewport:
    """Toggling a filter off then on again restores the original viewport."""

    def test_toggle_is_off_then_on_restores_viewport(self) -> None:
        rf_station = _make_station("RF1", 45.5, -121.5, sources={"KISS TCP"})
        is_station = _make_station("IS1", 35.0, -118.0, sources={"APRS-IS"})
        all_stations = [rf_station, is_station]

        filters = MapFilters()

        # Original viewport with all stations
        ctrl1 = _fresh_controller()
        original = ctrl1.update(filters.filter_stations(all_stations))
        assert original is not None

        # Hide IS, get contracted viewport
        filters.toggle_is()
        ctrl2 = _fresh_controller()
        contracted = ctrl2.update(filters.filter_stations(all_stations))
        assert contracted is not None
        assert contracted[2] >= original[2]

        # Show IS again, viewport should match original
        filters.toggle_is()
        ctrl3 = _fresh_controller()
        restored = ctrl3.update(filters.filter_stations(all_stations))
        assert restored is not None

        assert abs(restored[0] - original[0]) < 1e-9
        assert abs(restored[1] - original[1]) < 1e-9
        assert abs(restored[2] - original[2]) < 1e-9
