"""Tests for aprs_tui.map.filters.MapFilters."""
from __future__ import annotations

from aprs_tui.core.station_tracker import StationRecord
from aprs_tui.map.filters import MapFilters


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_station(
    callsign: str = "N0CALL",
    sources: set[str] | None = None,
    symbol_table: str | None = "/",
    symbol_code: str | None = ">",
    latitude: float | None = 40.0,
    longitude: float | None = -105.0,
) -> StationRecord:
    """Create a StationRecord with sensible defaults for filter testing."""
    return StationRecord(
        callsign=callsign,
        sources=sources if sources is not None else set(),
        symbol_table=symbol_table,
        symbol_code=symbol_code,
        latitude=latitude,
        longitude=longitude,
    )


def _rf_station(callsign: str = "RF1") -> StationRecord:
    return _make_station(callsign=callsign, sources={"KISS-TNC"})


def _is_station(callsign: str = "IS1") -> StationRecord:
    return _make_station(callsign=callsign, sources={"APRS-IS"})


def _mixed_station(callsign: str = "MIX1") -> StationRecord:
    return _make_station(callsign=callsign, sources={"KISS-TNC", "APRS-IS"})


def _wx_station(callsign: str = "WX1", sources: set[str] | None = None) -> StationRecord:
    return _make_station(
        callsign=callsign,
        sources=sources if sources is not None else {"APRS-IS"},
        symbol_table="/",
        symbol_code="_",
    )


def _digi_station(callsign: str = "DIGI1", sources: set[str] | None = None) -> StationRecord:
    return _make_station(
        callsign=callsign,
        sources=sources if sources is not None else {"KISS-TNC"},
        symbol_table="/",
        symbol_code="#",
    )


def _igate_station(callsign: str = "IGATE1", sources: set[str] | None = None) -> StationRecord:
    return _make_station(
        callsign=callsign,
        sources=sources if sources is not None else {"APRS-IS"},
        symbol_table="/",
        symbol_code="&",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestDefaults:
    def test_default_all_visible(self) -> None:
        f = MapFilters()
        assert f.show_is_stations is True
        assert f.show_rf_stations is True
        assert f.show_wx_stations is True
        assert f.show_digi_stations is True
        assert f.show_tracks is True


class TestToggleIS:
    def test_toggle_is_hides_is_only_stations(self) -> None:
        f = MapFilters()
        stations = [_rf_station(), _is_station(), _mixed_station()]
        f.toggle_is()
        result = f.filter_stations(stations)
        callsigns = {s.callsign for s in result}
        assert "IS1" not in callsigns
        assert "RF1" in callsigns
        # Mixed station has RF source, so it is NOT is_only → should remain
        assert "MIX1" in callsigns

    def test_mixed_source_station_not_hidden_by_is_toggle(self) -> None:
        """A station heard on both RF and IS is NOT is_only, so hiding IS keeps it."""
        f = MapFilters()
        f.toggle_is()
        mixed = _mixed_station("BOTH1")
        result = f.filter_stations([mixed])
        # mixed station is_rf_station → True, is_is_only → False
        # But show_rf_stations is still True, so it should pass
        assert len(result) == 1
        assert result[0].callsign == "BOTH1"


class TestToggleRF:
    def test_toggle_rf_hides_rf_stations(self) -> None:
        f = MapFilters()
        stations = [_rf_station(), _is_station()]
        f.toggle_rf()
        result = f.filter_stations(stations)
        callsigns = {s.callsign for s in result}
        assert "RF1" not in callsigns
        assert "IS1" in callsigns


class TestToggleWX:
    def test_toggle_wx_hides_weather_stations(self) -> None:
        f = MapFilters()
        stations = [_rf_station(), _wx_station()]
        f.toggle_wx()
        result = f.filter_stations(stations)
        callsigns = {s.callsign for s in result}
        assert "WX1" not in callsigns
        assert "RF1" in callsigns


class TestToggleDigi:
    def test_toggle_digi_hides_digipeaters(self) -> None:
        f = MapFilters()
        digi = _digi_station()
        igate = _igate_station()
        normal = _rf_station()
        stations = [digi, igate, normal]
        f.toggle_digi()
        result = f.filter_stations(stations)
        callsigns = {s.callsign for s in result}
        assert "DIGI1" not in callsigns
        assert "IGATE1" not in callsigns
        assert "RF1" in callsigns


class TestEmptySources:
    def test_filter_preserves_stations_without_sources(self) -> None:
        """Stations with empty sources set should pass all source filters."""
        f = MapFilters()
        # Hide both IS and RF
        f.toggle_is()
        f.toggle_rf()
        no_source = _make_station(callsign="NOSRC", sources=set())
        result = f.filter_stations([no_source])
        # is_is_only_station → False (empty sources), is_rf_station → False
        # So neither source filter blocks it
        assert len(result) == 1
        assert result[0].callsign == "NOSRC"


class TestStatusText:
    def test_status_text_all_visible(self) -> None:
        f = MapFilters()
        stations = [_rf_station(), _is_station()]
        text = f.status_text(stations)
        assert "RF:1" in text
        assert "IS:1" in text
        assert "hidden" not in text

    def test_status_text_is_hidden(self) -> None:
        f = MapFilters()
        f.toggle_is()
        stations = [_rf_station(), _is_station()]
        text = f.status_text(stations)
        assert "IS:hidden" in text
        assert "RF:1" in text

    def test_status_text_wx_and_digi_hidden(self) -> None:
        f = MapFilters()
        f.toggle_wx()
        f.toggle_digi()
        stations = [_rf_station()]
        text = f.status_text(stations)
        assert "WX:hidden" in text
        assert "DG:hidden" in text


class TestToggleTracks:
    def test_toggle_tracks_returns_new_state(self) -> None:
        f = MapFilters()
        assert f.show_tracks is True
        result = f.toggle_tracks()
        assert result is False
        assert f.show_tracks is False
        result = f.toggle_tracks()
        assert result is True
        assert f.show_tracks is True


class TestReset:
    def test_reset_restores_defaults(self) -> None:
        f = MapFilters()
        f.toggle_is()
        f.toggle_rf()
        f.toggle_wx()
        f.toggle_digi()
        f.toggle_tracks()
        # Verify everything is toggled off
        assert f.show_is_stations is False
        assert f.show_rf_stations is False
        assert f.show_wx_stations is False
        assert f.show_digi_stations is False
        assert f.show_tracks is False
        # Reset
        f.reset()
        assert f.show_is_stations is True
        assert f.show_rf_stations is True
        assert f.show_wx_stations is True
        assert f.show_digi_stations is True
        assert f.show_tracks is True


class TestFilterDoesNotMutate:
    def test_filter_does_not_affect_original_list(self) -> None:
        """filter_stations must return a new list, not modify the input."""
        f = MapFilters()
        f.toggle_is()
        original = [_rf_station(), _is_station()]
        original_len = len(original)
        result = f.filter_stations(original)
        # Original list should be unchanged
        assert len(original) == original_len
        # Result should be a different list object
        assert result is not original
        # Only RF station passes
        assert len(result) == 1
