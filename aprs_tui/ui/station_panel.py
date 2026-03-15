"""Station list panel with sortable DataTable."""
from __future__ import annotations

import time

from textual.message import Message
from textual.widgets import DataTable

from aprs_tui.core.station_tracker import StationRecord


SORT_KEYS = ["last_heard", "callsign", "distance"]

# Symbol display map (subset)
SYMBOL_MAP = {
    "/>": "[car]",
    "/[": "[jog]",
    "/-": "[hse]",
    "/k": "[trk]",
    "/_": "[wx]",
    "/#": "[dgi]",
    "/&": "[gw]",
    "/b": "[bik]",
}


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
        self._callsigns: list[str] = []  # Track callsigns by row index
        self.selected_callsign: str = ""
        self._user_selected = False  # True once user explicitly selects a station

    def on_mount(self) -> None:
        self.add_columns("Callsign", "Sym", "Last Heard", "Dist", "Brg", "Pkts")
        self.cursor_type = "row"
        self.show_cursor = False  # No selection by default

    def refresh_stations(self, stations: list[StationRecord]) -> None:
        """Update the table with current station data, preserving selection."""
        # Remember current selection
        prev_callsign = self.selected_callsign

        self.clear()
        self._callsigns.clear()
        now = time.monotonic()
        for stn in stations:
            age = now - stn.last_heard if stn.last_heard else 0
            sym_key = f"{stn.symbol_table or ''}{stn.symbol_code or ''}"
            sym = SYMBOL_MAP.get(sym_key, "")
            dist = f"{stn.distance_km:.1f}km" if stn.distance_km is not None else ""
            brg = f"{stn.bearing:.0f}\u00b0" if stn.bearing is not None else ""
            self.add_row(
                stn.callsign, sym, _format_age(age), dist, brg, str(stn.packet_count)
            )
            self._callsigns.append(stn.callsign)
        self.border_title = f"Stations ({len(stations)})"

        # Restore selection if user had selected a station
        if self._user_selected and prev_callsign and prev_callsign in self._callsigns:
            row_idx = self._callsigns.index(prev_callsign)
            try:
                self.move_cursor(row=row_idx)
            except Exception:
                pass

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

    def cycle_sort(self) -> str:
        """Cycle through sort options. Returns the new sort key."""
        self._sort_idx = (self._sort_idx + 1) % len(SORT_KEYS)
        self._sort_key = SORT_KEYS[self._sort_idx]
        return self._sort_key

    @property
    def sort_key(self) -> str:
        return self._sort_key
