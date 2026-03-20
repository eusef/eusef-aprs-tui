"""Acceptance tests for header and footer redesign.

Covers: Issue #73 - Redesign header (left-aligned callsign + clock, right-aligned ko-fi)
        Issue #74 - New footer with TX/RX, RF state, APRS-IS state
Sprint: UI Feedback Round 1 (Milestone M1)
PRD refs: Header shows callsign + clock on left, ko-fi on right.
          Footer shows TX/RX counters, RF connection state, APRS-IS connection state.

Module under test: aprs_tui.ui.status_bar (header), aprs_tui.ui.footer (new)
Architecture ref: docs/ARCHITECTURE-FEEDBACK-R1.md sections 3.1, 3.2
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
# Issue #73: Header Redesign
# ==========================================================================


class TestHeaderLayout:
    """Header bar displays callsign + clock on left, ko-fi on right."""

    @pytest.mark.asyncio
    async def test_header_shows_callsign(self):
        """Header displays the station callsign in the left region."""
        assert False, "not implemented — header must show callsign (e.g. 'N0CALL') on the left side"

    @pytest.mark.asyncio
    async def test_header_shows_clock_local_and_utc(self):
        """Header displays a clock with local time and UTC in format 'HH:MM TZ / HH:MM UTC'."""
        assert False, "not implemented — header must show dual clock (local TZ / UTC)"

    @pytest.mark.asyncio
    async def test_header_clock_updates_every_second(self):
        """Header clock updates at 1-second intervals via set_interval."""
        assert False, "not implemented — clock must auto-update every second"

    @pytest.mark.asyncio
    async def test_header_kofi_right_aligned(self):
        """Ko-fi link appears right-aligned in the header."""
        assert False, "not implemented — ko-fi link must be right-aligned"

    @pytest.mark.asyncio
    async def test_header_no_tx_rx_counters(self):
        """TX/RX counters are NOT in the header (moved to footer in #74)."""
        assert False, "not implemented — header must not contain TX/RX counters after redesign"

    @pytest.mark.asyncio
    async def test_header_no_connection_state(self):
        """Connection state is NOT in the header (moved to footer in #74)."""
        assert False, "not implemented — header must not contain connection state after redesign"

    @pytest.mark.asyncio
    async def test_header_is_widget_not_static(self):
        """StatusBar is now a Widget (not Static) using Horizontal layout."""
        assert False, "not implemented — StatusBar must be a Widget with Horizontal layout"

    @pytest.mark.asyncio
    async def test_header_left_region_exists(self):
        """Header contains a left region element (id='header-left')."""
        assert False, "not implemented — header must have #header-left child"

    @pytest.mark.asyncio
    async def test_header_right_region_exists(self):
        """Header contains a right region element (id='header-right')."""
        assert False, "not implemented — header must have #header-right child"


# ==========================================================================
# Issue #74: Footer Redesign
# ==========================================================================


class TestFooterLayout:
    """New AppFooter widget shows TX/RX, RF state, APRS-IS state."""

    @pytest.mark.asyncio
    async def test_footer_exists_in_app(self):
        """The app composes an AppFooter widget (not Textual's built-in Footer)."""
        assert False, "not implemented — app must compose AppFooter widget"

    @pytest.mark.asyncio
    async def test_footer_docked_bottom(self):
        """AppFooter is docked to the bottom of the screen."""
        assert False, "not implemented — footer must be docked bottom"

    @pytest.mark.asyncio
    async def test_footer_height_one_line(self):
        """AppFooter has a height of 1 line."""
        assert False, "not implemented — footer height must be 1"


class TestFooterTxRxCounters:
    """TX and RX counters in the footer."""

    @pytest.mark.asyncio
    async def test_footer_tx_counter_starts_zero(self):
        """TX counter starts at 0 in the footer."""
        assert False, "not implemented — footer TX counter must start at 0"

    @pytest.mark.asyncio
    async def test_footer_rx_counter_starts_zero(self):
        """RX counter starts at 0 in the footer."""
        assert False, "not implemented — footer RX counter must start at 0"

    @pytest.mark.asyncio
    async def test_footer_tx_counter_increments(self):
        """TX counter increments when increment_tx() is called on footer."""
        assert False, "not implemented — footer must support increment_tx()"

    @pytest.mark.asyncio
    async def test_footer_rx_counter_increments(self):
        """RX counter increments when increment_rx() is called on footer."""
        assert False, "not implemented — footer must support increment_rx()"

    @pytest.mark.asyncio
    async def test_footer_shows_tx_rx_text(self):
        """Footer renders 'TX: N  RX: N' text."""
        assert False, "not implemented — footer must render TX/RX counter text"


class TestFooterRfState:
    """RF connection state display in the footer."""

    @pytest.mark.asyncio
    async def test_footer_rf_connected(self):
        """Footer shows 'RF: [=] {transport_name}' in green when RF connected."""
        assert False, "not implemented — footer must show RF connected state"

    @pytest.mark.asyncio
    async def test_footer_rf_connecting(self):
        """Footer shows 'RF: [~] Connecting...' in yellow when connecting."""
        assert False, "not implemented — footer must show RF connecting state"

    @pytest.mark.asyncio
    async def test_footer_rf_disconnected(self):
        """Footer shows 'RF: [X] Disconnected' in red when disconnected."""
        assert False, "not implemented — footer must show RF disconnected state"

    @pytest.mark.asyncio
    async def test_footer_rf_not_configured(self):
        """Footer shows 'RF: [--] Not configured' dimmed when no RF transport."""
        assert False, "not implemented — footer must show RF not-configured state"

    @pytest.mark.asyncio
    async def test_footer_rf_transport_name_displayed(self):
        """Footer shows the transport name (e.g. 'Mobilinkd TNC4') when connected."""
        assert False, "not implemented — footer must display RF transport name"


class TestFooterIsState:
    """APRS-IS connection state display in the footer."""

    @pytest.mark.asyncio
    async def test_footer_is_connected(self):
        """Footer shows 'IS: [=] Connected' in green when APRS-IS connected."""
        assert False, "not implemented — footer must show IS connected state"

    @pytest.mark.asyncio
    async def test_footer_is_disconnected(self):
        """Footer shows 'IS: [X] Disconnected' in red when APRS-IS disconnected."""
        assert False, "not implemented — footer must show IS disconnected state"

    @pytest.mark.asyncio
    async def test_footer_is_not_configured(self):
        """Footer shows 'IS: [--] Not configured' dimmed when APRS-IS not enabled."""
        assert False, "not implemented — footer must show IS not-configured state"


class TestFooterStateApi:
    """AppFooter public API for state updates."""

    @pytest.mark.asyncio
    async def test_footer_update_rf_state_method(self):
        """AppFooter has update_rf_state(state, transport_name) method."""
        assert False, "not implemented — AppFooter must have update_rf_state method"

    @pytest.mark.asyncio
    async def test_footer_update_is_state_method(self):
        """AppFooter has update_is_state(state) method."""
        assert False, "not implemented — AppFooter must have update_is_state method"
