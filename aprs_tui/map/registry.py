"""Map registry for tracking downloaded offline MBTiles files.

Manages a ``maps.toml`` file inside the user data directory, recording
metadata for each downloaded map so the application can select the best
tile source at runtime.
"""
from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

import tomli_w
from platformdirs import user_data_dir


def default_maps_dir() -> Path:
    """Default maps directory."""
    return Path(user_data_dir("aprs-tui")) / "maps"


@dataclass
class MapEntry:
    """Metadata for a downloaded map file."""

    file: str  # filename (relative to maps_dir)
    name: str  # human-readable name
    bounds: tuple[float, float, float, float]  # west, south, east, north
    min_zoom: int
    max_zoom: int
    size_mb: float
    downloaded: str  # ISO timestamp
    source: str = "openmaptiles"


class MapRegistry:
    """Registry of downloaded offline map files, backed by maps.toml."""

    def __init__(self, maps_dir: Path | None = None) -> None:
        self._maps_dir = maps_dir or default_maps_dir()
        self._maps_dir.mkdir(parents=True, exist_ok=True)
        self._registry_path = self._maps_dir / "maps.toml"
        self._entries: dict[str, MapEntry] = {}
        self._load()

    def _load(self) -> None:
        """Load registry from maps.toml."""
        if not self._registry_path.exists():
            return
        data = tomllib.loads(self._registry_path.read_text())
        maps_data = data.get("maps", {})
        for key, val in maps_data.items():
            bounds_list = val.get("bounds", [0, 0, 0, 0])
            self._entries[key] = MapEntry(
                file=val["file"],
                name=val.get("name", key),
                bounds=tuple(bounds_list),
                min_zoom=val.get("min_zoom", 0),
                max_zoom=val.get("max_zoom", 14),
                size_mb=val.get("size_mb", 0),
                downloaded=val.get("downloaded", ""),
                source=val.get("source", "openmaptiles"),
            )

    def save(self) -> None:
        """Write registry to maps.toml."""
        data: dict[str, dict[str, object]] = {"maps": {}}
        for key, entry in self._entries.items():
            data["maps"][key] = {
                "file": entry.file,
                "name": entry.name,
                "bounds": list(entry.bounds),
                "min_zoom": entry.min_zoom,
                "max_zoom": entry.max_zoom,
                "size_mb": entry.size_mb,
                "downloaded": entry.downloaded,
                "source": entry.source,
            }
        self._registry_path.write_text(tomli_w.dumps(data))

    def register(self, key: str, entry: MapEntry) -> None:
        """Add or update a map entry and save."""
        self._entries[key] = entry
        self.save()

    def remove(self, key: str) -> None:
        """Remove a map entry and save."""
        self._entries.pop(key, None)
        self.save()

    def list_maps(self) -> list[MapEntry]:
        """Return all registered maps."""
        return list(self._entries.values())

    def select_map(
        self, center_lat: float, center_lon: float, zoom: float
    ) -> MapEntry | None:
        """Select the best map for the given viewport.

        Selection logic:
        1. Find maps whose bounds contain the center point
        2. Among those, filter to maps whose max_zoom >= current zoom
        3. Return the one with the highest max_zoom
        4. If none found, return None
        """
        candidates = []
        for entry in self._entries.values():
            w, s, e, n = entry.bounds
            if w <= center_lon <= e and s <= center_lat <= n:
                if entry.max_zoom >= int(zoom):
                    candidates.append(entry)
        if not candidates:
            # Fall back: any map containing the point
            for entry in self._entries.values():
                w, s, e, n = entry.bounds
                if w <= center_lon <= e and s <= center_lat <= n:
                    candidates.append(entry)
        if not candidates:
            return None
        return max(candidates, key=lambda e: e.max_zoom)

    def get_mbtiles_path(self, entry: MapEntry) -> Path:
        """Return the full path to the MBTiles file for an entry."""
        return self._maps_dir / entry.file
