"""Acceptance tests for TUI status bar state display.

Covers: Issue #11 - Status Bar (connection state, TX/RX, reactive attrs)
Sprint: 2 (TUI Shell + Stream Panel)
PRD refs: AC-02 (status bar shows connected state with host and port)
          AC-11 (status bar shows RECONNECTING...)
          AC-12 (status bar shows health warning)

Module under test: aprs_tui.ui.status_bar
Estimated implementation: tested via Textual snapshot/pilot testing

The status bar displays:
- Connection state (DISCONNECTED, CONNECTING, CONNECTED, RECONNECTING, FAILED)
- Transport display name (e.g., "KISS TCP 127.0.0.1:8001")
- TX/RX packet counters (reactive attributes)
- Health warning indicator (no packets for >60s)
- Beacon active/inactive indicator
"""
from __future__ import annotations

import pytest

from aprs_tui.app import APRSTuiApp
from aprs_tui.config import AppConfig, StationConfig
from aprs_tui.transport.base import ConnectionState
from aprs_tui.ui.status_bar import StatusBar


def _make_app() -> APRSTuiApp:
    """Create an APRSTuiApp with a minimal valid config."""
    config = AppConfig(station=StationConfig(callsign="N0CALL"))
    return APRSTuiApp(config)


# ==========================================================================
# Connection state display
# ==========================================================================

class TestStatusBarConnectionState:
    """Status bar displays the current connection state."""

    @pytest.mark.asyncio
    async def test_disconnected_state(self):
        """StatusBar renders NOT CONNECTED when in DISCONNECTED state."""
        app = _make_app()
        async with app.run_test():
            bar = app.query_one(StatusBar)
            # App may auto-connect on startup; force DISCONNECTED to test rendering
            bar.update_state(ConnectionState.DISCONNECTED)
            assert bar.connection_state == "DISCONNECTED"
            rendered = bar.render()
            assert "NOT CONNECTED" in rendered.plain

    @pytest.mark.skip(reason="Sprint 3: Requires transport integration")
    async def test_connecting_state(self, tmp_config_file):
        """Status bar shows CONNECTING during connection attempt."""
        pass

    @pytest.mark.skip(reason="Sprint 3: Requires transport integration")
    async def test_connected_state(self, tmp_config_file):
        """Status bar shows CONNECTED with host:port after successful
        connection (AC-02)."""
        pass

    @pytest.mark.skip(reason="Sprint 3: Requires transport integration")
    async def test_reconnecting_state(self, tmp_config_file):
        """Status bar shows RECONNECTING... when connection drops (AC-11)."""
        pass

    @pytest.mark.skip(reason="Sprint 3: Requires transport integration")
    async def test_failed_state(self, tmp_config_file):
        """Status bar shows FAILED after max reconnect attempts."""
        pass

    @pytest.mark.asyncio
    async def test_connected_shows_transport_name(self):
        """Status bar includes the transport display name (e.g.,
        'KISS TCP 127.0.0.1:8001') when connected (AC-02)."""
        app = _make_app()
        async with app.run_test():
            bar = app.query_one(StatusBar)
            bar.update_state(ConnectionState.CONNECTED, transport_name="KISS TCP 127.0.0.1:8001")
            assert bar.connection_state == "CONNECTED"
            assert bar.transport_name == "KISS TCP 127.0.0.1:8001"
            rendered = bar.render()
            assert "KISS TCP 127.0.0.1:8001" in rendered.plain


# ==========================================================================
# TX/RX counters
# ==========================================================================

