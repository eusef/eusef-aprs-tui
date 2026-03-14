"""Status bar widget showing connection state, callsign, and counters."""
from __future__ import annotations

from textual.widgets import Static
from rich.text import Text

from aprs_tui.transport.base import ConnectionState


class StatusBar(Static):
    """Top status bar with connection info, callsign, and TX/RX counters."""

    DEFAULT_CSS = """
    StatusBar {
        dock: top;
        height: 1;
        background: #1a2233;
        color: #e6edf3;
        padding: 0 1;
        text-style: bold;
    }
    """

    def __init__(self, callsign: str = "", **kwargs) -> None:
        super().__init__(**kwargs)
        self._callsign = callsign
        self._connection_state = "DISCONNECTED"
        self._transport_name = ""
        self._rx_count = 0
        self._tx_count = 0
        self._refresh_content()

    def _refresh_content(self) -> None:
        """Rebuild the status bar text and update display."""
        text = Text()

        # Callsign
        text.append(f" {self._callsign} ", style="bold white")
        text.append("\u2502", style="#30363d")

        # Connection state
        state = self._connection_state
        if state == "CONNECTED":
            text.append(f" [=] {self._transport_name} ", style="bold #56d364")
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
        text.append(f" TX: {self._tx_count}  RX: {self._rx_count} ", style="white")

        self.update(text)

    def update_state(self, state: ConnectionState, transport_name: str = "") -> None:
        """Update connection state and transport name."""
        self._connection_state = state.value.upper()
        if transport_name:
            self._transport_name = transport_name
        self._refresh_content()

    @property
    def connection_state(self) -> str:
        return self._connection_state

    @connection_state.setter
    def connection_state(self, value: str) -> None:
        self._connection_state = value
        self._refresh_content()

    @property
    def callsign(self) -> str:
        return self._callsign

    @callsign.setter
    def callsign(self, value: str) -> None:
        self._callsign = value
        self._refresh_content()

    @property
    def transport_name(self) -> str:
        return self._transport_name

    @property
    def rx_count(self) -> int:
        return self._rx_count

    @property
    def tx_count(self) -> int:
        return self._tx_count

    def increment_rx(self) -> None:
        self._rx_count += 1
        self._refresh_content()

    def increment_tx(self) -> None:
        self._tx_count += 1
        self._refresh_content()
