"""Tests for aprs_tui.map.auto_zoom — auto-zoom algorithm."""
from __future__ import annotations

import time

from aprs_tui.core.station_tracker import StationRecord
from aprs_tui.map.auto_zoom import AutoZoomController, calculate_auto_zoom

OWN_LAT = 40.0
OWN_LON = -105.0
WIDTH = 200
HEIGHT = 100


def _make_station(
    callsign: str,
    lat: float | None = None,
    lon: float | None = None,
    *,
    wall_ts: float | None = None,
    last_heard_mono: float | None = None,
    use_position_history: bool = True,
) -> StationRecord:
    """Helper to build a StationRecord for testing."""
    stn = StationRecord(callsign=callsign)
    stn.latitude = lat
    stn.longitude = lon
    if lat is not None and lon is not None and use_position_history:
        ts = wall_ts if wall_ts is not None else time.time()
        stn.position_history = [(lat, lon, ts)]
    if last_heard_mono is not None:
        stn.last_heard = last_heard_mono
    else:
        stn.last_heard = time.monotonic()
    return stn


class TestNoStations:
    """No stations → centers on own position at default zoom."""

    def test_empty_list(self) -> None:
        lat, lon, zoom = calculate_auto_zoom(
            [], OWN_LAT, OWN_LON, WIDTH, HEIGHT, default_zoom=10.0,
        )
        assert lat == OWN_LAT
        assert lon == OWN_LON
        assert zoom == 10.0


class TestSingleStation:
    """Single station → bounding box of own + station, appropriate zoom."""

    def test_single_station_returns_fitted_zoom(self) -> None:
        stn = _make_station("W1AW", 41.0, -104.0)
        lat, lon, zoom = calculate_auto_zoom(
            [stn], OWN_LAT, OWN_LON, WIDTH, HEIGHT,
        )
        # Center should be between own and station
        assert min(OWN_LAT, 41.0) <= lat <= max(OWN_LAT, 41.0)
        assert min(OWN_LON, -104.0) <= lon <= max(OWN_LON, -104.0)
        # Zoom should be within bounds
        assert 4.0 <= zoom <= 14.0


class TestMultipleStations:
    """Multiple stations → bounding box encompasses all."""

    def test_bbox_covers_all(self) -> None:
        stations = [
            _make_station("W1AW", 42.0, -103.0),
            _make_station("W2AB", 38.0, -107.0),
            _make_station("W3CD", 41.0, -106.0),
        ]
        lat, lon, zoom = calculate_auto_zoom(
            stations, OWN_LAT, OWN_LON, WIDTH, HEIGHT,
        )
        # Center should be roughly in the middle of the bounding box
        # Bounding box: lat 38..42, lon -107..-103 (including own 40, -105)
        # Padded: lat 37.6..42.4, lon -107.4..-102.6
        assert 37.0 < lat < 43.0
        assert -108.0 < lon < -102.0
        assert 4.0 <= zoom <= 14.0


class TestSamePositionAsOwn:
    """Stations at same position as own → uses default zoom (zero-area bbox)."""

    def test_zero_area_bbox(self) -> None:
        stn = _make_station("W1AW", OWN_LAT, OWN_LON)
        lat, lon, zoom = calculate_auto_zoom(
            [stn], OWN_LAT, OWN_LON, WIDTH, HEIGHT, default_zoom=10.0,
        )
        assert lat == OWN_LAT
        assert lon == OWN_LON
        assert zoom == 10.0


