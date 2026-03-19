"""Interactive map panel widget for Textual TUI.

Renders offline tiles with station overlays inside a Textual Widget,
managing viewport state (center, zoom, auto-zoom) and providing a
status line with coordinates, zoom level, and filter indicators.
"""
from __future__ import annotations

from textual.binding import Binding
from textual.events import Key
from textual.reactive import reactive
from textual.widget import Widget
from rich.text import Text

from aprs_tui.core.station_tracker import (
    StationRecord,
    StationTracker,
    is_is_only_station,
    is_rf_station,
)
from aprs_tui.map.auto_zoom import AutoZoomController
from aprs_tui.map.filters import MapFilters
from aprs_tui.map.registry import MapRegistry
from aprs_tui.map.renderer import MapRenderer
from aprs_tui.map.tile_math import latlon_to_pixel, pixel_to_latlon
from aprs_tui.map.tile_source import MBTilesSource
from aprs_tui.map.track_renderer import TrackRenderer


class MapPanel(Widget, can_focus=True):
    """Interactive map panel rendering offline tiles with station overlays."""

    DEFAULT_CSS = """
    MapPanel {
        height: 100%;
        width: 100%;
    }
    """

    BINDINGS = [
        Binding("plus,equal", "zoom_in", "Zoom In", show=False),
        Binding("minus", "zoom_out", "Zoom Out", show=False),
        Binding("a", "toggle_auto_zoom", "Auto Zoom", show=False),
        Binding("0", "reset_auto_zoom", "Reset Zoom", show=False),
        Binding("i", "toggle_is", "IS Stations", show=False),
        Binding("R", "toggle_rf", "RF Stations", show=False),
        Binding("w", "toggle_wx", "WX Stations", show=False),
        Binding("d", "toggle_digi", "Digipeaters", show=False),
        Binding("t", "toggle_tracks", "Tracks", show=False),
        Binding("n", "next_station", "Next Station", show=False),
        Binding("N", "prev_station", "Prev Station", show=False),
        Binding("f", "toggle_fullscreen", "Fullscreen", show=False),
    ]

    # Reactive state
    center_lat: reactive[float] = reactive(0.0)
    center_lon: reactive[float] = reactive(0.0)
    zoom: reactive[float] = reactive(10.0)
    auto_zoom_enabled: reactive[bool] = reactive(True)

    def __init__(
        self,
        station_tracker: StationTracker | None = None,
        own_callsign: str = "",
        map_config: dict | None = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._station_tracker = station_tracker
        self._own_callsign = own_callsign
        self._selected_callsign: str | None = None
        self._renderer = MapRenderer()

        # Config defaults
        cfg = map_config or {}
        self._auto_zoom_min = cfg.get("auto_zoom_min", 4)
        self._auto_zoom_max = cfg.get("auto_zoom_max", 14)
        self._default_zoom = cfg.get("default_zoom", 10)
        self.zoom = self._default_zoom

        # Auto-zoom controller
        own_lat = cfg.get("own_lat", 0.0)
        own_lon = cfg.get("own_lon", 0.0)
        self.center_lat = own_lat
        self.center_lon = own_lon
        self._auto_zoom = AutoZoomController(
            own_lat=own_lat,
            own_lon=own_lon,
            default_zoom=self._default_zoom,
            auto_zoom_min=self._auto_zoom_min,
            auto_zoom_max=self._auto_zoom_max,
        )

        # Map visibility filters (session-only)
        self._filters = MapFilters(
            show_is_stations=cfg.get("show_is_stations", True),
            show_tracks=cfg.get("show_tracks", True),
        )

        # Track renderer
        self._track_renderer = TrackRenderer()

        # Try to load tile source from registry
        self._registry: MapRegistry | None = None
        self._try_load_tiles()

        # Render throttle
        self._last_render_time: float = 0.0

    def _try_load_tiles(self) -> None:
        """Attempt to load the best tile source for current viewport."""
        try:
            self._registry = MapRegistry()
            entry = self._registry.select_map(
                self.center_lat, self.center_lon, self.zoom
            )
            if entry:
                path = self._registry.get_mbtiles_path(entry)
                if path.exists():
                    self._renderer.set_tile_source(MBTilesSource(str(path)))
        except Exception:
            pass  # No maps available -- graceful degradation

    def render(self) -> Text:
        """Render the map as a Rich Text block for Textual."""
        # Get available size
        w = self.size.width
        h = self.size.height - 2  # reserve 2 rows: status line + key hints
        if w <= 0 or h <= 0:
            return Text("")

        # Get filtered stations
        stations = self._get_filtered_stations()

        # Auto-zoom update
        if self.auto_zoom_enabled and self._station_tracker:
            self._auto_zoom._panel_width_dots = w * 2
            self._auto_zoom._panel_height_dots = h * 4
            result = self._auto_zoom.update(stations)
            if result:
                self.center_lat, self.center_lon, self.zoom = result

        # Render map frame
        lines = self._renderer.render(
            center_lat=self.center_lat,
            center_lon=self.center_lon,
            zoom=self.zoom,
            char_width=w,
            char_height=h,
            stations=stations,
            own_callsign=self._own_callsign,
            selected_callsign=self._selected_callsign,
        )

        # Build status line and key hints
        status = self._build_status_line(w, stations)
        hints = self._build_key_hints(w)

        # Combine all lines
        combined = Text()
        for line in lines:
            combined.append_text(line)
            combined.append("\n")
        combined.append_text(status)
        combined.append("\n")
        combined.append_text(hints)
        return combined

    def _build_status_line(
        self, width: int, stations: list[StationRecord]
    ) -> Text:
        """Build the bottom status line showing coords, zoom, and filter state."""
        lat_str = (
            f"{abs(self.center_lat):.2f}{'N' if self.center_lat >= 0 else 'S'}"
        )
        lon_str = (
            f"{abs(self.center_lon):.2f}{'E' if self.center_lon >= 0 else 'W'}"
        )
        zoom_str = f"z:{self.zoom:.1f}"
        mode = "[Auto]" if self.auto_zoom_enabled else "[Manual]"

        # Count visible stations by source
        rf_count = sum(
            1
            for s in stations
            if s.latitude is not None and is_rf_station(s)
        )
        is_count = sum(
            1
            for s in stations
            if s.latitude is not None and is_is_only_station(s)
        )

        is_label = f"IS:{is_count}" if self._filters.show_is_stations else "IS:hidden"

        status_text = (
            f"{lat_str} {lon_str}  {zoom_str}  {mode}  RF:{rf_count} {is_label}"
        )
        # Pad/truncate to width
        status_text = status_text[:width].ljust(width)

        return Text(status_text)

    def _build_key_hints(self, width: int) -> Text:
        """Build the key hints line at the bottom of the map panel."""
        hints = Text()
        keys = [
            ("+/-", "Zoom"),
            ("hjkl", "Pan"),
            ("a", "Auto"),
            ("0", "Reset"),
            ("n/N", "Stn"),
            ("i", "IS"),
            ("R", "RF"),
            ("w", "WX"),
            ("d", "Digi"),
            ("t", "Trk"),
            ("f", "Full"),
            ("m", "Close"),
        ]
        for i, (key, label) in enumerate(keys):
            if hints.cell_len >= width - 10:
                break
            if i > 0:
                hints.append("  ", style="dim #484f58")
            hints.append(key, style="bold #e3b341")
            hints.append(":", style="dim #484f58")
            hints.append(label, style="#8b949e")
        # Pad to width
        pad = width - hints.cell_len
        if pad > 0:
            hints.append(" " * pad)
        return hints

    def notify_station_update(self) -> None:
        """Called when station data changes. Triggers a re-render."""
        self.refresh()

    @property
    def selected_callsign(self) -> str | None:
        return self._selected_callsign

    @selected_callsign.setter
    def selected_callsign(self, value: str | None) -> None:
        self._selected_callsign = value
        self.refresh()

    # ------------------------------------------------------------------
    # Zoom / Pan actions (#51)
    # ------------------------------------------------------------------

    def _disable_auto_zoom(self) -> None:
        """Switch to manual mode on any user navigation."""
        self.auto_zoom_enabled = False

    def action_zoom_in(self) -> None:
        self._disable_auto_zoom()
        self.zoom = min(18.0, self.zoom + 1.0)
        self.refresh()

    def action_zoom_out(self) -> None:
        self._disable_auto_zoom()
        self.zoom = max(0.0, self.zoom - 1.0)
        self.refresh()

    def action_toggle_auto_zoom(self) -> None:
        self.auto_zoom_enabled = not self.auto_zoom_enabled
        if self.auto_zoom_enabled:
            self._auto_zoom.reset(self._get_filtered_stations())
        self.refresh()

    def action_reset_auto_zoom(self) -> None:
        self.auto_zoom_enabled = True
        stations = self._get_filtered_stations()
        result = self._auto_zoom.reset(stations)
        if result:
            self.center_lat, self.center_lon, self.zoom = result
        self.refresh()

    def action_toggle_fullscreen(self) -> None:
        """Push a fullscreen map screen overlaying the entire app."""
        from aprs_tui.map.fullscreen import FullscreenMapScreen
        cfg = {
            "own_lat": self._auto_zoom._own_lat,
            "own_lon": self._auto_zoom._own_lon,
            "auto_zoom_min": self._auto_zoom_min,
            "auto_zoom_max": self._auto_zoom_max,
            "default_zoom": self._default_zoom,
            "show_is_stations": self._filters.show_is_stations,
            "show_tracks": self._filters.show_tracks,
        }
        self.app.push_screen(FullscreenMapScreen(
            station_tracker=self._station_tracker,
            own_callsign=self._own_callsign,
            map_config=cfg,
            source_panel=self,
        ))

    def _pan(self, dx_frac: float, dy_frac: float) -> None:
        """Pan the map by a fraction of the viewport."""
        self._disable_auto_zoom()
        w_dots = max(self.size.width * 2, 1)
        h_dots = max(self.size.height * 4, 1)
        cx, cy = latlon_to_pixel(self.center_lat, self.center_lon, self.zoom)
        cx += w_dots * dx_frac
        cy += h_dots * dy_frac
        self.center_lat, self.center_lon = pixel_to_latlon(cx, cy, self.zoom)
        self.refresh()

    def on_key(self, event: Key) -> None:
        """Handle pan keys (hjkl, arrows, HJKL, shift+arrows)."""
        key = event.key
        # Standard pan (25%)
        pan_keys = {
            "h": (-0.25, 0), "left": (-0.25, 0),
            "l": (0.25, 0), "right": (0.25, 0),
            "k": (0, -0.25), "up": (0, -0.25),
            "j": (0, 0.25), "down": (0, 0.25),
        }
        # Fast pan (50%)
        fast_keys = {
            "H": (-0.5, 0), "shift+left": (-0.5, 0),
            "L": (0.5, 0), "shift+right": (0.5, 0),
            "K": (0, -0.5), "shift+up": (0, -0.5),
            "J": (0, 0.5), "shift+down": (0, 0.5),
        }

        if key in pan_keys:
            dx, dy = pan_keys[key]
            self._pan(dx, dy)
            event.prevent_default()
        elif key in fast_keys:
            dx, dy = fast_keys[key]
            self._pan(dx, dy)
            event.prevent_default()

    # ------------------------------------------------------------------
    # Filter actions (#60)
    # ------------------------------------------------------------------

    def action_toggle_is(self) -> None:
        self._filters.toggle_is()
        self._on_filter_changed()

    def action_toggle_rf(self) -> None:
        self._filters.toggle_rf()
        self._on_filter_changed()

    def action_toggle_wx(self) -> None:
        self._filters.toggle_wx()
        self._on_filter_changed()

    def action_toggle_digi(self) -> None:
        self._filters.toggle_digi()
        self._on_filter_changed()

    def action_toggle_tracks(self) -> None:
        self._filters.toggle_tracks()
        self.refresh()

    def _on_filter_changed(self) -> None:
        """Recalculate auto-zoom with filtered stations when filters change (#61)."""
        if self.auto_zoom_enabled:
            stations = self._get_filtered_stations()
            result = self._auto_zoom.update(stations)
            if result:
                self.center_lat, self.center_lon, self.zoom = result
        self.refresh()

    def _get_filtered_stations(self) -> list[StationRecord]:
        if not self._station_tracker:
            return []
        return self._filters.filter_stations(self._station_tracker.get_stations())

    # ------------------------------------------------------------------
    # Station selection actions (#62)
    # ------------------------------------------------------------------

    def action_next_station(self) -> None:
        stations = self._get_filtered_stations()
        positioned = [s for s in stations if s.latitude is not None]
        if not positioned:
            return
        if self._selected_callsign is None:
            self.selected_callsign = positioned[0].callsign
        else:
            calls = [s.callsign for s in positioned]
            try:
                idx = calls.index(self._selected_callsign)
                self.selected_callsign = calls[(idx + 1) % len(calls)]
            except ValueError:
                self.selected_callsign = calls[0]

    def action_prev_station(self) -> None:
        stations = self._get_filtered_stations()
        positioned = [s for s in stations if s.latitude is not None]
        if not positioned:
            return
        if self._selected_callsign is None:
            self.selected_callsign = positioned[-1].callsign
        else:
            calls = [s.callsign for s in positioned]
            try:
                idx = calls.index(self._selected_callsign)
                self.selected_callsign = calls[(idx - 1) % len(calls)]
            except ValueError:
                self.selected_callsign = calls[-1]
