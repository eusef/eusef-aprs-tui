"""Mini map widget for showing two station positions with distance."""
from __future__ import annotations

from rich.text import Text
from textual.widgets import Static

from aprs_tui.core.station_tracker import haversine


class MiniMapWidget(Static):
    """Small map showing own station and peer station with distance."""

    DEFAULT_CSS = """
    MiniMapWidget {
        width: 28;
        height: 10;
        background: #0d1117;
        border: solid #30363d;
        border-title-color: #8b949e;
        padding: 0;
        margin: 0;
    }
    """

    def __init__(
        self,
        own_lat: float,
        own_lon: float,
        peer_lat: float,
        peer_lon: float,
        own_callsign: str = "",
        peer_callsign: str = "",
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._own_lat = own_lat
        self._own_lon = own_lon
        self._peer_lat = peer_lat
        self._peer_lon = peer_lon
        self._own_call = own_callsign
        self._peer_call = peer_callsign
        self._distance = haversine(own_lat, own_lon, peer_lat, peer_lon)

    def on_mount(self) -> None:
        self.border_title = f" Map \u2014 {self._distance:.1f} km "
        self._render_map()

    def _render_map(self) -> None:
        """Render a simple ASCII mini map showing two points."""
        # Available drawing area (inside borders/padding)
        w = 26  # chars wide
        h = 7   # rows tall (reserve 1 for distance label)

        # Calculate positions within the drawing area
        # Normalize lat/lon to fit in the available space
        min_lat = min(self._own_lat, self._peer_lat)
        max_lat = max(self._own_lat, self._peer_lat)
        min_lon = min(self._own_lon, self._peer_lon)
        max_lon = max(self._own_lon, self._peer_lon)

        # Add 20% padding
        lat_range = max_lat - min_lat
        lon_range = max_lon - min_lon
        if lat_range == 0:
            lat_range = 0.01
        if lon_range == 0:
            lon_range = 0.01
        pad_lat = lat_range * 0.2
        pad_lon = lon_range * 0.2
        min_lat -= pad_lat
        max_lat += pad_lat
        min_lon -= pad_lon
        max_lon += pad_lon
        lat_range = max_lat - min_lat
        lon_range = max_lon - min_lon

        # Map positions to grid
        own_col = int((self._own_lon - min_lon) / lon_range * (w - 1))
        own_row = int((max_lat - self._own_lat) / lat_range * (h - 1))  # Invert Y
        peer_col = int((self._peer_lon - min_lon) / lon_range * (w - 1))
        peer_row = int((max_lat - self._peer_lat) / lat_range * (h - 1))

        # Clamp to bounds
        own_col = max(0, min(w - 1, own_col))
        own_row = max(0, min(h - 1, own_row))
        peer_col = max(0, min(w - 1, peer_col))
        peer_row = max(0, min(h - 1, peer_row))

        # Build the grid
        grid = [[" " for _ in range(w)] for _ in range(h)]

        # Draw a simple line between the two points
        # Use Bresenham-style stepping
        steps = max(abs(peer_col - own_col), abs(peer_row - own_row), 1)
        for i in range(1, steps):
            t = i / steps
            lc = int(own_col + t * (peer_col - own_col))
            lr = int(own_row + t * (peer_row - own_row))
            if 0 <= lc < w and 0 <= lr < h:
                grid[lr][lc] = "\u00b7"

        # Place markers (after line so they override)
        grid[own_row][own_col] = "\u2605"
        grid[peer_row][peer_col] = "\u25cf"

        # Build Rich Text output with proper styling
        text = Text()
        for r, row in enumerate(grid):
            for _c, ch in enumerate(row):
                if ch == "\u2605":
                    text.append(ch, style="bold #e3b341")
                elif ch == "\u25cf":
                    text.append(ch, style="bold #58a6ff")
                elif ch == "\u00b7":
                    text.append(ch, style="#484f58")
                else:
                    text.append(ch, style="#21262d")
            if r < len(grid) - 1:
                text.append("\n")

        # Add legend line
        text.append("\n")
        text.append("\u2605", style="bold #e3b341")
        text.append(f" {self._own_call}  ", style="dim")
        text.append("\u25cf", style="bold #58a6ff")
        text.append(f" {self._peer_call}", style="dim")

        self.update(text)

    @property
    def distance_km(self) -> float:
        return self._distance