class TestZoomClamping:
    """Zoom is clamped to min/max range."""

    def test_clamped_to_min(self) -> None:
        # Stations very far apart — zoom would be very low
        stations = [
            _make_station("W1AW", 70.0, 170.0),
            _make_station("W2AB", -70.0, -170.0),
        ]
        _, _, zoom = calculate_auto_zoom(
            stations, OWN_LAT, OWN_LON, WIDTH, HEIGHT,
            auto_zoom_min=4.0, auto_zoom_max=14.0,
        )
        assert zoom >= 4.0

    def test_clamped_to_max(self) -> None:
        # Stations very close — zoom would be very high
        stations = [
            _make_station("W1AW", OWN_LAT + 0.0001, OWN_LON + 0.0001),
        ]
        _, _, zoom = calculate_auto_zoom(
            stations, OWN_LAT, OWN_LON, WIDTH, HEIGHT,
            auto_zoom_min=4.0, auto_zoom_max=14.0,
        )
        assert zoom <= 14.0

    def test_custom_min_max(self) -> None:
        # Very far stations with high min
        stations = [
            _make_station("W1AW", 70.0, 170.0),
        ]
        _, _, zoom = calculate_auto_zoom(
            stations, OWN_LAT, OWN_LON, WIDTH, HEIGHT,
            auto_zoom_min=6.0, auto_zoom_max=12.0,
        )
        assert 6.0 <= zoom <= 12.0


class TestTimedOutStations:
    """Timed-out stations are excluded."""

    def test_all_timed_out_returns_default(self) -> None:
        old_ts = time.time() - 3600  # 1 hour ago (> 1800s timeout)
        stn = _make_station("W1AW", 42.0, -103.0, wall_ts=old_ts)
        lat, lon, zoom = calculate_auto_zoom(
            [stn], OWN_LAT, OWN_LON, WIDTH, HEIGHT,
            default_zoom=10.0, auto_zoom_timeout=1800.0,
        )
        assert lat == OWN_LAT
        assert lon == OWN_LON
        assert zoom == 10.0

    def test_mix_of_timed_out_and_active(self) -> None:
        old_stn = _make_station("W1AW", 60.0, -80.0, wall_ts=time.time() - 3600)
        fresh_stn = _make_station("W2AB", 41.0, -104.0)
        lat, lon, zoom = calculate_auto_zoom(
            [old_stn, fresh_stn], OWN_LAT, OWN_LON, WIDTH, HEIGHT,
            auto_zoom_timeout=1800.0,
        )
        # The old station at 60/-80 should be excluded, so center should be
        # near own (40/-105) and fresh (41/-104), not pulled toward 60/-80
        assert 39.0 < lat < 42.0
        assert -106.0 < lon < -103.0

    def test_timeout_via_last_heard_monotonic(self) -> None:
        """Station without position_history uses last_heard (monotonic)."""
        stn = _make_station(
            "W1AW", 42.0, -103.0,
            use_position_history=False,
            last_heard_mono=time.monotonic() - 3600,
        )
        lat, lon, zoom = calculate_auto_zoom(
            [stn], OWN_LAT, OWN_LON, WIDTH, HEIGHT,
            default_zoom=10.0, auto_zoom_timeout=1800.0,
        )
        assert lat == OWN_LAT
        assert lon == OWN_LON
        assert zoom == 10.0

    def test_fresh_via_last_heard_monotonic(self) -> None:
        """Station without position_history but recently heard is included."""
        stn = _make_station(
            "W1AW", 42.0, -103.0,
            use_position_history=False,
            last_heard_mono=time.monotonic(),
        )
        lat, lon, zoom = calculate_auto_zoom(
            [stn], OWN_LAT, OWN_LON, WIDTH, HEIGHT,
        )
        # Should NOT fall back to default since station is fresh
        assert lat != OWN_LAT or lon != OWN_LON or zoom != 10.0


class TestStationsWithoutPosition:
    """Stations without position are excluded."""

    def test_no_lat_lon(self) -> None:
        stn = StationRecord(callsign="W1AW")
        stn.last_heard = time.monotonic()
        lat, lon, zoom = calculate_auto_zoom(
            [stn], OWN_LAT, OWN_LON, WIDTH, HEIGHT, default_zoom=10.0,
        )
        assert lat == OWN_LAT
        assert lon == OWN_LON
        assert zoom == 10.0

    def test_partial_position(self) -> None:
        stn = StationRecord(callsign="W1AW", latitude=42.0)
        stn.last_heard = time.monotonic()
        lat, lon, zoom = calculate_auto_zoom(
            [stn], OWN_LAT, OWN_LON, WIDTH, HEIGHT, default_zoom=10.0,
        )
        assert lat == OWN_LAT
        assert lon == OWN_LON
        assert zoom == 10.0


