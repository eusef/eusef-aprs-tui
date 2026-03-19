"""Auto-zoom algorithm — calculates viewport to show all active stations."""
from __future__ import annotations

import time

from aprs_tui.core.station_tracker import StationRecord
from aprs_tui.map.tile_math import fit_bounds_to_viewport


def calculate_auto_zoom(
    stations: list[StationRecord],
    own_lat: float,
    own_lon: float,
    panel_width_dots: int,
    panel_height_dots: int,
    default_zoom: float = 10.0,
    auto_zoom_min: float = 4.0,
    auto_zoom_max: float = 14.0,
    auto_zoom_timeout: float = 1800.0,
) -> tuple[float, float, float]:
    """Calculate auto-zoom viewport to show all visible stations.

    Returns (center_lat, center_lon, zoom_level).

    Algorithm:
    1. Filter stations: must have position, must not be timed out
    2. If no stations, return (own_lat, own_lon, default_zoom)
    3. Calculate bounding box of all stations + own position
    4. Add 10% padding on each side
    5. Calculate zoom level that fits the bounding box
    6. Clamp zoom between auto_zoom_min and auto_zoom_max
    7. Return center and zoom
    """
    now_wall = time.time()
    now_mono = time.monotonic()

    # Step 1: Filter stations — must have position, must not be timed out
    visible: list[StationRecord] = []
    for stn in stations:
        if stn.latitude is None or stn.longitude is None:
            continue

        # Determine timestamp for timeout check
        if stn.position_history:
            # position_history entries are (lat, lon, wall_clock_time)
            latest_ts = stn.position_history[-1][2]
            if now_wall - latest_ts > auto_zoom_timeout:
                continue
        else:
            # last_heard is monotonic
            if now_mono - stn.last_heard > auto_zoom_timeout:
                continue

        visible.append(stn)

    # Step 2: No visible stations — center on own position at default zoom
    if not visible:
        return (own_lat, own_lon, default_zoom)

    # Step 3: Calculate bounding box including own position
    lats = [own_lat] + [stn.latitude for stn in visible]  # type: ignore[misc]
    lons = [own_lon] + [stn.longitude for stn in visible]  # type: ignore[misc]

    min_lat = min(lats)
    max_lat = max(lats)
    min_lon = min(lons)
    max_lon = max(lons)

    # If the bounding box has zero area, return own position at default zoom
    if min_lat == max_lat and min_lon == max_lon:
        return (own_lat, own_lon, default_zoom)

    # Step 4: Add 10% padding on each side
    lat_span = max_lat - min_lat
    lon_span = max_lon - min_lon
    lat_pad = lat_span * 0.1
    lon_pad = lon_span * 0.1
    min_lat -= lat_pad
    max_lat += lat_pad
    min_lon -= lon_pad
    max_lon += lon_pad

    # Step 5: Calculate zoom level that fits the padded bounding box
    zoom = fit_bounds_to_viewport(
        min_lat, max_lat, min_lon, max_lon,
        panel_width_dots, panel_height_dots,
    )

    # Step 6: Clamp zoom
    zoom = max(auto_zoom_min, min(auto_zoom_max, zoom))

    # Step 7: Return center of bounding box and zoom
    center_lat = (min_lat + max_lat) / 2.0
    center_lon = (min_lon + max_lon) / 2.0

    return (center_lat, center_lon, zoom)


class AutoZoomController:
    """Stateful auto-zoom controller with smoothing and hysteresis."""

    def __init__(
        self,
        own_lat: float = 0.0,
        own_lon: float = 0.0,
        panel_width_dots: int = 160,
        panel_height_dots: int = 96,
        default_zoom: float = 10.0,
        auto_zoom_min: float = 4.0,
        auto_zoom_max: float = 14.0,
        auto_zoom_timeout: float = 1800.0,
    ):
        self.enabled: bool = True
        self._prev_center_lat: float | None = None
        self._prev_center_lon: float | None = None
        self._prev_zoom: float | None = None
        self._own_lat = own_lat
        self._own_lon = own_lon
        self._panel_width_dots = panel_width_dots
        self._panel_height_dots = panel_height_dots
        self._default_zoom = default_zoom
        self._auto_zoom_min = auto_zoom_min
        self._auto_zoom_max = auto_zoom_max
        self._auto_zoom_timeout = auto_zoom_timeout

    def update(
        self, stations: list[StationRecord],
    ) -> tuple[float, float, float] | None:
        """Recalculate viewport with smoothing.

        Returns (lat, lon, zoom) or None if disabled.
        """
        if not self.enabled:
            return None

        # 1. Get raw calculation from calculate_auto_zoom
        raw_lat, raw_lon, raw_zoom = calculate_auto_zoom(
            stations,
            self._own_lat,
            self._own_lon,
            self._panel_width_dots,
            self._panel_height_dots,
            default_zoom=self._default_zoom,
            auto_zoom_min=self._auto_zoom_min,
            auto_zoom_max=self._auto_zoom_max,
            auto_zoom_timeout=self._auto_zoom_timeout,
        )

        # 2. Apply center smoothing: 70% old + 30% new
        if self._prev_center_lat is not None:
            smooth_lat = self._prev_center_lat * 0.7 + raw_lat * 0.3
            smooth_lon = self._prev_center_lon * 0.7 + raw_lon * 0.3  # type: ignore[operator]
        else:
            smooth_lat, smooth_lon = raw_lat, raw_lon

        # 3. Zoom dampening: max +/-0.5 per update
        if self._prev_zoom is not None:
            zoom_delta = raw_zoom - self._prev_zoom
            zoom_delta = max(-0.5, min(0.5, zoom_delta))
            smooth_zoom = self._prev_zoom + zoom_delta
        else:
            smooth_zoom = raw_zoom

        # 4. Clamp zoom
        smooth_zoom = max(self._auto_zoom_min, min(self._auto_zoom_max, smooth_zoom))

        # 5. Update state
        self._prev_center_lat = smooth_lat
        self._prev_center_lon = smooth_lon
        self._prev_zoom = smooth_zoom

        return (smooth_lat, smooth_lon, smooth_zoom)

    def toggle(self) -> bool:
        """Toggle auto-zoom on/off. Returns new state."""
        self.enabled = not self.enabled
        return self.enabled

    def reset(
        self, stations: list[StationRecord],
    ) -> tuple[float, float, float]:
        """Re-enable auto-zoom, clear smoothing state, recalculate immediately."""
        self.enabled = True
        self._prev_center_lat = None
        self._prev_center_lon = None
        self._prev_zoom = None
        result = self.update(stations)
        return result  # type: ignore[return-value]  # guaranteed non-None since we just enabled
