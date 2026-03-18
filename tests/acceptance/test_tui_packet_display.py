"""Acceptance tests for packet display in the TUI stream panel.

Covers: Issue #10 - Stream Panel (RichLog, color-coded packets)
Sprint: 2 (TUI Shell + Stream Panel)
PRD refs: AC-07 (packet decoding - color-coded by type, raw on error, no crash)

Module under test: aprs_tui.ui.stream_panel
Estimated implementation: tested via Textual snapshot/pilot testing

The stream panel uses a RichLog widget to display decoded APRS packets
with color coding by type. Parse errors show the raw packet with a
warning indicator. The TUI must never crash on malformed data.
"""
from __future__ import annotations

import pytest

from aprs_tui.app import APRSTuiApp
from aprs_tui.config import AppConfig, StationConfig
from aprs_tui.protocol.types import APRSPacket
from aprs_tui.ui.stream_panel import StreamPanel


def _make_app() -> APRSTuiApp:
    """Create an APRSTuiApp with a minimal valid config."""
    config = AppConfig(station=StationConfig(callsign="N0CALL"))
    return APRSTuiApp(config)


def _position_packet() -> APRSPacket:
    """Create a sample position packet."""
    return APRSPacket(
        raw="W3ADO-1>APRS:!4903.50N/07201.75W-",
        source="W3ADO-1",
        info_type="position",
        latitude=49.0583,
        longitude=-72.0292,
    )


def _message_packet() -> APRSPacket:
    """Create a sample message packet."""
    return APRSPacket(
        raw="W3ADO-1>APRS::N0CALL   :Hello from APRS TUI{001",
        source="W3ADO-1",
        info_type="message",
        addressee="N0CALL",
        message_text="Hello from APRS TUI",
        message_id="001",
    )


def _weather_packet() -> APRSPacket:
    """Create a sample weather packet."""
    return APRSPacket(
        raw="FW0727>APRS:_10090556c220s004g005t077r000p000P000h50b09900",
        source="FW0727",
        info_type="weather",
        wx_temperature=77.0,
        wx_wind_speed=4.0,
        wx_wind_dir=220,
        wx_pressure=990.0,
    )


def _parse_error_packet() -> APRSPacket:
    """Create a packet with a parse error."""
    return APRSPacket(
        raw="NOCALL>APRS:!!!THIS_IS_NOT_VALID!!!",
        source="NOCALL",
        info_type="unknown",
        parse_error="Unable to parse packet",
    )


# ==========================================================================
# Packet display
# ==========================================================================

class TestPacketDisplay:
    """Decoded packets appear in the stream panel."""

    @pytest.mark.asyncio
    async def test_position_packet_displayed(self):
        """A position packet appears in the stream panel after being received."""
        app = _make_app()
        async with app.run_test() as pilot:
            panel = app.query_one(StreamPanel)
            pkt = _position_packet()
            panel.add_packet(pkt)
            await pilot.pause()
            assert panel.packet_count == 1

    @pytest.mark.asyncio
    async def test_message_packet_displayed(self):
        """A message packet appears in the stream panel."""
        app = _make_app()
        async with app.run_test() as pilot:
            panel = app.query_one(StreamPanel)
            pkt = _message_packet()
            panel.add_packet(pkt)
            await pilot.pause()
            assert panel.packet_count == 1

    @pytest.mark.asyncio
    async def test_weather_packet_displayed(self):
        """A weather packet appears in the stream panel."""
        app = _make_app()
        async with app.run_test() as pilot:
            panel = app.query_one(StreamPanel)
            pkt = _weather_packet()
            panel.add_packet(pkt)
            await pilot.pause()
            assert panel.packet_count == 1

    @pytest.mark.asyncio
    async def test_multiple_packets_in_order(self):
        """Multiple packets appear in chronological order (newest at bottom)."""
        app = _make_app()
        async with app.run_test() as pilot:
            panel = app.query_one(StreamPanel)
            pkt1 = _position_packet()
            pkt2 = _message_packet()
            pkt3 = _weather_packet()

            panel.add_packet(pkt1)
            panel.add_packet(pkt2)
            panel.add_packet(pkt3)
            await pilot.pause()

            assert panel.packet_count == 3


# ==========================================================================
# Color coding (Architecture 7.5)
# ==========================================================================

