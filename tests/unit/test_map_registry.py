"""Tests for aprs_tui.map.registry — map registry and selection logic."""
from __future__ import annotations

from pathlib import Path

import pytest

from aprs_tui.map.registry import MapEntry, MapRegistry


def _make_entry(
    file: str = "test.mbtiles",
    name: str = "Test Map",
    bounds: tuple[float, float, float, float] = (-180.0, -85.0, 180.0, 85.0),
    min_zoom: int = 0,
    max_zoom: int = 14,
    size_mb: float = 100.0,
    downloaded: str = "2025-01-01T00:00:00Z",
    source: str = "openmaptiles",
) -> MapEntry:
    return MapEntry(
        file=file,
        name=name,
        bounds=bounds,
        min_zoom=min_zoom,
        max_zoom=max_zoom,
        size_mb=size_mb,
        downloaded=downloaded,
        source=source,
    )


class TestEmptyRegistry:
    def test_empty_registry(self, tmp_path: Path) -> None:
        """New registry with no maps.toml returns empty list."""
        reg = MapRegistry(maps_dir=tmp_path / "maps")
        assert reg.list_maps() == []


class TestRegisterAndList:
    def test_register_and_list(self, tmp_path: Path) -> None:
        reg = MapRegistry(maps_dir=tmp_path / "maps")
        entry = _make_entry()
        reg.register("world", entry)
        maps = reg.list_maps()
        assert len(maps) == 1
        assert maps[0].name == "Test Map"
        assert maps[0].file == "test.mbtiles"
        assert maps[0].bounds == (-180.0, -85.0, 180.0, 85.0)
        assert maps[0].min_zoom == 0
        assert maps[0].max_zoom == 14


class TestPersistence:
    def test_register_persists_to_file(self, tmp_path: Path) -> None:
        """Save, create new registry instance, verify data loaded."""
        maps_dir = tmp_path / "maps"
        reg1 = MapRegistry(maps_dir=maps_dir)
        reg1.register("world", _make_entry())

        # Create a fresh registry pointing at the same directory
        reg2 = MapRegistry(maps_dir=maps_dir)
        maps = reg2.list_maps()
        assert len(maps) == 1
        assert maps[0].name == "Test Map"
        assert maps[0].max_zoom == 14


class TestRemoveMap:
    def test_remove_map(self, tmp_path: Path) -> None:
        reg = MapRegistry(maps_dir=tmp_path / "maps")
        reg.register("world", _make_entry())
        assert len(reg.list_maps()) == 1
        reg.remove("world")
        assert len(reg.list_maps()) == 0

    def test_remove_nonexistent_key_is_noop(self, tmp_path: Path) -> None:
        reg = MapRegistry(maps_dir=tmp_path / "maps")
        reg.remove("nonexistent")  # should not raise
        assert len(reg.list_maps()) == 0


