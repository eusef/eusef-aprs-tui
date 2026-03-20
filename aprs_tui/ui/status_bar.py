"""Header status bar widget showing callsign and clock.

Issue #73: Redesigned header — callsign + clock on left, ko-fi on right.
TX/RX counters and connection state moved to AppFooter (#74).
"""
from __future__ import annotations

from datetime import datetime, timezone

from rich.text import Text
from textual.widget import Widget
from textual.widgets import Static


class StatusBar(Widget):
    """Top header bar with callsign + clock (left) and ko-fi link (right).

    Replaces the old single-line Static that showed connection state and
    TX/RX counters. Those now live in AppFooter (issue #74).

    Backward-compatible properties (callsign, connection_state,
    transport_name, rx_count, tx_count, increment_rx, increment_tx,
    update_state) are retained so existing code that references them
    does not crash, but they no longer affect the header rendering.
    """

    DEFAULT_CSS = """
    StatusBar {
        dock: top;
        height: 1;
        background: #1a2233;
        color: #e6edf3;
        padding: 0 1;
        text-style: bold;
        layout: horizontal;
    }

    StatusBar #header-left {
        width: 1fr;
        height: 1;
        content-align: left middle;
    }

    StatusBar #header-right {
        width: auto;
        height: 1;
        content-align: right middle;
    }
    """

    def __init__(self, callsign: str = "", **kwargs) -> None:
        super().__init__(**kwargs)
        self._callsign = callsign
        # Backward-compat state (no longer rendered in header)
        self._connection_state = "DISCONNECTED"
        self._transport_name = ""
        self._rx_count = 0
        self._tx_count = 0

    def compose(self):
        """Compose the header with left and right regions."""
        yield Static(id="header-left")
        yield Static(id="header-right")

    def on_mount(self) -> None:
        """Start the clock timer and do initial render."""
        self._update_clock()
        self.set_interval(1, self._update_clock)
        self._update_kofi()

    def _update_clock(self) -> None:
        """Refresh the left region with callsign + dual clock."""
        now_local = datetime.now().astimezone()
        now_utc = datetime.now(timezone.utc)

        local_time = now_local.strftime("%H:%M")
        local_tz = now_local.strftime("%Z") or "LCL"
        utc_time = now_utc.strftime("%H:%M")

        text = Text()
        text.append(f"{self._callsign}", style="bold white")
        text.append(f"  {local_time} {local_tz} / {utc_time} UTC", style="#8b949e")

        try:
            self.query_one("#header-left", Static).update(text)
        except Exception:
            pass

    def _update_kofi(self) -> None:
        """Set the right region with ko-fi link."""
        text = Text()
        text.append("\u2615 ko-fi.com/philj2", style="#e3b341")
        try:
            self.query_one("#header-right", Static).update(text)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Backward-compatible API (state moved to AppFooter in #74)
    # ------------------------------------------------------------------

    def update_state(self, state, transport_name: str = "") -> None:
        """Update connection state (retained for backward compat).

        In the new design, connection state is shown in AppFooter.
        This method stores the values but does not affect header rendering.
        """
        if hasattr(state, "value"):
            self._connection_state = state.value.upper()
        else:
            self._connection_state = str(state).upper()
        if transport_name:
            self._transport_name = transport_name

    @property
    def connection_state(self) -> str:
        return self._connection_state

    @connection_state.setter
    def connection_state(self, value: str) -> None:
        self._connection_state = value

    @property
    def callsign(self) -> str:
        return self._callsign

    @callsign.setter
    def callsign(self, value: str) -> None:
        self._callsign = value
        if self.is_mounted:
            self._update_clock()

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

    def increment_tx(self) -> None:
        self._tx_count += 1