class TestStatusBarCounters:
    """TX and RX packet counters in the status bar."""

    @pytest.mark.asyncio
    async def test_rx_counter_starts_at_zero(self):
        """RX counter starts at 0 on launch."""
        app = _make_app()
        async with app.run_test():
            bar = app.query_one(StatusBar)
            assert bar.rx_count == 0

    @pytest.mark.asyncio
    async def test_tx_counter_starts_at_zero(self):
        """TX counter starts at 0 on launch."""
        app = _make_app()
        async with app.run_test():
            bar = app.query_one(StatusBar)
            assert bar.tx_count == 0

    @pytest.mark.asyncio
    async def test_rx_counter_increments(self):
        """RX counter increments when increment_rx is called."""
        app = _make_app()
        async with app.run_test():
            bar = app.query_one(StatusBar)
            assert bar.rx_count == 0
            bar.increment_rx()
            assert bar.rx_count == 1
            bar.increment_rx()
            assert bar.rx_count == 2

    @pytest.mark.skip(reason="Sprint 3: Beacon not implemented yet")
    async def test_tx_counter_increments_on_beacon(self, tmp_config_file):
        """TX counter increments when a beacon is transmitted."""
        pass

    @pytest.mark.skip(reason="Sprint 4: Messaging not implemented yet")
    async def test_tx_counter_increments_on_message(self, tmp_config_file):
        """TX counter increments when a message is sent."""
        pass

    @pytest.mark.asyncio
    async def test_counters_update_reactively(self):
        """Counter updates render immediately via Textual reactive attributes."""
        app = _make_app()
        async with app.run_test() as pilot:
            bar = app.query_one(StatusBar)
            # Initial render
            rendered = bar.render()
            assert "RX: 0" in rendered.plain
            assert "TX: 0" in rendered.plain

            # Update counters
            bar.increment_rx()
            bar.increment_tx()
            bar.increment_rx()
            await pilot.pause()

            # Re-render should reflect updates
            rendered = bar.render()
            assert "RX: 2" in rendered.plain
            assert "TX: 1" in rendered.plain


# ==========================================================================
# Health warning indicator (AC-12)
# ==========================================================================

class TestStatusBarHealth:
    """Connection health warning in the status bar."""

    @pytest.mark.skip(reason="Sprint 3: Not implemented yet")
    async def test_health_warning_shown_after_timeout(self, tmp_config_file):
        """A warning indicator appears after no packets for >60 seconds (AC-12)."""
        pass

    @pytest.mark.skip(reason="Sprint 3: Not implemented yet")
    async def test_health_warning_clears(self, tmp_config_file):
        """The warning indicator clears when a packet is received."""
        pass

    @pytest.mark.skip(reason="Sprint 3: Not implemented yet")
    async def test_health_warning_not_shown_when_disconnected(self, tmp_config_file):
        """No health warning when intentionally disconnected."""
        pass


# ==========================================================================
# Beacon indicator
# ==========================================================================

class TestStatusBarBeacon:
    """Beacon active/inactive indicator in the status bar."""

    @pytest.mark.skip(reason="Sprint 3: Not implemented yet")
    async def test_beacon_inactive_indicator(self, tmp_config_file):
        """Status bar shows beacon as inactive when beacon.enabled=false."""
        pass

    @pytest.mark.skip(reason="Sprint 3: Not implemented yet")
    async def test_beacon_active_indicator(self, tmp_config_file):
        """Status bar shows beacon as active when beacon.enabled=true."""
        pass

    @pytest.mark.skip(reason="Sprint 3: Not implemented yet")
    async def test_beacon_toggle_updates_indicator(self, tmp_config_file):
        """Toggling beacon at runtime updates the status bar indicator."""
        pass


# ==========================================================================
# APRS-IS dual-mode indicator
# ==========================================================================

class TestStatusBarDualMode:
    """Dual-mode (radio + APRS-IS) indicator."""

    @pytest.mark.skip(reason="Sprint 7: Not implemented yet")
    async def test_dual_mode_indicator(self, tmp_config_file):
        """Status bar shows both transport names when in dual mode."""
        pass

    @pytest.mark.skip(reason="Sprint 7: Not implemented yet")
    async def test_aprs_is_only_indicator(self, tmp_config_file):
        """Status bar shows APRS-IS indicator when in APRS-IS only mode."""
        pass
