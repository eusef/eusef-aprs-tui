"""Tests for aprs_tui.map.downloader — tile download with progress and resume."""
from __future__ import annotations

import gzip
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock

import httpx
import pytest

from aprs_tui.map.downloader import (
    DownloadProgress,
    TileDownloader,
    bounding_box_from_center,
    calculate_tile_count,
    estimate_size_mb,
)


class TestCalculateTileCount:
    def test_single_zoom_small_bbox(self) -> None:
        """A small bounding box at zoom 0 should yield 1 tile."""
        count = calculate_tile_count(
            min_lat=40.0, max_lat=41.0,
            min_lon=-74.0, max_lon=-73.0,
            min_zoom=0, max_zoom=0,
        )
        assert count == 1

    def test_multiple_zoom_levels(self) -> None:
        """Tile count increases across zoom levels."""
        count_z0 = calculate_tile_count(
            min_lat=40.0, max_lat=41.0,
            min_lon=-74.5, max_lon=-73.5,
            min_zoom=0, max_zoom=0,
        )
        count_z0_to_2 = calculate_tile_count(
            min_lat=40.0, max_lat=41.0,
            min_lon=-74.5, max_lon=-73.5,
            min_zoom=0, max_zoom=2,
        )
        assert count_z0_to_2 > count_z0

    def test_known_tile_count(self) -> None:
        """Zoom 1 covers the whole world in 4 tiles (2x2)."""
        count = calculate_tile_count(
            min_lat=-85.0, max_lat=85.0,
            min_lon=-180.0, max_lon=179.9,
            min_zoom=1, max_zoom=1,
        )
        assert count == 4


class TestEstimateSizeMb:
    def test_zero_tiles(self) -> None:
        assert estimate_size_mb(0) == 0.0

    def test_known_count(self) -> None:
        # 1024 tiles * 5 KB / 1024 = 5.0 MB
        assert estimate_size_mb(1024) == pytest.approx(5.0)

    def test_positive(self) -> None:
        assert estimate_size_mb(100) > 0


class TestBoundingBoxFromCenter:
    def test_returns_four_values(self) -> None:
        result = bounding_box_from_center(40.0, -74.0, 10.0)
        assert len(result) == 4

    def test_min_less_than_max(self) -> None:
        min_lat, max_lat, min_lon, max_lon = bounding_box_from_center(
            40.0, -74.0, 50.0
        )
        assert min_lat < max_lat
        assert min_lon < max_lon

    def test_center_inside_box(self) -> None:
        lat, lon = 40.0, -74.0
        min_lat, max_lat, min_lon, max_lon = bounding_box_from_center(
            lat, lon, 100.0
        )
        assert min_lat < lat < max_lat
        assert min_lon < lon < max_lon

    def test_approximate_radius(self) -> None:
        """A 111 km radius should give roughly 1 degree of latitude."""
        min_lat, max_lat, _, _ = bounding_box_from_center(0.0, 0.0, 111.0)
        lat_delta = max_lat - 0.0
        assert lat_delta == pytest.approx(1.0, abs=0.05)


class TestInitMbtiles:
    def test_creates_tables(self, tmp_path: Path) -> None:
        """_init_mbtiles creates the metadata and tiles tables."""
        db_path = tmp_path / "test.mbtiles"
        conn = sqlite3.connect(str(db_path))
        downloader = TileDownloader()
        downloader._init_mbtiles(conn, "test", 40.0, 41.0, -74.0, -73.0, 0, 14)

        # Verify tables exist
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        table_names = {row[0] for row in tables}
        assert "metadata" in table_names
        assert "tiles" in table_names

        # Verify metadata was inserted
        meta = dict(
            conn.execute("SELECT name, value FROM metadata").fetchall()
        )
        assert meta["name"] == "test"
        assert meta["format"] == "pbf"
        assert meta["minzoom"] == "0"
        assert meta["maxzoom"] == "14"
        assert "-74.0" in meta["bounds"]

        conn.close()

    def test_idempotent_metadata(self, tmp_path: Path) -> None:
        """Calling _init_mbtiles twice does not duplicate metadata."""
        db_path = tmp_path / "test.mbtiles"
        conn = sqlite3.connect(str(db_path))
        downloader = TileDownloader()
        downloader._init_mbtiles(conn, "test", 40.0, 41.0, -74.0, -73.0, 0, 14)
        downloader._init_mbtiles(conn, "test", 40.0, 41.0, -74.0, -73.0, 0, 14)

        count = conn.execute("SELECT COUNT(*) FROM metadata").fetchone()[0]
        assert count == 5  # 5 metadata entries, not 10

        conn.close()


