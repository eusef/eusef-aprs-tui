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


# ==========================================================================
# Application launch
# ==========================================================================

class TestTuiLaunch:
    """The TUI application launches and renders its initial layout."""

    @pytest.mark.skip(reason="Sprint 2: Not implemented yet")
    async def test_app_starts_without_crash(self, tmp_config_file):
        """The Textual app starts with a valid config and exits cleanly on 'q'."""
        pass

    @pytest.mark.skip(reason="Sprint 2: Not implemented yet")
    async def test_app_renders_stream_panel(self, tmp_config_file):
        """On launch, the stream panel widget is present in the DOM."""
        pass

    @pytest.mark.skip(reason="Sprint 2: Not implemented yet")
    async def test_app_renders_station_panel(self, tmp_config_file):
        """On launch, the station panel widget is present in the DOM."""
        pass

    @pytest.mark.skip(reason="Sprint 2: Not implemented yet")
    async def test_app_renders_message_panel(self, tmp_config_file):
        """On launch, the message panel widget is present in the DOM."""
        pass

    @pytest.mark.skip(reason="Sprint 2: Not implemented yet")
    async def test_app_renders_status_bar(self, tmp_config_file):
        """On launch, the status bar widget is present in the DOM."""
        pass

    @pytest.mark.skip(reason="Sprint 2: Not implemented yet")
    async def test_app_layout_matches_spec(self, tmp_config_file):
        """Panel layout matches the architecture spec: status bar on top,
        stream and station panels in the middle, message panel at bottom."""
        pass


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

    @pytest.mark.skip(reason="Sprint 2: Not implemented yet")
    async def test_malformed_config_shows_error(self, tmp_path):
        """A malformed config.toml shows a clear error message with the
        invalid field name and expected type (AC-14)."""
        pass

    @pytest.mark.skip(reason="Sprint 2: Not implemented yet")
    async def test_malformed_config_exits_nonzero(self, tmp_path):
        """A malformed config.toml causes exit with non-zero exit code (AC-14)."""
        pass


# ==========================================================================
# Quit behavior
# ==========================================================================

class TestTuiQuit:
    """Application quit behavior."""

    @pytest.mark.skip(reason="Sprint 2: Not implemented yet")
    async def test_quit_on_q_key(self, tmp_config_file):
        """Pressing 'q' quits the application cleanly."""
        pass

    @pytest.mark.skip(reason="Sprint 2: Not implemented yet")
    async def test_quit_disconnects_transport(self, tmp_config_file):
        """Quitting disconnects the transport before exit."""
        pass
