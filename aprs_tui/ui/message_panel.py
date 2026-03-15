"""Message panel with inbox and compose interface."""
from __future__ import annotations

from dataclasses import dataclass, field
import time

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widget import Widget
from textual.widgets import Input, RichLog, Static


# Message state symbols
STATE_SYMBOLS = {
    "pending": (">>", "#e3b341"),    # yellow
    "acked": ("OK", "#56d364"),      # green
    "rejected": ("RJ", "#f85149"),   # red
    "failed": ("!!", "#f85149"),     # red
    "received": ("<<", "#58a6ff"),   # blue
}


@dataclass
class DisplayMessage:
    """A message for display in the inbox."""
    source: str
    destination: str
    text: str
    msg_id: str | None = None
    state: str = "received"  # pending, acked, rejected, failed, received
    timestamp: float = field(default_factory=time.monotonic)
    retry_info: str = ""  # e.g., "2/5, retry in 30s"


class MessagePanel(Widget):
    """Combined inbox and compose panel for APRS messaging."""

    DEFAULT_CSS = """
    MessagePanel {
        height: auto;
        max-height: 12;
        border: solid #30363d;
        border-title-color: #8b949e;
        layout: vertical;
    }
    MessagePanel:focus-within {
        border: double #58a6ff;
        border-title-color: #58a6ff;
    }
    #msg-inbox {
        height: 1fr;
        min-height: 2;
        max-height: 6;
    }
    #msg-to-input {
        width: 100%;
        margin: 0 0;
    }
    #msg-text-input {
        width: 100%;
        margin: 0 0;
    }
    """

    BINDINGS = [
        Binding("escape", "focus_inbox", "Back to inbox", show=False),
    ]

    def __init__(self, callsign: str = "", **kwargs) -> None:
        super().__init__(**kwargs)
        self.border_title = "Messages (0)"
        self._callsign = callsign
        self._messages: list[DisplayMessage] = []

    def compose(self) -> ComposeResult:
        yield RichLog(id="msg-inbox", wrap=True, markup=False)
        yield Input(placeholder="To: callsign", id="msg-to-input", max_length=9)
        yield Input(placeholder="Msg: (67 chars max) Enter to send", id="msg-text-input", max_length=67)

    def add_received_message(self, source: str, text: str, msg_id: str | None = None) -> None:
        """Add an inbound message to the inbox."""
        msg = DisplayMessage(
            source=source, destination=self._callsign,
            text=text, msg_id=msg_id, state="received",
        )
        self._messages.append(msg)
        self._render_message(msg)
        self.border_title = f"Messages ({len(self._messages)})"

    def add_sent_message(self, destination: str, text: str, msg_id: str, state: str = "pending") -> None:
        """Add an outbound message to the inbox."""
        msg = DisplayMessage(
            source=self._callsign, destination=destination,
            text=text, msg_id=msg_id, state=state,
        )
        self._messages.append(msg)
        self._render_message(msg)
        self.border_title = f"Messages ({len(self._messages)})"

    def update_message_state(self, msg_id: str, new_state: str) -> None:
        """Update the state of a tracked outbound message."""
        for msg in self._messages:
            if msg.msg_id == msg_id:
                msg.state = new_state
                msg.retry_info = ""  # Clear retry info on state change
                break
        self._refresh_inbox()

    def update_retry_info(self, msg_id: str, info: str) -> None:
        """Update the retry status display for a pending message."""
        for msg in self._messages:
            if msg.msg_id == msg_id:
                msg.retry_info = info
                break
        self._refresh_inbox()

    def get_compose_values(self) -> tuple[str, str]:
        """Get the current callsign and message text from compose inputs."""
        to_input = self.query_one("#msg-to-input", Input)
        text_input = self.query_one("#msg-text-input", Input)
        return to_input.value.strip(), text_input.value.strip()

    def clear_compose(self) -> None:
        """Clear the compose inputs."""
        self.query_one("#msg-to-input", Input).value = ""
        self.query_one("#msg-text-input", Input).value = ""

    def _render_message(self, msg: DisplayMessage) -> None:
        """Render a single message to the inbox log."""
        inbox = self.query_one("#msg-inbox", RichLog)
        sym, color = STATE_SYMBOLS.get(msg.state, ("??", "#484f58"))

        line = Text()

        # Status symbol
        line.append(f" {sym} ", style=f"bold {color}")

        if msg.state == "received":
            # Inbound: << FROM: message text
            line.append(f"{msg.source:<10s} ", style="bold #58a6ff")
            line.append(msg.text, style="#58a6ff")
        else:
            # Outbound: >> → DEST: message text
            line.append(f"→ {msg.destination:<10s} ", style=f"bold {color}")
            line.append(msg.text, style=color)

        # Message ID
        if msg.msg_id:
            line.append(f"  #{msg.msg_id}", style=f"dim {color}")

        # Retry info for pending messages
        if msg.retry_info:
            line.append(f"  [{msg.retry_info}]", style=f"bold {color}")

        # State label for completed messages
        if msg.state == "acked":
            line.append("  DELIVERED", style="bold #56d364")
        elif msg.state == "failed":
            line.append("  FAILED", style="bold #f85149")
        elif msg.state == "rejected":
            line.append("  REJECTED", style="bold #f85149")

        inbox.write(line)

    def _refresh_inbox(self) -> None:
        """Re-render all messages (for state updates)."""
        inbox = self.query_one("#msg-inbox", RichLog)
        inbox.clear()
        for msg in self._messages:
            self._render_message(msg)

    def action_focus_inbox(self) -> None:
        inbox = self.query_one("#msg-inbox", RichLog)
        inbox.focus()