class TestDownloadProgressPercentage:
    def test_zero_total(self) -> None:
        p = DownloadProgress(
            total_tiles=0, downloaded_tiles=0,
            skipped_tiles=0, bytes_downloaded=0, elapsed_seconds=0.0,
        )
        assert p.percentage == 100.0

    def test_half_done(self) -> None:
        p = DownloadProgress(
            total_tiles=100, downloaded_tiles=30,
            skipped_tiles=20, bytes_downloaded=0, elapsed_seconds=1.0,
        )
        assert p.percentage == pytest.approx(50.0)

    def test_all_downloaded(self) -> None:
        p = DownloadProgress(
            total_tiles=50, downloaded_tiles=50,
            skipped_tiles=0, bytes_downloaded=0, elapsed_seconds=1.0,
        )
        assert p.percentage == pytest.approx(100.0)

    def test_all_skipped(self) -> None:
        p = DownloadProgress(
            total_tiles=50, downloaded_tiles=0,
            skipped_tiles=50, bytes_downloaded=0, elapsed_seconds=1.0,
        )
        assert p.percentage == pytest.approx(100.0)


class TestDownloadProgressEta:
    def test_no_downloads_yet(self) -> None:
        p = DownloadProgress(
            total_tiles=100, downloaded_tiles=0,
            skipped_tiles=0, bytes_downloaded=0, elapsed_seconds=0.0,
        )
        assert p.eta_seconds == 0.0

    def test_eta_calculation(self) -> None:
        p = DownloadProgress(
            total_tiles=100, downloaded_tiles=50,
            skipped_tiles=0, bytes_downloaded=0, elapsed_seconds=10.0,
        )
        # Rate = 50/10 = 5 tiles/sec, remaining = 50, ETA = 10 sec
        assert p.eta_seconds == pytest.approx(10.0)

    def test_eta_with_skipped(self) -> None:
        p = DownloadProgress(
            total_tiles=100, downloaded_tiles=25,
            skipped_tiles=25, bytes_downloaded=0, elapsed_seconds=5.0,
        )
        # Rate = 25/5 = 5 tiles/sec, remaining = 50, ETA = 10 sec
        assert p.eta_seconds == pytest.approx(10.0)


def _make_mock_transport(tile_data: bytes = b"fake-tile-data") -> httpx.MockTransport:
    """Create an httpx MockTransport that returns tile_data for all requests.

    Uses an async handler for compatibility with AsyncClient.
    """

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=tile_data)

    return httpx.MockTransport(handler)


