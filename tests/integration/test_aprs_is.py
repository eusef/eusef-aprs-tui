"""Integration tests for APRS-IS transport (transport/aprs_is.py).

Covers: Issue #34 - APRS-IS async transport (custom, not aprslib.IS)
Sprint: 7 (APRS-IS + Discovery + Polish)
PRD refs: AC-05 (APRS-IS connection - connect, filtered packets, status bar)
          ADR-8 (custom async client, not wrapping aprslib.IS)

Module under test: aprs_tui.transport.aprs_is
Fixtures: aprs_is_server (local mock APRS-IS server)
Estimated implementation: ~100 lines (lightweight async TCP client)

APRS-IS protocol:
  1. Server sends greeting banner (# line)
  2. Client sends login: "user CALL pass CODE vers NAME VER filter SPEC\\r\\n"
  3. Server responds with login ack (# logresp ...)
  4. Server sends packet lines; client skips lines starting with #
  5. Client can send packets as text lines
"""
from __future__ import annotations

import pytest


# ==========================================================================
# Connection and login
# ==========================================================================

class TestAprsIsConnect:
    """APRS-IS transport connection and login handshake."""

    @pytest.mark.skip(reason="Sprint 7: Not implemented yet")
    async def test_connect_to_server(self, aprs_is_server):
        """Transport connects to the mock APRS-IS server."""
        pass

    @pytest.mark.skip(reason="Sprint 7: Not implemented yet")
    async def test_sends_login_line(self, aprs_is_server):
        """After connecting, transport sends a properly formatted login line."""
        pass

    @pytest.mark.skip(reason="Sprint 7: Not implemented yet")
    async def test_login_includes_callsign(self, aprs_is_server):
        """Login line contains the configured callsign."""
        pass

    @pytest.mark.skip(reason="Sprint 7: Not implemented yet")
    async def test_login_includes_passcode(self, aprs_is_server):
        """Login line contains the APRS-IS passcode (-1 for read-only)."""
        pass

    @pytest.mark.skip(reason="Sprint 7: Not implemented yet")
    async def test_login_includes_filter(self, aprs_is_server):
        """Login line contains the configured server-side filter string."""
        pass

    @pytest.mark.skip(reason="Sprint 7: Not implemented yet")
    async def test_login_includes_software_version(self, aprs_is_server):
        """Login line includes 'vers aprs-tui <version>' for server stats."""
        pass

    @pytest.mark.skip(reason="Sprint 7: Not implemented yet")
    async def test_connect_sets_connected(self, aprs_is_server):
        """After login ack is received, is_connected() returns True."""
        pass

    @pytest.mark.skip(reason="Sprint 7: Not implemented yet")
    async def test_disconnect(self, aprs_is_server):
        """disconnect() closes the TCP connection cleanly."""
        pass

    @pytest.mark.skip(reason="Sprint 7: Not implemented yet")
    async def test_display_name(self, aprs_is_server):
        """display_name shows 'APRS-IS <host>:<port>'."""
        pass


# ==========================================================================
# Receiving packets
# ==========================================================================

class TestAprsIsReceive:
    """Receiving APRS packet lines from the APRS-IS server."""

    @pytest.mark.skip(reason="Sprint 7: Not implemented yet")
    async def test_receive_packet_line(self, aprs_is_server, sample_packets):
        """A packet line sent by the server is received by the transport."""
        pass

    @pytest.mark.skip(reason="Sprint 7: Not implemented yet")
    async def test_skip_comment_lines(self, aprs_is_server):
        """Lines starting with '#' (server comments) are skipped, not returned."""
        pass

    @pytest.mark.skip(reason="Sprint 7: Not implemented yet")
    async def test_receive_strips_crlf(self, aprs_is_server):
        """Trailing \\r\\n is stripped from received packet lines."""
        pass

    @pytest.mark.skip(reason="Sprint 7: Not implemented yet")
    async def test_receive_multiple_packets(self, aprs_is_server, sample_packets):
        """Multiple packet lines are received in order."""
        pass

    @pytest.mark.skip(reason="Sprint 7: Not implemented yet")
    async def test_receive_detects_server_disconnect(self, aprs_is_server):
        """If the server closes the connection, the transport signals disconnect."""
        pass


# ==========================================================================
# Sending packets
# ==========================================================================

class TestAprsIsSend:
    """Sending APRS packets to the APRS-IS server."""

    @pytest.mark.skip(reason="Sprint 7: Not implemented yet")
    async def test_send_packet_line(self, aprs_is_server):
        """send_frame() sends a text line to the APRS-IS server."""
        pass

    @pytest.mark.skip(reason="Sprint 7: Not implemented yet")
    async def test_send_appends_crlf(self, aprs_is_server):
        """Sent lines have \\r\\n appended per APRS-IS protocol."""
        pass

    @pytest.mark.skip(reason="Sprint 7: Not implemented yet")
    async def test_send_requires_valid_passcode(self, aprs_is_server):
        """Sending is only allowed if passcode != -1 (read-only mode blocks TX)."""
        pass

    @pytest.mark.skip(reason="Sprint 7: Not implemented yet")
    async def test_send_when_disconnected_raises(self):
        """Sending on a disconnected transport raises an error."""
        pass


# ==========================================================================
# Read-only mode (passcode -1)
# ==========================================================================

class TestAprsIsReadOnly:
    """APRS-IS in read-only mode (no valid passcode)."""

    @pytest.mark.skip(reason="Sprint 7: Not implemented yet")
    async def test_read_only_receives_packets(self, aprs_is_server):
        """Read-only mode still receives packets normally."""
        pass

    @pytest.mark.skip(reason="Sprint 7: Not implemented yet")
    async def test_read_only_blocks_send(self, aprs_is_server):
        """Read-only mode prevents send_frame() (passcode=-1)."""
        pass
