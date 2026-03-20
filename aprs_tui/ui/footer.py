"""Application footer widget showing TX/RX counters and connection states.

Issue #74: New footer replacing Textual's built-in Footer().
Displays: TX/RX counters | RF connection state | APRS-IS connection state.
"""
from __future__ import annotations

from rich.text import Text
from textual.widget import Widget

from aprs_tui.transport.base import ConnectionState

# Color scheme for connection states
_COLORS = {
    "connected": "#56d364",
    "connecting": "#e3b341",
    "reconnecting": "#e3b341",
    "disconnected": "#f85149",
    "failed": "#f85149",
    "not_configured": "#484f58",
}


class AppFooter(Widget):
    """Bottom footer bar with TX/RX counters, RF state, and APRS-IS state.

    Target rendering:
        TX: 15  RX: 342 | RF: [=] Mobilinkd TNC4 | IS: [=] Connected
    """

    DEFAULT_CSS = """
    AppFooter {
        dock: bottom;
        height: 1;
        background: #1a2233;
        color: #e6edf3;
        padding: 0 1;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._tx_count = 0
        self._rx_count = 0
        self._rf_state = "not_configured"
        self._rf_transport_name = ""
        self._is_state = "not_configured"

    def on_mount(self) -> None:
        """Render the initial footer content."""
        self._refresh_content()

    def render(self) -> Text:
        """Build the footer text from current state."""
        text = Text()

        # TX/RX counters
        text.append(f"TX: {self._tx_count}  RX: {self._rx_count}", style="white")

        text.append(" \u2502 ", style="#30363d")

        # RF connection state
        text.append("RF: ", style="#8b949e")
        rf_segment = self._format_state(self._rf_state, self._rf_transport_name)
        text.append_text(rf_segment)

        text.append(" \u2502 ", style="#30363d")

        # APRS-IS connection state
        text.append("IS: ", style="#8b949e")
        is_segment = self._format_state(self._is_state, "")
        text.append_text(is_segment)

        return text

    @staticmethod
    def _format_state(state: str, transport_name: str) -> Text:
        """Format a connection state segment with icon and color."""
        color = _COLORS.get(state, "#484f58")
        text = Text()

        if state == "connected":
            label = transport_name if transport_name else "Connected"
            text.append(f"[=] {label}", style=f"bold {color}")
        elif state == "connecting":
            text.append("[~] Connecting...", style=color)
        elif state == "reconnecting":
            text.append("[~] Reconnecting...", style=color)
        elif state == "disconnected":
            text.append("[X] Disconnected", style=f"bold {color}")
        elif state == "failed":
            text.append("[X] Failed", style=f"bold {color}")
        else:
            # not_configured or unknown
            text.append("[\u2014] Not configured", style=f"{color}")

        return text

    def _refresh_content(self) -> None:
        """Trigger a re-render of the widget."""
        self.refresh()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update_rf_state(self, state: ConnectionState, transport_name: str = "") -> None:
        """Update the RF connection state display.

        Args:
            state: The new ConnectionState for the RF transport.
            transport_name: Human-readable transport name (e.g. "Mobilinkd TNC4").
        """
        self._rf_state = state.value
        if transport_name:
            self._rf_transport_name = transport_name
        self._refresh_content()

    def update_is_state(self, state: ConnectionState) -> None:
        """Update the APRS-IS connection state display.

        Args:
            state: The new ConnectionState for the APRS-IS connection.
        """
        self._is_state = state.value
        self._refresh_content()

    def increment_tx(self) -> None:
        """Increment the TX packet counter."""
        self._tx_count += 1
        self._refresh_content()

    def increment_rx(self) -> None:
        """Increment the RX packet counter."""
        self._rx_count += 1
        self._refresh_content()

    @property
    def tx_count(self) -> int:
        return self._tx_count

    @property
    def rx_count(self) -> int:
        return self._rx_count

    @property
    def rf_state(self) -> str:
        return self._rf_state

    @property
    def is_state(self) -> str:
        return self._is_state
