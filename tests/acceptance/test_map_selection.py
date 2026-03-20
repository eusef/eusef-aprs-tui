"""Acceptance tests for bidirectional station selection and info screen.

Covers: Issue #80 - Station list selection highlights station on map
        Issue #81 - Map station selection highlights row in station list
        Issue #82 - Enter on map station opens station info screen
Sprint: UI Feedback Round 1 (Milestone M4)
PRD refs: Selecting in list highlights on map and vice versa.
          Enter on map station opens info screen.

Module under test: aprs_tui.app, aprs_tui.ui.station_panel,
                   aprs_tui.map.panel, aprs_tui.ui.station_info_screen
Architecture ref: docs/ARCHITECTURE-FEEDBACK-R1.md sections 3.9, 3.10
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
# Issue #80: Station List -> Map Selection
# ==========================================================================


class TestListToMapSelection:
    """Selecting a station in the list highlights it on the map."""

    @pytest.mark.asyncio
    async def test_list_selection_updates_map(self):
        """When a station is selected in the list, MapPanel.select_station() is called."""
        assert False, "not implemented — list selection must call map_panel.select_station()"

    @pytest.mark.asyncio
    async def test_list_selection_posts_station_selected(self):
        """StationPanel posts StationSelected message on cursor move."""
        assert False, "not implemented — StationPanel must post StationSelected"

    @pytest.mark.asyncio
    async def test_app_handles_station_panel_selected(self):
        """App handler on_station_panel_station_selected updates the map."""
        assert False, "not implemented — app must handle StationPanel.StationSelected and update map"

    @pytest.mark.asyncio
    async def test_map_panel_has_select_station_method(self):
        """MapPanel has a select_station(callsign) method."""
        assert False, "not implemented — MapPanel must have select_station method"


# ==========================================================================
# Issue #81: Map -> Station List Selection
# ==========================================================================


class TestMapToListSelection:
    """Selecting a station on the map highlights it in the station list."""

    @pytest.mark.asyncio
    async def test_map_selection_posts_message(self):
        """MapPanel posts StationSelected message when n/N cycles stations."""
        assert False, "not implemented — MapPanel must post StationSelected on n/N key"

    @pytest.mark.asyncio
    async def test_map_station_selected_message_has_callsign(self):
        """MapPanel.StationSelected message includes the callsign."""
        assert False, "not implemented — MapPanel.StationSelected must carry callsign"

    @pytest.mark.asyncio
    async def test_app_handles_map_panel_selected(self):
        """App handler on_map_panel_station_selected updates the station list."""
        assert False, "not implemented — app must handle MapPanel.StationSelected"

    @pytest.mark.asyncio
    async def test_station_panel_has_select_callsign_method(self):
        """StationPanel has a select_callsign(callsign) method."""
        assert False, "not implemented — StationPanel must have select_callsign method"

    @pytest.mark.asyncio
    async def test_select_callsign_moves_cursor(self):
        """StationPanel.select_callsign moves the cursor to the matching row."""
        assert False, "not implemented — select_callsign must move cursor to correct row"

    @pytest.mark.asyncio
    async def test_select_callsign_enables_cursor(self):
        """StationPanel.select_callsign enables cursor visibility and user_selected."""
        assert False, "not implemented — select_callsign must set show_cursor=True"

    @pytest.mark.asyncio
    async def test_stream_panel_highlight_on_map_select(self):
        """Map station selection also highlights the callsign in the stream panel."""
        assert False, "not implemented — map selection must highlight in stream panel too"


class TestBidirectionalGuard:
    """Bidirectional selection does not cause infinite loops."""

    @pytest.mark.asyncio
    async def test_no_infinite_loop(self):
        """Selecting same station on both sides does not cause recursive updates."""
        assert False, "not implemented — guard must prevent infinite loop: 'if selected == callsign: return'"


# ==========================================================================
# Issue #82: Enter on Map Station -> Info Screen
# ==========================================================================


class TestMapStationInfoScreen:
    """Pressing Enter on a selected map station opens an info screen."""

    @pytest.mark.asyncio
    async def test_enter_key_bound_on_map(self):
        """MapPanel has an Enter key binding for station activation."""
        assert False, "not implemented — MapPanel must have Enter key binding"

    @pytest.mark.asyncio
    async def test_enter_posts_station_activated(self):
        """Pressing Enter on a selected station posts StationActivated message."""
        assert False, "not implemented — Enter must post MapPanel.StationActivated"

    @pytest.mark.asyncio
    async def test_enter_no_op_without_selection(self):
        """Pressing Enter with no station selected does nothing."""
        assert False, "not implemented — Enter without selection must be a no-op"

    @pytest.mark.asyncio
    async def test_info_screen_is_modal(self):
        """Station info screen is a ModalScreen."""
        assert False, "not implemented — station info screen must be a ModalScreen"

    @pytest.mark.asyncio
    async def test_info_screen_shows_callsign(self):
        """Station info screen displays the station callsign."""
        assert False, "not implemented — info screen must show callsign"

    @pytest.mark.asyncio
    async def test_info_screen_shows_position(self):
        """Station info screen displays the station lat/lon position."""
        assert False, "not implemented — info screen must show position"

    @pytest.mark.asyncio
    async def test_info_screen_shows_distance(self):
        """Station info screen displays the distance from own station."""
        assert False, "not implemented — info screen must show distance"

    @pytest.mark.asyncio
    async def test_info_screen_shows_bearing(self):
        """Station info screen displays the bearing to the station."""
        assert False, "not implemented — info screen must show bearing"

    @pytest.mark.asyncio
    async def test_info_screen_shows_last_heard(self):
        """Station info screen displays the last-heard time."""
        assert False, "not implemented — info screen must show last heard"

    @pytest.mark.asyncio
    async def test_info_screen_shows_packet_count(self):
        """Station info screen displays the packet count."""
        assert False, "not implemented — info screen must show packet count"

    @pytest.mark.asyncio
    async def test_info_screen_shows_symbol(self):
        """Station info screen displays the APRS symbol description."""
        assert False, "not implemented — info screen must show symbol"

    @pytest.mark.asyncio
    async def test_info_screen_escape_closes(self):
        """Pressing Escape on the info screen closes it."""
        assert False, "not implemented — Escape must close info screen"

    @pytest.mark.asyncio
    async def test_info_screen_enter_opens_chat(self):
        """Pressing Enter on the info screen opens chat with that station."""
        assert False, "not implemented — Enter on info screen must open chat"

    @pytest.mark.asyncio
    async def test_info_screen_from_station_panel_activated(self):
        """StationPanel.StationActivated and MapPanel.StationActivated both open info screen."""
        assert False, "not implemented — both activation sources must open info screen"
