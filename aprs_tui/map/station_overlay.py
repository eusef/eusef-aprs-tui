"""Station overlay renderer — plots APRS stations onto a BrailleCanvas."""
from __future__ import annotations

from collections import defaultdict

from aprs_tui.core.station_tracker import (
    StationRecord,
    is_is_only_station,
    is_rf_station,
)
from aprs_tui.map.braille_canvas import BrailleCanvas
from aprs_tui.map.tile_math import latlon_to_braille_pixel

# APRS symbol table+code → single terminal character.
SYMBOL_MAP: dict[str, str] = {
    "/>": ">",  # Car (mobile)
    "/-": "H",  # House (fixed QTH)
    "/#": "#",  # Digipeater
    "/&": "&",  # Gateway / iGate
    "/_": "W",  # Weather station
    "/O": "O",  # Balloon
    "/[": "P",  # Human / pedestrian
    "/R": "R",  # Recreational vehicle
    "/b": "b",  # Bicycle
    "/Y": "Y",  # Yacht / sailboat
    "/k": "k",  # Truck
    "/u": "u",  # Truck (18-wheeler)
    "\\n": "!",  # Emergency
}
DEFAULT_SYMBOL = "*"

# Legend entries — symbol character → human-readable description.
# Exported for use by the map panel legend overlay.
LEGEND_ENTRIES: list[tuple[str, str]] = [
    ("(>)", "Car/Mobile"),
    ("(H)", "House/QTH"),
    ("(#)", "Digipeater"),
    ("(&)", "Gateway"),
    ("(W)", "Weather"),
    ("(P)", "Pedestrian"),
    ("(b)", "Bicycle"),
    ("(k)", "Truck"),
    ("(*)", "Other"),
    ("(N)", "Cluster"),
]

# Cluster threshold — cells with this many or more stations render as a count.
CLUSTER_THRESHOLD = 3

# Style names that will be applied once set_cell_style is available.
_STYLE_OWN = "station_own"
_STYLE_SELECTED = "station_selected"
_STYLE_RF = "station_rf"
_STYLE_IS = "station_is"
_STYLE_EMERGENCY = "station_emergency"
_STYLE_CLUSTER = "station_rf"
_STYLE_CHAT = "station_chat"


def _cluster_radius(zoom: float) -> int:
    """Return cluster grouping radius in character cells based on zoom level."""
    if zoom >= 14:
        return 1  # Tight: same-cell only (current behavior)
    elif zoom >= 11:
        return 2  # Medium: 2-cell radius
    elif zoom >= 8:
        return 3  # Wide: 3-cell radius
    else:
        return 5  # Very wide: 5-cell radius


def _symbol_char(station: StationRecord) -> str:
    """Return the terminal character for a station's APRS symbol."""
    if station.symbol_table is None or station.symbol_code is None:
        return DEFAULT_SYMBOL
    key = station.symbol_table + station.symbol_code
    return SYMBOL_MAP.get(key, DEFAULT_SYMBOL)


def _choose_style(
    station: StationRecord,
    own_callsign: str,
    selected_callsign: str | None,
) -> str:
    """Determine the Rich style name for a station marker."""
    symbol_key = ""
    if station.symbol_table and station.symbol_code:
        symbol_key = station.symbol_table + station.symbol_code

    if station.callsign.upper() == own_callsign.upper():
        return _STYLE_OWN
    if selected_callsign and station.callsign.upper() == selected_callsign.upper():
        return _STYLE_SELECTED
    if symbol_key == "\\n":
        return _STYLE_EMERGENCY
    if is_rf_station(station):
        return _STYLE_RF
    if is_is_only_station(station):
        return _STYLE_IS
    return _STYLE_RF  # default for stations with no source info


