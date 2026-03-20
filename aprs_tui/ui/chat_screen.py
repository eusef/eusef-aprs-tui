"""Chat screen - isolated conversation view with a single station."""
from __future__ import annotations

import contextlib
import time
from dataclasses import dataclass, field

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import Input, RichLog, Static

from aprs_tui.ui.mini_map import MiniMapWidget


@dataclass
class ChatMessage:
    """A single message in a conversation."""
    direction: str  # "sent" or "received"
    text: str
    msg_id: str | None = None
    state: str = ""  # pending, acked, failed, received
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "direction": self.direction,
            "text": self.text,
            "msg_id": self.msg_id,
            "state": self.state,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, d: dict) -> ChatMessage:
        return cls(
            direction=d.get("direction", "received"),
            text=d.get("text", ""),
            msg_id=d.get("msg_id"),
            state=d.get("state", ""),
            timestamp=d.get("timestamp", time.time()),
        )


class ChatScreen(ModalScreen[None]):
    """Modal chat overlay with a single station. Background activity visible."""

    CSS = """
    ChatScreen {
        align: center middle;
    }
    #chat-outer {
        width: 80;
        max-width: 85%;
        height: 70%;
        background: #161b22;
        border: solid #58a6ff;
        border-title-color: #58a6ff;
        padding: 0 1;
    }
    #chat-body {
        height: 1fr;
    }
    #chat-minimap {
        width: 28;
        height: 100%;
    }
    #chat-log {
        width: 1fr;
        height: 1fr;
        margin: 0;
        padding: 0;
        scrollbar-size: 1 1;
    }
    #chat-input {
        height: 1;
        background: #21262d;
        border: none;
        margin: 0;
        padding: 0 1;
    }
    #chat-input:focus {
        background: #30363d;
        border: none;
    }
    #chat-footer {
        height: 1;
        color: #484f58;
    }
    """

    BINDINGS = [
        Binding("escape", "close_chat", "Close", priority=True),
        Binding("ctrl+d", "delete_chat", "Delete", priority=True),
    ]

    def __init__(self, callsign: str, own_callsign: str,
                 own_lat: float | None = None, own_lon: float | None = None,
                 peer_lat: float | None = None, peer_lon: float | None = None,
                 **kwargs) -> None:
        super().__init__(**kwargs)
        self.peer_callsign = callsign.upper()
        self.own_callsign = own_callsign.upper()
        self.messages: list[ChatMessage] = []
        self._own_lat = own_lat
        self._own_lon = own_lon
        self._peer_lat = peer_lat
        self._peer_lon = peer_lon

    def compose(self) -> ComposeResult:
        with Vertical(id="chat-outer"):
            with Horizontal(id="chat-body"):
                yield RichLog(id="chat-log", wrap=True, markup=False)
                # Mini map (only if both positions available)
                if (self._own_lat is not None and self._own_lon is not None
                        and self._peer_lat is not None and self._peer_lon is not None):
                    yield MiniMapWidget(
                        self._own_lat, self._own_lon,
                        self._peer_lat, self._peer_lon,
                        own_callsign=self.own_callsign,
                        peer_callsign=self.peer_callsign,
                        id="chat-minimap",
                    )
            yield Input(
                placeholder=f"Message to {self.peer_callsign}... (Enter to send)",
                id="chat-input",
                max_length=67,
            )
            yield Static(
                "[dim]Enter[/dim] Send  [dim]Esc[/dim] Close  "
                "[dim]Ctrl+D[/dim] Delete  "
                "[dim]j/k[/dim] Scroll  [dim]67 char max[/dim]",
                id="chat-footer",
                markup=True,
            )

    def on_mount(self) -> None:
        title = f" Chat: {self.own_callsign} \u2194 {self.peer_callsign} "
        if (self._own_lat is not None and self._own_lon is not None
                and self._peer_lat is not None and self._peer_lon is not None):
            from aprs_tui.core.station_tracker import haversine
            dist = haversine(self._own_lat, self._own_lon, self._peer_lat, self._peer_lon)
            title += f"\u2014 {dist:.1f} km "
        self.query_one("#chat-outer").border_title = title
        # Render any pre-loaded history
        for msg in self.messages:
            self._render_message(msg)
        self.query_one("#chat-input", Input).focus()

    def add_message(self, direction: str, text: str, msg_id: str | None = None,
                    state: str = "") -> None:
        """Add a message to the conversation. Renders if screen is mounted."""
        msg = ChatMessage(
            direction=direction, text=text, msg_id=msg_id, state=state,
        )
        self.messages.append(msg)
        # Only render if the screen is mounted (widgets exist)
        with contextlib.suppress(Exception):
            self._render_message(msg)  # Not mounted yet - will render in on_mount

    def update_message_state(self, msg_id: str, new_state: str) -> None:
        """Update state of a sent message and re-render."""
        for msg in self.messages:
            if msg.msg_id == msg_id:
                msg.state = new_state
                break
        try:
            self._rerender()
            self.refresh()
        except Exception:
            pass  # Screen not yet mounted

    def _render_message(self, msg: ChatMessage) -> None:
        """Render a single chat message."""
        log = self.query_one("#chat-log", RichLog)
        line = Text()

        # Timestamp
        ts = time.strftime("%H:%M", time.localtime(msg.timestamp))
        line.append(f"{ts} ", style="dim #484f58")

        if msg.direction == "sent":
            line.append(f"{self.own_callsign} → {self.peer_callsign}", style="bold #e3b341")
            line.append(f"  {msg.text}", style="#e6edf3")
            if msg.state == "acked":
                line.append("  ✓", style="bold #56d364")
            elif msg.state == "failed":
                line.append("  ✗", style="bold #f85149")
            elif msg.state == "pending":
                line.append("  ⏳", style="#e3b341")
            if msg.msg_id:
                line.append(f"  #{msg.msg_id}", style="dim #484f58")
        else:
            line.append(f"{self.peer_callsign} → {self.own_callsign}", style="bold #58a6ff")
            line.append(f"  {msg.text}", style="#e6edf3")

        log.write(line)

    def _rerender(self) -> None:
        """Re-render all messages."""
        log = self.query_one("#chat-log", RichLog)
        log.clear()
        for msg in self.messages:
            self._render_message(msg)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Send message on Enter."""
        if event.input.id == "chat-input" and event.value.strip():
            text = event.value.strip()
            event.input.value = ""
            # Post a message to the app to handle actual sending
            self.post_message(self.SendChatMessage(self.peer_callsign, text))

    def action_close_chat(self) -> None:
        self.dismiss(None)

    def action_delete_chat(self) -> None:
        self.post_message(self.DeleteChat(self.peer_callsign))
        self.dismiss(None)

    class SendChatMessage(Message):
        """Posted when user sends a message from the chat screen."""
        def __init__(self, callsign: str, text: str) -> None:
            super().__init__()
            self.callsign = callsign
            self.text = text

    class DeleteChat(Message):
        """Posted when user deletes a chat conversation."""
        def __init__(self, callsign: str) -> None:
            super().__init__()
            self.callsign = callsign
