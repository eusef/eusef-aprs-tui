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

# Cluster threshold — cells with this many or more stations render as a count.
CLUSTER_THRESHOLD = 3

# Style names that will be applied once set_cell_style is available.
_STYLE_OWN = "station_own"
_STYLE_SELECTED = "station_selected"
_STYLE_RF = "station_rf"
_STYLE_IS = "station_is"
_STYLE_EMERGENCY = "station_emergency"
_STYLE_CLUSTER = "station_rf"


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
        for c in range(start_col, start_col + length):
            if self.is_occupied(c, row):
                return False
        return True

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
    ) -> None:
        """Plot all stations onto the canvas with collision-aware labels.

        Steps:
        1. Convert all stations to pixel positions, discard out-of-bounds.
        2. Group by character cell; cells with 3+ stations become clusters.
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

        # --- Phase 2: group by character cell ------------------------------
        cell_groups: dict[tuple[int, int], list[tuple[StationRecord, int, int]]] = (
            defaultdict(list)
        )
        for station, dot_x, dot_y in positioned:
            char_col = dot_x // 2
            char_row = dot_y // 4
            cell_groups[(char_col, char_row)].append((station, dot_x, dot_y))

        # Separate clusters from individual stations.
        individual: list[tuple[StationRecord, int, int]] = []
        clusters: list[tuple[int, int, int]] = []  # (char_col, char_row, count)

        for (char_col, char_row), group in cell_groups.items():
            if len(group) >= CLUSTER_THRESHOLD:
                clusters.append((char_col, char_row, len(group)))
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
        for station, dot_x, dot_y in individual:
            char_col = dot_x // 2
            char_row = dot_y // 4

            # Draw station symbol marker.
            symbol = _symbol_char(station)
            canvas.draw_text(dot_x, dot_y, symbol)
            occupancy.mark(char_col, char_row)

            # Try to place callsign label in 4 candidate positions.
            label = station.callsign
            label_len = len(label)
            placed = False
            for lbl_col, lbl_row in _label_candidates(
                char_col, char_row, label_len
            ):
                if occupancy.can_place_label(lbl_col, lbl_row, label_len):
                    canvas.draw_text(lbl_col * 2, lbl_row * 4, label)
                    occupancy.mark_label(lbl_col, lbl_row, label_len)
                    placed = True
                    break

            # Apply style.
            style = _choose_style(station, own_callsign, selected_callsign)
            if hasattr(canvas, "set_cell_style"):
                canvas.set_cell_style(char_col, char_row, style)
                if placed:
                    for i in range(label_len):
                        canvas.set_cell_style(lbl_col + i, lbl_row, style)  # noqa: F821

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
) -> list[tuple[int, int]]:
    """Return candidate (start_col, row) positions for a callsign label.

    Positions tried in order:
    1. Right of marker
    2. Above marker
    3. Left of marker
    4. Below marker
    """
    return [
        (char_col + 1, char_row),  # right
        (char_col, char_row - 1),  # above (label starts at same col)
        (char_col - label_len, char_row),  # left
        (char_col, char_row + 1),  # below (label starts at same col)
    ]
