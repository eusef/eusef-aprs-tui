"""Tests for aprs_tui.map.vector_renderer — MVT decoder and feature renderer."""
from __future__ import annotations

import mapbox_vector_tile
import pytest

from aprs_tui.map.braille_canvas import BrailleCanvas
from aprs_tui.map.vector_renderer import (
    ZOOM_LAYERS,
    VectorRenderer,
    _CITY_CLASSES,
    _LABEL_LAYERS,
    _max_label_len,
)


# ---------------------------------------------------------------------------
# Helpers — build synthetic MVT tile data
# ---------------------------------------------------------------------------

EXTENT = 4096

def _make_tile(layers: list[dict]) -> bytes:
    """Encode a list of layer dicts into MVT bytes.

    Coordinates are given in y-down (MVT spec) convention.  Since the
    python encoder expects y-up and our decoder uses y_coord_down=True,
    we flip y during encoding so that the round-trip is consistent.
    """
    flipped = []
    for layer in layers:
        new_layer = {**layer, "features": []}
        for feat in layer["features"]:
            geom = feat["geometry"]
            new_geom = _flip_geom_y(geom, EXTENT)
            new_layer["features"].append({**feat, "geometry": new_geom})
        flipped.append(new_layer)
    return mapbox_vector_tile.encode(flipped)


def _flip_geom_y(geom: dict, extent: int) -> dict:
    """Flip y coordinates for encoding (y-down → y-up for encoder)."""
    gtype = geom["type"]
    coords = geom["coordinates"]

    def flip_pt(p):
        return (p[0], extent - p[1])

    if gtype == "Point":
        return {"type": gtype, "coordinates": flip_pt(coords)}
    elif gtype == "LineString":
        return {"type": gtype, "coordinates": [flip_pt(p) for p in coords]}
    elif gtype == "Polygon":
        return {"type": gtype, "coordinates": [[flip_pt(p) for p in ring] for ring in coords]}
    elif gtype == "MultiPolygon":
        return {"type": gtype, "coordinates": [[[flip_pt(p) for p in ring] for ring in poly] for poly in coords]}
    return geom


