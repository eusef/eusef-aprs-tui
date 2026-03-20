"""Station list panel with sortable DataTable."""
from __future__ import annotations

import contextlib
import time

from textual.message import Message
from textual.widgets import DataTable

from rich.text import Text as RichText

from aprs_tui.core.station_tracker import StationRecord, is_rf_station, is_is_only_station

SORT_KEYS = ["last_heard", "callsign", "distance"]

SORT_COLUMNS = {
    "Callsign":   {"key": "callsign",      "default_reverse": False},
    "Last Heard": {"key": "last_heard",     "default_reverse": True},   # Most recent first
    "Dist":       {"key": "distance",       "default_reverse": False},
    "Brg":        {"key": "bearing",        "default_reverse": False},
    "Pkts":       {"key": "packet_count",   "default_reverse": True},   # Most packets first
}

# Symbol display map – ~25 most common APRS primary symbols
SYMBOL_MAP = {
    "/>": "Car", "/[": "Jog", "/-": "Hse", "/k": "Trk",
    "/_": "WX",  "/#": "Dgi", "/&": "GW",  "/b": "Bik",
    "/O": "Bal", "/R": "RV",  "/Y": "Yht", "/u": "18W",
    "/p": "Rov", "/s": "Boa", "/v": "Van", "/j": "Jep",
    "/f": "FD",  "/a": "Amb", "/U": "Bus", "/X": "Hel",
    "/g": "Air", "/^": "Ant", "\\n": "EM!", "/!": "Pol",
    "/'": "Air", "/=": "Trn",
}
DEFAULT_SYMBOL = "---"


def _format_age(seconds: float) -> str:
    if seconds < 60:
        return f"{int(seconds)}s"
    if seconds < 3600:
        return f"{int(seconds / 60)}m"
    if seconds < 86400:
        return f"{int(seconds / 3600)}h"
    return f"{int(seconds / 86400)}d"