class TestDownloadCreatesMbtiles:
    def test_download_creates_file_with_tiles(self, tmp_path: Path) -> None:
        """Download should create an MBTiles file and populate tiles table."""
        output = tmp_path / "output.mbtiles"
        tile_data = b"fake-vector-tile"

        transport = _make_mock_transport(tile_data)
        downloader = TileDownloader(
            tile_url_template="https://tiles.example.com/{z}/{x}/{y}.pbf",
            transport=transport,
        )

        result = downloader.download(
            output_path=output,
            min_lat=40.0, max_lat=40.1,
            min_lon=-74.0, max_lon=-73.9,
            min_zoom=0, max_zoom=1,
            map_name="test-download",
        )

        assert result == output
        assert output.exists()

        conn = sqlite3.connect(str(output))
        tile_count = conn.execute("SELECT COUNT(*) FROM tiles").fetchone()[0]
        assert tile_count > 0

        # Verify tiles are gzip compressed
        row = conn.execute("SELECT tile_data FROM tiles LIMIT 1").fetchone()
        assert row[0][:2] == b"\x1f\x8b"  # gzip magic bytes

        # Verify metadata
        meta = dict(conn.execute("SELECT name, value FROM metadata").fetchall())
        assert meta["name"] == "test-download"
        assert meta["format"] == "pbf"
        conn.close()

    def test_download_stores_already_gzipped_data(self, tmp_path: Path) -> None:
        """If server returns gzipped data, it should not double-compress."""
        output = tmp_path / "output.mbtiles"
        raw_data = b"fake-vector-tile"
        gzipped_data = gzip.compress(raw_data)

        transport = _make_mock_transport(gzipped_data)
        downloader = TileDownloader(
            tile_url_template="https://tiles.example.com/{z}/{x}/{y}.pbf",
            transport=transport,
        )

        downloader.download(
            output_path=output,
            min_lat=40.0, max_lat=40.1,
            min_lon=-74.0, max_lon=-73.9,
            min_zoom=0, max_zoom=0,
            map_name="test",
        )

        conn = sqlite3.connect(str(output))
        row = conn.execute("SELECT tile_data FROM tiles LIMIT 1").fetchone()
        assert gzip.decompress(row[0]) == raw_data
        conn.close()


class TestDownloadResumeSkipsExisting:
    def test_resume_skips_existing_tiles(self, tmp_path: Path) -> None:
        """Tiles already in the database should be skipped on resume."""
        output = tmp_path / "output.mbtiles"

        # Pre-populate with one tile at zoom 0
        conn = sqlite3.connect(str(output))
        conn.execute("CREATE TABLE metadata (name TEXT, value TEXT)")
        conn.execute(
            "CREATE TABLE tiles ("
            "zoom_level INTEGER, tile_column INTEGER, "
            "tile_row INTEGER, tile_data BLOB, "
            "UNIQUE(zoom_level, tile_column, tile_row))"
        )
        meta = [
            ("name", "test"), ("format", "pbf"),
            ("bounds", "-74.0,40.0,-73.9,40.1"),
            ("minzoom", "0"), ("maxzoom", "0"),
        ]
        conn.executemany("INSERT INTO metadata (name, value) VALUES (?, ?)", meta)
        conn.execute(
            "INSERT INTO tiles (zoom_level, tile_column, tile_row, tile_data) "
            "VALUES (0, 0, 0, ?)",
            (gzip.compress(b"existing-tile"),),
        )
        conn.commit()
        conn.close()

        progress_reports: list[DownloadProgress] = []

        transport = _make_mock_transport(b"new-tile-data")
        downloader = TileDownloader(
            tile_url_template="https://tiles.example.com/{z}/{x}/{y}.pbf",
            progress_callback=lambda p: progress_reports.append(p),
            transport=transport,
        )

        downloader.download(
            output_path=output,
            min_lat=40.0, max_lat=40.1,
            min_lon=-74.0, max_lon=-73.9,
            min_zoom=0, max_zoom=0,
            map_name="test",
        )

        conn = sqlite3.connect(str(output))
        tile_count = conn.execute("SELECT COUNT(*) FROM tiles").fetchone()[0]
        assert tile_count == 1  # Still just the pre-existing tile

        row = conn.execute("SELECT tile_data FROM tiles").fetchone()
        assert gzip.decompress(row[0]) == b"existing-tile"
        conn.close()

    def test_progress_callback_reports_skipped(self, tmp_path: Path) -> None:
        """Progress callback should report skipped tiles separately."""
        output = tmp_path / "output.mbtiles"
        progress_reports: list[DownloadProgress] = []

        transport = _make_mock_transport(b"tile")
        downloader = TileDownloader(
            tile_url_template="https://tiles.example.com/{z}/{x}/{y}.pbf",
            progress_callback=lambda p: progress_reports.append(p),
            transport=transport,
        )

        downloader.download(
            output_path=output,
            min_lat=-85.0, max_lat=85.0,
            min_lon=-180.0, max_lon=179.9,
            min_zoom=0, max_zoom=2,
            map_name="test",
        )

        assert len(progress_reports) > 0
        last = progress_reports[-1]
        assert last.downloaded_tiles + last.skipped_tiles > 0
        assert last.total_tiles > 0
