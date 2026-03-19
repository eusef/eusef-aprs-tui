"""Tile downloader with progress reporting and resume support.

Downloads vector tiles from a tile server into an MBTiles (SQLite) file.
Supports resuming interrupted downloads by skipping tiles already present
in the database.
"""
from __future__ import annotations

import gzip
import math
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import mercantile


@dataclass
class DownloadProgress:
    """Progress info for a tile download."""

    total_tiles: int
    downloaded_tiles: int
    skipped_tiles: int  # already existed (resume)
    bytes_downloaded: int
    elapsed_seconds: float

    @property
    def percentage(self) -> float:
        if self.total_tiles == 0:
            return 100.0
        return (self.downloaded_tiles + self.skipped_tiles) / self.total_tiles * 100

    @property
    def eta_seconds(self) -> float:
        if self.downloaded_tiles == 0:
            return 0.0
        remaining = self.total_tiles - self.downloaded_tiles - self.skipped_tiles
        rate = self.downloaded_tiles / max(self.elapsed_seconds, 0.001)
        return remaining / rate


def calculate_tile_count(
    min_lat: float,
    max_lat: float,
    min_lon: float,
    max_lon: float,
    min_zoom: int,
    max_zoom: int,
) -> int:
    """Calculate total number of tiles in a bounding box across zoom levels."""
    count = 0
    for z in range(min_zoom, max_zoom + 1):
        ul_tile = mercantile.tile(min_lon, max_lat, z)
        lr_tile = mercantile.tile(max_lon, min_lat, z)
        cols = lr_tile.x - ul_tile.x + 1
        rows = lr_tile.y - ul_tile.y + 1
        count += cols * rows
    return count


def estimate_size_mb(tile_count: int) -> float:
    """Rough estimate of download size. ~5KB per vector tile average."""
    return tile_count * 5 / 1024


def bounding_box_from_center(
    lat: float,
    lon: float,
    radius_km: float,
) -> tuple[float, float, float, float]:
    """Calculate bounding box from center point and radius.

    Returns (min_lat, max_lat, min_lon, max_lon).
    """
    # Approximate degrees per km
    lat_delta = radius_km / 111.0
    lon_delta = radius_km / (111.0 * math.cos(math.radians(lat)))
    return (
        lat - lat_delta,
        lat + lat_delta,
        lon - lon_delta,
        lon + lon_delta,
    )


class TileDownloader:
    """Downloads vector tiles from a tile server into an MBTiles file."""

    def __init__(
        self,
        tile_url_template: str = "https://tiles.example.com/{z}/{x}/{y}.pbf",
        progress_callback: Callable[[DownloadProgress], None] | None = None,
    ) -> None:
        self._url_template = tile_url_template
        self._progress_callback = progress_callback

    def download(
        self,
        output_path: Path,
        min_lat: float,
        max_lat: float,
        min_lon: float,
        max_lon: float,
        min_zoom: int = 0,
        max_zoom: int = 14,
        map_name: str = "downloaded",
    ) -> Path:
        """Download tiles for a region into an MBTiles file.

        Resumable: skips tiles already present in the database.
        Returns the output path.
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Create/open MBTiles database
        conn = sqlite3.connect(str(output_path))
        self._init_mbtiles(
            conn, map_name, min_lat, max_lat, min_lon, max_lon, min_zoom, max_zoom
        )

        # Calculate tiles to download
        tiles = []
        for z in range(min_zoom, max_zoom + 1):
            ul_tile = mercantile.tile(min_lon, max_lat, z)
            lr_tile = mercantile.tile(max_lon, min_lat, z)
            for x in range(ul_tile.x, lr_tile.x + 1):
                for y in range(ul_tile.y, lr_tile.y + 1):
                    tiles.append((z, x, y))

        total = len(tiles)
        downloaded = 0
        skipped = 0
        total_bytes = 0
        start_time = time.monotonic()

        import httpx

        with httpx.Client(timeout=30.0) as client:
            for z, x, y in tiles:
                # Check if tile already exists (resume support)
                tms_y = (1 << z) - 1 - y
                existing = conn.execute(
                    "SELECT 1 FROM tiles WHERE zoom_level=? AND tile_column=? AND tile_row=?",
                    (z, x, tms_y),
                ).fetchone()

                if existing:
                    skipped += 1
                else:
                    url = self._url_template.format(z=z, x=x, y=y)
                    try:
                        resp = client.get(url)
                        if resp.status_code == 200:
                            tile_data = resp.content
                            # Store as gzip if not already compressed
                            if tile_data[:2] != b"\x1f\x8b":
                                tile_data = gzip.compress(tile_data)
                            conn.execute(
                                "INSERT OR IGNORE INTO tiles (zoom_level, tile_column, tile_row, tile_data) "
                                "VALUES (?, ?, ?, ?)",
                                (z, x, tms_y, tile_data),
                            )
                            total_bytes += len(tile_data)
                            downloaded += 1
                    except httpx.HTTPError:
                        pass  # Skip failed tiles

                # Report progress
                if self._progress_callback and (downloaded + skipped) % 10 == 0:
                    elapsed = time.monotonic() - start_time
                    self._progress_callback(
                        DownloadProgress(
                            total_tiles=total,
                            downloaded_tiles=downloaded,
                            skipped_tiles=skipped,
                            bytes_downloaded=total_bytes,
                            elapsed_seconds=elapsed,
                        )
                    )

        conn.commit()
        conn.close()
        return output_path

    def _init_mbtiles(
        self,
        conn: sqlite3.Connection,
        name: str,
        min_lat: float,
        max_lat: float,
        min_lon: float,
        max_lon: float,
        min_zoom: int,
        max_zoom: int,
    ) -> None:
        """Create MBTiles tables and metadata if they don't exist."""
        conn.execute("CREATE TABLE IF NOT EXISTS metadata (name TEXT, value TEXT)")
        conn.execute(
            "CREATE TABLE IF NOT EXISTS tiles ("
            "zoom_level INTEGER, tile_column INTEGER, "
            "tile_row INTEGER, tile_data BLOB, "
            "UNIQUE(zoom_level, tile_column, tile_row))"
        )
        # Only insert metadata if not already present
        existing = conn.execute("SELECT COUNT(*) FROM metadata").fetchone()[0]
        if existing == 0:
            bounds = f"{min_lon},{min_lat},{max_lon},{max_lat}"
            meta = [
                ("name", name),
                ("format", "pbf"),
                ("bounds", bounds),
                ("minzoom", str(min_zoom)),
                ("maxzoom", str(max_zoom)),
            ]
            conn.executemany(
                "INSERT INTO metadata (name, value) VALUES (?, ?)", meta
            )
        conn.commit()