class StationPanel(DataTable):

    class StationSelected(Message):
        """Posted when a station row is selected (cursor moved)."""
        def __init__(self, callsign: str) -> None:
            super().__init__()
            self.callsign = callsign

    class StationActivated(Message):
        """Posted when a station row is activated (Enter/double-click)."""
        def __init__(self, callsign: str) -> None:
            super().__init__()
            self.callsign = callsign

    class SortChanged(Message):
        """Posted when the sort column or direction changes."""
        def __init__(self, sort_key: str, reverse: bool) -> None:
            super().__init__()
            self.sort_key = sort_key
            self.reverse = reverse

    DEFAULT_CSS = """
    StationPanel {
        height: 1fr;
        border: solid #30363d;
        border-title-color: #8b949e;
    }
    StationPanel:focus {
        border: double #58a6ff;
        border-title-color: #58a6ff;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.border_title = "Stations (0)"
        self._sort_key = "last_heard"
        self._sort_idx = 0
        self._sort_column: str = "Last Heard"  # Default sort column
        self._sort_reverse: bool = True         # Default for Last Heard
        self._callsigns: list[str] = []  # Track callsigns by row index
        self.selected_callsign: str = ""
        self._user_selected = False  # True once user explicitly selects a station

    def on_mount(self) -> None:
        self.add_columns("Callsign", "Sym", "Last Heard", "Dist", "Brg", "Pkts")
        self.cursor_type = "row"
        self.show_cursor = False  # No selection by default
        self._update_column_headers()

    def refresh_stations(self, stations: list[StationRecord],
                         chat_callsigns: set[str] | None = None) -> None:
        """Update the table with current station data, preserving selection.

        Args:
            stations: List of station records to display
            chat_callsigns: Set of callsigns with chat history (shown with indicator)
        """
        # Remember current selection
        prev_callsign = self.selected_callsign
        chats = chat_callsigns or set()

        self.clear()
        self._callsigns.clear()
        now = time.monotonic()
        for stn in stations:
            age = now - stn.last_heard if stn.last_heard else 0
            sym_key = f"{stn.symbol_table or ''}{stn.symbol_code or ''}"
            sym = SYMBOL_MAP.get(sym_key, DEFAULT_SYMBOL)
            dist = f"{stn.distance_km:.1f}km" if stn.distance_km is not None else ""
            brg = f"{stn.bearing:.0f}\u00b0" if stn.bearing is not None else ""
            # Chat indicator + RF/IS color
            call_text = RichText()
            if stn.callsign.upper() in chats:
                call_text.append("\U0001f4ac ", style="")
            if is_rf_station(stn):
                call_text.append(stn.callsign, style="bold #56d364")
            elif is_is_only_station(stn):
                call_text.append(stn.callsign, style="dim #6e7681")
            else:
                call_text.append(stn.callsign)
            self.add_row(
                call_text, sym, _format_age(age), dist, brg, str(stn.packet_count)
            )
            self._callsigns.append(stn.callsign)
        self.border_title = f"Stations ({len(stations)})"

        # Restore selection if user had selected a station
        if self._user_selected and prev_callsign and prev_callsign in self._callsigns:
            row_idx = self._callsigns.index(prev_callsign)
            with contextlib.suppress(Exception):
                self.move_cursor(row=row_idx)

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """When cursor moves to a row, post StationSelected."""
        if not self._user_selected:
            return  # Don't fire until user explicitly interacts
        if event.cursor_row < len(self._callsigns):
            self.selected_callsign = self._callsigns[event.cursor_row]
            self.post_message(self.StationSelected(self.selected_callsign))

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """When Enter/double-click on a row, post StationActivated."""
        if event.cursor_row < len(self._callsigns):
            callsign = self._callsigns[event.cursor_row]
            self._user_selected = True
            self.show_cursor = True
            self.selected_callsign = callsign
            self.post_message(self.StationActivated(callsign))

    def on_focus(self) -> None:
        """When station panel gets focus, enable cursor."""
        if self._callsigns:
            self._user_selected = True
            self.show_cursor = True
            # Post selection for current row
            if self.cursor_row < len(self._callsigns):
                self.selected_callsign = self._callsigns[self.cursor_row]
                self.post_message(self.StationSelected(self.selected_callsign))

    def on_blur(self) -> None:
        """When station panel loses focus, keep selection but clear highlight."""
        pass  # Keep the highlight active even when unfocused

    def select_callsign(self, callsign: str) -> None:
        """Programmatically select a station row (called from app)."""
        if callsign == self.selected_callsign:
            return  # Guard against infinite loop
        if callsign in self._callsigns:
            self._user_selected = True
            self.show_cursor = True
            row_idx = self._callsigns.index(callsign)
            with contextlib.suppress(Exception):
                self.move_cursor(row=row_idx)
            self.selected_callsign = callsign

    def on_data_table_header_selected(self, event: DataTable.HeaderSelected) -> None:
        """Handle column header click to change sort column/direction."""
        column_label = event.label.plain if hasattr(event.label, 'plain') else str(event.label)
        # Strip existing sort indicators
        column_label = column_label.replace(" \u25b2", "").replace(" \u25bc", "").replace(" \u21d5", "").strip()
        if column_label not in SORT_COLUMNS:
            return  # "Sym" column, not sortable
        if column_label == self._sort_column:
            self._sort_reverse = not self._sort_reverse
        else:
            self._sort_column = column_label
            self._sort_reverse = SORT_COLUMNS[column_label]["default_reverse"]
        self._update_column_headers()
        # Notify app to refresh
        self.post_message(self.SortChanged(self.sort_key, self._sort_reverse))

    def _update_column_headers(self) -> None:
        """Update column headers to show sort indicator on active column."""
        for col in self.columns.values():
            label = col.label.plain if hasattr(col.label, 'plain') else str(col.label)
            label = label.replace(" \u25b2", "").replace(" \u25bc", "").replace(" \u21d5", "").strip()
            if label == self._sort_column:
                indicator = " \u25bc" if self._sort_reverse else " \u25b2"
                col.label = label + indicator
            elif label in SORT_COLUMNS:
                col.label = label + " \u21d5"
            else:
                col.label = label

    def cycle_sort(self) -> str:
        """Cycle through sort options. Returns the new sort key."""
        self._sort_idx = (self._sort_idx + 1) % len(SORT_KEYS)
        self._sort_key = SORT_KEYS[self._sort_idx]
        # Also update column-based sort state to stay in sync
        key_to_column = {v["key"]: k for k, v in SORT_COLUMNS.items()}
        if self._sort_key in key_to_column:
            self._sort_column = key_to_column[self._sort_key]
            self._sort_reverse = SORT_COLUMNS[self._sort_column]["default_reverse"]
        return self._sort_key

    @property
    def sort_key(self) -> str:
        if self._sort_column in SORT_COLUMNS:
            return SORT_COLUMNS[self._sort_column]["key"]
        return "last_heard"

    @property
    def sort_reverse(self) -> bool:
        return self._sort_reverse
