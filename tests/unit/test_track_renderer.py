"""Tests for aprs_tui.map.track_renderer — track/trail rendering for mobile stations."""
from __future__ import annotations

import time
from unittest.mock import patch

from aprs_tui.core.station_tracker import StationRecord
from aprs_tui.map.braille_canvas import BrailleCanvas
from aprs_tui.map.track_renderer import TrackRenderer

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

CENTER_LAT = 45.0
CENTER_LON = -122.0
ZOOM = 10
CANVAS_CHARS_W = 40  # 80 dots wide
CANVAS_CHARS_H = 15  # 60 dots tall


def _make_canvas() -> BrailleCanvas:
    return BrailleCanvas(CANVAS_CHARS_W, CANVAS_CHARS_H)


def _make_station(
    callsign: str = "N0CALL",
    position_history: list[tuple[float, float, float]] | None = None,
) -> StationRecord:
    return StationRecord(
        callsign=callsign,
        latitude=CENTER_LAT,
        longitude=CENTER_LON,
        sources={"RF"},
        position_history=position_history if position_history is not None else [],
    )


def _canvas_has_any_dot(canvas: BrailleCanvas) -> bool:
    """Return True if any braille dot is set on the canvas."""
    return any(b != 0 for b in canvas._cells)


def _count_set_dots(canvas: BrailleCanvas) -> int:
    """Count the total number of set braille dots on the canvas."""
    count = 0
    for b in canvas._cells:
        count += bin(b).count("1")
    return count


# ---------------------------------------------------------------------------
# No tracks for single position
# ---------------------------------------------------------------------------


class TestNoTracksForSinglePosition:
    def test_no_tracks_for_single_position(self):
        """A station with only 1 position report should not produce any track."""
        now = time.time()
        canvas = _make_canvas()
        renderer = TrackRenderer()
        stn = _make_station(
            position_history=[(CENTER_LAT, CENTER_LON, now)],
        )
        renderer.render_tracks(
            canvas, [stn], ZOOM, CENTER_LAT, CENTER_LON,
        )
        assert not _canvas_has_any_dot(canvas)

    def test_no_tracks_for_zero_positions(self):
        """A station with no position history should not produce any track."""
        canvas = _make_canvas()
        renderer = TrackRenderer()
        stn = _make_station(position_history=[])
        renderer.render_tracks(
            canvas, [stn], ZOOM, CENTER_LAT, CENTER_LON,
        )
        assert not _canvas_has_any_dot(canvas)


# ---------------------------------------------------------------------------
# Track drawn for two positions
# ---------------------------------------------------------------------------


class TestTrackDrawnForTwoPositions:
    def test_track_drawn_for_two_positions(self):
        """A station with 2 position reports should draw a line between them."""
        now = time.time()
        canvas = _make_canvas()
        renderer = TrackRenderer()
        # Two positions slightly offset so the line is visible
        stn = _make_station(
            position_history=[
                (CENTER_LAT, CENTER_LON, now - 60),
                (CENTER_LAT + 0.01, CENTER_LON + 0.01, now),
            ],
        )
        renderer.render_tracks(
            canvas, [stn], ZOOM, CENTER_LAT, CENTER_LON,
        )
        assert _canvas_has_any_dot(canvas)


# ---------------------------------------------------------------------------
# Track drawn for multiple positions
# ---------------------------------------------------------------------------


