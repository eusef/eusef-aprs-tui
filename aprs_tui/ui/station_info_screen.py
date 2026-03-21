"""Station information screen -- displays details about a selected station."""
from __future__ import annotations

import time

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import Static

from aprs_tui.core.station_tracker import StationRecord


class StationInfoScreen(ModalScreen[None]):
    """Modal overlay showing station details."""

    CSS = """
    StationInfoScreen {
        align: center middle;
    }
    #info-outer {
        width: 60;
        max-width: 85%;
        height: auto;
        max-height: 80%;
        background: #161b22;
        border: solid #58a6ff;
        border-title-color: #58a6ff;
        padding: 1 2;
    }
    #info-content {
        height: auto;
        margin: 0;
        padding: 0;
    }
    #info-footer {
        height: 1;
        color: #484f58;
        margin-top: 1;
    }
    """

    BINDINGS = [
        Binding("escape", "close", "Close", priority=True),
        Binding("enter", "open_chat", "Chat", priority=True),
    ]

    class OpenChat(Message):
        def __init__(self, callsign: str) -> None:
            super().__init__()
            self.callsign = callsign

    def __init__(self, station: StationRecord, **kwargs) -> None:
        super().__init__(**kwargs)
        self.station = station

    def compose(self) -> ComposeResult:
        with Vertical(id="info-outer"):
            yield Static(id="info-content")
            yield Static(
                "[dim]Enter[/dim] Chat  [dim]Esc[/dim] Close",
                id="info-footer",
                markup=True,
            )

    def on_mount(self) -> None:
        self.query_one("#info-outer").border_title = f" Station: {self.station.callsign} "
        content = self._build_content()
        self.query_one("#info-content", Static).update(content)

    def _build_content(self) -> Text:
        stn = self.station
        text = Text()

        def _row(label: str, value: str) -> None:
            text.append(f"  {label:<14}", style="bold #8b949e")
            text.append(f"{value}\n", style="#e6edf3")

        _row("Callsign:", stn.callsign)

        # Symbol
        sym = ""
        if stn.symbol_table and stn.symbol_code:
            sym = f"{stn.symbol_table}{stn.symbol_code}"
        _row("Symbol:", sym or "Unknown")

        # Position
        if stn.latitude is not None and stn.longitude is not None:
            lat_dir = "N" if stn.latitude >= 0 else "S"
            lon_dir = "E" if stn.longitude >= 0 else "W"
            _row("Position:", f"{abs(stn.latitude):.4f}{lat_dir} {abs(stn.longitude):.4f}{lon_dir}")
        else:
            _row("Position:", "Unknown")

        # Comment
        if stn.comment:
            _row("Comment:", stn.comment)

        # Last heard
        if stn.last_heard:
            age = time.monotonic() - stn.last_heard
            if age < 60:
                age_str = f"{int(age)}s ago"
            elif age < 3600:
                age_str = f"{int(age / 60)}m ago"
            else:
                age_str = f"{int(age / 3600)}h ago"
            _row("Last Heard:", age_str)

        # Distance
        if stn.distance_km is not None:
            _row("Distance:", f"{stn.distance_km:.1f} km")

        # Bearing
        if stn.bearing is not None:
            _row("Bearing:", f"{stn.bearing:.0f}")

        # Packets
        _row("Packets:", str(stn.packet_count))

        # Sources
        if stn.sources:
            _row("Sources:", ", ".join(sorted(stn.sources)))

        # Info type
        if stn.last_info_type:
            _row("Info Type:", stn.last_info_type)

        return text

    def action_close(self) -> None:
        self.dismiss(None)

    def action_open_chat(self) -> None:
        self.post_message(self.OpenChat(self.station.callsign))
        self.dismiss(None)
