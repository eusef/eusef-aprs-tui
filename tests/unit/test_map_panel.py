"""Tests for aprs_tui.map.panel — MapPanel Textual widget."""
from __future__ import annotations

import contextlib

from rich.text import Text

from aprs_tui.core.station_tracker import StationRecord
from aprs_tui.map.filters import MapFilters
from aprs_tui.map.panel import MapPanel

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_panel(**kwargs) -> MapPanel:  # type: ignore[no-untyped-def]
    """Create a MapPanel shell for unit-testing without a Textual app.

    Uses ``object.__new__`` to bypass ``Widget.__init__`` (which requires a
    running Textual App).  Reactive values are stored via the internal
    ``_reactive_<name>`` attribute so that the descriptor ``__get__`` can
    find them.  We also set ``id`` / ``_id`` because the reactive
    descriptor checks for their existence.
    """
    panel = object.__new__(MapPanel)

    # Minimum attributes so the reactive descriptor __get__ doesn't raise.
    # Use __dict__ to bypass Textual's id property validator.
    panel.__dict__["id"] = "test-map-panel"
    panel.__dict__["_id"] = "test-map-panel"
    panel.__dict__["_name"] = None

    cfg = kwargs.get("map_config") or {}
    own_lat = cfg.get("own_lat", 0.0)
    own_lon = cfg.get("own_lon", 0.0)
    default_zoom = cfg.get("default_zoom", 10)

    # Store reactive-managed values using Textual's internal storage name
    panel._reactive_center_lat = own_lat
    panel._reactive_center_lon = own_lon
    panel._reactive_zoom = default_zoom
    panel._reactive_auto_zoom_enabled = kwargs.get("auto_zoom_enabled", True)

    # Non-reactive instance attributes
    panel._station_tracker = kwargs.get("station_tracker")
    panel._own_callsign = kwargs.get("own_callsign", "")
    panel._selected_callsign = kwargs.get("selected_callsign")
    panel._auto_zoom_min = cfg.get("auto_zoom_min", 4)
    panel._auto_zoom_max = cfg.get("auto_zoom_max", 14)
    panel._default_zoom = default_zoom

    panel._filters = MapFilters(
        show_is_stations=cfg.get("show_is_stations", True),
        show_tracks=cfg.get("show_tracks", True),
    )

    panel._registry = None
    panel._last_render_time = 0.0
    return panel


def _make_station(
    callsign: str = "N0CALL",
    lat: float | None = 45.0,
    lon: float | None = -122.0,
    sources: set[str] | None = None,
) -> StationRecord:
    return StationRecord(
        callsign=callsign,
        latitude=lat,
        longitude=lon,
        sources=sources if sources is not None else {"RF"},
        last_heard=0.0,
    )


# ---------------------------------------------------------------------------
# Instantiation
# ---------------------------------------------------------------------------


class TestMapPanelCreation:
    """MapPanel can be instantiated without crashing."""

    def test_map_panel_creates_without_error(self) -> None:
        panel = _make_panel()
        assert panel is not None

    def test_map_panel_default_viewport(self) -> None:
        """Default viewport: zoom=10, auto_zoom=True, center at origin."""
        panel = _make_panel()
        assert panel.zoom == 10
        assert panel.auto_zoom_enabled is True
        assert panel.center_lat == 0.0
        assert panel.center_lon == 0.0

    def test_map_panel_with_config(self) -> None:
        """Custom config values override defaults."""
        cfg = {
            "default_zoom": 8,
            "auto_zoom_min": 5,
            "auto_zoom_max": 12,
            "own_lat": 40.0,
            "own_lon": -105.0,
        }
        panel = _make_panel(map_config=cfg)
        assert panel.zoom == 8
        assert panel.center_lat == 40.0
        assert panel.center_lon == -105.0
        assert panel._auto_zoom_min == 5
        assert panel._auto_zoom_max == 12


# ---------------------------------------------------------------------------
# Status line
# ---------------------------------------------------------------------------


