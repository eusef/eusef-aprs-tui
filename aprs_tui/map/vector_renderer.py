"""Vector tile decoder and feature renderer.

Decodes Mapbox Vector Tile (MVT/PBF) data and rasterizes geographic
features (water, roads, buildings, etc.) onto a :class:`BrailleCanvas`.
"""
from __future__ import annotations

from collections import OrderedDict

import mapbox_vector_tile

from aprs_tui.map.braille_canvas import BrailleCanvas
from aprs_tui.map.tile_math import latlon_to_braille_pixel, tile_bounds

# ---------------------------------------------------------------------------
# Layer visibility by minimum zoom level
# ---------------------------------------------------------------------------

# Supports both OpenMapTiles and VersaTiles layer names.
ZOOM_LAYERS: dict[str, int] = {
    # OpenMapTiles
    "water": 0,
    "waterway": 0,
    "landcover": 8,
    "landuse": 8,
    "transportation": 4,
    "building": 14,
    "boundary": 0,
    "place": 4,
    # VersaTiles
    "ocean": 0,
    "water_polygons": 0,
    "water_lines": 4,
    "water_lines_labels": 6,
    "boundaries": 0,
    "boundary_labels": 4,
    "streets": 6,
    "street_labels": 10,
    "land": 0,
    "place_labels": 4,
    "ferries": 8,
}

# Map MVT layer names to feature-type strings used by styles.py.
# Supports both OpenMapTiles and VersaTiles schemas.
_LAYER_TO_STYLE: dict[str, str] = {
    # OpenMapTiles
    "water": "water",
    "waterway": "water",
    "landcover": "landuse",
    "landuse": "landuse",
    "transportation": "road",
    "building": "building",
    "boundary": "boundary",
    "place": "label",
    # VersaTiles
    "ocean": "water",
    "water_polygons": "water",
    "water_lines": "coastline",
    "water_lines_labels": "label",
    "boundaries": "boundary",
    "boundary_labels": "label",
    "streets": "road",
    "street_labels": "label",
    "land": "landuse",
    "place_labels": "label",
    "ferries": "road_minor",
}