class TestPadding:
    """Padding: bounding box is 10% larger than station positions on each side."""

    def test_padding_expands_bbox(self) -> None:
        """Verify that the bounding box used includes 10% padding."""
        # Use a station that creates a known bounding box
        stn = _make_station("W1AW", 42.0, -103.0)
        lat, lon, zoom = calculate_auto_zoom(
            [stn], OWN_LAT, OWN_LON, WIDTH, HEIGHT,
        )

        # Raw bbox: lat 40..42, lon -105..-103
        # Lat span = 2, padding = 0.2 → padded bbox: 39.8..42.2
        # Lon span = 2, padding = 0.2 → padded bbox: -105.2..-102.8
        # Center of padded bbox: (39.8+42.2)/2 = 41.0, (-105.2+-102.8)/2 = -104.0
        assert abs(lat - 41.0) < 0.01
        assert abs(lon - (-104.0)) < 0.01

    def test_asymmetric_padding(self) -> None:
        """Padding is proportional to span, so asymmetric bbox gets proportional padding."""
        # Station far in latitude, close in longitude
        stn = _make_station("W1AW", 50.0, -104.9)
        lat, lon, zoom = calculate_auto_zoom(
            [stn], OWN_LAT, OWN_LON, WIDTH, HEIGHT,
        )

        # Raw bbox: lat 40..50, lon -105..-104.9
        # Lat span = 10, lat_pad = 1.0 → padded 39..51, center_lat = 45.0
        # Lon span = 0.1, lon_pad = 0.01 → padded -105.01..-104.89, center_lon ≈ -104.95
        assert abs(lat - 45.0) < 0.01
        assert abs(lon - (-104.95)) < 0.01


