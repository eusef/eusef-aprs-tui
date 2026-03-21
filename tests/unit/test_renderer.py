"""Tests for aprs_tui.map.renderer — top-level map compositor."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import mapbox_vector_tile
from rich.text import Text

from aprs_tui.core.station_tracker import StationRecord
from aprs_tui.map.renderer import MapRenderer
from aprs_tui.map.tile_source import MBTilesSource

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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


_EXTENT = 4096


def _flip_y(coords, geom_type: str):
    """Flip y coords from y-down (test convention) to y-up (encoder convention)."""
    def fp(p):
        return (p[0], _EXTENT - p[1])
    if geom_type == "Polygon":
        return [[fp(p) for p in ring] for ring in coords]
    if geom_type == "LineString":
        return [fp(p) for p in coords]
    if geom_type == "Point":
        return fp(coords)
    return coords


def _make_mvt_tile(layers: list[dict]) -> bytes:
    """Encode layer dicts into MVT bytes.

    Test coordinates use y-down convention (matching MVT spec).
    We flip to y-up for the encoder since our decoder uses y_coord_down=True.
    """
    flipped = []
    for layer in layers:
        new_layer = {**layer, "features": []}
        for feat in layer["features"]:
            geom = feat["geometry"]
            new_coords = _flip_y(geom["coordinates"], geom["type"])
            new_geom = {**geom, "coordinates": new_coords}
            new_layer["features"].append({**feat, "geometry": new_geom})
        flipped.append(new_layer)
    return mapbox_vector_tile.encode(flipped)


def _water_polygon_tile() -> bytes:
    """Tile with a single water polygon covering part of the tile."""
    return _make_mvt_tile([{
        "name": "water",
        "features": [{
            "geometry": {
                "type": "Polygon",
                "coordinates": [[(0, 0), (500, 0), (500, 500), (0, 500), (0, 0)]],
            },
            "properties": {},
            "id": 1,
        }],
    }])


def _road_linestring_tile() -> bytes:
    """Tile with a transportation linestring."""
    return _make_mvt_tile([{
        "name": "transportation",
        "features": [{
            "geometry": {
                "type": "LineString",
                "coordinates": [(100, 100), (300, 300)],
            },
            "properties": {"class": "primary"},
            "id": 2,
        }],
    }])


def _make_station(
    callsign: str = "N0CALL",
    lat: float | None = 45.0,
    lon: float | None = -122.0,
    symbol_table: str | None = "/",
    symbol_code: str | None = ">",
    sources: set[str] | None = None,
    last_heard: float = 0.0,
) -> StationRecord:
    return StationRecord(
        callsign=callsign,
        latitude=lat,
        longitude=lon,
        symbol_table=symbol_table,
        symbol_code=symbol_code,
        sources=sources if sources is not None else {"RF"},
        last_heard=last_heard,
    )


# ---------------------------------------------------------------------------
# No tile source — graceful degradation
# ---------------------------------------------------------------------------


class TestRenderNoData:
    """When no tile source is configured, render a compass rose."""

    def test_render_no_data_draws_compass(self) -> None:
        """Without a tile source the canvas should contain compass labels."""
        renderer = MapRenderer(tile_source=None)
        lines = renderer.render_plain(
            center_lat=45.0, center_lon=-122.0, zoom=10,
            char_width=20, char_height=10,
        )
        # Should get char_height rows
        assert len(lines) == 10
        # All rows should be char_width characters long
        for line in lines:
            assert len(line) == 20

        # The compass crosshair should set dots — check that the output is
        # not entirely blank braille (U+2800).
        all_text = "".join(lines)
        assert all_text != "\u2800" * (20 * 10), "Canvas should not be blank"

        # Compass cardinal labels should appear somewhere in the text
        assert "N" in all_text
        assert "S" in all_text
        assert "W" in all_text
        assert "E" in all_text

    def test_render_no_data_returns_rich_text(self) -> None:
        """render() should return a list of Rich Text objects even without tiles."""
        renderer = MapRenderer(tile_source=None)
        result = renderer.render(
            center_lat=45.0, center_lon=-122.0, zoom=10,
            char_width=20, char_height=10,
        )
        assert len(result) == 10
        for item in result:
            assert isinstance(item, Text)


# ---------------------------------------------------------------------------
# With tile source
# ---------------------------------------------------------------------------


class TestRenderWithTileSource:
    """Render with actual MVT tile data from a synthetic MBTiles file."""

    def test_render_with_tile_source(self, tmp_path: Path) -> None:
        """Canvas should have content when tiles are available."""
        # Build an MBTiles with a water polygon at zoom 10.
        # We need to figure out which tile(s) the renderer will request
        # for center=(0, 0) at zoom 10.  Tile (512, 512) at z=10 covers
        # the area near (0, 0).
        # Use a road tile (produces dots) rather than water (background only)
        tile_data = _make_mvt_tile([{
            "name": "transportation",
            "features": [{
                "geometry": {
                    "type": "LineString",
                    "coordinates": [(0, 0), (4096, 4096)],
                },
                "properties": {},
                "id": 1,
            }],
        }])
        tms_y = (1 << 10) - 1 - 512
        tiles = [(10, 512, tms_y, tile_data)]
        metadata = {"name": "Test", "minzoom": "0", "maxzoom": "14"}
        db_path = _create_mbtiles(
            tmp_path / "test.mbtiles", tiles=tiles, metadata=metadata
        )

        with MBTilesSource(db_path) as src:
            renderer = MapRenderer(tile_source=src)
            result = renderer.render(
                center_lat=0.0, center_lon=0.0, zoom=10,
                char_width=40, char_height=20,
            )

        assert len(result) == 20
        for item in result:
            assert isinstance(item, Text)
        # At least some cells should have content (non-blank)
        all_plain = "".join(str(t) for t in result)
        has_content = any(ch != "\u2800" for ch in all_plain)
        assert has_content, "Expected canvas to have content from tile data"


# ---------------------------------------------------------------------------
# With stations
# ---------------------------------------------------------------------------


class TestRenderWithStations:
    """Station overlay composited on top of map."""

    def test_render_with_stations(self) -> None:
        """Station callsign labels should appear in the rendered output."""
        renderer = MapRenderer(tile_source=None)
        stations = [
            _make_station(callsign="W7TEST", lat=45.0, lon=-122.0),
        ]
        result = renderer.render(
            center_lat=45.0, center_lon=-122.0, zoom=10,
            char_width=40, char_height=15,
            stations=stations,
            own_callsign="ME",
        )
        # Reconstruct all text from Rich Text objects
        all_text = "".join(str(t) for t in result)
        # The station callsign label should appear
        assert "W7TEST" in all_text

    def test_render_with_no_stations_is_just_base_map(self) -> None:
        """Passing stations=None should produce the same as no stations."""
        renderer = MapRenderer(tile_source=None)
        result_no_stations = renderer.render(
            center_lat=45.0, center_lon=-122.0, zoom=10,
            char_width=20, char_height=10,
            stations=None,
        )
        result_empty_stations = renderer.render(
            center_lat=45.0, center_lon=-122.0, zoom=10,
            char_width=20, char_height=10,
            stations=[],
        )
        # Both should produce the same number of lines
        assert len(result_no_stations) == len(result_empty_stations)

    def test_render_with_selected_station(self) -> None:
        """Selected callsign should be passed through to overlay."""
        renderer = MapRenderer(tile_source=None)
        stations = [
            _make_station(callsign="SELSTA", lat=45.0, lon=-122.0),
        ]
        result = renderer.render(
            center_lat=45.0, center_lon=-122.0, zoom=10,
            char_width=40, char_height=15,
            stations=stations,
            own_callsign="ME",
            selected_callsign="SELSTA",
        )
        all_text = "".join(str(t) for t in result)
        assert "SELSTA" in all_text


# ---------------------------------------------------------------------------
# set_tile_source cache invalidation
# ---------------------------------------------------------------------------


class TestSetTileSource:
    def test_set_tile_source_invalidates_cache(self) -> None:
        """Changing tile source should clear cached viewport state."""
        renderer = MapRenderer(tile_source=None)

        # Populate internal cache state
        renderer._cached_base = ["fake"]
        renderer._cached_viewport = (45.0, -122.0, 10.0, 20, 10)

        renderer.set_tile_source(None)

        assert renderer._cached_base is None
        assert renderer._cached_viewport is None

    def test_set_tile_source_updates_source(self, tmp_path: Path) -> None:
        """set_tile_source should update the internal tile source reference."""
        renderer = MapRenderer(tile_source=None)
        assert renderer._tile_source is None

        db_path = _create_mbtiles(
            tmp_path / "s.mbtiles", metadata={"name": "S"}
        )
        with MBTilesSource(db_path) as src:
            renderer.set_tile_source(src)
            assert renderer._tile_source is src

        # Setting back to None
        renderer.set_tile_source(None)
        assert renderer._tile_source is None


# ---------------------------------------------------------------------------
# render_plain
# ---------------------------------------------------------------------------


class TestRenderPlain:
    def test_render_plain_returns_strings(self) -> None:
        """render_plain should return a list of plain strings, not Text objects."""
        renderer = MapRenderer(tile_source=None)
        result = renderer.render_plain(
            center_lat=45.0, center_lon=-122.0, zoom=10,
            char_width=20, char_height=10,
        )
        assert len(result) == 10
        for line in result:
            assert isinstance(line, str)
            assert len(line) == 20

    def test_render_plain_no_stations(self) -> None:
        """render_plain should never include station data (it renders base map only)."""
        renderer = MapRenderer(tile_source=None)
        result = renderer.render_plain(
            center_lat=45.0, center_lon=-122.0, zoom=10,
            char_width=40, char_height=15,
        )
        all_text = "".join(result)
        # Compass labels should be present
        assert "N" in all_text
        # Station callsigns should NOT appear since render_plain skips stations
        assert "W7TEST" not in all_text


# ---------------------------------------------------------------------------
# Compositing order
# ---------------------------------------------------------------------------


class TestCompositingOrder:
    def test_stations_drawn_on_top_of_base_map(self, tmp_path: Path) -> None:
        """Station markers should appear in the composite output.

        We render a tile with a road (which produces dots), then add a station
        and check the station label appears in the output.
        """
        # Use a road tile (fills dots) rather than water (background only)
        tile_data = _make_mvt_tile([{
            "name": "transportation",
            "features": [{
                "geometry": {
                    "type": "LineString",
                    "coordinates": [(0, 0), (4096, 4096)],
                },
                "properties": {},
                "id": 1,
            }],
        }])
        # Place tile at z=10, x=512, y=512 which covers area near (0,0)
        tms_y = (1 << 10) - 1 - 512
        tiles = [(10, 512, tms_y, tile_data)]
        metadata = {"name": "Test", "minzoom": "0", "maxzoom": "14"}
        db_path = _create_mbtiles(
            tmp_path / "comp.mbtiles", tiles=tiles, metadata=metadata
        )

        # Render base map only (plain) to confirm there's content
        with MBTilesSource(db_path) as src:
            renderer = MapRenderer(tile_source=src)
            base_only = renderer.render_plain(
                center_lat=0.0, center_lon=0.0, zoom=10,
                char_width=40, char_height=20,
            )
            base_text = "".join(base_only)
            has_base = any(ch != "\u2800" for ch in base_text)

        # Render with station overlay
        with MBTilesSource(db_path) as src:
            renderer = MapRenderer(tile_source=src)
            station = _make_station(callsign="ONTOP", lat=0.0, lon=0.0)
            result = renderer.render(
                center_lat=0.0, center_lon=0.0, zoom=10,
                char_width=40, char_height=20,
                stations=[station],
                own_callsign="ME",
            )
            composite_text = "".join(str(t) for t in result)

        # Base map should have had some content
        assert has_base, "Base map should have content from water tile"
        # Station label should appear on top of the composite
        assert "ONTOP" in composite_text, "Station label should be drawn on top of base map"