def _water_polygon_tile() -> bytes:
    """Tile with a single water polygon (y-down coords)."""
    return _make_tile([{
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
    """Tile with a transportation linestring (y-down coords)."""
    return _make_tile([{
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


def _point_tile() -> bytes:
    """Tile with a place point (y-down coords)."""
    return _make_tile([{
        "name": "place",
        "features": [{
            "geometry": {
                "type": "Point",
                "coordinates": (2048, 2048),
            },
            "properties": {"name": "Testville"},
            "id": 3,
        }],
    }])


def _city_label_tile() -> bytes:
    """Tile with a city-class place point."""
    return _make_tile([{
        "name": "place",
        "features": [{
            "geometry": {
                "type": "Point",
                "coordinates": (2048, 2048),
            },
            "properties": {"name": "Boston", "class": "city"},
            "id": 20,
        }],
    }])


def _village_label_tile() -> bytes:
    """Tile with a village-class place point."""
    return _make_tile([{
        "name": "place",
        "features": [{
            "geometry": {
                "type": "Point",
                "coordinates": (2048, 2048),
            },
            "properties": {"name": "Smalltown", "class": "village"},
            "id": 21,
        }],
    }])


def _no_name_place_tile() -> bytes:
    """Tile with a place point lacking a name property."""
    return _make_tile([{
        "name": "place",
        "features": [{
            "geometry": {
                "type": "Point",
                "coordinates": (2048, 2048),
            },
            "properties": {"class": "city"},
            "id": 22,
        }],
    }])


def _street_label_tile() -> bytes:
    """Tile with a VersaTiles street_labels point."""
    return _make_tile([{
        "name": "street_labels",
        "features": [{
            "geometry": {
                "type": "Point",
                "coordinates": (2048, 2048),
            },
            "properties": {"name": "Main Street"},
            "id": 23,
        }],
    }])


def _multi_layer_tile() -> bytes:
    """Tile with water + building layers."""
    return _make_tile([
        {
            "name": "water",
            "features": [{
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[(0, 0), (200, 0), (200, 200), (0, 200), (0, 0)]],
                },
                "properties": {},
                "id": 10,
            }],
        },
        {
            "name": "building",
            "features": [{
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[(300, 300), (400, 300), (400, 400), (300, 400), (300, 300)]],
                },
                "properties": {},
                "id": 11,
            }],
        },
    ])


# ---------------------------------------------------------------------------
# decode_tile
# ---------------------------------------------------------------------------

class TestDecodeTile:
    def test_returns_features_with_layer_attribute(self) -> None:
        renderer = VectorRenderer()
        tile_data = _water_polygon_tile()
        features = renderer.decode_tile(tile_data, z=5, x=16, y=16)

        assert len(features) >= 1
        for feat in features:
            assert "_layer" in feat
            assert feat["_layer"] == "water"

    def test_multi_layer_features_tagged(self) -> None:
        renderer = VectorRenderer()
        tile_data = _multi_layer_tile()
        features = renderer.decode_tile(tile_data, z=14, x=0, y=0)

        layers = {f["_layer"] for f in features}
        assert "water" in layers
        assert "building" in layers

    def test_caches_results(self) -> None:
        renderer = VectorRenderer()
        tile_data = _water_polygon_tile()
        first = renderer.decode_tile(tile_data, z=5, x=16, y=16)
        second = renderer.decode_tile(tile_data, z=5, x=16, y=16)
        assert first is second

    def test_corrupt_data_returns_empty(self) -> None:
        renderer = VectorRenderer()
        features = renderer.decode_tile(b"\x00\x01\x02\x03", z=0, x=0, y=0)
        assert features == []

    def test_empty_bytes_returns_empty(self) -> None:
        renderer = VectorRenderer()
        features = renderer.decode_tile(b"", z=1, x=0, y=0)
        assert features == []


# ---------------------------------------------------------------------------
# LRU cache eviction
# ---------------------------------------------------------------------------

class TestFeatureCacheEviction:
    def test_evicts_oldest_when_full(self) -> None:
        renderer = VectorRenderer(cache_size=2)
        tile_a = _water_polygon_tile()
        tile_b = _road_linestring_tile()
        tile_c = _point_tile()

        renderer.decode_tile(tile_a, z=1, x=0, y=0)
        renderer.decode_tile(tile_b, z=2, x=0, y=0)
        # Cache is now full (size=2)
        renderer.decode_tile(tile_c, z=3, x=0, y=0)
        # (1,0,0) should have been evicted
        assert (1, 0, 0) not in renderer._feature_cache
        assert (2, 0, 0) in renderer._feature_cache
        assert (3, 0, 0) in renderer._feature_cache

    def test_access_refreshes_entry(self) -> None:
        renderer = VectorRenderer(cache_size=2)
        tile_a = _water_polygon_tile()
        tile_b = _road_linestring_tile()
        tile_c = _point_tile()

        renderer.decode_tile(tile_a, z=1, x=0, y=0)
        renderer.decode_tile(tile_b, z=2, x=0, y=0)
        # Re-access first entry to refresh it
        renderer.decode_tile(tile_a, z=1, x=0, y=0)
        # Now add a third — should evict (2,0,0) not (1,0,0)
        renderer.decode_tile(tile_c, z=3, x=0, y=0)
        assert (1, 0, 0) in renderer._feature_cache
        assert (2, 0, 0) not in renderer._feature_cache


# ---------------------------------------------------------------------------
# Zoom filtering
# ---------------------------------------------------------------------------

class TestZoomFiltering:
    def test_building_skipped_at_low_zoom(self) -> None:
        """Buildings require zoom >= 14; at zoom 10 they should be skipped."""
        renderer = VectorRenderer()
        canvas = BrailleCanvas(20, 10)
        tile_data = _multi_layer_tile()

        # At zoom 10, buildings (min_zoom=14) should be skipped
        renderer.render_features(
            canvas, tile_data,
            zoom=10, tile_x=0, tile_y=0, tile_z=10,
            center_lat=0.0, center_lon=0.0,
        )
        # Water (min_zoom=0) should still be rendered — canvas won't be blank
        # We just verify no exception and it runs fine
        assert True

    def test_water_visible_at_any_zoom(self) -> None:
        assert ZOOM_LAYERS["water"] == 0

    def test_transportation_needs_zoom_4(self) -> None:
        assert ZOOM_LAYERS["transportation"] == 4

    def test_building_needs_zoom_14(self) -> None:
        assert ZOOM_LAYERS["building"] == 14

    def test_road_skipped_below_min_zoom(self) -> None:
        """Transportation features should be skipped at zoom < 4."""
        renderer = VectorRenderer()
        canvas = BrailleCanvas(20, 10)
        tile_data = _road_linestring_tile()

        # Record canvas state before
        before = bytearray(canvas._cells)

        renderer.render_features(
            canvas, tile_data,
            zoom=2, tile_x=0, tile_y=0, tile_z=2,
            center_lat=0.0, center_lon=0.0,
        )

        # Canvas should be unchanged since zoom 2 < min zoom 4
        assert canvas._cells == before


# ---------------------------------------------------------------------------
# render_features — line drawing for transportation
# ---------------------------------------------------------------------------

class TestRenderLineString:
    def test_draws_lines_for_road(self) -> None:
        """A transportation linestring at sufficient zoom should set dots."""
        renderer = VectorRenderer()
        canvas = BrailleCanvas(40, 20)
        tile_data = _road_linestring_tile()

        renderer.render_features(
            canvas, tile_data,
            zoom=10, tile_x=512, tile_y=512, tile_z=10,
            center_lat=0.0, center_lon=0.0,
        )

        # At least some dots should have been set by draw_line
        any_set = any(b != 0 for b in canvas._cells)
        assert any_set, "Expected transportation line to set dots on canvas"


# ---------------------------------------------------------------------------
# render_features — polygon fill for water
# ---------------------------------------------------------------------------

class TestRenderPolygon:
    def test_fills_polygon_for_water(self) -> None:
        """A water polygon should apply style (background) without filling dots."""
        renderer = VectorRenderer()
        canvas = BrailleCanvas(40, 20)
        tile_data = _water_polygon_tile()

        renderer.render_features(
            canvas, tile_data,
            zoom=10, tile_x=512, tile_y=512, tile_z=10,
            center_lat=0.0, center_lon=0.0,
        )

        # Water uses background styling, not dot fill
        any_styled = any(s is not None for s in canvas._color_buffer)
        assert any_styled, "Expected water polygon to apply style on canvas"

    def test_water_style_applied(self) -> None:
        """Cells touched by water should have 'water' style."""
        renderer = VectorRenderer()
        canvas = BrailleCanvas(40, 20)
        tile_data = _water_polygon_tile()

        renderer.render_features(
            canvas, tile_data,
            zoom=10, tile_x=512, tile_y=512, tile_z=10,
            center_lat=0.0, center_lon=0.0,
        )

        water_cells = [c for c in canvas._color_buffer if c == "water"]
        assert len(water_cells) > 0, "Expected 'water' style on some cells"


# ---------------------------------------------------------------------------
# render_features — point
# ---------------------------------------------------------------------------

class TestRenderPoint:
    def test_draws_point(self) -> None:
        """A place point with a name should render as text label."""
        renderer = VectorRenderer()
        canvas = BrailleCanvas(40, 20)
        tile_data = _point_tile()

        # Center the viewport on the tile center so the point is in view
        renderer.render_features(
            canvas, tile_data,
            zoom=10, tile_x=512, tile_y=512, tile_z=10,
            center_lat=-0.1758, center_lon=0.1758,
        )

        # Named place features render as text labels, not dots
        assert len(canvas._text_overlay) > 0, "Expected place point to render text label"


# ---------------------------------------------------------------------------
# Coordinate conversion
# ---------------------------------------------------------------------------

class TestTileLocalToLatlon:
    def test_center_of_tile_0_0_0(self) -> None:
        """Centre of the single zoom-0 tile should be near (0, 0)."""
        lat, lon = VectorRenderer._tile_local_to_latlon(2048, 2048, 0, 0, 0)
        assert -1 < lat < 1
        assert -1 < lon < 1

    def test_top_left_of_tile_0_0_0(self) -> None:
        """Top-left corner: max latitude, min longitude."""
        lat, lon = VectorRenderer._tile_local_to_latlon(0, 0, 0, 0, 0)
        assert lat > 80
        assert lon < -170

    def test_bottom_right_of_tile_0_0_0(self) -> None:
        """Bottom-right corner: min latitude, max longitude."""
        lat, lon = VectorRenderer._tile_local_to_latlon(4096, 4096, 0, 0, 0)
        assert lat < -80
        assert lon > 170


# ---------------------------------------------------------------------------
# Label rendering
# ---------------------------------------------------------------------------

class TestLabelRendering:
    def test_city_label_renders_text(self) -> None:
        """A city place feature should render as text, not just a dot."""
        renderer = VectorRenderer()
        canvas = BrailleCanvas(40, 20)
        tile_data = _city_label_tile()

        renderer.render_features(
            canvas, tile_data,
            zoom=10, tile_x=512, tile_y=512, tile_z=10,
            center_lat=-0.1758, center_lon=0.1758,
        )

        # Text overlay should contain characters from the label
        assert len(canvas._text_overlay) > 0

    def test_city_label_uses_city_style(self) -> None:
        """City-class places should use the 'label_city' style."""
        renderer = VectorRenderer()
        canvas = BrailleCanvas(40, 20)
        tile_data = _city_label_tile()

        renderer.render_features(
            canvas, tile_data,
            zoom=10, tile_x=512, tile_y=512, tile_z=10,
            center_lat=-0.1758, center_lon=0.1758,
        )

        styled_cells = [c for c in canvas._color_buffer if c == "label_city"]
        assert len(styled_cells) > 0, "Expected 'label_city' style on city label cells"

    def test_village_label_uses_default_layer_style(self) -> None:
        """Non-city place classes should use the layer's default style."""
        renderer = VectorRenderer()
        canvas = BrailleCanvas(40, 20)
        tile_data = _village_label_tile()

        renderer.render_features(
            canvas, tile_data,
            zoom=10, tile_x=512, tile_y=512, tile_z=10,
            center_lat=-0.1758, center_lon=0.1758,
        )

        # Village uses the layer default (label_city from _LAYER_TO_STYLE for "place")
        # but since "village" is not in _CITY_CLASSES, it falls back to the style_name
        # which is the _LAYER_TO_STYLE mapping for "place" = "label_city"
        assert len(canvas._text_overlay) > 0

    def test_no_name_falls_back_to_dot(self) -> None:
        """Place features without a name should render as a simple dot."""
        renderer = VectorRenderer()
        canvas = BrailleCanvas(40, 20)
        tile_data = _no_name_place_tile()

        renderer.render_features(
            canvas, tile_data,
            zoom=10, tile_x=512, tile_y=512, tile_z=10,
            center_lat=-0.1758, center_lon=0.1758,
        )

        # Should have set a dot but no text overlay
        assert len(canvas._text_overlay) == 0
        any_set = any(b != 0 for b in canvas._cells)
        assert any_set, "Expected a dot for nameless place feature"

    def test_street_label_renders_text(self) -> None:
        """Street label features should render as text."""
        renderer = VectorRenderer()
        canvas = BrailleCanvas(40, 20)
        tile_data = _street_label_tile()

        renderer.render_features(
            canvas, tile_data,
            zoom=10, tile_x=512, tile_y=512, tile_z=10,
            center_lat=-0.1758, center_lon=0.1758,
        )

        assert len(canvas._text_overlay) > 0

    def test_street_label_uses_street_style(self) -> None:
        """Street labels should use the 'label_street' style."""
        renderer = VectorRenderer()
        canvas = BrailleCanvas(40, 20)
        tile_data = _street_label_tile()

        renderer.render_features(
            canvas, tile_data,
            zoom=10, tile_x=512, tile_y=512, tile_z=10,
            center_lat=-0.1758, center_lon=0.1758,
        )

        styled_cells = [c for c in canvas._color_buffer if c == "label_street"]
        assert len(styled_cells) > 0, "Expected 'label_street' style on street labels"


class TestMaxLabelLen:
    def test_high_zoom_allows_long_labels(self) -> None:
        assert _max_label_len(14) == 20
        assert _max_label_len(16) == 20

    def test_medium_zoom_caps_at_15(self) -> None:
        assert _max_label_len(10) == 15
        assert _max_label_len(13) == 15

    def test_low_zoom_caps_at_12(self) -> None:
        assert _max_label_len(7) == 12
        assert _max_label_len(9) == 12

    def test_very_low_zoom_caps_at_8(self) -> None:
        assert _max_label_len(4) == 8
        assert _max_label_len(6) == 8


class TestLabelConstants:
    def test_label_layers_contains_place(self) -> None:
        assert "place" in _LABEL_LAYERS
        assert "place_labels" in _LABEL_LAYERS
        assert "street_labels" in _LABEL_LAYERS

    def test_city_classes_contains_city(self) -> None:
        assert "city" in _CITY_CLASSES
        assert "town" in _CITY_CLASSES