class _OccupancyGrid:
    """2D boolean grid tracking which character cells are occupied by labels."""

    def __init__(self, char_width: int, char_height: int) -> None:
        self._width = char_width
        self._height = char_height
        self._grid = bytearray(char_width * char_height)

    @property
    def width(self) -> int:
        return self._width

    @property
    def height(self) -> int:
        return self._height

    def is_occupied(self, col: int, row: int) -> bool:
        """Check if a cell is occupied. Out-of-bounds is considered occupied."""
        if col < 0 or row < 0 or col >= self._width or row >= self._height:
            return True
        return bool(self._grid[row * self._width + col])

    def mark(self, col: int, row: int) -> None:
        """Mark a cell as occupied. Out-of-bounds is silently ignored."""
        if 0 <= col < self._width and 0 <= row < self._height:
            self._grid[row * self._width + col] = 1

    def can_place_label(self, start_col: int, row: int, length: int) -> bool:
        """Check if *length* consecutive cells starting at (start_col, row) are free."""
        return all(
            not self.is_occupied(c, row)
            for c in range(start_col, start_col + length)
        )

    def mark_label(self, start_col: int, row: int, length: int) -> None:
        """Mark *length* consecutive cells starting at (start_col, row) as occupied."""
        for c in range(start_col, start_col + length):
            self.mark(c, row)


