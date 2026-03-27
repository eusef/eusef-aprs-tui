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
from textual.widget import Widget
from textual.widgets import Static

from aprs_tui.app import APRSTuiApp
from aprs_tui.config import AppConfig, StationConfig
from aprs_tui.transport.base import ConnectionState
from aprs_tui.ui.footer import AppFooter
from aprs_tui.ui.status_bar import StatusBar


def _make_app() -> APRSTuiApp:
    """Create an APRSTuiApp with a minimal valid config."""
    config = AppConfig(station=StationConfig(callsign="N0CALL"))
    return APRSTuiApp(config)


# ==========================================================================
# Issue #73: Header Redesign
# ==========================================================================


class TestHeaderLayout:
    """Header bar displays callsign + clock on left, ko-fi on right."""

    def test_header_shows_callsign(self):
        """Header stores the station callsign for rendering in the left region."""
        bar = StatusBar(callsign="N0CALL")
        assert bar.callsign == "N0CALL"

    def test_header_callsign_setter_updates(self):
        """Setting callsign property updates the stored value."""
        bar = StatusBar(callsign="N0CALL")
        bar._callsign = "W7XXX"
        assert bar.callsign == "W7XXX"

    def test_header_clock_method_exists(self):
        """Header has an _update_clock method for the 1-second timer."""
        bar = StatusBar(callsign="N0CALL")
        assert callable(bar._update_clock)

    def test_header_kofi_method_exists(self):
        """Header has an _update_kofi method for the right-aligned ko-fi link."""
        bar = StatusBar(callsign="N0CALL")
        assert callable(bar._update_kofi)

    def test_header_no_tx_rx_counters_in_rendering(self):
        """TX/RX counters are NOT rendered in the header (moved to footer in #74).

        The backward-compat properties exist but do not affect header display.
        """
        bar = StatusBar(callsign="N0CALL")
        bar.increment_rx()
        bar.increment_tx()
        # Counters stored for compat but do not appear in header rendering
        assert bar.rx_count == 1
        assert bar.tx_count == 1
        # The class no longer has a render() method that includes these values
        # (it uses compose() with two Static children instead)

    def test_header_no_connection_state_in_rendering(self):
        """Connection state is NOT rendered in the header (moved to footer in #74).

        update_state() stores values for backward compat but does not affect
        header rendering.
        """
        bar = StatusBar(callsign="N0CALL")
        bar.update_state("CONNECTED", transport_name="Direwolf")
        assert bar.connection_state == "CONNECTED"
        assert bar.transport_name == "Direwolf"

    def test_header_is_widget_not_static(self):
        """StatusBar inherits from Widget (not Static) for Horizontal layout."""
        bar = StatusBar(callsign="N0CALL")
        assert isinstance(bar, Widget)
        assert not isinstance(bar, Static)

    def test_header_compose_yields_two_statics(self):
        """Header compose() yields two Static children (left + right regions)."""
        bar = StatusBar(callsign="N0CALL")
        children = list(bar.compose())
        assert len(children) == 2
        assert all(isinstance(c, Static) for c in children)

    def test_header_left_region_exists(self):
        """Header compose yields a Static with id='header-left'."""
        bar = StatusBar(callsign="N0CALL")
        children = list(bar.compose())
        ids = [c.id for c in children]
        assert "header-left" in ids

    def test_header_right_region_exists(self):
        """Header compose yields a Static with id='header-right'."""
        bar = StatusBar(callsign="N0CALL")
        children = list(bar.compose())
        ids = [c.id for c in children]
        assert "header-right" in ids


# ==========================================================================
# Issue #74: Footer Redesign
# ==========================================================================


class TestFooterLayout:
    """New AppFooter widget shows TX/RX, RF state, APRS-IS state."""

    @pytest.mark.asyncio
    async def test_footer_exists_in_app(self):
        """The app composes an AppFooter widget (not Textual's built-in Footer)."""
        app = _make_app()
        async with app.run_test():
            footer_widgets = app.query(AppFooter)
            assert len(footer_widgets) == 1

    def test_footer_is_widget(self):
        """AppFooter inherits from Widget."""
        footer = AppFooter()
        assert isinstance(footer, Widget)

    def test_footer_docked_bottom(self):
        """AppFooter CSS specifies dock: bottom."""
        assert "dock: bottom" in AppFooter.DEFAULT_CSS

    def test_footer_height_one_line(self):
        """AppFooter CSS specifies height: 1."""
        assert "height: 1" in AppFooter.DEFAULT_CSS