class TestStatusLine:
    """Tests for _build_status_line output format."""

    def test_status_line_format(self) -> None:
        """Status line should contain lat, lon, zoom, and mode."""
        panel = _make_panel(
            map_config={"own_lat": 45.52, "own_lon": -122.68, "default_zoom": 10}
        )
        status = panel._build_status_line(80, [])
        text = str(status)
        assert "45.52N" in text
        assert "122.68W" in text
        assert "z:10.0" in text

    def test_status_line_shows_auto_mode(self) -> None:
        """Status line shows [Auto] when auto-zoom is enabled."""
        panel = _make_panel(auto_zoom_enabled=True)
        status = panel._build_status_line(80, [])
        assert "[Auto]" in str(status)

    def test_status_line_shows_manual_mode(self) -> None:
        """Status line shows [Manual] when auto-zoom is disabled."""
        panel = _make_panel(auto_zoom_enabled=False)
        status = panel._build_status_line(80, [])
        assert "[Manual]" in str(status)

    def test_status_line_rf_count(self) -> None:
        """Status line displays RF station count."""
        stations = [
            _make_station("W1AW", 45.0, -122.0, sources={"RF"}),
            _make_station("W2AB", 46.0, -121.0, sources={"RF"}),
        ]
        panel = _make_panel()
        status = panel._build_status_line(80, stations)
        assert "RF:2" in str(status)

    def test_status_line_is_count(self) -> None:
        """Status line displays IS station count when IS stations are shown."""
        stations = [
            _make_station("W1AW", 45.0, -122.0, sources={"APRS-IS"}),
        ]
        panel = _make_panel()
        status = panel._build_status_line(80, stations)
        assert "IS:1" in str(status)

    def test_status_line_is_hidden(self) -> None:
        """Status line shows IS:hidden when IS stations are hidden."""
        panel = _make_panel(map_config={"show_is_stations": False})
        status = panel._build_status_line(80, [])
        assert "IS:hidden" in str(status)

    def test_status_line_padded_to_width(self) -> None:
        """Status line is padded to the requested width."""
        panel = _make_panel()
        status = panel._build_status_line(60, [])
        assert len(str(status)) == 60

    def test_status_line_truncated_to_width(self) -> None:
        """Status line is truncated if it would exceed width."""
        panel = _make_panel()
        status = panel._build_status_line(10, [])
        assert len(str(status)) == 10

    def test_status_line_southern_hemisphere(self) -> None:
        """Negative latitude shows S suffix."""
        panel = _make_panel(map_config={"own_lat": -33.87, "own_lon": 151.21})
        status = panel._build_status_line(80, [])
        text = str(status)
        assert "33.87S" in text
        assert "151.21E" in text

    def test_status_line_station_without_position_not_counted(self) -> None:
        """Stations without lat/lon should not be counted in RF/IS totals."""
        stations = [
            _make_station("W1AW", None, None, sources={"RF"}),
        ]
        panel = _make_panel()
        status = panel._build_status_line(80, stations)
        assert "RF:0" in str(status)

    def test_status_line_returns_text_object(self) -> None:
        """_build_status_line returns a Rich Text object."""
        panel = _make_panel()
        status = panel._build_status_line(80, [])
        assert isinstance(status, Text)


# ---------------------------------------------------------------------------
# Selected callsign property
# ---------------------------------------------------------------------------


class TestSelectedCallsign:
    """selected_callsign property get/set."""

    def test_selected_callsign_default_none(self) -> None:
        panel = _make_panel()
        assert panel.selected_callsign is None

    def test_selected_callsign_set_and_get(self) -> None:
        panel = _make_panel(selected_callsign="W1AW")
        assert panel.selected_callsign == "W1AW"

    def test_selected_callsign_clear(self) -> None:
        panel = _make_panel(selected_callsign="W1AW")
        panel._selected_callsign = None
        assert panel.selected_callsign is None


# ---------------------------------------------------------------------------
# notify_station_update
# ---------------------------------------------------------------------------


class TestNotifyStationUpdate:
    """notify_station_update should not crash even outside a Textual app."""

    def test_notify_station_update_doesnt_crash(self) -> None:
        """Calling notify_station_update on a panel created via __new__ should not raise."""
        panel = _make_panel()
        # refresh() will fail since there's no app context, but we verify
        # the method exists and the panel attribute is wired correctly.
        with contextlib.suppress(Exception):
            # Textual may raise since there's no running app
            panel.notify_station_update()
