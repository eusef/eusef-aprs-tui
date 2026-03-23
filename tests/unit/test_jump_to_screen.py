"""Tests for aprs_tui.ui.jump_to_screen — coordinate parsing, Maidenhead, callsign lookup."""
from __future__ import annotations

import pytest

from aprs_tui.core.station_tracker import StationRecord, StationTracker
from aprs_tui.ui.jump_to_screen import (
    maidenhead_to_latlon,
    parse_coordinates,
    resolve_input,
    _is_callsign,
    _is_maidenhead,
)


# ---------------------------------------------------------------------------
# parse_coordinates
# ---------------------------------------------------------------------------


class TestParseCoordinates:
    """Tests for the lat/lon coordinate parser."""

    def test_space_separated_signed(self) -> None:
        lat, lon = parse_coordinates("47.6062 -122.3321")
        assert lat == pytest.approx(47.6062)
        assert lon == pytest.approx(-122.3321)

    def test_comma_separated_signed(self) -> None:
        lat, lon = parse_coordinates("47.6062, -122.3321")
        assert lat == pytest.approx(47.6062)
        assert lon == pytest.approx(-122.3321)

    def test_nsew_suffix(self) -> None:
        lat, lon = parse_coordinates("47.6062N 122.3321W")
        assert lat == pytest.approx(47.6062)
        assert lon == pytest.approx(-122.3321)

    def test_nsew_prefix(self) -> None:
        lat, lon = parse_coordinates("N47.6062 W122.3321")
        assert lat == pytest.approx(47.6062)
        assert lon == pytest.approx(-122.3321)

    def test_southern_hemisphere(self) -> None:
        lat, lon = parse_coordinates("33.87S 151.21E")
        assert lat == pytest.approx(-33.87)
        assert lon == pytest.approx(151.21)

    def test_extra_whitespace(self) -> None:
        lat, lon = parse_coordinates("  47.6  ,  -122.3  ")
        assert lat == pytest.approx(47.6)
        assert lon == pytest.approx(-122.3)

    def test_too_few_values_raises(self) -> None:
        with pytest.raises(ValueError, match="Expected two values"):
            parse_coordinates("47.6062")

    def test_too_many_values_raises(self) -> None:
        with pytest.raises(ValueError, match="Expected two values"):
            parse_coordinates("47 -122 10")

    def test_lat_out_of_range(self) -> None:
        with pytest.raises(ValueError, match="Latitude.*out of range"):
            parse_coordinates("91.0 0.0")

    def test_lon_out_of_range(self) -> None:
        with pytest.raises(ValueError, match="Longitude.*out of range"):
            parse_coordinates("0.0 181.0")

    def test_non_numeric_raises(self) -> None:
        with pytest.raises(ValueError, match="Cannot parse"):
            parse_coordinates("abc def")


# ---------------------------------------------------------------------------
# maidenhead_to_latlon
# ---------------------------------------------------------------------------


class TestMaidenheadToLatLon:
    """Tests for the Maidenhead grid square converter."""

    def test_4_char_locator(self) -> None:
        """CN87 should resolve to the centre of that grid square."""
        lat, lon = maidenhead_to_latlon("CN87")
        # CN87: lon = (2*20-180) + 8*2 + 1.0 = -124+16+1 = -107? No...
        # C=2, N=13 → lon = 2*20 - 180 = -140, lat = 13*10 - 90 = 40
        # 8 → lon += 8*2 = 16, 7 → lat += 7*1 = 7
        # centre: lon = -140 + 16 + 1.0 = -123.0, lat = 40 + 7 + 0.5 = 47.5
        assert lat == pytest.approx(47.5)
        assert lon == pytest.approx(-123.0)

    def test_6_char_locator(self) -> None:
        """CN87us — subsquare resolution."""
        lat, lon = maidenhead_to_latlon("CN87us")
        # u=20, s=18 (0-indexed from A)
        # lon += 20 * (2/24) = 1.6667, lat += 18 * (1/24) = 0.75
        # centre offset: lon += (2/24)/2 = 0.04167, lat += (1/24)/2 = 0.02083
        expected_lon = -140 + 16 + 20 * (2 / 24) + (2 / 24) / 2
        expected_lat = 40 + 7 + 18 * (1 / 24) + (1 / 24) / 2
        assert lat == pytest.approx(expected_lat, abs=0.001)
        assert lon == pytest.approx(expected_lon, abs=0.001)

    def test_8_char_locator(self) -> None:
        """CN87us12 — extended square resolution."""
        lat, lon = maidenhead_to_latlon("CN87us12")
        # After subsquare (u=20, s=18):
        # sub_lon = 2/24, sub_lat = 1/24
        # 1 → lon += 1 * (sub_lon/10), 2 → lat += 2 * (sub_lat/10)
        # centre: lon += (sub_lon/10)/2, lat += (sub_lat/10)/2
        sub_lon = 2 / 24
        sub_lat = 1 / 24
        expected_lon = -140 + 16 + 20 * sub_lon + 1 * (sub_lon / 10) + (sub_lon / 10) / 2
        expected_lat = 40 + 7 + 18 * sub_lat + 2 * (sub_lat / 10) + (sub_lat / 10) / 2
        assert lat == pytest.approx(expected_lat, abs=0.0001)
        assert lon == pytest.approx(expected_lon, abs=0.0001)

    def test_lowercase_accepted(self) -> None:
        """Lowercase locators should work."""
        lat, lon = maidenhead_to_latlon("cn87")
        assert lat == pytest.approx(47.5)
        assert lon == pytest.approx(-123.0)

    def test_aa00_corner(self) -> None:
        """AA00 is the bottom-left corner of the grid."""
        lat, lon = maidenhead_to_latlon("AA00")
        # lon = 0*20-180 + 0*2 + 1.0 = -179.0
        # lat = 0*10-90 + 0*1 + 0.5 = -89.5
        assert lat == pytest.approx(-89.5)
        assert lon == pytest.approx(-179.0)

    def test_rr99_corner(self) -> None:
        """RR99 is the top-right corner of the grid."""
        lat, lon = maidenhead_to_latlon("RR99")
        # R=17 → lon = 17*20-180 + 9*2 + 1.0 = 160+18+1 = 179.0
        # R=17 → lat = 17*10-90 + 9*1 + 0.5 = 80+9+0.5 = 89.5
        assert lat == pytest.approx(89.5)
        assert lon == pytest.approx(179.0)

    def test_invalid_length_raises(self) -> None:
        with pytest.raises(ValueError, match="4, 6, or 8 characters"):
            maidenhead_to_latlon("CN8")

    def test_5_char_raises(self) -> None:
        with pytest.raises(ValueError, match="4, 6, or 8 characters"):
            maidenhead_to_latlon("CN87u")

    def test_invalid_field_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid field"):
            maidenhead_to_latlon("ZZ00")

    def test_invalid_subsquare_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid subsquare"):
            maidenhead_to_latlon("CN87z9")


