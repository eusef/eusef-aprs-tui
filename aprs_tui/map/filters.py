"""Map-specific station visibility toggles (RF/IS/WX/Digi)."""
from __future__ import annotations

from dataclasses import dataclass

from aprs_tui.core.station_tracker import StationRecord, is_is_only_station, is_rf_station


@dataclass
class MapFilters:
    """Map-specific visibility toggles. Session-only (not persisted)."""

    show_is_stations: bool = True
    show_rf_stations: bool = True
    show_wx_stations: bool = True
    show_digi_stations: bool = True
    show_tracks: bool = True

    def toggle_is(self) -> bool:
        """Toggle APRS-IS station visibility. Returns new state."""
        self.show_is_stations = not self.show_is_stations
        return self.show_is_stations

    def toggle_rf(self) -> bool:
        """Toggle RF station visibility. Returns new state."""
        self.show_rf_stations = not self.show_rf_stations
        return self.show_rf_stations

    def toggle_wx(self) -> bool:
        """Toggle weather station visibility. Returns new state."""
        self.show_wx_stations = not self.show_wx_stations
        return self.show_wx_stations

    def toggle_digi(self) -> bool:
        """Toggle digipeater/igate visibility. Returns new state."""
        self.show_digi_stations = not self.show_digi_stations
        return self.show_digi_stations

    def toggle_tracks(self) -> bool:
        """Toggle track visibility. Returns new state."""
        self.show_tracks = not self.show_tracks
        return self.show_tracks

    def filter_stations(self, stations: list[StationRecord]) -> list[StationRecord]:
        """Return only stations that pass the current filter set."""
        result = []
        for stn in stations:
            if not self._passes_filter(stn):
                continue
            result.append(stn)
        return result

    def _passes_filter(self, stn: StationRecord) -> bool:
        """Check if a station passes all active filters."""
        # Source filter
        if is_is_only_station(stn) and not self.show_is_stations:
            return False
        if is_rf_station(stn) and not self.show_rf_stations:
            return False

        # Type filter: weather stations
        if not self.show_wx_stations and stn.symbol_table and stn.symbol_code:
            sym = stn.symbol_table + stn.symbol_code
            if sym == "/_":  # Weather station symbol
                return False

        # Type filter: digipeaters/igates
        if not self.show_digi_stations and stn.symbol_table and stn.symbol_code:
            sym = stn.symbol_table + stn.symbol_code
            if sym in ("/#", "/&"):  # Digipeater, iGate
                return False

        return True

    def status_text(self, stations: list[StationRecord]) -> str:
        """Generate filter status string for the map panel header.

        Format: 'RF:8 IS:14' or 'RF:8 IS:hidden'
        """
        visible = self.filter_stations(stations)
        rf_count = sum(
            1 for s in visible if s.latitude is not None and is_rf_station(s)
        )
        is_count = sum(
            1 for s in visible if s.latitude is not None and is_is_only_station(s)
        )

        parts = []
        parts.append(f"RF:{rf_count}" if self.show_rf_stations else "RF:hidden")
        parts.append(f"IS:{is_count}" if self.show_is_stations else "IS:hidden")

        extras = []
        if not self.show_wx_stations:
            extras.append("WX:hidden")
        if not self.show_digi_stations:
            extras.append("DG:hidden")

        return " ".join(parts + extras)

    def reset(self) -> None:
        """Reset all filters to defaults (all visible)."""
        self.show_is_stations = True
        self.show_rf_stations = True
        self.show_wx_stations = True
        self.show_digi_stations = True
        self.show_tracks = True
