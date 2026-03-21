"""Quick reference panel showing grouped key bindings."""
from __future__ import annotations

from rich.text import Text
from textual.widgets import Static

# Grouped key bindings for the quick reference panel.
KEY_GROUPS: list[tuple[str, list[tuple[str, str]]]] = [
    ("General", [
        ("q", "Quit"),
        ("?", "Command palette"),
        ("^W", "Config wizard"),
        ("Tab", "Next panel"),
        ("j/k", "Scroll"),
        (":", "Commands"),
    ]),
    ("Messages", [
        ("c", "Compose"),
        ("Enter", "Chat (station list)"),
        ("x", "Cancel retries"),
        ("y", "Copy last packet"),
    ]),
    ("Map", [
        ("m/M", "Map (large/small)"),
        ("+/-", "Zoom in/out"),
        ("\u2190\u2191\u2192\u2193", "Pan (Shift=fast)"),
        ("a", "Auto-zoom toggle"),
        ("0", "Reset zoom"),
        ("n/N", "Next/prev station"),
        ("f", "Fullscreen"),
        ("g", "Legend toggle"),
    ]),
    ("Map Filters", [
        ("i", "APRS-IS stations"),
        ("R", "RF stations"),
        ("w", "Weather"),
        ("d", "Digipeaters"),
        ("t", "Tracks"),
    ]),
    ("Other", [
        ("b", "Beacon on/off"),
        ("r", "Raw packets"),
        ("a", "About"),
        ("Esc", "Close overlay"),
    ]),
]


class KeyReferencePanel(Static):
    """Compact quick reference showing all key bindings, grouped by section."""

    DEFAULT_CSS = """
    KeyReferencePanel {
        width: 1fr;
        height: 100%;
        background: #0d1117;
        border: solid #30363d;
        border-title-color: #8b949e;
        padding: 0 1;
        overflow-y: auto;
    }
    KeyReferencePanel:focus {
        border: double #58a6ff;
        border-title-color: #58a6ff;
    }
    """

    def on_mount(self) -> None:
        self.border_title = "Quick Reference"
        self._render_keys()

    def _render_keys(self) -> None:
        text = Text()
        for i, (group_name, bindings) in enumerate(KEY_GROUPS):
            if i > 0:
                text.append("\n")
            text.append(f" {group_name}\n", style="bold #58a6ff")
            for key, desc in bindings:
                text.append(f"  {key:<10s}", style="bold #e3b341")
                text.append(f"{desc}\n", style="#8b949e")
        self.update(text)
