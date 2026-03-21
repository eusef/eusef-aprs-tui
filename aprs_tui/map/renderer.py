"""Top-level map renderer — composites tiles + overlays into a final frame.

Combines base map tiles (roads, water, etc.) with station markers to
produce a complete map frame as Rich Text objects or plain braille strings.
"""
from __future__ import annotations

from rich.text import Text

from aprs_tui.core.station_tracker import StationRecord
from aprs_tui.map.braille_canvas import BrailleCanvas
from aprs_tui.map.station_overlay import StationOverlay
from aprs_tui.map.tile_math import viewport_tiles
from aprs_tui.map.tile_source import MBTilesSource
from aprs_tui.map.vector_renderer import VectorRenderer


class MapRenderer:
    """Top-level map renderer -- composites tiles + overlays into a frame."""

    def __init__(self, tile_source: MBTilesSource | None = None) -> None:
        self._tile_source = tile_source
        self._vector_renderer = VectorRenderer()
        # Cache the last rendered base map to avoid re-rendering when only stations change
        self._cached_base: list[str] | None = None
        # (lat, lon, zoom, w, h)
        self._cached_viewport: tuple[float, float, float, int, int] | None = None

    def set_tile_source(self, source: MBTilesSource | None) -> None:
        """Change the tile source. Invalidates base map cache."""
        self._tile_source = source
        self._cached_base = None
        self._cached_viewport = None

    def render(
        self,
        center_lat: float,
        center_lon: float,
        zoom: float,
        char_width: int,
        char_height: int,
        stations: list[StationRecord] | None = None,
        own_callsign: str = "",
        selected_callsign: str | None = None,
        chat_callsigns: set[str] | None = None,
    ) -> list[Text]:
        """Render a complete map frame as Rich Text objects.

        Compositing order:
        1. Base map tiles (roads, water, etc.)
        2. Station markers + labels
        """
        canvas = BrailleCanvas(char_width, char_height)
        int_zoom = max(0, int(zoom))

        # 1. Render base map tiles
        self._render_base_map(canvas, center_lat, center_lon, int_zoom)

        # 2. Render station overlay
        if stations:
            overlay = StationOverlay(canvas, int_zoom, center_lat, center_lon)
            overlay.render_stations(
                stations, own_callsign, selected_callsign, chat_callsigns
            )

        return canvas.render_rich()

    def render_plain(
        self,
        center_lat: float,
        center_lon: float,
        zoom: float,
        char_width: int,
        char_height: int,
    ) -> list[str]:
        """Render base map only as plain braille strings (no color, no stations)."""
        canvas = BrailleCanvas(char_width, char_height)
        int_zoom = max(0, int(zoom))
        self._render_base_map(canvas, center_lat, center_lon, int_zoom)
        return canvas.render()

    def _render_base_map(
        self,
        canvas: BrailleCanvas,
        center_lat: float,
        center_lon: float,
        zoom: int,
    ) -> None:
        """Render map tiles onto the canvas."""
        if self._tile_source is None:
            self._render_no_data(canvas, center_lat, center_lon)
            return

        tiles = viewport_tiles(
            center_lat, center_lon, zoom, canvas.char_width, canvas.char_height
        )
        for tx, ty, tz in tiles:
            tile_data = self._tile_source.get_tile(tz, tx, ty)
            if tile_data is not None:
                self._vector_renderer.render_features(
                    canvas,
                    tile_data,
                    zoom=zoom,
                    tile_x=tx,
                    tile_y=ty,
                    tile_z=tz,
                    center_lat=center_lat,
                    center_lon=center_lon,
                )

    def _render_no_data(
        self,
        canvas: BrailleCanvas,
        center_lat: float,
        center_lon: float,
    ) -> None:
        """Graceful degradation: compass rose grid when no map data available."""
        w, h = canvas.width, canvas.height
        cx, cy = w // 2, h // 2

        # Draw compass crosshair
        canvas.draw_line(cx, 0, cx, h - 1)  # vertical
        canvas.draw_line(0, cy, w - 1, cy)  # horizontal

        # Labels
        canvas.draw_text(cx - 1, 0, "N")
        canvas.draw_text(cx - 1, h - 4, "S")
        canvas.draw_text(0, cy - 2, "W")
        canvas.draw_text(w - 2, cy - 2, "E")