class TestSelectMap:
    def test_select_map_by_bounds(self, tmp_path: Path) -> None:
        """Map whose bounds contain the center point is selected."""
        reg = MapRegistry(maps_dir=tmp_path / "maps")
        entry = _make_entry(
            name="USA",
            bounds=(-125.0, 24.0, -66.0, 50.0),
            max_zoom=14,
        )
        reg.register("usa", entry)
        result = reg.select_map(center_lat=40.0, center_lon=-100.0, zoom=10)
        assert result is not None
        assert result.name == "USA"

    def test_select_map_prefers_highest_zoom(self, tmp_path: Path) -> None:
        reg = MapRegistry(maps_dir=tmp_path / "maps")
        low_zoom = _make_entry(
            file="low.mbtiles",
            name="Low Zoom",
            bounds=(-180.0, -85.0, 180.0, 85.0),
            max_zoom=8,
        )
        high_zoom = _make_entry(
            file="high.mbtiles",
            name="High Zoom",
            bounds=(-180.0, -85.0, 180.0, 85.0),
            max_zoom=14,
        )
        reg.register("low", low_zoom)
        reg.register("high", high_zoom)
        result = reg.select_map(center_lat=0.0, center_lon=0.0, zoom=5)
        assert result is not None
        assert result.name == "High Zoom"

    def test_select_map_returns_none_when_no_match(self, tmp_path: Path) -> None:
        reg = MapRegistry(maps_dir=tmp_path / "maps")
        entry = _make_entry(
            name="USA",
            bounds=(-125.0, 24.0, -66.0, 50.0),
        )
        reg.register("usa", entry)
        # Point in Europe, not covered by USA map
        result = reg.select_map(center_lat=48.0, center_lon=2.0, zoom=10)
        assert result is None

    def test_select_map_with_zoom_filter(self, tmp_path: Path) -> None:
        """When zoom exceeds max_zoom, fall back to map containing point."""
        reg = MapRegistry(maps_dir=tmp_path / "maps")
        low = _make_entry(
            file="low.mbtiles",
            name="Low Zoom Only",
            bounds=(-180.0, -85.0, 180.0, 85.0),
            max_zoom=5,
        )
        high = _make_entry(
            file="high.mbtiles",
            name="High Zoom",
            bounds=(-180.0, -85.0, 180.0, 85.0),
            max_zoom=14,
        )
        reg.register("low", low)
        reg.register("high", high)

        # At zoom 10, only "High Zoom" qualifies in first pass
        result = reg.select_map(center_lat=0.0, center_lon=0.0, zoom=10)
        assert result is not None
        assert result.name == "High Zoom"

        # At zoom 3, both qualify; highest max_zoom wins
        result = reg.select_map(center_lat=0.0, center_lon=0.0, zoom=3)
        assert result is not None
        assert result.name == "High Zoom"

    def test_select_map_fallback_when_all_below_zoom(self, tmp_path: Path) -> None:
        """When no map has max_zoom >= requested zoom, fall back to best available."""
        reg = MapRegistry(maps_dir=tmp_path / "maps")
        entry = _make_entry(
            name="Low Res",
            bounds=(-180.0, -85.0, 180.0, 85.0),
            max_zoom=5,
        )
        reg.register("lowres", entry)
        # Request zoom 10 but only zoom-5 map available
        result = reg.select_map(center_lat=0.0, center_lon=0.0, zoom=10)
        assert result is not None
        assert result.name == "Low Res"


class TestRoundtrip:
    def test_roundtrip_save_load(self, tmp_path: Path) -> None:
        maps_dir = tmp_path / "maps"
        reg = MapRegistry(maps_dir=maps_dir)
        entries = {
            "world": _make_entry(
                file="world.mbtiles",
                name="World",
                bounds=(-180.0, -85.0, 180.0, 85.0),
                min_zoom=0,
                max_zoom=7,
                size_mb=50.0,
                downloaded="2025-06-01T12:00:00Z",
                source="openmaptiles",
            ),
            "usa": _make_entry(
                file="usa.mbtiles",
                name="United States",
                bounds=(-125.0, 24.0, -66.0, 50.0),
                min_zoom=0,
                max_zoom=14,
                size_mb=800.0,
                downloaded="2025-06-15T08:30:00Z",
                source="openmaptiles",
            ),
        }
        for key, entry in entries.items():
            reg.register(key, entry)

        # Reload from disk
        reg2 = MapRegistry(maps_dir=maps_dir)
        loaded = {e.file: e for e in reg2.list_maps()}
        assert len(loaded) == 2

        world = loaded["world.mbtiles"]
        assert world.name == "World"
        assert world.bounds == (-180.0, -85.0, 180.0, 85.0)
        assert world.min_zoom == 0
        assert world.max_zoom == 7
        assert world.size_mb == 50.0
        assert world.downloaded == "2025-06-01T12:00:00Z"
        assert world.source == "openmaptiles"

        usa = loaded["usa.mbtiles"]
        assert usa.name == "United States"
        assert usa.bounds == (-125.0, 24.0, -66.0, 50.0)
        assert usa.max_zoom == 14
        assert usa.size_mb == 800.0


class TestGetMBTilesPath:
    def test_get_mbtiles_path(self, tmp_path: Path) -> None:
        maps_dir = tmp_path / "maps"
        reg = MapRegistry(maps_dir=maps_dir)
        entry = _make_entry(file="usa.mbtiles")
        assert reg.get_mbtiles_path(entry) == maps_dir / "usa.mbtiles"
