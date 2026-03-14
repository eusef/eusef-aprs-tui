"""Status bar widget showing connection state, callsign, and counters."""
from __future__ import annotations

from textual.app import RenderResult
from textual.reactive import reactive
from textual.widget import Widget
from rich.text import Text

from aprs_tui.transport.base import ConnectionState


class StatusBar(Widget):
    """Bottom status bar with connection info, callsign, and TX/RX counters."""

    DEFAULT_CSS = """
    StatusBar {
        dock: top;
        height: 3;
        background: #1a2233;
        color: #e6edf3;
        padding: 1 1;
        border-bottom: solid #30363d;
    }
    """

    callsign: reactive[str] = reactive("")
    connection_state: reactive[str] = reactive("DISCONNECTED")
    transport_name: reactive[str] = reactive("")
    rx_count: reactive[int] = reactive(0)
    tx_count: reactive[int] = reactive(0)

    def __init__(self, callsign: str = "", **kwargs) -> None:
        super().__init__(**kwargs)
        self.callsign = callsign

    def render(self) -> RenderResult:
        text = Text()

        # Callsign
        text.append(f" {self.callsign} ", style="bold white")
        text.append("\u2502", style="#30363d")

        # Connection state
        state = self.connection_state
        if state == "CONNECTED":
            text.append(f" [=] {self.transport_name} ", style="bold #56d364")
        elif state == "DISCONNECTED":
            text.append(" [X] NOT CONNECTED ", style="bold #f85149")
        elif state == "CONNECTING":
            text.append(" [~] Connecting... ", style="#e3b341")
        elif state == "RECONNECTING":
            text.append(" [~] Reconnecting... ", style="#e3b341")
        elif state == "FAILED":
            text.append(" [X] FAILED ", style="bold #f85149")

        text.append("\u2502", style="#30363d")

        # TX/RX counters
        text.append(f" TX: {self.tx_count}  RX: {self.rx_count} ", style="white")

        return text

    def update_state(self, state: ConnectionState, transport_name: str = "") -> None:
        """Update connection state and transport name."""
        self.connection_state = state.value.upper()
        if transport_name:
            self.transport_name = transport_name

    def increment_rx(self) -> None:
        self.rx_count += 1

    def increment_tx(self) -> None:
        self.tx_count += 1
