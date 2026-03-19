"""Feature-to-style mapping for map rendering."""
from __future__ import annotations

from rich.style import Style

# Map feature types to Rich styles
FEATURE_STYLES: dict[str, Style] = {
    "water": Style(color="blue"),
    "coastline": Style(color="bright_blue"),
    "boundary": Style(color="white", dim=True),
    "highway": Style(color="yellow"),
    "road": Style(color="white"),
    "road_minor": Style(color="white", dim=True),
    "landuse": Style(color="green"),
    "building": Style(color="bright_black"),
    "label": Style(color="white"),
    "station_rf": Style(color="green", bold=True),
    "station_is": Style(color="green", dim=True),
    "station_own": Style(reverse=True),
    "station_selected": Style(color="bright_white", underline=True),
    "station_emergency": Style(color="red", bold=True, blink=True),
    "track": Style(color="cyan", dim=True),
    "default": Style(color="white"),
}


def get_style(feature_type: str) -> Style:
    """Get the Rich style for a map feature type."""
    return FEATURE_STYLES.get(feature_type, FEATURE_STYLES["default"])
