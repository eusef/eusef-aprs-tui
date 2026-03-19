"""MBTiles tile source reader with LRU cache.

Reads vector tiles from MBTiles (SQLite) databases.  The public API
accepts standard XYZ (slippy-map) coordinates; the TMS y-flip is
handled internally.
"""
from __future__ import annotations

import gzip
import sqlite3
from collections import OrderedDict
from pathlib import Path
from typing import Self


class MBTilesSource:
    """Read vector tiles from an MBTiles SQLite database."""

    def __init__(self, path: str | Path, cache_size: int = 64) -> None:
        self._path = Path(path)
        if not self._path.exists():
            raise FileNotFoundError(f"MBTiles file not found: {self._path}")

        self._conn = sqlite3.connect(str(self._path), check_same_thread=False)
        try:
            self._conn.execute("SELECT name FROM metadata LIMIT 1")
        except sqlite3.OperationalError as exc:
            self._conn.close()
            raise sqlite3.DatabaseError(
                f"Not a valid MBTiles database: {self._path}"
            ) from exc

        self._cache_size = max(cache_size, 1)
        self._cache: OrderedDict[tuple[int, int, int], bytes | None] = (
            OrderedDict()
        )
        self._metadata: dict[str, str] | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_tile(self, z: int, x: int, y: int) -> bytes | None:
        """Retrieve raw tile data (PBF bytes) for XYZ coordinates.

        Returns None if the tile doesn't exist.  Handles gzip
        decompression.  Results are LRU-cached.
        """
        key = (z, x, y)
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]

        data = self._read_tile(z, x, y)
        self._put_cache(key, data)
        return data

    def get_metadata(self) -> dict[str, str]:
        """Return all metadata key-value pairs."""
        if self._metadata is None:
            cursor = self._conn.execute("SELECT name, value FROM metadata")
            self._metadata = {row[0]: row[1] for row in cursor.fetchall()}
        return dict(self._metadata)

    @property
    def bounds(self) -> tuple[float, float, float, float] | None:
        """Return (west, south, east, north) bounds, or None."""
        raw = self.get_metadata().get("bounds")
        if raw is None:
            return None
        parts = [float(p.strip()) for p in raw.split(",")]
        if len(parts) != 4:
            return None
        return (parts[0], parts[1], parts[2], parts[3])

    @property
    def min_zoom(self) -> int:
        return int(self.get_metadata().get("minzoom", "0"))

    @property
    def max_zoom(self) -> int:
        return int(self.get_metadata().get("maxzoom", "0"))

    @property
    def name(self) -> str:
        return self.get_metadata().get("name", "")

    def close(self) -> None:
        """Close the SQLite connection and clear cache."""
        self._cache.clear()
        self._metadata = None
        self._conn.close()

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _xyz_to_tms(z: int, y: int) -> int:
        """Convert XYZ y-coordinate to TMS y-coordinate."""
        return (1 << z) - 1 - y

    def _read_tile(self, z: int, x: int, y: int) -> bytes | None:
        tms_y = self._xyz_to_tms(z, y)
        cursor = self._conn.execute(
            "SELECT tile_data FROM tiles "
            "WHERE zoom_level = ? AND tile_column = ? AND tile_row = ?",
            (z, x, tms_y),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        data: bytes = row[0]
        if data[:2] == b"\x1f\x8b":
            data = gzip.decompress(data)
        return data

    def _put_cache(
        self, key: tuple[int, int, int], value: bytes | None
    ) -> None:
        if key in self._cache:
            self._cache.move_to_end(key)
            self._cache[key] = value
        else:
            if len(self._cache) >= self._cache_size:
                self._cache.popitem(last=False)
            self._cache[key] = value
