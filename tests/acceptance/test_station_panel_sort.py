"""Acceptance tests for station list improvements.

Covers: Issue #76 - Sortable station list column headers with direction toggle
        Issue #77 - Expand symbol display in station list
        Issue #78 - Add space between chat icon and callsign in station list
Sprint: UI Feedback Round 1 (Milestone M3)
PRD refs: Column headers are clickable for sort. Symbols display correctly.
          Chat icon has a space before callsign.

Module under test: aprs_tui.ui.station_panel, aprs_tui.core.station_tracker
Architecture ref: docs/ARCHITECTURE-FEEDBACK-R1.md sections 3.5, 3.6, 3.7
"""
from __future__ import annotations

import pytest

from aprs_tui.app import APRSTuiApp
from aprs_tui.config import AppConfig, StationConfig


def _make_app() -> APRSTuiApp:
    """Create an APRSTuiApp with a minimal valid config."""
    config = AppConfig(station=StationConfig(callsign="N0CALL"))
    return APRSTuiApp(config)


# ==========================================================================
# Issue #76: Sortable Station List Headers
# ==========================================================================


class TestSortableHeaders:
    """Column headers are clickable and toggle sort direction."""

    @pytest.mark.asyncio
    async def test_clicking_column_header_sorts_by_column(self):
        """Clicking a column header sorts the station list by that column."""
        pytest.skip("not implemented — clicking a column header must sort by that column")

    @pytest.mark.asyncio
    async def test_clicking_same_column_toggles_direction(self):
        """Clicking the same column header again reverses the sort direction."""
        pytest.skip("not implemented — clicking same column must toggle sort direction")

    @pytest.mark.asyncio
    async def test_sort_indicator_shown_on_active_column(self):
        """Active sort column shows a direction indicator (triangle up or down)."""
        pytest.skip("not implemented — active sort column must show sort indicator")

    @pytest.mark.asyncio
    async def test_sort_indicator_up_for_ascending(self):
        """Sort indicator shows up-triangle for ascending sort."""
        pytest.skip("not implemented — ascending sort must show up-triangle indicator")

    @pytest.mark.asyncio
    async def test_sort_indicator_down_for_descending(self):
        """Sort indicator shows down-triangle for descending sort."""
        pytest.skip("not implemented — descending sort must show down-triangle indicator")

    @pytest.mark.asyncio
    async def test_default_sort_callsign_ascending(self):
        """Default sort direction for Callsign is ascending (A-Z)."""
        pytest.skip("not implemented — Callsign default sort must be ascending")

    @pytest.mark.asyncio
    async def test_default_sort_last_heard_most_recent(self):
        """Default sort direction for Last Heard is most recent first."""
        pytest.skip("not implemented — Last Heard default sort must be most recent first")

    @pytest.mark.asyncio
    async def test_default_sort_distance_nearest(self):
        """Default sort direction for Distance is nearest first."""
        pytest.skip("not implemented — Distance default sort must be nearest first")

    @pytest.mark.asyncio
    async def test_default_sort_bearing_ascending(self):
        """Default sort direction for Bearing is 0 degrees first."""
        pytest.skip("not implemented — Bearing default sort must be ascending")

    @pytest.mark.asyncio
    async def test_default_sort_pkts_descending(self):
        """Default sort direction for Pkts is most packets first."""
        pytest.skip("not implemented — Pkts default sort must be descending")

    @pytest.mark.asyncio
    async def test_switching_column_resets_to_default_direction(self):
        """Switching to a different column resets sort direction to that column's default."""
        pytest.skip("not implemented — switching columns must reset to default sort direction")

    @pytest.mark.asyncio
    async def test_header_selected_event_handled(self):
        """on_data_table_header_selected event is handled by StationPanel."""
        pytest.skip("not implemented — StationPanel must handle header selection events")


class TestSortableHeadersStationTracker:
    """StationTracker supports new sort keys and reverse parameter."""

    def test_station_tracker_sort_by_bearing(self):
        """StationTracker.get_stations() accepts sort_by='bearing'."""
        pytest.skip("not implemented — get_stations must support bearing sort")

    def test_station_tracker_sort_by_packet_count(self):
        """StationTracker.get_stations() accepts sort_by='packet_count'."""
        pytest.skip("not implemented — get_stations must support packet_count sort")

    def test_station_tracker_reverse_parameter(self):
        """StationTracker.get_stations() accepts a 'reverse' parameter."""
        pytest.skip("not implemented — get_stations must accept reverse parameter")

    def test_bearing_sort_none_values_last(self):
        """Stations with no bearing are sorted to the end."""
        pytest.skip("not implemented — None bearing must sort to end (float('inf'))")


# ==========================================================================
# Issue #77: Expand Symbol Display
# ==========================================================================


class TestSymbolDisplay:
    """Station list symbol column displays a wider range of APRS symbols."""

    def test_symbol_map_has_at_least_20_entries(self):
        """SYMBOL_MAP has at least 20 entries (expanded from original 8)."""
        pytest.skip("not implemented — SYMBOL_MAP must have >= 20 entries")

    def test_car_symbol_mapped(self):
        """Car symbol '/>' maps to a display string."""
        pytest.skip("not implemented — car symbol '/>' must be mapped")

    def test_house_symbol_mapped(self):
        """House symbol '/-' maps to a display string."""
        pytest.skip("not implemented — house symbol '/-' must be mapped")

    def test_weather_symbol_mapped(self):
        """Weather station symbol '/_' maps to a display string."""
        pytest.skip("not implemented — weather symbol '/_' must be mapped")

    def test_digipeater_symbol_mapped(self):
        """Digipeater symbol '/#' maps to a display string."""
        pytest.skip("not implemented — digipeater symbol '/#' must be mapped")

    def test_ambulance_symbol_mapped(self):
        """Ambulance symbol '/a' maps to a display string."""
        pytest.skip("not implemented — ambulance symbol '/a' must be mapped")

    def test_bus_symbol_mapped(self):
        """Bus symbol '/U' maps to a display string."""
        pytest.skip("not implemented — bus symbol '/U' must be mapped")

    def test_unmapped_symbol_shows_default(self):
        """Unmapped symbol codes show a default placeholder (not empty string)."""
        pytest.skip("not implemented — unmapped symbols must show default, not empty")

    def test_default_symbol_not_empty(self):
        """DEFAULT_SYMBOL is a non-empty string (e.g. '---')."""
        pytest.skip("not implemented — DEFAULT_SYMBOL must not be empty")


# ==========================================================================
# Issue #78: Chat Icon Spacing
# ==========================================================================


class TestChatIconSpacing:
    """Chat icon in station list has a space before the callsign."""

    @pytest.mark.asyncio
    async def test_chat_icon_has_space_before_callsign(self):
        """When a station has chat history, the display shows 'icon CALLSIGN' with a space."""
        pytest.skip("not implemented — chat icon display must have space between icon and callsign")

    @pytest.mark.asyncio
    async def test_chat_icon_format_string(self):
        """The chat display format uses 'icon CALLSIGN' not 'iconCALLSIGN'."""
        pytest.skip("not implemented — format string must be 'icon CALLSIGN' with space")