class TestAutoZoomController:
    """Tests for the stateful AutoZoomController with smoothing and hysteresis."""

    def _make_controller(self, **kwargs) -> AutoZoomController:  # type: ignore[no-untyped-def]
        """Create controller with test defaults."""
        defaults = {
            "own_lat": OWN_LAT,
            "own_lon": OWN_LON,
            "panel_width_dots": WIDTH,
            "panel_height_dots": HEIGHT,
            "default_zoom": 10.0,
            "auto_zoom_min": 4.0,
            "auto_zoom_max": 14.0,
        }
        defaults.update(kwargs)
        return AutoZoomController(**defaults)

    def test_initial_update_returns_raw_values(self) -> None:
        """First update has no previous state, so no smoothing is applied."""
        ctrl = self._make_controller()
        stn = _make_station("W1AW", 42.0, -103.0)

        # Get raw values for comparison
        raw_lat, raw_lon, raw_zoom = calculate_auto_zoom(
            [stn], OWN_LAT, OWN_LON, WIDTH, HEIGHT,
        )

        result = ctrl.update([stn])
        assert result is not None
        lat, lon, zoom = result
        assert lat == raw_lat
        assert lon == raw_lon
        assert zoom == raw_zoom

    def test_center_smoothing_70_30_blend(self) -> None:
        """Second update blends 70% previous center + 30% new center."""
        ctrl = self._make_controller()

        # First update: station at (42, -103) — sets initial state
        stn1 = _make_station("W1AW", 42.0, -103.0)
        result1 = ctrl.update([stn1])
        assert result1 is not None
        prev_lat, prev_lon, _ = result1

        # Second update: station moves to (44, -101) — should be smoothed
        stn2 = _make_station("W1AW", 44.0, -101.0)
        raw_lat, raw_lon, _ = calculate_auto_zoom(
            [stn2], OWN_LAT, OWN_LON, WIDTH, HEIGHT,
        )

        result2 = ctrl.update([stn2])
        assert result2 is not None
        smooth_lat, smooth_lon, _ = result2

        expected_lat = prev_lat * 0.7 + raw_lat * 0.3
        expected_lon = prev_lon * 0.7 + raw_lon * 0.3
        assert abs(smooth_lat - expected_lat) < 1e-9
        assert abs(smooth_lon - expected_lon) < 1e-9

    def test_zoom_dampening_max_half_level(self) -> None:
        """Zoom changes are capped at +/-0.5 per update."""
        ctrl = self._make_controller()

        # First update: station close by — high zoom
        stn_close = _make_station("W1AW", OWN_LAT + 0.001, OWN_LON + 0.001)
        result1 = ctrl.update([stn_close])
        assert result1 is not None
        _, _, zoom1 = result1

        # Second update: station far away — raw zoom would drop significantly
        stn_far = _make_station("W1AW", 60.0, -80.0)
        raw_lat, raw_lon, raw_zoom = calculate_auto_zoom(
            [stn_far], OWN_LAT, OWN_LON, WIDTH, HEIGHT,
        )

        result2 = ctrl.update([stn_far])
        assert result2 is not None
        _, _, zoom2 = result2

        # The zoom change should be capped at -0.5 (since raw would be much lower)
        assert abs(zoom2 - zoom1) <= 0.5 + 1e-9

    def test_toggle_on_off(self) -> None:
        """Toggle switches enabled state and returns new state."""
        ctrl = self._make_controller()
        assert ctrl.enabled is True

        new_state = ctrl.toggle()
        assert new_state is False
        assert ctrl.enabled is False

        new_state = ctrl.toggle()
        assert new_state is True
        assert ctrl.enabled is True

    def test_disabled_returns_none(self) -> None:
        """When disabled, update returns None."""
        ctrl = self._make_controller()
        ctrl.toggle()  # disable
        assert ctrl.enabled is False

        stn = _make_station("W1AW", 42.0, -103.0)
        result = ctrl.update([stn])
        assert result is None

    def test_reset_clears_smoothing_state(self) -> None:
        """Reset clears previous smoothing state so next result is unsmoothed."""
        ctrl = self._make_controller()

        # First update to set state
        stn1 = _make_station("W1AW", 42.0, -103.0)
        ctrl.update([stn1])

        # Second update — would normally be smoothed
        stn2 = _make_station("W1AW", 44.0, -101.0)
        ctrl.update([stn2])

        # Reset and recalculate with stn2 — should match raw values (no smoothing)
        result = ctrl.reset([stn2])
        raw_lat, raw_lon, raw_zoom = calculate_auto_zoom(
            [stn2], OWN_LAT, OWN_LON, WIDTH, HEIGHT,
        )
        assert result[0] == raw_lat
        assert result[1] == raw_lon
        assert result[2] == raw_zoom

    def test_reset_returns_immediately_recalculated(self) -> None:
        """Reset re-enables auto-zoom and returns a non-None result immediately."""
        ctrl = self._make_controller()
        ctrl.toggle()  # disable
        assert ctrl.enabled is False

        stn = _make_station("W1AW", 42.0, -103.0)
        result = ctrl.reset([stn])

        assert ctrl.enabled is True
        assert result is not None
        lat, lon, zoom = result
        assert 4.0 <= zoom <= 14.0

    def test_multiple_updates_converge(self) -> None:
        """Repeated updates with same stations converge toward raw values."""
        ctrl = self._make_controller()

        # First update to set initial state with a different station position
        stn_initial = _make_station("W1AW", 42.0, -103.0)
        ctrl.update([stn_initial])

        # Now repeatedly update with a target station position
        stn_target = _make_station("W1AW", 44.0, -101.0)
        raw_lat, raw_lon, raw_zoom = calculate_auto_zoom(
            [stn_target], OWN_LAT, OWN_LON, WIDTH, HEIGHT,
        )

        # Run many updates — center should converge toward raw center
        for _ in range(100):
            result = ctrl.update([stn_target])

        assert result is not None
        lat, lon, zoom = result
        # After 100 iterations of 70/30 blend, center should be very close to raw
        assert abs(lat - raw_lat) < 0.01
        assert abs(lon - raw_lon) < 0.01
        # Zoom converges too (at +/-0.5 per step, 100 steps is plenty)
        assert abs(zoom - raw_zoom) < 0.5 + 1e-9