# ---------------------------------------------------------------------------
# _is_maidenhead / _is_callsign helpers
# ---------------------------------------------------------------------------


class TestPatternMatchers:
    """Tests for input classification helpers."""

    def test_maidenhead_4_char(self) -> None:
        assert _is_maidenhead("CN87") is True

    def test_maidenhead_6_char(self) -> None:
        assert _is_maidenhead("CN87us") is True

    def test_maidenhead_8_char(self) -> None:
        assert _is_maidenhead("CN87us12") is True

    def test_maidenhead_rejects_invalid_field(self) -> None:
        assert _is_maidenhead("ZZ87") is False

    def test_maidenhead_rejects_short(self) -> None:
        assert _is_maidenhead("CN8") is False

    def test_callsign_basic(self) -> None:
        assert _is_callsign("W7XXX") is True

    def test_callsign_with_ssid(self) -> None:
        assert _is_callsign("W7XXX-9") is True

    def test_callsign_rejects_no_digit(self) -> None:
        assert _is_callsign("ABCDE") is False

    def test_callsign_rejects_too_short(self) -> None:
        assert _is_callsign("W7") is False


# ---------------------------------------------------------------------------
# resolve_input
# ---------------------------------------------------------------------------


class TestResolveInput:
    """Tests for the unified input resolver."""

    def test_resolves_maidenhead(self) -> None:
        lat, lon = resolve_input("CN87")
        assert lat == pytest.approx(47.5)
        assert lon == pytest.approx(-123.0)

    def test_resolves_latlon(self) -> None:
        lat, lon = resolve_input("47.6 -122.3")
        assert lat == pytest.approx(47.6)
        assert lon == pytest.approx(-122.3)

    def test_resolves_callsign_with_tracker(self) -> None:
        tracker = StationTracker(own_lat=0.0, own_lon=0.0)
        tracker._stations["W7XXX-9"] = StationRecord(
            callsign="W7XXX-9", latitude=47.6, longitude=-122.3, sources={"RF"}
        )
        lat, lon = resolve_input("W7XXX-9", station_tracker=tracker)
        assert lat == pytest.approx(47.6)
        assert lon == pytest.approx(-122.3)

    def test_callsign_not_found_raises(self) -> None:
        tracker = StationTracker(own_lat=0.0, own_lon=0.0)
        with pytest.raises(ValueError, match="not found"):
            resolve_input("W7ZZZ", station_tracker=tracker)

    def test_callsign_no_tracker_raises(self) -> None:
        with pytest.raises(ValueError, match="No station data"):
            resolve_input("W7ZZZ")

    def test_callsign_no_position_raises(self) -> None:
        tracker = StationTracker(own_lat=0.0, own_lon=0.0)
        tracker._stations["W7ZZZ"] = StationRecord(
            callsign="W7ZZZ", sources={"RF"}
        )
        with pytest.raises(ValueError, match="no position"):
            resolve_input("W7ZZZ", station_tracker=tracker)

    def test_empty_input_raises(self) -> None:
        with pytest.raises(ValueError, match="No input"):
            resolve_input("")

    def test_maidenhead_takes_priority_over_callsign(self) -> None:
        """A valid Maidenhead locator should be resolved as grid, not callsign."""
        # CN87 matches both Maidenhead pattern — should resolve as grid
        lat, lon = resolve_input("CN87")
        assert lat == pytest.approx(47.5)
