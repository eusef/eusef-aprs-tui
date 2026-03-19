"""Fullscreen map screen — overlays the entire app with just the map."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen

from aprs_tui.core.station_tracker import StationTracker
from aprs_tui.map.panel import MapPanel


class FullscreenMapScreen(Screen):
    """Full-terminal map view. Press f or Escape to return."""

    DEFAULT_CSS = """
    FullscreenMapScreen {
        background: #0d1117;
    }
    FullscreenMapScreen MapPanel {
        width: 100%;
        height: 100%;
        border: none;
    }
    FullscreenMapScreen MapPanel:focus {
        border: none;
    }
    """

    BINDINGS = [
        Binding("f", "close", "Close", priority=True),
        Binding("escape", "close", "Close", priority=True),
    ]

    def __init__(
        self,
        station_tracker: StationTracker | None = None,
        own_callsign: str = "",
        map_config: dict | None = None,
        source_panel: MapPanel | None = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._station_tracker = station_tracker
        self._own_callsign = own_callsign
        self._map_config = map_config or {}
        self._source_panel = source_panel

    def compose(self) -> ComposeResult:
        panel = MapPanel(
            station_tracker=self._station_tracker,
            own_callsign=self._own_callsign,
            map_config=self._map_config,
            id="fullscreen-map-panel",
        )
        yield panel

    def on_mount(self) -> None:
        panel = self.query_one(MapPanel)
        # Copy viewport state from the source panel if available
        if self._source_panel:
            panel._reactive_center_lat = self._source_panel.center_lat
            panel._reactive_center_lon = self._source_panel.center_lon
            panel._reactive_zoom = self._source_panel.zoom
            panel._reactive_auto_zoom_enabled = self._source_panel.auto_zoom_enabled
            panel._selected_callsign = self._source_panel._selected_callsign
            panel._filters = self._source_panel._filters
        panel.focus()

    def action_close(self) -> None:
        # Copy viewport state back to the source panel
        if self._source_panel:
            panel = self.query_one(MapPanel)
            self._source_panel.center_lat = panel.center_lat
            self._source_panel.center_lon = panel.center_lon
            self._source_panel.zoom = panel.zoom
            self._source_panel.auto_zoom_enabled = panel.auto_zoom_enabled
            self._source_panel._selected_callsign = panel._selected_callsign
            self._source_panel._filters = panel._filters
        self.app.pop_screen()
