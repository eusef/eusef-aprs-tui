"""Tests for aprs_tui.map.tile_math — coordinate conversions."""
from __future__ import annotations

import pytest

from aprs_tui.map.tile_math import (
    fit_bounds_to_viewport,
    latlon_to_braille_pixel,
    latlon_to_pixel,
    pixel_to_latlon,
    tile_bounds,
    viewport_tiles,
)


class TestLatLonToPixel:
    def test_origin(self):
        """(0, 0) at zoom 0 should be near center of the single tile."""
        px, py = latlon_to_pixel(0.0, 0.0, 0)
        assert abs(px - 128) < 1
        assert abs(py - 128) < 1

    def test_northwest_corner(self):
        """Top-left of world map is near (0, 0) pixels at zoom 0."""
        px, py = latlon_to_pixel(85.05, -180.0, 0)
        assert px < 1
        assert py < 1

    def test_zoom_increases_pixel_range(self):
        px0, py0 = latlon_to_pixel(45.0, -122.0, 0)
        px1, py1 = latlon_to_pixel(45.0, -122.0, 1)
        # At zoom 1, pixel values should be roughly 2x zoom 0
        assert abs(px1 - px0 * 2) < 2
        assert abs(py1 - py0 * 2) < 2


class TestPixelToLatLon:
    def test_roundtrip(self):
        """latlon_to_pixel and pixel_to_latlon are inverses."""
        lat, lon = 45.52, -122.68
        for zoom in (0, 5, 10, 15):
            px, py = latlon_to_pixel(lat, lon, zoom)
            rlat, rlon = pixel_to_latlon(px, py, zoom)
            assert abs(rlat - lat) < 0.001
            assert abs(rlon - lon) < 0.001

    def test_center_of_world(self):
        lat, lon = pixel_to_latlon(128, 128, 0)
        assert abs(lat) < 0.1
        assert abs(lon) < 0.1


class TestViewportTiles:
    def test_single_tile_at_zoom_0(self):
        tiles = viewport_tiles(0.0, 0.0, 0, 40, 20)
        assert (0, 0, 0) in tiles

    def test_returns_multiple_tiles_at_higher_zoom(self):
        tiles = viewport_tiles(45.52, -122.68, 10, 40, 20)
        assert len(tiles) >= 1
        for x, y, z in tiles:
            assert z == 10
            assert 0 <= x < 1024
            assert 0 <= y < 1024

    def test_small_viewport_few_tiles(self):
        tiles = viewport_tiles(45.52, -122.68, 5, 5, 3)
        assert len(tiles) >= 1
        assert len(tiles) <= 4  # small viewport, few tiles


class TestFitBoundsToViewport:
    def test_whole_world_fits_at_low_zoom(self):
        z = fit_bounds_to_viewport(-85, 85, -180, 180, 512, 512)
        assert z <= 1.0

    def test_small_area_fits_at_higher_zoom(self):
        # ~0.1 degree box should fit at a higher zoom than the whole world
        z = fit_bounds_to_viewport(45.0, 45.1, -122.1, -122.0, 200, 200)
        assert z >= 8

    def test_zero_viewport(self):
        z = fit_bounds_to_viewport(0, 1, 0, 1, 0, 0)
        assert z == 0.0

    def test_returns_half_integer(self):
        z = fit_bounds_to_viewport(45.0, 45.5, -123.0, -122.0, 200, 200)
        assert z * 2 == int(z * 2)  # half-integer


class TestLatLonToBraillePixel:
    def test_center_maps_to_canvas_center(self):
        dx, dy = latlon_to_braille_pixel(45.0, -122.0, 10, 45.0, -122.0, 80, 60)
        assert abs(dx - 40) <= 1
        assert abs(dy - 30) <= 1

    def test_offset_from_center(self):
        dx, dy = latlon_to_braille_pixel(45.1, -122.0, 10, 45.0, -122.0, 80, 60)
        # 45.1 is north of 45.0, so dy should be less than center
        assert dy < 30


class TestTileBounds:
    def test_zoom_0(self):
        w, s, e, n = tile_bounds(0, 0, 0)
        assert w == pytest.approx(-180.0)
        assert e == pytest.approx(180.0)
        assert s == pytest.approx(-85.051129, abs=0.01)
        assert n == pytest.approx(85.051129, abs=0.01)

    def test_tile_has_positive_area(self):
        w, s, e, n = tile_bounds(5, 10, 8)
        assert e > w
        assert n > s
