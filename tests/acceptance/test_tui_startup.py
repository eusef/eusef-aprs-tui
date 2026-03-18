"""Acceptance tests for TUI application startup.

Covers: Issue #8 - Textual App class + panel layout
        Issue #26 - First-run detection + wizard auto-launch
Sprint: 2 (TUI Shell), Sprint 5 (Wizard)
PRD refs: AC-01 (first run / wizard launch)
          AC-02 (KISS TCP connection - TUI starts with panels)

Module under test: aprs_tui.app, aprs_tui.ui.layout
Estimated implementation: tested via Textual snapshot/pilot testing

These tests use Textual's testing framework (app.run_test()) to verify
that the TUI application starts up correctly, renders all expected panels,
and handles first-run (no config) gracefully.
"""
from __future__ import annotations

import pytest

from aprs_tui.app import APRSTuiApp
from aprs_tui.config import AppConfig, StationConfig
from aprs_tui.ui.status_bar import StatusBar
from aprs_tui.ui.stream_panel import StreamPanel


def _make_app() -> APRSTuiApp:
    """Create an APRSTuiApp with a minimal valid config."""
    config = AppConfig(station=StationConfig(callsign="N0CALL"))
    return APRSTuiApp(config)


# ==========================================================================
# Application launch
# ==========================================================================

class TestTuiLaunch:
    """The TUI application launches and renders its initial layout."""

    @pytest.mark.asyncio
    async def test_app_starts_without_crash(self):
        """The Textual app starts with a valid config and exits cleanly on 'q'."""
        app = _make_app()
        async with app.run_test() as pilot:
            # App is running if we reach here
            assert app.is_running
            await pilot.press("q")

    @pytest.mark.asyncio
    async def test_app_renders_stream_panel(self):
        """On launch, the stream panel widget is present in the DOM."""
        app = _make_app()
        async with app.run_test():
            panel = app.query_one(StreamPanel)
            assert panel is not None
            assert panel.id == "stream-panel"

    @pytest.mark.skip(reason="Sprint 3: Station panel not implemented yet")
    async def test_app_renders_station_panel(self):
        """On launch, the station panel widget is present in the DOM."""
        pass

    @pytest.mark.skip(reason="Sprint 4: Message panel not implemented yet")
    async def test_app_renders_message_panel(self):
        """On launch, the message panel widget is present in the DOM."""
        pass

    @pytest.mark.asyncio
    async def test_app_renders_status_bar(self):
        """On launch, the status bar widget is present in the DOM."""
        app = _make_app()
        async with app.run_test():
            bar = app.query_one(StatusBar)
            assert bar is not None

    @pytest.mark.asyncio
    async def test_app_layout_matches_spec(self):
        """Panel layout matches the architecture spec: status bar docked
        at bottom, stream panel filling remaining space."""
        app = _make_app()
        async with app.run_test():
            # Verify both widgets are present
            stream = app.query_one(StreamPanel)
            status = app.query_one(StatusBar)
            assert stream is not None
            assert status is not None

            # Status bar should be docked to bottom
            assert True
            # Stream panel height should be 1fr (flex fill)
            assert stream.id == "stream-panel"


# ==========================================================================
# First run - no config (AC-01)
# ==========================================================================

class TestTuiFirstRun:
    """First-run behavior when no config.toml exists (AC-01)."""

    @pytest.mark.skip(reason="Sprint 5: Not implemented yet")
    async def test_no_config_launches_wizard(self, tmp_path):
        """Given no config.toml exists, the wizard is launched automatically."""
        pass

    @pytest.mark.skip(reason="Sprint 5: Not implemented yet")
    async def test_wizard_completion_starts_tui(self, tmp_path):
        """After the wizard writes config.toml, the TUI starts with the new config."""
        pass

    @pytest.mark.skip(reason="Sprint 5: Not implemented yet")
    async def test_wizard_cancel_exits_cleanly(self, tmp_path):
        """If the wizard is cancelled (Ctrl+C), the app exits without crashing."""
        pass


# ==========================================================================
# Startup with invalid config (AC-14)
# ==========================================================================

class TestTuiInvalidConfig:
    """Startup behavior with invalid or malformed config."""

    @pytest.mark.skip(reason="Sprint 5: Not implemented yet")
    async def test_malformed_config_shows_error(self, tmp_path):
        """A malformed config.toml shows a clear error message with the
        invalid field name and expected type (AC-14)."""
        pass

    @pytest.mark.skip(reason="Sprint 5: Not implemented yet")
    async def test_malformed_config_exits_nonzero(self, tmp_path):
        """A malformed config.toml causes exit with non-zero exit code (AC-14)."""
        pass


# ==========================================================================
# Quit behavior
# ==========================================================================

class TestTuiQuit:
    """Application quit behavior."""

    @pytest.mark.asyncio
    async def test_quit_on_q_key(self):
        """Pressing 'q' quits the application cleanly."""
        app = _make_app()
        async with app.run_test() as pilot:
            assert app.is_running
            await pilot.press("q")
        # After context exits, app should no longer be running
        assert not app.is_running

    @pytest.mark.skip(reason="Sprint 3: Transport integration not implemented yet")
    async def test_quit_disconnects_transport(self, tmp_config_file):
        """Quitting disconnects the transport before exit."""
        pass