class StationOverlay:
    """Renders APRS station markers and labels onto a BrailleCanvas."""

    def __init__(
        self,
        canvas: BrailleCanvas,
        zoom: float,
        center_lat: float,
        center_lon: float,
    ) -> None:
        self._canvas = canvas
        self._zoom = zoom
        self._center_lat = center_lat
        self._center_lon = center_lon

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def render_stations(
        self,
        stations: list[StationRecord],
        own_callsign: str,
        selected_callsign: str | None = None,
        chat_callsigns: set[str] | None = None,
    ) -> None:
        """Plot all stations onto the canvas with collision-aware labels.

        Steps:
        1. Convert all stations to pixel positions, discard out-of-bounds.
        2. Group by zoom-dependent grid cells; cells with 3+ stations become
           clusters.  Own station and selected station are never clustered.
        3. Render clusters as count indicators like ``(3)``.
        4. Render remaining individual stations with collision-aware label
           placement using an occupancy grid.
        """
        canvas = self._canvas
        canvas_w = canvas.width
        canvas_h = canvas.height
        char_w = canvas.char_width
        char_h = canvas.char_height

        # --- Phase 1: convert to pixel coords, filter OOB -----------------
        positioned: list[tuple[StationRecord, int, int]] = []
        for station in stations:
            if station.latitude is None or station.longitude is None:
                continue
            dot_x, dot_y = latlon_to_braille_pixel(
                station.latitude,
                station.longitude,
                self._zoom,
                self._center_lat,
                self._center_lon,
                canvas_w,
                canvas_h,
            )
            if dot_x < 0 or dot_x >= canvas_w or dot_y < 0 or dot_y >= canvas_h:
                continue
            positioned.append((station, dot_x, dot_y))

        if not positioned:
            return

        # --- Phase 2: zoom-dependent grouping --------------------------------
        radius = _cluster_radius(self._zoom)

        # Extract priority stations (never clustered)
        priority: list[tuple[StationRecord, int, int]] = []
        rest: list[tuple[StationRecord, int, int]] = []
        for item in positioned:
            stn = item[0]
            if stn.callsign.upper() == own_callsign.upper() or (
                selected_callsign
                and stn.callsign.upper() == selected_callsign.upper()
            ):
                priority.append(item)
            else:
                rest.append(item)

        # Group remaining by grid cells
        cell_groups: dict[tuple[int, int], list[tuple[StationRecord, int, int]]] = (
            defaultdict(list)
        )
        for station, dot_x, dot_y in rest:
            char_col = dot_x // 2
            char_row = dot_y // 4
            grid_key = (char_col // radius, char_row // radius)
            cell_groups[grid_key].append((station, dot_x, dot_y))

        # Separate clusters from individual stations.
        individual: list[tuple[StationRecord, int, int]] = list(priority)
        clusters: list[tuple[int, int, int]] = []  # (char_col, char_row, count)

        for _grid_key, group in cell_groups.items():
            if len(group) >= CLUSTER_THRESHOLD:
                # Use the average position for cluster placement
                avg_col = sum(item[1] // 2 for item in group) // len(group)
                avg_row = sum(item[2] // 4 for item in group) // len(group)
                clusters.append((avg_col, avg_row, len(group)))
            else:
                individual.extend(group)

        # --- Phase 3: render clusters --------------------------------------
        occupancy = _OccupancyGrid(char_w, char_h)

        for char_col, char_row, count in clusters:
            label = f"({count})"
            dot_x = char_col * 2
            dot_y = char_row * 4
            canvas.draw_text(dot_x, dot_y, label)
            # Mark all cells used by the cluster indicator as occupied.
            for i in range(len(label)):
                occupancy.mark(char_col + i, char_row)
            if hasattr(canvas, "set_cell_style"):
                canvas.set_cell_style(char_col, char_row, _STYLE_CLUSTER)

        # --- Phase 4: sort individual stations by priority -----------------
        individual = self._sort_by_priority(
            individual, own_callsign, selected_callsign
        )

        # --- Phase 5: render individual stations with collision avoidance ---
        icon_width = 3  # "(>)" is 3 chars wide
        for station, dot_x, dot_y in individual:
            char_col = dot_x // 2
            char_row = dot_y // 4

            # Draw station symbol marker with parentheses.
            symbol = _symbol_char(station)
            icon_text = f"({symbol})"
            canvas.draw_text(dot_x, dot_y, icon_text)
            for i in range(icon_width):
                occupancy.mark(char_col + i, char_row)

            # Try to place callsign label in 4 candidate positions.
            label = station.callsign
            label_len = len(label)
            placed = False
            for lbl_col, lbl_row in _label_candidates(
                char_col, char_row, label_len, icon_width=icon_width
            ):
                if occupancy.can_place_label(lbl_col, lbl_row, label_len):
                    canvas.draw_text(lbl_col * 2, lbl_row * 4, label)
                    occupancy.mark_label(lbl_col, lbl_row, label_len)
                    placed = True
                    break

            # Apply style to all icon cells.
            style = _choose_style(station, own_callsign, selected_callsign)
            if hasattr(canvas, "set_cell_style"):
                for i in range(icon_width):
                    canvas.set_cell_style(char_col + i, char_row, style)
                if placed:
                    for i in range(label_len):
                        canvas.set_cell_style(lbl_col + i, lbl_row, style)  # noqa: F821

            # Chat indicator
            chats = chat_callsigns or set()
            if station.callsign.upper() in chats:
                # Draw 'C' one cell to the right of the icon
                chat_col = char_col + icon_width
                if not occupancy.is_occupied(chat_col, char_row):
                    canvas.draw_text(chat_col * 2, dot_y, "C")
                    occupancy.mark(chat_col, char_row)
                    if hasattr(canvas, "set_cell_style"):
                        canvas.set_cell_style(chat_col, char_row, _STYLE_CHAT)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _sort_by_priority(
        items: list[tuple[StationRecord, int, int]],
        own_callsign: str,
        selected_callsign: str | None,
    ) -> list[tuple[StationRecord, int, int]]:
        """Sort stations for label placement priority.

        Order: own station first, selected station second, then by
        ``last_heard`` descending (most recent first).
        """

        def _key(item: tuple[StationRecord, int, int]) -> tuple[int, float]:
            stn = item[0]
            if stn.callsign.upper() == own_callsign.upper():
                return (0, 0.0)
            if (
                selected_callsign
                and stn.callsign.upper() == selected_callsign.upper()
            ):
                return (1, 0.0)
            # Lower last_heard → lower priority (sorted later).
            return (2, -stn.last_heard)

        return sorted(items, key=_key)


def _label_candidates(
    char_col: int,
    char_row: int,
    label_len: int,
    icon_width: int = 1,
) -> list[tuple[int, int]]:
    """Return candidate (start_col, row) positions for a callsign label.

    Positions tried in order:
    1. Right of marker (offset by icon_width)
    2. Above marker
    3. Left of marker
    4. Below marker
    """
    return [
        (char_col + icon_width, char_row),  # right
        (char_col, char_row - 1),  # above (label starts at same col)
        (char_col - label_len, char_row),  # left
        (char_col, char_row + 1),  # below (label starts at same col)
    ]
