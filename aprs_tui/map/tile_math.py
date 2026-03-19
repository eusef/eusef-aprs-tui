"""Tile coordinate math — wraps mercantile for lat/lon ↔ tile/pixel conversions."""
from __future__ import annotations

import math

import mercantile


def viewport_tiles(
    center_lat: float,
    center_lon: float,
    zoom: int,
    width_chars: int,
    height_chars: int,
) -> list[tuple[int, int, int]]:
    """Return (x, y, z) tile coordinates visible in the viewport.

    *width_chars* and *height_chars* are terminal character dimensions.
    Braille resolution: width_chars*2 dots wide, height_chars*4 dots tall.
    """
    width_dots = width_chars * 2
    height_dots = height_chars * 4

    cx, cy = latlon_to_pixel(center_lat, center_lon, zoom)

    # Viewport corners in pixel space
    left = cx - width_dots / 2
    right = cx + width_dots / 2
    top = cy - height_dots / 2
    bottom = cy + height_dots / 2

    # Convert pixel bounds to tile indices
    tile_size = 256
    min_tx = max(0, int(left // tile_size))
    max_tx = min((1 << zoom) - 1, int(right // tile_size))
    min_ty = max(0, int(top // tile_size))
    max_ty = min((1 << zoom) - 1, int(bottom // tile_size))

    tiles = []
    for tx in range(min_tx, max_tx + 1):
        for ty in range(min_ty, max_ty + 1):
            tiles.append((tx, ty, zoom))
    return tiles


def latlon_to_pixel(lat: float, lon: float, zoom: float) -> tuple[float, float]:
    """Convert lat/lon to absolute pixel position at given zoom.

    Uses Web Mercator projection.  Pixel space is 256 * 2^zoom wide/tall.
    """
    lat = max(-85.051129, min(85.051129, lat))
    n = 2.0**zoom
    px = ((lon + 180.0) / 360.0) * 256 * n
    lat_rad = math.radians(lat)
    py = (
        (1.0 - math.log(math.tan(lat_rad) + 1.0 / math.cos(lat_rad)) / math.pi)
        / 2.0
        * 256
        * n
    )
    return px, py


def pixel_to_latlon(px: float, py: float, zoom: float) -> tuple[float, float]:
    """Convert absolute pixel position back to lat/lon."""
    n = 2.0**zoom
    lon = px / (256 * n) * 360.0 - 180.0
    lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * py / (256 * n))))
    lat = math.degrees(lat_rad)
    return lat, lon


def fit_bounds_to_viewport(
    min_lat: float,
    max_lat: float,
    min_lon: float,
    max_lon: float,
    viewport_width_dots: int,
    viewport_height_dots: int,
) -> float:
    """Calculate the zoom level that fits the bounding box into the viewport.

    Returns the largest half-integer zoom where the bounds fit.
    """
    if viewport_width_dots <= 0 or viewport_height_dots <= 0:
        return 0.0

    # Try zoom levels from high to low in 0.5 steps
    for z_half in range(36, -1, -1):
        z = z_half / 2.0
        tl_px, tl_py = latlon_to_pixel(max_lat, min_lon, z)
        br_px, br_py = latlon_to_pixel(min_lat, max_lon, z)
        bbox_w = abs(br_px - tl_px)
        bbox_h = abs(br_py - tl_py)
        if bbox_w <= viewport_width_dots and bbox_h <= viewport_height_dots:
            return z
    return 0.0


def latlon_to_braille_pixel(
    lat: float,
    lon: float,
    zoom: float,
    center_lat: float,
    center_lon: float,
    canvas_width_dots: int,
    canvas_height_dots: int,
) -> tuple[int, int]:
    """Convert lat/lon to braille dot coords relative to canvas center.

    Returns (dot_x, dot_y) where (0, 0) is top-left.
    """
    px, py = latlon_to_pixel(lat, lon, zoom)
    cx, cy = latlon_to_pixel(center_lat, center_lon, zoom)
    dot_x = int(px - cx + canvas_width_dots / 2)
    dot_y = int(py - cy + canvas_height_dots / 2)
    return dot_x, dot_y


def tile_bounds(x: int, y: int, z: int) -> tuple[float, float, float, float]:
    """Return (west, south, east, north) geographic bounds of a tile."""
    b = mercantile.bounds(mercantile.Tile(x, y, z))
    return (b.west, b.south, b.east, b.north)
