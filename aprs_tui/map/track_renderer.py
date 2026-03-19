"""Track/trail renderer for mobile stations.

Draws movement trails on the braille canvas by connecting consecutive
position reports with lines.  Older positions are filtered by age and
the total number of points is capped to keep rendering fast.
"""
from __future__ import annotations

import time

from aprs_tui.core.station_tracker import StationRecord
from aprs_tui.map.braille_canvas import BrailleCanvas
from aprs_tui.map.tile_math import latlon_to_braille_pixel


class TrackRenderer:
    """Renders movement trails for mobile stations."""

    def __init__(
        self,
        max_points: int = 50,
        max_age: int = 3600,
    ) -> None:
        self._max_points = max_points
        self._max_age = max_age

    def render_tracks(
        self,
        canvas: BrailleCanvas,
        stations: list[StationRecord],
        zoom: float,
        center_lat: float,
        center_lon: float,
        selected_callsign: str | None = None,
    ) -> None:
        """Render track trails for all stations with 2+ position reports."""
        now = time.time()
        for station in stations:
            if len(station.position_history) < 2:
                continue
            self._render_track(
                canvas, station, zoom, center_lat, center_lon,
                now, selected_callsign,
            )

    def _render_track(
        self,
        canvas: BrailleCanvas,
        station: StationRecord,
        zoom: float,
        center_lat: float,
        center_lon: float,
        now: float,
        selected_callsign: str | None,
    ) -> None:
        # Filter by age
        points = [
            (lat, lon, ts) for lat, lon, ts in station.position_history
            if now - ts <= self._max_age
        ]
        # Cap points
        if len(points) > self._max_points:
            points = points[-self._max_points:]

        if len(points) < 2:
            return

        # Simplify at low zoom: keep every Nth point
        if zoom < 8 and len(points) > 10:
            step = max(2, len(points) // 5)
            simplified = points[::step]
            if points[-1] not in simplified:
                simplified.append(points[-1])
            points = simplified

        # Convert to braille pixels and draw lines between consecutive points
        prev_bx, prev_by = None, None
        for lat, lon, _ts in points:
            bx, by = latlon_to_braille_pixel(
                lat, lon, zoom, center_lat, center_lon,
                canvas.width, canvas.height,
            )
            if prev_bx is not None:
                canvas.draw_line(prev_bx, prev_by, bx, by)
            prev_bx, prev_by = bx, by

        # Apply track style to the cells that got drawn
        # (set_cell_style for the track region)
        if hasattr(canvas, 'set_cell_style'):
            # We can't easily know which cells got track lines,
            # so we skip per-cell styling here — the renderer compositor
            # will handle it via layer ordering
            pass
