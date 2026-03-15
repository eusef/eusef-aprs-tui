"""Packet stream panel - real-time decoded APRS packet feed."""
from __future__ import annotations

from rich.text import Text
from textual.widgets import RichLog

from aprs_tui.protocol.types import APRSPacket


# Color map for packet types
PACKET_COLORS = {
    "position": "#58a6ff",    # blue
    "mic-e": "#bc8cff",       # magenta
    "message": "#f0883e",     # orange/yellow
    "weather": "#56d364",     # green
    "object": "#79c0ff",      # light blue
    "status": "#8b949e",      # grey
    "telemetry": "#79c0ff",   # cyan
}

PACKET_PREFIXES = {
    "position": "[POS]",
    "mic-e": "[MIC]",
    "message": "[MSG]",
    "weather": "[WX ]",
    "object": "[OBJ]",
    "status": "[STS]",
    "telemetry": "[TEL]",
}


class StreamPanel(RichLog):
    """Scrolling packet stream with color-coded entries."""

    DEFAULT_CSS = """
    StreamPanel {
        height: 1fr;
        border: solid #30363d;
        border-title-color: #8b949e;
    }
    StreamPanel:focus {
        border: double #58a6ff;
        border-title-color: #58a6ff;
    }
    """

    def __init__(self, callsign: str = "", max_lines: int = 5000, **kwargs) -> None:
        super().__init__(max_lines=max_lines, wrap=True, highlight=True, markup=False, **kwargs)
        self.border_title = "Packet Stream"
        self._callsign = callsign
        self._packet_count = 0
        self._highlight_callsign: str = ""  # Station to highlight
        self._hide_transport: str = ""  # Transport name to hide (e.g., "APRS-IS")
        self._max_lines = max_lines
        self._filter_text: str = ""
        self._filter_type: str = ""  # packet type filter
        self._all_packets: list[APRSPacket] = []  # store all packets for re-filtering
        self._show_raw = False

    @property
    def packet_count(self) -> int:
        return self._packet_count

    def add_packet(self, pkt: APRSPacket) -> None:
        """Add a decoded APRS packet to the stream."""
        self._all_packets.append(pkt)
        # Keep bounded
        if len(self._all_packets) > self._max_lines:
            self._all_packets = self._all_packets[-self._max_lines:]

        if self._passes_filter(pkt):
            self._packet_count += 1
            line = self._format_packet(pkt)
            self.write(line)
            if self._show_raw:
                raw_text = Text(f"  RAW: {pkt.raw}", style="italic #8b949e")
                self.write(raw_text)

    def _passes_filter(self, pkt: APRSPacket) -> bool:
        """Check if packet passes current filter."""
        if self._hide_transport and self._hide_transport in (pkt.transport or ""):
            return False
        if self._filter_type and pkt.info_type != self._filter_type:
            return False
        if self._filter_text:
            search = self._filter_text.upper()
            source = (pkt.source or "").upper()
            raw = (pkt.raw or "").upper()
            if search not in source and search not in raw:
                return False
        return True

    def set_filter(self, text: str = "", packet_type: str = "") -> None:
        """Set filter and re-render matching packets."""
        self._filter_text = text
        self._filter_type = packet_type
        self.clear()
        self._packet_count = 0
        for pkt in self._all_packets:
            if self._passes_filter(pkt):
                self._packet_count += 1
                self.write(self._format_packet(pkt))
                if self._show_raw:
                    raw_text = Text(f"  RAW: {pkt.raw}", style="italic #8b949e")
                    self.write(raw_text)

        # Update border title with filter indicator
        if text or packet_type:
            parts = []
            if text:
                parts.append(f"call={text}")
            if packet_type:
                parts.append(f"type={packet_type}")
            self.border_title = f"Packet Stream [FILTER: {', '.join(parts)}]"
        else:
            self.border_title = "Packet Stream"

    def clear_filter(self) -> None:
        """Clear all filters and re-render."""
        self.set_filter("", "")

    def set_highlight_station(self, callsign: str) -> None:
        """Set a callsign to highlight in the stream. Empty string clears highlight."""
        self._highlight_callsign = callsign.upper()
        self._rerender()

    def _rerender(self) -> None:
        """Re-render all visible packets."""
        self.clear()
        self._packet_count = 0
        for pkt in self._all_packets:
            if self._passes_filter(pkt):
                self._packet_count += 1
                self.write(self._format_packet(pkt))
                if self._show_raw:
                    raw_text = Text(f"  RAW: {pkt.raw}", style="italic #8b949e")
                    self.write(raw_text)

    def toggle_raw(self) -> None:
        """Toggle raw packet display."""
        self._show_raw = not self._show_raw
        # Re-render all packets
        self.clear()
        self._packet_count = 0
        for pkt in self._all_packets:
            if self._passes_filter(pkt):
                self._packet_count += 1
                self.write(self._format_packet(pkt))
                if self._show_raw:
                    raw_text = Text(f"  RAW: {pkt.raw}", style="italic #8b949e")
                    self.write(raw_text)

    def _format_packet(self, pkt: APRSPacket) -> Text:
        """Format an APRSPacket as a Rich Text with color coding."""
        prefix = PACKET_PREFIXES.get(pkt.info_type, "[???]")
        color = PACKET_COLORS.get(pkt.info_type, "#484f58")

        # Check if this packet involves the highlighted station
        is_highlighted = False
        if self._highlight_callsign:
            src = (pkt.source or "").upper()
            addr = (pkt.addressee or "").upper()
            dest = (pkt.destination or "").upper()
            hl = self._highlight_callsign
            if src == hl or addr == hl or dest == hl:
                is_highlighted = True

        text = Text()

        # Highlight marker
        if is_highlighted:
            text.append("▸ ", style="bold #ffa657")
        else:
            text.append("  ")

        text.append(prefix, style=f"bold {color}")
        text.append(" ")

        # Source callsign - highlight own callsign or selected station
        source_style = f"bold {color}"
        if self._callsign and pkt.source and pkt.source.upper() == self._callsign.upper():
            source_style = "bold #ffa657 on #3d2200"
        elif is_highlighted and (pkt.source or "").upper() == self._highlight_callsign:
            source_style = "bold #ffa657"
        text.append(f"{pkt.source or '???':<10s}", style=source_style)

        if pkt.parse_error:
            text.append(f"  (parse error) {pkt.raw[:60]}", style="dim #f85149")
        elif pkt.info_type in ("position", "mic-e"):
            if pkt.latitude is not None and pkt.longitude is not None:
                text.append(f"  {pkt.latitude:.4f}\u00b0N {pkt.longitude:.4f}\u00b0W", style=color)
            if pkt.comment:
                text.append(f'  "{pkt.comment}"', style=f"dim {color}")
        elif pkt.info_type == "message":
            if pkt.is_ack:
                text.append(f"  ack#{pkt.message_id}", style=color)
            elif pkt.is_rej:
                text.append(f"  rej#{pkt.message_id}", style=color)
            else:
                addr = pkt.addressee or "?"
                # Highlight if message is to own callsign
                addr_style = color
                if self._callsign and addr.upper() == self._callsign.upper():
                    addr_style = "bold #ffa657 on #3d2200"
                text.append(f"  \u2192 {addr}", style=addr_style)
                text.append(f'  "{pkt.message_text or ""}"', style=color)
                if pkt.message_id:
                    text.append(f"  {{#{pkt.message_id}}}", style=f"dim {color}")
        elif pkt.info_type == "weather":
            parts = []
            if pkt.wx_temperature is not None:
                parts.append(f"{pkt.wx_temperature:.0f}\u00b0F")
            if pkt.wx_wind_speed is not None:
                parts.append(f"Wind {pkt.wx_wind_speed:.0f}mph@{pkt.wx_wind_dir or 0}\u00b0")
            if pkt.wx_pressure is not None:
                parts.append(f"Baro {pkt.wx_pressure:.1f}")
            text.append(f"  {'  '.join(parts)}", style=color)
        elif pkt.info_type == "object":
            text.append(f'  "{pkt.object_name}"', style=color)
        elif pkt.info_type == "status":
            text.append(f'  "{pkt.status_text}"', style=color)
        elif pkt.info_type == "telemetry":
            if pkt.telemetry_values:
                text.append(f"  #{pkt.telemetry_seq} {pkt.telemetry_values}", style=color)

        return text