class VectorRenderer:
    """Decode MVT/PBF vector tiles and rasterize features onto a BrailleCanvas."""

    def __init__(self, cache_size: int = 32) -> None:
        self._feature_cache: OrderedDict[tuple[int, int, int], list[dict]] = (
            OrderedDict()
        )
        self._cache_size = cache_size

    # ------------------------------------------------------------------
    # Decoding
    # ------------------------------------------------------------------

    def decode_tile(
        self, tile_data: bytes, z: int, x: int, y: int
    ) -> list[dict]:
        """Decode PBF tile data into a list of feature dicts.  Cached.

        Each returned dict is a GeoJSON-like feature dict produced by
        *mapbox_vector_tile.decode*, augmented with a ``_layer`` key
        holding the source layer name.
        """
        key = (z, x, y)
        if key in self._feature_cache:
            self._feature_cache.move_to_end(key)
            return self._feature_cache[key]

        try:
            decoded = mapbox_vector_tile.decode(
                tile_data,
                default_options={"y_coord_down": True},
            )
        except Exception:
            decoded = {}

        features: list[dict] = []
        for layer_name, layer_data in decoded.items():
            for feature in layer_data.get("features", []):
                feature["_layer"] = layer_name
                features.append(feature)

        # LRU eviction
        if len(self._feature_cache) >= self._cache_size:
            self._feature_cache.popitem(last=False)
        self._feature_cache[key] = features
        return features

    # ------------------------------------------------------------------
    # High-level convenience
    # ------------------------------------------------------------------

    def render_features(
        self,
        canvas: BrailleCanvas,
        tile_data: bytes,
        zoom: int,
        tile_x: int,
        tile_y: int,
        tile_z: int,
        center_lat: float,
        center_lon: float,
    ) -> None:
        """Decode and render a complete tile onto the canvas."""
        features = self.decode_tile(tile_data, tile_z, tile_x, tile_y)
        for feature in features:
            layer = feature.get("_layer", "")
            min_zoom = ZOOM_LAYERS.get(layer, 0)
            if zoom < min_zoom:
                continue
            self._render_feature(
                canvas,
                feature,
                layer,
                zoom,
                tile_x,
                tile_y,
                tile_z,
                center_lat,
                center_lon,
            )

    # ------------------------------------------------------------------
    # Per-tile rendering (public for direct use)
    # ------------------------------------------------------------------

    def render_tile(
        self,
        canvas: BrailleCanvas,
        features: list[dict],
        layer_name: str,
        zoom: int,
        tile_x: int,
        tile_y: int,
        tile_z: int,
        viewport_center_lat: float,
        viewport_center_lon: float,
    ) -> None:
        """Rasterize features from a single tile onto the canvas.

        Only features whose ``_layer`` matches *layer_name* are drawn.
        """
        for feature in features:
            if feature.get("_layer", "") != layer_name:
                continue
            min_zoom = ZOOM_LAYERS.get(layer_name, 0)
            if zoom < min_zoom:
                continue
            self._render_feature(
                canvas,
                feature,
                layer_name,
                zoom,
                tile_x,
                tile_y,
                tile_z,
                viewport_center_lat,
                viewport_center_lon,
            )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _render_feature(
        self,
        canvas: BrailleCanvas,
        feature: dict,
        layer: str,
        zoom: int,
        tile_x: int,
        tile_y: int,
        tile_z: int,
        center_lat: float,
        center_lon: float,
    ) -> None:
        """Rasterize a single decoded feature onto the canvas."""
        geometry = feature.get("geometry")
        if geometry is None:
            return

        geom_type = geometry.get("type", "")
        coords = geometry.get("coordinates", [])
        style_name = _LAYER_TO_STYLE.get(layer, "default")

        if geom_type == "Point":
            self._draw_point(
                canvas, coords, tile_x, tile_y, tile_z,
                center_lat, center_lon, zoom, style_name,
            )
        elif geom_type == "MultiPoint":
            for pt in coords:
                self._draw_point(
                    canvas, pt, tile_x, tile_y, tile_z,
                    center_lat, center_lon, zoom, style_name,
                )
        elif geom_type == "LineString":
            self._draw_linestring(
                canvas, coords, tile_x, tile_y, tile_z,
                center_lat, center_lon, zoom, style_name,
            )
        elif geom_type == "MultiLineString":
            for ring in coords:
                self._draw_linestring(
                    canvas, ring, tile_x, tile_y, tile_z,
                    center_lat, center_lon, zoom, style_name,
                )
        elif geom_type == "Polygon":
            self._draw_polygon(
                canvas, coords, tile_x, tile_y, tile_z,
                center_lat, center_lon, zoom, style_name,
            )
        elif geom_type == "MultiPolygon":
            for polygon_rings in coords:
                self._draw_polygon(
                    canvas, polygon_rings, tile_x, tile_y, tile_z,
                    center_lat, center_lon, zoom, style_name,
                )

    # -- coordinate conversion ------------------------------------------

    @staticmethod
    def _tile_local_to_latlon(
        feat_x: float,
        feat_y: float,
        tile_x: int,
        tile_y: int,
        tile_z: int,
        extent: int = 4096,
    ) -> tuple[float, float]:
        """Convert MVT tile-local coordinates to (lat, lon).

        MVT coordinates run from 0..extent within the tile.  ``feat_y``
        increases downward in the tile (north to south).
        """
        west, south, east, north = tile_bounds(tile_x, tile_y, tile_z)
        geo_x = west + (feat_x / extent) * (east - west)
        geo_y = north - (feat_y / extent) * (north - south)
        return geo_y, geo_x  # lat, lon

    def _to_braille(
        self,
        feat_x: float,
        feat_y: float,
        tile_x: int,
        tile_y: int,
        tile_z: int,
        center_lat: float,
        center_lon: float,
        zoom: int,
        canvas: BrailleCanvas,
    ) -> tuple[int, int]:
        """Convert MVT tile-local coords to braille pixel coords."""
        lat, lon = self._tile_local_to_latlon(
            feat_x, feat_y, tile_x, tile_y, tile_z
        )
        return latlon_to_braille_pixel(
            lat, lon, zoom, center_lat, center_lon,
            canvas.width, canvas.height,
        )

    # -- geometry primitives --------------------------------------------

    def _draw_point(
        self,
        canvas: BrailleCanvas,
        coords: list,
        tile_x: int,
        tile_y: int,
        tile_z: int,
        center_lat: float,
        center_lon: float,
        zoom: int,
        style_name: str,
    ) -> None:
        bx, by = self._to_braille(
            coords[0], coords[1],
            tile_x, tile_y, tile_z,
            center_lat, center_lon, zoom, canvas,
        )
        canvas.set_dot(bx, by)
        canvas.set_cell_style(bx // 2, by // 4, style_name)

    def _draw_linestring(
        self,
        canvas: BrailleCanvas,
        coords: list,
        tile_x: int,
        tile_y: int,
        tile_z: int,
        center_lat: float,
        center_lon: float,
        zoom: int,
        style_name: str,
    ) -> None:
        pixels = [
            self._to_braille(
                c[0], c[1],
                tile_x, tile_y, tile_z,
                center_lat, center_lon, zoom, canvas,
            )
            for c in coords
        ]
        for i in range(len(pixels) - 1):
            x0, y0 = pixels[i]
            x1, y1 = pixels[i + 1]
            canvas.draw_line(x0, y0, x1, y1)
            # Style each cell touched by the segment endpoints
            canvas.set_cell_style(x0 // 2, y0 // 4, style_name)
            canvas.set_cell_style(x1 // 2, y1 // 4, style_name)

    # Water/ocean layers — style only, no dot fill
    _WATER_STYLES = frozenset({"water", "coastline"})

    def _draw_polygon(
        self,
        canvas: BrailleCanvas,
        rings: list,
        tile_x: int,
        tile_y: int,
        tile_z: int,
        center_lat: float,
        center_lon: float,
        zoom: int,
        style_name: str,
    ) -> None:
        if not rings:
            return
        # Exterior ring (first ring)
        exterior = rings[0]
        pixels = [
            self._to_braille(
                c[0], c[1],
                tile_x, tile_y, tile_z,
                center_lat, center_lon, zoom, canvas,
            )
            for c in exterior
        ]
        if len(pixels) < 3:
            return

        if style_name in self._WATER_STYLES:
            # Water: set background style only — no dot fill.
            # This gives a clean colored background without dense braille.
            xs = [p[0] for p in pixels]
            ys = [p[1] for p in pixels]
            canvas.set_region_style(
                min(xs), min(ys), max(xs), max(ys), style_name
            )
        else:
            # Land features: fill with dots + apply style
            canvas.fill_polygon(pixels)
            xs = [p[0] for p in pixels]
            ys = [p[1] for p in pixels]
            canvas.set_region_style(
                min(xs), min(ys), max(xs), max(ys), style_name
            )