class TestTrackDrawnForMultiplePositions:
    def test_track_drawn_for_multiple_positions(self):
        """3+ points should produce connected line segments."""
        now = time.time()
        canvas = _make_canvas()
        renderer = TrackRenderer()
        stn = _make_station(
            position_history=[
                (CENTER_LAT, CENTER_LON, now - 120),
                (CENTER_LAT + 0.005, CENTER_LON + 0.005, now - 60),
                (CENTER_LAT + 0.01, CENTER_LON + 0.01, now),
            ],
        )
        renderer.render_tracks(
            canvas, [stn], ZOOM, CENTER_LAT, CENTER_LON,
        )
        assert _canvas_has_any_dot(canvas)
        # Should have more dots than a two-point line (the path is longer)
        dots = _count_set_dots(canvas)
        assert dots > 2

    def test_multiple_segments_drawn(self):
        """Verify that intermediate points produce additional dots vs. a direct line."""
        now = time.time()

        # Direct line: point A -> point C
        canvas_direct = _make_canvas()
        renderer = TrackRenderer()
        stn_direct = _make_station(
            position_history=[
                (CENTER_LAT, CENTER_LON, now - 60),
                (CENTER_LAT + 0.01, CENTER_LON + 0.01, now),
            ],
        )
        renderer.render_tracks(
            canvas_direct, [stn_direct], ZOOM, CENTER_LAT, CENTER_LON,
        )
        dots_direct = _count_set_dots(canvas_direct)

        # Detoured line: point A -> point B (offset) -> point C
        canvas_detour = _make_canvas()
        stn_detour = _make_station(
            position_history=[
                (CENTER_LAT, CENTER_LON, now - 120),
                (CENTER_LAT + 0.005, CENTER_LON - 0.01, now - 60),  # detour
                (CENTER_LAT + 0.01, CENTER_LON + 0.01, now),
            ],
        )
        renderer.render_tracks(
            canvas_detour, [stn_detour], ZOOM, CENTER_LAT, CENTER_LON,
        )
        dots_detour = _count_set_dots(canvas_detour)

        # Detour should produce more dots because the path is longer
        assert dots_detour > dots_direct


# ---------------------------------------------------------------------------
# Old positions filtered by age
# ---------------------------------------------------------------------------


class TestOldPositionsFilteredByAge:
    def test_old_positions_filtered_by_age(self):
        """Points older than max_age should be excluded."""
        now = time.time()
        canvas = _make_canvas()
        renderer = TrackRenderer(max_age=600)  # 10 minutes
        # All points are older than 600 seconds except none are recent enough
        stn = _make_station(
            position_history=[
                (CENTER_LAT, CENTER_LON, now - 1000),
                (CENTER_LAT + 0.01, CENTER_LON + 0.01, now - 900),
            ],
        )
        renderer.render_tracks(
            canvas, [stn], ZOOM, CENTER_LAT, CENTER_LON,
        )
        # Both points are too old, so nothing should be drawn
        assert not _canvas_has_any_dot(canvas)

    def test_mixed_age_keeps_recent_points(self):
        """Only recent points should be kept; old ones discarded."""
        now = time.time()
        canvas = _make_canvas()
        renderer = TrackRenderer(max_age=600)
        stn = _make_station(
            position_history=[
                (CENTER_LAT, CENTER_LON, now - 1000),       # too old
                (CENTER_LAT + 0.005, CENTER_LON, now - 300), # recent
                (CENTER_LAT + 0.01, CENTER_LON, now - 100),  # recent
            ],
        )
        renderer.render_tracks(
            canvas, [stn], ZOOM, CENTER_LAT, CENTER_LON,
        )
        # Two recent points remain → line should be drawn
        assert _canvas_has_any_dot(canvas)

    def test_one_recent_point_after_filter_no_line(self):
        """If only one point survives the age filter, no line should be drawn."""
        now = time.time()
        canvas = _make_canvas()
        renderer = TrackRenderer(max_age=600)
        stn = _make_station(
            position_history=[
                (CENTER_LAT, CENTER_LON, now - 1000),       # too old
                (CENTER_LAT + 0.01, CENTER_LON, now - 100),  # recent
            ],
        )
        renderer.render_tracks(
            canvas, [stn], ZOOM, CENTER_LAT, CENTER_LON,
        )
        assert not _canvas_has_any_dot(canvas)