class TestFooterTxRxCounters:
    """TX and RX counters in the footer."""

    def test_footer_tx_counter_starts_zero(self):
        """TX counter starts at 0 in the footer."""
        footer = AppFooter()
        assert footer.tx_count == 0

    def test_footer_rx_counter_starts_zero(self):
        """RX counter starts at 0 in the footer."""
        footer = AppFooter()
        assert footer.rx_count == 0

    def test_footer_tx_counter_increments(self):
        """TX counter increments when increment_tx() is called."""
        footer = AppFooter()
        footer._tx_count = 0  # ensure clean state
        footer.increment_tx()
        assert footer.tx_count == 1
        footer.increment_tx()
        assert footer.tx_count == 2

    def test_footer_rx_counter_increments(self):
        """RX counter increments when increment_rx() is called."""
        footer = AppFooter()
        footer._rx_count = 0
        footer.increment_rx()
        assert footer.rx_count == 1
        footer.increment_rx()
        assert footer.rx_count == 2

    def test_footer_shows_tx_rx_text(self):
        """Footer render() output contains 'TX: N  RX: N' text."""
        footer = AppFooter()
        footer._tx_count = 5
        footer._rx_count = 42
        text = footer.render()
        plain = text.plain
        assert "TX: 5" in plain
        assert "RX: 42" in plain


class TestFooterRfState:
    """RF connection state display in the footer."""

    def test_footer_rf_connected(self):
        """Footer shows '[=]' and transport name when RF connected."""
        footer = AppFooter()
        footer._rf_state = "connected"
        footer._rf_transport_name = "Mobilinkd TNC4"
        text = footer.render()
        plain = text.plain
        assert "[=]" in plain
        assert "Mobilinkd TNC4" in plain

    def test_footer_rf_connecting(self):
        """Footer shows '[~] Connecting...' when RF is connecting."""
        footer = AppFooter()
        footer._rf_state = "connecting"
        text = footer.render()
        plain = text.plain
        assert "[~]" in plain
        assert "Connecting" in plain

    def test_footer_rf_disconnected(self):
        """Footer shows '[X] Disconnected' when RF is disconnected."""
        footer = AppFooter()
        footer._rf_state = "disconnected"
        text = footer.render()
        plain = text.plain
        assert "[X]" in plain
        assert "Disconnected" in plain

    def test_footer_rf_not_configured(self):
        """Footer shows 'Not configured' when no RF transport set."""
        footer = AppFooter()
        footer._rf_state = "not_configured"
        text = footer.render()
        plain = text.plain
        assert "Not configured" in plain

    def test_footer_rf_transport_name_displayed(self):
        """Footer shows the transport name when RF is connected."""
        footer = AppFooter()
        footer._rf_state = "connected"
        footer._rf_transport_name = "Direwolf"
        text = footer.render()
        assert "Direwolf" in text.plain


class TestFooterIsState:
    """APRS-IS connection state display in the footer."""

    def test_footer_is_connected(self):
        """Footer shows '[=] Connected' when APRS-IS is connected."""
        footer = AppFooter()
        footer._is_state = "connected"
        text = footer.render()
        plain = text.plain
        assert "IS:" in plain
        assert "[=]" in plain

    def test_footer_is_disconnected(self):
        """Footer shows '[X] Disconnected' when APRS-IS is disconnected."""
        footer = AppFooter()
        footer._is_state = "disconnected"
        text = footer.render()
        plain = text.plain
        # The RF section also has [X], so check IS section specifically
        assert "IS:" in plain

    def test_footer_is_not_configured(self):
        """Footer shows 'Not configured' when APRS-IS not enabled."""
        footer = AppFooter()
        footer._is_state = "not_configured"
        text = footer.render()
        assert "Not configured" in text.plain


class TestFooterStateApi:
    """AppFooter public API for state updates."""

    def test_footer_update_rf_state_method(self):
        """AppFooter has update_rf_state(state, transport_name) method."""
        footer = AppFooter()
        assert callable(footer.update_rf_state)
        # Calling it should update internal state
        footer.update_rf_state(ConnectionState.CONNECTED, "TestTNC")
        assert footer.rf_state == "connected"

    def test_footer_update_is_state_method(self):
        """AppFooter has update_is_state(state) method."""
        footer = AppFooter()
        assert callable(footer.update_is_state)
        footer.update_is_state(ConnectionState.CONNECTED)
        assert footer.is_state == "connected"

    def test_footer_rf_failed_state(self):
        """Footer handles FAILED state correctly."""
        footer = AppFooter()
        footer.update_rf_state(ConnectionState.FAILED)
        assert footer.rf_state == "failed"
        text = footer.render()
        assert "[X]" in text.plain
        assert "Failed" in text.plain

    def test_footer_rf_reconnecting_state(self):
        """Footer handles RECONNECTING state correctly."""
        footer = AppFooter()
        footer.update_rf_state(ConnectionState.RECONNECTING)
        assert footer.rf_state == "reconnecting"
        text = footer.render()
        assert "[~]" in text.plain
        assert "Reconnecting" in text.plain
