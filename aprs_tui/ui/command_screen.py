"""Command palette screen - searchable list of all available commands."""
from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Static

COMMANDS = [
    ("q", "Quit", "Exit the application"),
    ("?", "Help", "Show key bindings reference"),
    ("^W", "Config", "Open setup wizard (all sections)"),
    ("b", "Beacon", "Toggle position beacon on/off"),
    ("c", "Compose", "Compose and send an APRS message"),
    ("Enter", "Chat", "Open chat with selected station (in station list)"),
    ("r", "Raw", "Toggle raw packet display below decoded lines"),
    ("i", "APRS-IS", "Show/hide APRS-IS packets in stream"),
    ("y", "Copy", "Copy last packet to clipboard"),
    ("x", "Cancel", "Cancel all pending message retries"),
    ("j/k", "Scroll", "Scroll up/down in focused panel"),
    ("Tab", "Next Panel", "Cycle focus between panels"),
    (":", "Commands", "Show this command list"),
    ("a", "About", "About APRS TUI, licenses, and legal notices"),
    ("Esc", "Close", "Close this overlay / cancel input"),
    # -- Map panel --
    ("m", "Map (large)", "Map replaces Packet Stream (large view)"),
    ("M", "Map (small)", "Map replaces Station List (sidebar view)"),
    ("+/-", "Zoom", "Zoom in/out on map"),
    ("hjkl", "Pan", "Pan map (arrows also work, HJKL=fast)"),
    ("a", "Auto Zoom", "Toggle auto-zoom (when map focused)"),
    ("0", "Reset Zoom", "Re-enable auto-zoom and recalculate"),
    ("n/N", "Stations", "Cycle to next/previous station on map"),
    ("i", "Hide IS", "Toggle APRS-IS stations on map"),
    ("R", "Hide RF", "Toggle RF stations on map"),
    ("w", "Hide WX", "Toggle weather stations on map"),
    ("d", "Hide Digi", "Toggle digipeaters/iGates on map"),
    ("t", "Tracks", "Toggle station movement trails on map"),
    ("f", "Fullscreen", "Fullscreen map (press f or Esc to exit)"),
]


class CommandScreen(ModalScreen[str | None]):
    """Modal overlay showing all available commands with search."""

    DEFAULT_CSS = """
    CommandScreen {
        align: center middle;
    }
    #command-dialog {
        width: 70;
        max-width: 90%;
        height: auto;
        max-height: 80%;
        background: #161b22;
        border: solid #58a6ff;
        border-title-color: #58a6ff;
        padding: 1 2;
    }
    #command-search {
        margin-bottom: 1;
    }
    #command-list {
        height: auto;
        max-height: 20;
        overflow-y: auto;
        padding: 0 1;
    }
    .cmd-row {
        height: 1;
    }
    """

    BINDINGS = [
        Binding("escape", "close", "Close", priority=True),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="command-dialog"):
            yield Static(
                Text("Commands", style="bold #58a6ff"),
            )
            yield Input(
                placeholder="Search commands...",
                id="command-search",
            )
            yield Static(id="command-list")

    def on_mount(self) -> None:
        self.query_one("#command-dialog").border_title = "Command Palette"
        self._render_commands("")

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "command-search":
            self._render_commands(event.value)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "command-search":
            # Execute first matching command
            query = event.value.lower()
            for key, name, desc in COMMANDS:
                if query in name.lower() or query in desc.lower() or query in key.lower():
                    self.dismiss(key)
                    return
            self.dismiss(None)

    def _render_commands(self, query: str) -> None:
        """Render the filtered command list."""
        text = Text()
        query_lower = query.lower()
        count = 0

        for key, name, desc in COMMANDS:
            if query_lower and (
                query_lower not in name.lower()
                and query_lower not in desc.lower()
                and query_lower not in key.lower()
            ):
                continue

            count += 1
            # Key column
            text.append(f"  {key:<8s}", style="bold #e3b341")
            # Name column
            text.append(f"{name:<14s}", style="bold #e6edf3")
            # Description
            text.append(f"{desc}\n", style="#8b949e")

        if count == 0:
            text.append("  No matching commands\n", style="dim #8b949e")

        text.append(f"\n  {count} command(s)", style="dim #484f58")
        text.append("  |  Enter=execute  Esc=close", style="dim #484f58")

        self.query_one("#command-list", Static).update(text)

    def action_close(self) -> None:
        self.dismiss(None)
