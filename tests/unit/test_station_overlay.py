"""Tests for aprs_tui.map.station_overlay — station rendering on BrailleCanvas."""
from __future__ import annotations

from unittest.mock import patch

from aprs_tui.core.station_tracker import StationRecord
from aprs_tui.map.braille_canvas import BrailleCanvas
from aprs_tui.map.station_overlay import (
    CLUSTER_THRESHOLD,
    DEFAULT_SYMBOL,
    SYMBOL_MAP,
    StationOverlay,
    _OccupancyGrid,
    _label_candidates,
    _symbol_char,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Use a fixed center and zoom so pixel math is predictable.
CENTER_LAT = 45.0
CENTER_LON = -122.0
ZOOM = 10
CANVAS_CHARS_W = 40  # 80 dots wide
CANVAS_CHARS_H = 15  # 60 dots tall


def _make_canvas() -> BrailleCanvas:
    return BrailleCanvas(CANVAS_CHARS_W, CANVAS_CHARS_H)


def _make_station(
    callsign: str = "N0CALL",
    lat: float | None = CENTER_LAT,
    lon: float | None = CENTER_LON,
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


def _overlay(canvas: BrailleCanvas) -> StationOverlay:
    return StationOverlay(canvas, ZOOM, CENTER_LAT, CENTER_LON)


def _text_chars(canvas: BrailleCanvas) -> dict[tuple[int, int], str]:
    """Return the text overlay dict from the canvas."""
    return canvas._text_overlay


# ---------------------------------------------------------------------------
# Symbol mapping
# ---------------------------------------------------------------------------


class TestSymbolMapping:
    def test_known_symbols(self):
        """Each entry in SYMBOL_MAP should produce the expected character."""
        for key, expected in SYMBOL_MAP.items():
            table = key[0]
            code = key[1]
            stn = _make_station(symbol_table=table, symbol_code=code)
            assert _symbol_char(stn) == expected, f"Failed for key {key!r}"

    def test_unknown_symbol_falls_back_to_default(self):
        stn = _make_station(symbol_table="/", symbol_code="Z")
        assert _symbol_char(stn) == DEFAULT_SYMBOL

    def test_none_symbol_falls_back_to_default(self):
        stn = _make_station(symbol_table=None, symbol_code=None)
        assert _symbol_char(stn) == DEFAULT_SYMBOL

    def test_car_symbol(self):
        stn = _make_station(symbol_table="/", symbol_code=">")
        assert _symbol_char(stn) == ">"

    def test_emergency_symbol(self):
        stn = _make_station(symbol_table="\\", symbol_code="n")
        assert _symbol_char(stn) == "!"


# ---------------------------------------------------------------------------
# Station rendering — position on canvas
# ---------------------------------------------------------------------------


class TestStationAtCenter:
    def test_station_at_center_appears_on_canvas(self):
        """A station at the map center should produce text overlay entries."""
        canvas = _make_canvas()
        overlay = _overlay(canvas)
        stn = _make_station(callsign="W7TEST", lat=CENTER_LAT, lon=CENTER_LON)
        overlay.render_stations([stn], own_callsign="ME")
        text = _text_chars(canvas)
        assert len(text) > 0, "Expected at least one text overlay entry"

    def test_station_symbol_char_matches(self):
        """The first character placed should be the APRS symbol."""
        canvas = _make_canvas()
        overlay = _overlay(canvas)
        stn = _make_station(
            callsign="W7TEST",
            lat=CENTER_LAT,
            lon=CENTER_LON,
            symbol_table="/",
            symbol_code=">",
        )
        overlay.render_stations([stn], own_callsign="ME")
        text = _text_chars(canvas)
        chars = list(text.values())
        # The symbol ">" must appear somewhere in the overlay.
        assert ">" in chars

    def test_callsign_label_drawn(self):
        """The callsign should appear in the text overlay."""
        canvas = _make_canvas()
        overlay = _overlay(canvas)
        stn = _make_station(callsign="W7TEST", lat=CENTER_LAT, lon=CENTER_LON)
        overlay.render_stations([stn], own_callsign="ME")
        text = _text_chars(canvas)
        # Reconstruct label characters that were placed.
        placed = "".join(text.values())
        assert "W7TEST" in placed


class TestOwnStation:
    def test_own_station_plotted(self):
        """Own station should always be plotted when it has a position."""
        canvas = _make_canvas()
        overlay = _overlay(canvas)
        stn = _make_station(callsign="MYOWN", lat=CENTER_LAT, lon=CENTER_LON)
        overlay.render_stations([stn], own_callsign="MYOWN")
        text = _text_chars(canvas)
        assert len(text) > 0


# ---------------------------------------------------------------------------
# Out-of-bounds stations
# ---------------------------------------------------------------------------


class TestOutOfBounds:
    def test_station_far_away_is_skipped(self):
        """A station far from the viewport center should produce no overlay."""
        canvas = _make_canvas()
        overlay = _overlay(canvas)
        stn = _make_station(callsign="FAR", lat=-30.0, lon=50.0)
        overlay.render_stations([stn], own_callsign="ME")
        text = _text_chars(canvas)
        assert len(text) == 0

    def test_station_without_position_is_skipped(self):
        """A station with lat/lon = None should be silently ignored."""
        canvas = _make_canvas()
        overlay = _overlay(canvas)
        stn = _make_station(callsign="NOPOS", lat=None, lon=None)
        overlay.render_stations([stn], own_callsign="ME")
        text = _text_chars(canvas)
        assert len(text) == 0


# ---------------------------------------------------------------------------
# Multiple stations
# ---------------------------------------------------------------------------


class TestMultipleStations:
    def test_two_stations_at_different_positions(self):
        """Two stations at distinct positions should both appear."""
        canvas = _make_canvas()
        overlay = _overlay(canvas)
        stn1 = _make_station(callsign="AA", lat=CENTER_LAT, lon=CENTER_LON)
        # Shift slightly — at zoom 10, 0.01 degrees is visible.
        stn2 = _make_station(callsign="BB", lat=CENTER_LAT + 0.005, lon=CENTER_LON)
        overlay.render_stations([stn1, stn2], own_callsign="ME")
        text = _text_chars(canvas)
        placed = "".join(text.values())
        # Both callsigns (or at least their symbol chars) should appear.
        # They may overlap so we just check total entries > 1 char cell.
        assert len(text) > 2

    def test_mixed_in_and_out_of_bounds(self):
        """Only in-bounds stations should appear."""
        canvas = _make_canvas()
        overlay = _overlay(canvas)
        stn_in = _make_station(callsign="IN", lat=CENTER_LAT, lon=CENTER_LON)
        stn_out = _make_station(callsign="OUT", lat=-60.0, lon=170.0)
        overlay.render_stations([stn_in, stn_out], own_callsign="ME")
        text = _text_chars(canvas)
        placed = "".join(text.values())
        assert "OUT" not in placed
        assert len(text) > 0  # "IN" station should be there


# ---------------------------------------------------------------------------
# Emergency symbol
# ---------------------------------------------------------------------------


class TestEmergencySymbol:
    def test_emergency_produces_exclamation(self):
        canvas = _make_canvas()
        overlay = _overlay(canvas)
        stn = _make_station(
            callsign="EMERG",
            lat=CENTER_LAT,
            lon=CENTER_LON,
            symbol_table="\\",
            symbol_code="n",
        )
        overlay.render_stations([stn], own_callsign="ME")
        text = _text_chars(canvas)
        chars = list(text.values())
        assert "!" in chars


# ---------------------------------------------------------------------------
# Label collision avoidance
# ---------------------------------------------------------------------------


def _make_overlay_with_pixel_control(
    canvas: BrailleCanvas,
    stations_with_pixels: list[tuple[StationRecord, int, int]],
    own_callsign: str,
    selected_callsign: str | None = None,
) -> None:
    """Render stations with mocked latlon_to_braille_pixel for pixel control.

    Each entry is (station, dot_x, dot_y).  The mock returns positions in the
    order the stations appear (after the None-lat filter).
    """
    pixel_iter = iter(stations_with_pixels)
    station_list = [s for s, _, _ in stations_with_pixels]

    def _fake_latlon(*_args, **_kwargs):
        _, dx, dy = next(pixel_iter)
        return dx, dy

    overlay = StationOverlay(canvas, ZOOM, CENTER_LAT, CENTER_LON)
    with patch(
        "aprs_tui.map.station_overlay.latlon_to_braille_pixel",
        side_effect=_fake_latlon,
    ):
        overlay.render_stations(
            station_list,
            own_callsign=own_callsign,
            selected_callsign=selected_callsign,
        )


class TestLabelCollisionAvoidance:
    """Tests for the label placement system with occupancy grid."""

    def test_label_placed_right_of_marker(self):
        """Default placement should put the label to the right of the marker."""
        canvas = BrailleCanvas(30, 10)
        # Place station at char cell (10, 5) → dot (20, 20)
        stn = _make_station(callsign="AB", lat=CENTER_LAT, lon=CENTER_LON)
        _make_overlay_with_pixel_control(
            canvas,
            [(stn, 20, 20)],
            own_callsign="ME",
        )
        text = _text_chars(canvas)
        # Marker at char (10, 5).
        assert text.get((10, 5)) is not None, "Marker should be at (10, 5)"
        # Label "AB" should be at char (11, 5) and (12, 5) — right of marker.
        assert text.get((11, 5)) == "A"
        assert text.get((12, 5)) == "B"

    def test_label_collision_tries_alternate_position(self):
        """When right side is blocked, label should try above/left/below."""
        canvas = BrailleCanvas(30, 10)
        # Station A at char cell (10, 5) → dot (20, 20).
        # Its label "AA" goes to (11,5) and (12,5).
        stn_a = _make_station(
            callsign="AA", lat=CENTER_LAT, lon=CENTER_LON, last_heard=100.0
        )
        # Station B at char cell (11, 5) → dot (22, 20).
        # Its right-side label "BB" would want (12,5) and (13,5) but (12,5)
        # is already taken by A's label.  So it should try above → (11, 4).
        stn_b = _make_station(
            callsign="BB", lat=CENTER_LAT, lon=CENTER_LON, last_heard=50.0
        )
        _make_overlay_with_pixel_control(
            canvas,
            [(stn_a, 20, 20), (stn_b, 22, 20)],
            own_callsign="ME",
        )
        text = _text_chars(canvas)
        # Station A label originally at (11, 5) and (12, 5).
        # Station B marker overwrites (11, 5) with its symbol char, but (12, 5)
        # still has A's label character.
        assert text.get((12, 5)) == "A"
        # Station B label should NOT be at right (12,5)+(13,5) since (12,5)
        # is occupied in the occupancy grid. It tries above: (11, 4).
        assert text.get((11, 4)) == "B"
        assert text.get((12, 4)) == "B"

    def test_own_station_label_always_shown(self):
        """Own station gets highest priority for label placement."""
        canvas = BrailleCanvas(30, 10)
        # Own station and another station at adjacent cells.
        # Own station should place its label first even if passed second in list.
        stn_other = _make_station(
            callsign="OT", lat=CENTER_LAT, lon=CENTER_LON, last_heard=100.0
        )
        stn_own = _make_station(
            callsign="ME", lat=CENTER_LAT, lon=CENTER_LON, last_heard=1.0
        )
        # Place them at same row but different cols so they don't cluster.
        _make_overlay_with_pixel_control(
            canvas,
            [(stn_other, 20, 20), (stn_own, 24, 20)],
            own_callsign="ME",
        )
        text = _text_chars(canvas)
        placed = "".join(text.values())
        # Own station label should always appear.
        assert "ME" in placed

    def test_selected_station_label_always_shown(self):
        """Selected station gets second-highest priority for label placement."""
        canvas = BrailleCanvas(30, 10)
        stn_other = _make_station(
            callsign="OT", lat=CENTER_LAT, lon=CENTER_LON, last_heard=100.0
        )
        stn_sel = _make_station(
            callsign="SEL", lat=CENTER_LAT, lon=CENTER_LON, last_heard=1.0
        )
        # Two stations at different cells.
        _make_overlay_with_pixel_control(
            canvas,
            [(stn_other, 20, 20), (stn_sel, 26, 20)],
            own_callsign="ME",
            selected_callsign="SEL",
        )
        text = _text_chars(canvas)
        placed = "".join(text.values())
        # Selected station label should appear.
        assert "SEL" in placed

    def test_label_skipped_when_all_positions_blocked(self):
        """If all 4 label positions are blocked, marker still drawn but no label."""
        # Use a very small canvas so labels can't fit anywhere.
        canvas = BrailleCanvas(3, 3)
        # Place station near edge so no label position works.
        # Char cell (0, 0) → dot (0, 0).
        # Right (1, 0) — only 2 cells right, label "ABCDEF" needs 6 cells.
        # Above (0, -1) — out of bounds.
        # Left (0-6, 0) — out of bounds.
        # Below (0, 1) — 2 cells across but label needs 6.
        stn = _make_station(
            callsign="ABCDEF", lat=CENTER_LAT, lon=CENTER_LON
        )
        _make_overlay_with_pixel_control(
            canvas,
            [(stn, 0, 0)],
            own_callsign="ME",
        )
        text = _text_chars(canvas)
        # Marker should still be drawn.
        assert len(text) >= 1
        placed = "".join(text.values())
        # But the full callsign label should NOT appear.
        assert "ABCDEF" not in placed


# ---------------------------------------------------------------------------
# Clustering
# ---------------------------------------------------------------------------


class TestClustering:
    def test_cluster_indicator_for_overlapping_stations(self):
        """3+ stations at the same char cell should produce a cluster count."""
        canvas = BrailleCanvas(30, 10)
        # Place 3 stations all at the same char cell (10, 5) → dots within
        # the same 2x4 cell.
        stations_with_pixels = [
            (
                _make_station(
                    callsign=f"S{i}", lat=CENTER_LAT, lon=CENTER_LON
                ),
                20,
                20,
            )
            for i in range(3)
        ]
        _make_overlay_with_pixel_control(
            canvas,
            stations_with_pixels,
            own_callsign="ME",
        )
        text = _text_chars(canvas)
        placed = "".join(text.values())
        # Should show "(3)" cluster indicator.
        assert "(3)" in placed

    def test_no_cluster_for_two_stations_same_cell(self):
        """Two stations at the same cell should render individually, not cluster."""
        canvas = BrailleCanvas(30, 10)
        stn1 = _make_station(
            callsign="A1", lat=CENTER_LAT, lon=CENTER_LON, last_heard=100.0
        )
        stn2 = _make_station(
            callsign="A2", lat=CENTER_LAT, lon=CENTER_LON, last_heard=50.0
        )
        _make_overlay_with_pixel_control(
            canvas,
            [(stn1, 20, 20), (stn2, 20, 20)],
            own_callsign="ME",
        )
        text = _text_chars(canvas)
        placed = "".join(text.values())
        # Should NOT show cluster indicator.
        assert "(2)" not in placed
        # Both station markers should be drawn (at same cell, second overwrites first
        # but both render individually — at least their labels should appear).
        # At minimum, the marker character should appear.
        assert len(text) > 0

    def test_cluster_count_reflects_station_count(self):
        """Cluster indicator should show the correct count."""
        canvas = BrailleCanvas(30, 10)
        stations_with_pixels = [
            (
                _make_station(
                    callsign=f"S{i}", lat=CENTER_LAT, lon=CENTER_LON
                ),
                20,
                20,
            )
            for i in range(5)
        ]
        _make_overlay_with_pixel_control(
            canvas,
            stations_with_pixels,
            own_callsign="ME",
        )
        text = _text_chars(canvas)
        placed = "".join(text.values())
        assert "(5)" in placed

    def test_cluster_threshold_is_three(self):
        """Verify the cluster threshold constant is 3."""
        assert CLUSTER_THRESHOLD == 3


# ---------------------------------------------------------------------------
# OccupancyGrid unit tests
# ---------------------------------------------------------------------------


class TestOccupancyGrid:
    def test_empty_grid_is_unoccupied(self):
        grid = _OccupancyGrid(10, 10)
        assert not grid.is_occupied(0, 0)
        assert not grid.is_occupied(5, 5)

    def test_mark_and_check(self):
        grid = _OccupancyGrid(10, 10)
        grid.mark(3, 4)
        assert grid.is_occupied(3, 4)
        assert not grid.is_occupied(3, 5)

    def test_out_of_bounds_is_occupied(self):
        grid = _OccupancyGrid(10, 10)
        assert grid.is_occupied(-1, 0)
        assert grid.is_occupied(0, -1)
        assert grid.is_occupied(10, 0)
        assert grid.is_occupied(0, 10)

    def test_can_place_label_free(self):
        grid = _OccupancyGrid(20, 10)
        assert grid.can_place_label(5, 3, 4)

    def test_can_place_label_blocked(self):
        grid = _OccupancyGrid(20, 10)
        grid.mark(7, 3)
        assert not grid.can_place_label(5, 3, 4)

    def test_mark_label(self):
        grid = _OccupancyGrid(20, 10)
        grid.mark_label(5, 3, 3)
        assert grid.is_occupied(5, 3)
        assert grid.is_occupied(6, 3)
        assert grid.is_occupied(7, 3)
        assert not grid.is_occupied(8, 3)


# ---------------------------------------------------------------------------
# Label candidate positions
# ---------------------------------------------------------------------------


class TestLabelCandidates:
    def test_candidate_order(self):
        """Candidates should be: right, above, left, below."""
        candidates = _label_candidates(10, 5, 4)
        assert candidates == [
            (11, 5),  # right
            (10, 4),  # above
            (6, 5),   # left (10 - 4 = 6)
            (10, 6),  # below
        ]