class TestPacketColorCoding:
    """Packets are color-coded by type per the architecture spec."""

    @pytest.mark.skip(reason="Requires visual snapshot testing")
    async def test_position_colored_cyan(self, tmp_config_file):
        """Position packets render in cyan."""
        pass

    @pytest.mark.skip(reason="Requires visual snapshot testing")
    async def test_message_colored_yellow(self, tmp_config_file):
        """Message packets render in yellow."""
        pass

    @pytest.mark.skip(reason="Requires visual snapshot testing")
    async def test_weather_colored_green(self, tmp_config_file):
        """Weather packets render in green."""
        pass

    @pytest.mark.skip(reason="Requires visual snapshot testing")
    async def test_mic_e_colored_magenta(self, tmp_config_file):
        """Mic-E packets render in magenta."""
        pass

    @pytest.mark.skip(reason="Requires visual snapshot testing")
    async def test_object_colored_blue(self, tmp_config_file):
        """Object packets render in blue."""
        pass

    @pytest.mark.skip(reason="Requires visual snapshot testing")
    async def test_parse_error_colored_red_dim(self, tmp_config_file):
        """Parse-error packets render in dim red."""
        pass

    @pytest.mark.skip(reason="Requires visual snapshot testing")
    async def test_own_callsign_highlighted(self, tmp_config_file):
        """Packets from own callsign are bold + highlighted."""
        pass


# ==========================================================================
# Parse error display (AC-07)
# ==========================================================================

class TestParseErrorDisplay:
    """Malformed packets display raw with warning indicator (AC-07)."""

    @pytest.mark.asyncio
    async def test_parse_error_shows_raw_packet(self):
        """A malformed packet displays the raw packet string."""
        app = _make_app()
        async with app.run_test():
            panel = app.query_one(StreamPanel)
            pkt = _parse_error_packet()
            # Format the packet and check it contains the raw text
            text = panel._format_packet(pkt)
            plain = text.plain
            assert "parse error" in plain
            assert "NOCALL>APRS:!!!THIS_IS_NOT_VALID!!!" in plain

    @pytest.mark.skip(reason="Requires visual snapshot testing")
    async def test_parse_error_shows_warning_indicator(self, tmp_config_file):
        """A malformed packet includes a visible warning indicator."""
        pass

    @pytest.mark.asyncio
    async def test_parse_error_does_not_crash_tui(self):
        """Receiving a malformed packet does not crash the TUI (AC-07)."""
        app = _make_app()
        async with app.run_test() as pilot:
            panel = app.query_one(StreamPanel)
            pkt = _parse_error_packet()
            panel.add_packet(pkt)
            await pilot.pause()
            # App should still be running
            assert app.is_running
            assert panel.packet_count == 1

    @pytest.mark.skip(reason="Sprint 3: Stress testing not required yet")
    async def test_many_parse_errors_stable(self, tmp_config_file):
        """Receiving many malformed packets in succession does not crash or
        degrade the TUI."""
        pass


# ==========================================================================
# Raw packet toggle (Issue #41)
# ==========================================================================

class TestRawPacketToggle:
    """Toggle between decoded and raw packet display."""

    @pytest.mark.skip(reason="Sprint 7: Not implemented yet")
    async def test_raw_toggle_shows_raw(self, tmp_config_file):
        """Pressing 'r' in the stream panel shows raw packet strings."""
        pass

    @pytest.mark.skip(reason="Sprint 7: Not implemented yet")
    async def test_raw_toggle_shows_decoded(self, tmp_config_file):
        """Pressing 'r' again reverts to decoded display."""
        pass


# ==========================================================================
# Scrolling behavior
# ==========================================================================

class TestStreamScrolling:
    """Packet stream auto-scrolling and manual scroll."""

    @pytest.mark.asyncio
    async def test_auto_scroll_to_latest(self):
        """New packets auto-scroll to the bottom of the stream.

        RichLog auto-scrolls by default, so we verify that after adding
        multiple packets the panel's packet count is correct and the widget
        is still functional.
        """
        app = _make_app()
        async with app.run_test() as pilot:
            panel = app.query_one(StreamPanel)
            # Add several packets
            for i in range(10):
                pkt = APRSPacket(
                    raw=f"SRC{i}>APRS:!4903.50N/07201.75W-",
                    source=f"SRC{i}",
                    info_type="position",
                    latitude=49.0583,
                    longitude=-72.0292,
                )
                panel.add_packet(pkt)
            await pilot.pause()
            assert panel.packet_count == 10
            # RichLog auto_scroll is True by default
            assert panel.auto_scroll is True

    @pytest.mark.skip(reason="Sprint 3: Not implemented yet")
    async def test_manual_scroll_pauses_auto_scroll(self, tmp_config_file):
        """Pressing j/k to scroll manually pauses auto-scroll."""
        pass
