"""Station list panel with sortable DataTable."""
from __future__ import annotations

import time

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

    def on_mount(self) -> None:
        self.add_columns("Callsign", "Sym", "Last Heard", "Dist", "Brg", "Pkts")
        self.cursor_type = "row"

    def refresh_stations(self, stations: list[StationRecord]) -> None:
        """Update the table with current station data."""
        self.clear()
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
        self.border_title = f"Stations ({len(stations)})"

    def cycle_sort(self) -> str:
        """Cycle through sort options. Returns the new sort key."""
        self._sort_idx = (self._sort_idx + 1) % len(SORT_KEYS)
        self._sort_key = SORT_KEYS[self._sort_idx]
        return self._sort_key

    @property
    def sort_key(self) -> str:
        return self._sort_key