# ---------------------------------------------------------------------------
# Max points respected
# ---------------------------------------------------------------------------


class TestMaxPointsRespected:
    def test_max_points_respected(self):
        """Position history should be capped to max_points (keeping the latest)."""
        now = time.time()
        canvas_capped = _make_canvas()
        renderer = TrackRenderer(max_points=5, max_age=3600)

        # Create 20 points spread across the map
        history = [
            (CENTER_LAT + i * 0.002, CENTER_LON + i * 0.002, now - (20 - i) * 30)
            for i in range(20)
        ]
        stn = _make_station(position_history=history)
        renderer.render_tracks(
            canvas_capped, [stn], ZOOM, CENTER_LAT, CENTER_LON,
        )
        dots_capped = _count_set_dots(canvas_capped)

        # Now render with unlimited points
        canvas_full = _make_canvas()
        renderer_full = TrackRenderer(max_points=100, max_age=3600)
        stn_full = _make_station(position_history=list(history))
        renderer_full.render_tracks(
            canvas_full, [stn_full], ZOOM, CENTER_LAT, CENTER_LON,
        )
        dots_full = _count_set_dots(canvas_full)

        # Capped version should have fewer or equal dots (shorter trail)
        assert dots_capped <= dots_full
        # Both should have some dots
        assert dots_capped > 0
        assert dots_full > 0


# ---------------------------------------------------------------------------
# Simplification at low zoom
# ---------------------------------------------------------------------------


class TestSimplificationAtLowZoom:
    def test_simplification_at_low_zoom(self):
        """At zoom < 8 with many points, the renderer should simplify the track."""
        now = time.time()
        low_zoom = 5

        # Create 20 points
        history = [
            (CENTER_LAT + i * 0.1, CENTER_LON + i * 0.1, now - (20 - i) * 30)
            for i in range(20)
        ]

        # Track calls to draw_line to count segments
        canvas = _make_canvas()
        renderer = TrackRenderer(max_points=100, max_age=3600)

        draw_line_calls_low: list[tuple[int, int, int, int]] = []
        original_draw_line = canvas.draw_line

        def counting_draw_line(x0, y0, x1, y1):
            draw_line_calls_low.append((x0, y0, x1, y1))
            original_draw_line(x0, y0, x1, y1)

        canvas.draw_line = counting_draw_line  # type: ignore[assignment]

        stn = _make_station(position_history=list(history))
        renderer.render_tracks(
            canvas, [stn], low_zoom, CENTER_LAT, CENTER_LON,
        )
        segments_low = len(draw_line_calls_low)

        # At high zoom (>= 8) all points should be used
        canvas_high = _make_canvas()
        high_zoom = 10
        draw_line_calls_high: list[tuple[int, int, int, int]] = []
        original_draw_line_high = canvas_high.draw_line

        def counting_draw_line_high(x0, y0, x1, y1):
            draw_line_calls_high.append((x0, y0, x1, y1))
            original_draw_line_high(x0, y0, x1, y1)

        canvas_high.draw_line = counting_draw_line_high  # type: ignore[assignment]

        stn_high = _make_station(position_history=list(history))
        renderer.render_tracks(
            canvas_high, [stn_high], high_zoom, CENTER_LAT, CENTER_LON,
        )
        segments_high = len(draw_line_calls_high)

        # Low zoom should draw fewer segments than high zoom
        assert segments_low < segments_high
        # High zoom should use all 19 segments (20 points - 1)
        assert segments_high == 19

    def test_no_simplification_at_high_zoom(self):
        """At zoom >= 8, all points should be used without simplification."""
        now = time.time()
        canvas = _make_canvas()
        renderer = TrackRenderer(max_points=100, max_age=3600)

        history = [
            (CENTER_LAT + i * 0.001, CENTER_LON + i * 0.001, now - (15 - i) * 30)
            for i in range(15)
        ]

        draw_line_calls: list[tuple[int, int, int, int]] = []
        original_draw_line = canvas.draw_line

        def counting_draw_line(x0, y0, x1, y1):
            draw_line_calls.append((x0, y0, x1, y1))
            original_draw_line(x0, y0, x1, y1)

        canvas.draw_line = counting_draw_line  # type: ignore[assignment]

        stn = _make_station(position_history=list(history))
        renderer.render_tracks(
            canvas, [stn], 10, CENTER_LAT, CENTER_LON,
        )
        # 15 points → 14 segments, no simplification at zoom 10
        assert len(draw_line_calls) == 14

    def test_no_simplification_with_few_points_at_low_zoom(self):
        """At low zoom with <= 10 points, no simplification should occur."""
        now = time.time()
        canvas = _make_canvas()
        renderer = TrackRenderer(max_points=100, max_age=3600)

        history = [
            (CENTER_LAT + i * 0.1, CENTER_LON + i * 0.1, now - (5 - i) * 30)
            for i in range(5)
        ]

        draw_line_calls: list[tuple[int, int, int, int]] = []
        original_draw_line = canvas.draw_line

        def counting_draw_line(x0, y0, x1, y1):
            draw_line_calls.append((x0, y0, x1, y1))
            original_draw_line(x0, y0, x1, y1)

        canvas.draw_line = counting_draw_line  # type: ignore[assignment]

        stn = _make_station(position_history=list(history))
        renderer.render_tracks(
            canvas, [stn], 5, CENTER_LAT, CENTER_LON,
        )
        # 5 points, <= 10 so no simplification → 4 segments
        assert len(draw_line_calls) == 4


