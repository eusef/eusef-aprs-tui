"""Feature-to-style mapping for map rendering."""
from __future__ import annotations

from rich.style import Style

# Map feature types to Rich styles.
# Water uses background color (no dots); land features use foreground dots.
FEATURE_STYLES: dict[str, Style] = {
    "water": Style(color="#1a3a5c", bgcolor="#0d2137"),
    "coastline": Style(color="bright_cyan", bold=True),
    "boundary": Style(color="#6e7681"),
    "highway": Style(color="bright_yellow"),
    "road": Style(color="white"),
    "road_minor": Style(color="#8b949e"),
    "landuse": Style(color="#2ea043"),
    "building": Style(color="#6e7681"),
    "label": Style(color="bright_white", bold=True),
    "station_rf": Style(color="bright_green", bold=True),
    "station_is": Style(color="green", dim=True),
    "station_own": Style(reverse=True),
    "station_selected": Style(color="bright_white", underline=True, bold=True),
    "station_emergency": Style(color="red", bold=True, blink=True),
    "track": Style(color="cyan", dim=True),
    "default": Style(color="#8b949e"),
}


def get_style(feature_type: str) -> Style:
    """Get the Rich style for a map feature type."""
    return FEATURE_STYLES.get(feature_type, FEATURE_STYLES["default"])
