"""Feature-to-style mapping for map rendering."""
from __future__ import annotations

from rich.style import Style

# Map feature types to Rich styles.
# Water uses background color (no dots); land features use foreground dots.
FEATURE_STYLES: dict[str, Style] = {
    "water": Style(),  # No color — plain terminal background
    "coastline": Style(color="#2d5f5f"),
    "boundary": Style(color="#3a5a5a", dim=True),
    "highway": Style(color="#5a7a7a"),
    "road": Style(color="#4a6a6a"),
    "road_minor": Style(color="#3a5555"),
    "landuse": Style(color="#2d5f5f", dim=True),
    "building": Style(color="#3a6a6a"),
    "label": Style(color="bright_white", bold=True),
    "label_city": Style(color="#8b3a3a"),
    "label_street": Style(color="#8b3a3a"),
    "station_rf": Style(color="bright_green", bold=True),
    "station_is": Style(color="green", dim=True),
    "station_own": Style(reverse=True),
    "station_selected": Style(color="bright_white", underline=True, bold=True),
    "station_emergency": Style(color="red", bold=True, blink=True),
    "track": Style(color="cyan", dim=True),
    "default": Style(color="#2d5f5f"),
}


def get_style(feature_type: str) -> Style:
    """Get the Rich style for a map feature type."""
    return FEATURE_STYLES.get(feature_type, FEATURE_STYLES["default"])