# ---------------------------------------------------------------------------
# Selected station track rendered
# ---------------------------------------------------------------------------


class TestSelectedStationTrackRendered:
    def test_selected_station_track_rendered(self):
        """A selected station with position history should have its track drawn."""
        now = time.time()
        canvas = _make_canvas()
        renderer = TrackRenderer()
        stn = _make_station(
            callsign="SELCALL",
            position_history=[
                (CENTER_LAT, CENTER_LON, now - 60),
                (CENTER_LAT + 0.01, CENTER_LON + 0.01, now),
            ],
        )
        renderer.render_tracks(
            canvas, [stn], ZOOM, CENTER_LAT, CENTER_LON,
            selected_callsign="SELCALL",
        )
        assert _canvas_has_any_dot(canvas)

    def test_non_selected_station_also_rendered(self):
        """Non-selected stations with enough history should also be rendered."""
        now = time.time()
        canvas = _make_canvas()
        renderer = TrackRenderer()
        stn = _make_station(
            callsign="OTHER",
            position_history=[
                (CENTER_LAT, CENTER_LON, now - 60),
                (CENTER_LAT + 0.01, CENTER_LON + 0.01, now),
            ],
        )
        renderer.render_tracks(
            canvas, [stn], ZOOM, CENTER_LAT, CENTER_LON,
            selected_callsign="SELCALL",
        )
        assert _canvas_has_any_dot(canvas)

    def test_multiple_stations_all_rendered(self):
        """Multiple qualifying stations should all have their tracks drawn."""
        now = time.time()
        canvas = _make_canvas()
        renderer = TrackRenderer()
        stn1 = _make_station(
            callsign="STN1",
            position_history=[
                (CENTER_LAT, CENTER_LON, now - 60),
                (CENTER_LAT + 0.01, CENTER_LON, now),
            ],
        )
        stn2 = _make_station(
            callsign="STN2",
            position_history=[
                (CENTER_LAT, CENTER_LON, now - 60),
                (CENTER_LAT, CENTER_LON + 0.01, now),
            ],
        )
        renderer.render_tracks(
            canvas, [stn1, stn2], ZOOM, CENTER_LAT, CENTER_LON,
        )
        dots = _count_set_dots(canvas)
        # Both stations contribute dots
        assert dots > 2
