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


class MessagePanel(Widget):
    """Combined inbox and compose panel for APRS messaging."""

    DEFAULT_CSS = """
    MessagePanel {
        height: 1fr;
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
        min-height: 3;
    }
    #msg-compose {
        height: auto;
        max-height: 5;
        padding: 0 1;
    }
    #msg-to-input {
        width: 100%;
    }
    #msg-text-input {
        width: 100%;
    }
    .msg-label {
        height: 1;
        padding: 0 1;
        color: #8b949e;
    }
    .msg-counter {
        height: 1;
        padding: 0 1;
        color: #8b949e;
        text-align: right;
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
        with Vertical(id="msg-compose"):
            yield Static("To:", classes="msg-label")
            yield Input(placeholder="Callsign", id="msg-to-input", max_length=9)
            yield Static("Msg:", classes="msg-label")
            yield Input(placeholder="Message (67 chars max)", id="msg-text-input", max_length=67)

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
        line.append(f"{sym:>2s}", style=f"bold {color}")
        line.append(f"  {msg.source:<10s}", style="bold white")
        if msg.state == "received":
            line.append(f"  {msg.text}", style="#58a6ff")
        else:
            line.append(f"  → {msg.destination}: {msg.text}", style=color)
        if msg.msg_id:
            line.append(f"  {{#{msg.msg_id}}}", style=f"dim {color}")

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
