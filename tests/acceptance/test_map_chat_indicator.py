"""Acceptance tests for chat indicator on the map.

Covers: Issue #83 - Show chat indicator on map for stations with chat history
Sprint: UI Feedback Round 1 (Milestone M4)
PRD refs: Stations with chat history show a 'C' indicator on the map
          next to their station symbol.

Module under test: aprs_tui.map.station_overlay, aprs_tui.map.panel, aprs_tui.app
Architecture ref: docs/ARCHITECTURE-FEEDBACK-R1.md section 3.11
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
# Issue #83: Chat Icon on Map
# ==========================================================================


class TestChatIndicatorOnMap:
    """Stations with chat history show an indicator on the map."""

    def test_render_stations_accepts_chat_callsigns(self):
        """StationOverlay.render_stations() accepts chat_callsigns parameter."""
        assert False, "not implemented — render_stations must accept chat_callsigns parameter"

    def test_chat_indicator_rendered_for_chat_station(self):
        """A station in chat_callsigns has a 'C' indicator next to its symbol."""
        assert False, "not implemented — chat station must show 'C' indicator on map"

    def test_no_chat_indicator_for_non_chat_station(self):
        """A station NOT in chat_callsigns has no chat indicator."""
        assert False, "not implemented — non-chat station must not show chat indicator"

    def test_chat_indicator_position_right_of_symbol(self):
        """Chat indicator 'C' is drawn one cell to the right of the station symbol."""
        assert False, "not implemented — 'C' must be drawn adjacent to station symbol"

    def test_chat_indicator_distinct_style(self):
        """Chat indicator uses a distinct style (e.g., cyan) from station labels."""
        assert False, "not implemented — chat indicator must use distinct styling"

    def test_chat_callsigns_case_insensitive(self):
        """Chat callsign matching is case-insensitive (uppercased)."""
        assert False, "not implemented — chat callsign matching must be case-insensitive"


class TestChatCallsignsPipeline:
    """Chat callsigns flow from app to map panel to station overlay."""

    @pytest.mark.asyncio
    async def test_map_panel_has_set_chat_callsigns(self):
        """MapPanel has a set_chat_callsigns(callsigns) method."""
        assert False, "not implemented — MapPanel must have set_chat_callsigns method"

    @pytest.mark.asyncio
    async def test_app_passes_chat_callsigns_on_refresh(self):
        """App passes chat callsigns to map panel on station refresh."""
        assert False, "not implemented — app must pass chat_callsigns to map panel on refresh"

    @pytest.mark.asyncio
    async def test_chat_callsigns_updated_on_new_chat(self):
        """When a new chat is created, the map chat indicators update."""
        assert False, "not implemented — new chat must update map chat indicators"

    @pytest.mark.asyncio
    async def test_chat_callsigns_updated_on_delete(self):
        """When a chat is deleted, the map chat indicator is removed."""
        assert False, "not implemented — deleted chat must remove map indicator"
