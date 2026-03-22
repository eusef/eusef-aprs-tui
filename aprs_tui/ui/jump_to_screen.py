"""Jump-to coordinates modal for the map panel.

Lets the user type a lat/lon coordinate pair and jumps the map viewport there.

Issue #53: Add jump-to commands for map navigation.
"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Static


# ---------------------------------------------------------------------------
# Coordinate parser
# ---------------------------------------------------------------------------

def parse_coordinates(text: str) -> tuple[float, float]:
    """Parse a coordinate string into (lat, lon) decimal degrees.

    Accepted formats (examples):
    - ``"47.6062 -122.3321"``  — space-separated, signed
    - ``"47.6062, -122.3321"`` — comma-separated, signed
    - ``"47.6062N 122.3321W"`` — NSEW suffix
    - ``"N47.6062 W122.3321"`` — NSEW prefix

    Args:
        text: Raw input string from the user.

    Returns:
        ``(latitude, longitude)`` as floats in decimal degrees.

    Raises:
        ValueError: If the input cannot be parsed or the coordinates are
            out of valid range (lat −90..90, lon −180..180).
    """
    import re

    # Normalise: collapse commas and extra whitespace into a single space.
    cleaned = re.sub(r"[,]+", " ", text.strip())
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    parts = cleaned.split(" ")
    if len(parts) != 2:
        raise ValueError(
            f"Expected two values (lat lon), got {len(parts)}: {text!r}"
        )

    lat = _parse_single(parts[0], ("N", "S"))
    lon = _parse_single(parts[1], ("E", "W"))

    if not -90.0 <= lat <= 90.0:
        raise ValueError(f"Latitude {lat} out of range (must be −90 to 90)")
    if not -180.0 <= lon <= 180.0:
        raise ValueError(f"Longitude {lon} out of range (must be −180 to 180)")

    return lat, lon


def _parse_single(token: str, positive_negative: tuple[str, str]) -> float:
    """Parse one coordinate token, handling optional NSEW prefix or suffix.

    Args:
        token: A single coordinate string, e.g. ``"47.6062N"`` or ``"-122.33"``.
        positive_negative: A 2-tuple of ``(positive_letter, negative_letter)``
            e.g. ``("N", "S")`` for latitude or ``("E", "W")`` for longitude.

    Returns:
        Coordinate value as float (sign applied from direction letter if present).

    Raises:
        ValueError: If the token cannot be parsed as a number.
    """
    pos_letter, neg_letter = positive_negative
    token = token.strip().upper()
    sign = 1.0

    # Strip prefix direction letter.
    if token.startswith(pos_letter):
        token = token[1:]
    elif token.startswith(neg_letter):
        sign = -1.0
        token = token[1:]

    # Strip suffix direction letter.
    if token.endswith(pos_letter):
        token = token[:-1]
    elif token.endswith(neg_letter):
        sign = -1.0
        token = token[:-1]

    try:
        value = float(token)
    except ValueError:
        raise ValueError(f"Cannot parse {token!r} as a number") from None

    return sign * value


# ---------------------------------------------------------------------------
# Modal screen
# ---------------------------------------------------------------------------

class JumpToScreen(ModalScreen[tuple[float, float] | None]):
    """Small modal overlay that accepts a lat/lon coordinate pair.

    Dismisses with ``(lat, lon)`` on Enter, or ``None`` on Escape.
    """

    CSS = """
    JumpToScreen {
        align: center middle;
    }
    #jump-outer {
        width: 52;
        max-width: 85%;
        height: auto;
        background: #161b22;
        border: solid #58a6ff;
        border-title-color: #58a6ff;
        padding: 1 2;
    }
    #jump-label {
        height: 1;
        color: #8b949e;
        margin-bottom: 1;
    }
    #jump-input {
        height: 1;
        background: #21262d;
        border: none;
        margin-bottom: 1;
        padding: 0 1;
    }
    #jump-input:focus {
        background: #30363d;
        border: none;
    }
    #jump-hint {
        height: 1;
        color: #484f58;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", priority=True),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="jump-outer"):
            yield Static("Enter coordinates (decimal degrees):", id="jump-label")
            yield Input(
                placeholder="47.6062, -122.3321",
                id="jump-input",
            )
            yield Static(
                "[dim]lat, lon  ·  or  ·  47.6N 122.3W[/dim]"
                "    [dim]Esc[/dim] Cancel",
                id="jump-hint",
                markup=True,
            )

    def on_mount(self) -> None:
        self.query_one("#jump-outer").border_title = " Jump to Coordinates "
        self.query_one("#jump-input", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "jump-input":
            return
        text = event.value.strip()
        if not text:
            return
        try:
            lat, lon = parse_coordinates(text)
        except ValueError as exc:
            self.query_one("#jump-hint", Static).update(
                f"[bold #f85149]{exc}[/bold #f85149]",
                markup=True,
            )
            return
        self.dismiss((lat, lon))

    def action_cancel(self) -> None:
        self.dismiss(None)
