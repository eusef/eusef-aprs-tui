"""Jump-to coordinates modal for the map panel.

Lets the user type a lat/lon coordinate pair, callsign, or Maidenhead grid
square and jumps the map viewport there.

Issue #53: Add jump-to commands for map navigation.
"""
from __future__ import annotations

import re

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Static

from aprs_tui.core.station_tracker import StationTracker

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
    """Parse one coordinate token, handling optional NSEW prefix or suffix."""
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
# Maidenhead grid square converter
# ---------------------------------------------------------------------------

def maidenhead_to_latlon(grid: str) -> tuple[float, float]:
    """Convert a Maidenhead grid locator to (lat, lon) at the square centre.

    Supports 4, 6, or 8-character locators (e.g. CN87, CN87us, CN87us12).

    Args:
        grid: Maidenhead locator string.

    Returns:
        ``(latitude, longitude)`` as floats in decimal degrees.

    Raises:
        ValueError: If the locator is malformed.
    """
    grid = grid.strip()
    length = len(grid)
    if length not in (4, 6, 8):
        raise ValueError(
            f"Grid locator must be 4, 6, or 8 characters, got {length}: {grid!r}"
        )

    g = grid.upper()

    # Field (first pair): A-R → 0-17
    if not ("A" <= g[0] <= "R" and "A" <= g[1] <= "R"):
        raise ValueError(f"Invalid field characters in {grid!r}")
    lon = (ord(g[0]) - ord("A")) * 20 - 180
    lat = (ord(g[1]) - ord("A")) * 10 - 90

    # Square (second pair): 0-9
    if not (g[2].isdigit() and g[3].isdigit()):
        raise ValueError(f"Invalid square digits in {grid!r}")
    lon += int(g[2]) * 2
    lat += int(g[3]) * 1

    # Subsquare resolution for centring
    sub_lon = 2.0  # width of the square
    sub_lat = 1.0

    if length >= 6:
        s = grid  # use original case for subsquare (a-x)
        s4 = s[4].upper()
        s5 = s[5].upper()
        if not ("A" <= s4 <= "X" and "A" <= s5 <= "X"):
            raise ValueError(f"Invalid subsquare characters in {grid!r}")
        lon += (ord(s4) - ord("A")) * (2 / 24)
        lat += (ord(s5) - ord("A")) * (1 / 24)
        sub_lon = 2 / 24
        sub_lat = 1 / 24

    if length == 8:
        if not (g[6].isdigit() and g[7].isdigit()):
            raise ValueError(f"Invalid extended square digits in {grid!r}")
        lon += int(g[6]) * (sub_lon / 10)
        lat += int(g[7]) * (sub_lat / 10)
        sub_lon /= 10
        sub_lat /= 10

    # Return centre of the smallest grid division
    lon += sub_lon / 2
    lat += sub_lat / 2

    return lat, lon


def _is_maidenhead(text: str) -> bool:
    """Check if text looks like a Maidenhead grid locator."""
    return bool(re.match(r"^[A-Ra-r]{2}\d{2}(?:[A-Xa-x]{2}(?:\d{2})?)?$", text))


def _is_callsign(text: str) -> bool:
    """Check if text looks like an amateur radio callsign."""
    # Callsigns: 3-9 alphanumeric chars, must contain at least one digit
    return bool(
        re.match(r"^[A-Za-z0-9]{3,9}(-\d{1,2})?$", text)
        and re.search(r"\d", text)
    )


# ---------------------------------------------------------------------------
# Input resolver — tries Maidenhead, callsign, then lat/lon
# ---------------------------------------------------------------------------

def resolve_input(
    text: str,
    station_tracker: StationTracker | None = None,
) -> tuple[float, float]:
    """Resolve user input to (lat, lon).

    Tries in order: Maidenhead grid square, callsign lookup, lat/lon parse.

    Raises:
        ValueError: If no method can resolve the input.
    """
    cleaned = text.strip()
    if not cleaned:
        raise ValueError("No input provided")

    # Try Maidenhead grid square
    if _is_maidenhead(cleaned):
        return maidenhead_to_latlon(cleaned)

    # Try callsign lookup (single token, no spaces)
    if " " not in cleaned and "," not in cleaned and _is_callsign(cleaned):
        if station_tracker is not None:
            station = station_tracker.get_station(cleaned.upper())
            if station and station.latitude is not None and station.longitude is not None:
                return station.latitude, station.longitude
            raise ValueError(
                f"Station {cleaned.upper()} not found or has no position"
            )
        raise ValueError(f"No station data available to look up {cleaned!r}")

    # Fall back to lat/lon coordinate parsing
    return parse_coordinates(cleaned)


# ---------------------------------------------------------------------------
# Modal screen
# ---------------------------------------------------------------------------

class JumpToScreen(ModalScreen[tuple[float, float] | None]):
    """Small modal overlay that accepts coordinates, a callsign, or grid square.

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

    def __init__(
        self,
        station_tracker: StationTracker | None = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._station_tracker = station_tracker

    def compose(self) -> ComposeResult:
        with Vertical(id="jump-outer"):
            yield Static(
                "Enter coordinates, callsign, or grid square:", id="jump-label"
            )
            yield Input(
                placeholder="47.6062, -122.3321  or  W7XXX  or  CN87",
                id="jump-input",
            )
            yield Static(
                "[dim]lat, lon  ·  callsign  ·  grid square[/dim]"
                "    [dim]Esc[/dim] Cancel",
                id="jump-hint",
                markup=True,
            )

    def on_mount(self) -> None:
        self.query_one("#jump-outer").border_title = " Jump To "
        self.query_one("#jump-input", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "jump-input":
            return
        text = event.value.strip()
        if not text:
            return
        try:
            lat, lon = resolve_input(text, self._station_tracker)
        except ValueError as exc:
            self.query_one("#jump-hint", Static).update(
                f"[bold #f85149]{exc}[/bold #f85149]",
                markup=True,
            )
            return
        self.dismiss((lat, lon))

    def action_cancel(self) -> None:
        self.dismiss(None)
