"""Tests for aprs_tui.map.tile_source — MBTiles reader with LRU cache."""
from __future__ import annotations

import gzip
import sqlite3
from pathlib import Path

import pytest

from aprs_tui.map.tile_source import MBTilesSource


def _create_mbtiles(
    path: Path,
    *,
    tiles: list[tuple[int, int, int, bytes]] | None = None,
    metadata: dict[str, str] | None = None,
) -> Path:
    """Create a minimal MBTiles file for testing."""
    conn = sqlite3.connect(str(path))
    conn.execute("CREATE TABLE metadata (name TEXT, value TEXT)")
    conn.execute(
        "CREATE TABLE tiles ("
        "zoom_level INTEGER, tile_column INTEGER, "
        "tile_row INTEGER, tile_data BLOB)"
    )
    if metadata:
        conn.executemany(
            "INSERT INTO metadata (name, value) VALUES (?, ?)",
            list(metadata.items()),
        )
    if tiles:
        conn.executemany(
            "INSERT INTO tiles (zoom_level, tile_column, tile_row, tile_data) "
            "VALUES (?, ?, ?, ?)",
            tiles,
        )
    conn.commit()
    conn.close()
    return path


@pytest.fixture()
def sample_mbtiles(tmp_path: Path) -> Path:
    raw_tile = b"fake-pbf-data"
    gz_tile = gzip.compress(b"gzipped-pbf-data")
    # zoom=2, xyz_y=1 -> tms_y=2;  xyz_y=3 -> tms_y=0
    tiles = [
        (2, 1, 2, raw_tile),
        (2, 3, 0, gz_tile),
    ]
    metadata = {
        "name": "Test Tiles",
        "format": "pbf",
        "bounds": "-180.0,-85.05,180.0,85.05",
        "minzoom": "0",
        "maxzoom": "5",
    }
    return _create_mbtiles(tmp_path / "test.mbtiles", tiles=tiles, metadata=metadata)


@pytest.fixture()
def empty_mbtiles(tmp_path: Path) -> Path:
    return _create_mbtiles(
        tmp_path / "empty.mbtiles",
        metadata={"name": "Empty", "minzoom": "0", "maxzoom": "0"},
    )


class TestGetTile:
    def test_returns_raw_tile_data(self, sample_mbtiles: Path) -> None:
        with MBTilesSource(sample_mbtiles) as src:
            assert src.get_tile(z=2, x=1, y=1) == b"fake-pbf-data"

    def test_decompresses_gzipped_tile(self, sample_mbtiles: Path) -> None:
        with MBTilesSource(sample_mbtiles) as src:
            assert src.get_tile(z=2, x=3, y=3) == b"gzipped-pbf-data"

    def test_returns_none_for_missing(self, sample_mbtiles: Path) -> None:
        with MBTilesSource(sample_mbtiles) as src:
            assert src.get_tile(z=0, x=0, y=0) is None

    def test_returns_none_from_empty(self, empty_mbtiles: Path) -> None:
        with MBTilesSource(empty_mbtiles) as src:
            assert src.get_tile(z=1, x=0, y=0) is None


class TestTMSFlip:
    @pytest.mark.parametrize(
        ("z", "xyz_y", "expected"),
        [(0, 0, 0), (1, 0, 1), (1, 1, 0), (2, 0, 3), (2, 1, 2), (2, 3, 0)],
    )
    def test_xyz_to_tms(self, z: int, xyz_y: int, expected: int) -> None:
        assert MBTilesSource._xyz_to_tms(z, xyz_y) == expected

    def test_flip_applied_on_fetch(self, tmp_path: Path) -> None:
        zoom, x, xyz_y = 3, 2, 5
        tms_y = (1 << zoom) - 1 - xyz_y
        db = _create_mbtiles(
            tmp_path / "flip.mbtiles",
            tiles=[(zoom, x, tms_y, b"flip-test")],
            metadata={"name": "Flip"},
        )
        with MBTilesSource(db) as src:
            assert src.get_tile(zoom, x, xyz_y) == b"flip-test"


class TestLRUCache:
    def test_cached_on_second_call(self, sample_mbtiles: Path) -> None:
        with MBTilesSource(sample_mbtiles, cache_size=4) as src:
            first = src.get_tile(2, 1, 1)
            second = src.get_tile(2, 1, 1)
            assert first is second

    def test_cache_evicts_oldest(self, tmp_path: Path) -> None:
        tiles = [
            (0, 0, 0, b"a"),
            (1, 0, 0, b"b"),
            (1, 1, 0, b"c"),
        ]
        db = _create_mbtiles(
            tmp_path / "evict.mbtiles", tiles=tiles, metadata={"name": "E"}
        )
        with MBTilesSource(db, cache_size=2) as src:
            src.get_tile(0, 0, 0)
            src.get_tile(1, 0, 1)
            src.get_tile(1, 1, 1)
            assert src.get_tile(0, 0, 0) == b"a"

    def test_none_result_cached(self, sample_mbtiles: Path) -> None:
        with MBTilesSource(sample_mbtiles) as src:
            a = src.get_tile(9, 9, 9)
            b = src.get_tile(9, 9, 9)
            assert a is None and b is None


class TestMetadata:
    def test_get_metadata(self, sample_mbtiles: Path) -> None:
        with MBTilesSource(sample_mbtiles) as src:
            meta = src.get_metadata()
        assert meta["name"] == "Test Tiles"
        assert meta["format"] == "pbf"

    def test_bounds(self, sample_mbtiles: Path) -> None:
        with MBTilesSource(sample_mbtiles) as src:
            assert src.bounds == (-180.0, -85.05, 180.0, 85.05)

    def test_bounds_none_when_missing(self, empty_mbtiles: Path) -> None:
        with MBTilesSource(empty_mbtiles) as src:
            assert src.bounds is None

    def test_zoom_properties(self, sample_mbtiles: Path) -> None:
        with MBTilesSource(sample_mbtiles) as src:
            assert src.min_zoom == 0
            assert src.max_zoom == 5

    def test_name_property(self, sample_mbtiles: Path) -> None:
        with MBTilesSource(sample_mbtiles) as src:
            assert src.name == "Test Tiles"


class TestLifecycle:
    def test_context_manager(self, sample_mbtiles: Path) -> None:
        with MBTilesSource(sample_mbtiles) as src:
            assert src.get_tile(2, 1, 1) is not None

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            MBTilesSource(tmp_path / "nope.mbtiles")

    def test_invalid_db_raises(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.mbtiles"
        bad.write_bytes(b"not sqlite")
        with pytest.raises((ValueError, RuntimeError, Exception)):
            MBTilesSource(bad)
