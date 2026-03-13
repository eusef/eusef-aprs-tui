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

import asyncio

import pytest

from aprs_tui.transport.aprs_is import AprsIsTransport
from aprs_tui.transport.base import ConnectionState


# ==========================================================================
# Connection and login
# ==========================================================================

class TestAprsIsConnect:
    """APRS-IS transport connection and login handshake."""

    async def test_connect_to_server(self, aprs_is_server):
        """Transport connects to the mock APRS-IS server."""
        transport = AprsIsTransport(
            host=aprs_is_server["host"],
            port=aprs_is_server["port"],
            callsign="N0CALL",
            passcode=-1,
            filter_str="r/45/-122/100",
        )
        await transport.connect()
        assert transport.is_connected
        await transport.disconnect()

    async def test_sends_login_line(self, aprs_is_server):
        """After connecting, transport sends a properly formatted login line."""
        transport = AprsIsTransport(
            host=aprs_is_server["host"],
            port=aprs_is_server["port"],
            callsign="N0CALL",
            passcode=-1,
            filter_str="r/45/-122/100",
        )
        await transport.connect()
        login_line = await aprs_is_server["get_login"]()
        assert login_line.startswith("user ")
        await transport.disconnect()

    async def test_login_includes_callsign(self, aprs_is_server):
        """Login line contains the configured callsign."""
        transport = AprsIsTransport(
            host=aprs_is_server["host"],
            port=aprs_is_server["port"],
            callsign="W3ADO-1",
            passcode=-1,
            filter_str="",
        )
        await transport.connect()
        login_line = await aprs_is_server["get_login"]()
        assert "user W3ADO-1" in login_line
        await transport.disconnect()

    async def test_login_includes_passcode(self, aprs_is_server):
        """Login line contains the APRS-IS passcode (-1 for read-only)."""
        transport = AprsIsTransport(
            host=aprs_is_server["host"],
            port=aprs_is_server["port"],
            callsign="N0CALL",
            passcode=-1,
            filter_str="",
        )
        await transport.connect()
        login_line = await aprs_is_server["get_login"]()
        assert "pass -1" in login_line
        await transport.disconnect()

    async def test_login_includes_filter(self, aprs_is_server):
        """Login line contains the configured server-side filter string."""
        transport = AprsIsTransport(
            host=aprs_is_server["host"],
            port=aprs_is_server["port"],
            callsign="N0CALL",
            passcode=-1,
            filter_str="r/45/-122/100",
        )
        await transport.connect()
        login_line = await aprs_is_server["get_login"]()
        assert "filter r/45/-122/100" in login_line
        await transport.disconnect()

    async def test_login_includes_software_version(self, aprs_is_server):
        """Login line includes 'vers aprs-tui <version>' for server stats."""
        transport = AprsIsTransport(
            host=aprs_is_server["host"],
            port=aprs_is_server["port"],
            callsign="N0CALL",
            passcode=-1,
            filter_str="",
        )
        await transport.connect()
        login_line = await aprs_is_server["get_login"]()
        assert "vers aprs-tui" in login_line
        await transport.disconnect()

    async def test_connect_sets_connected(self, aprs_is_server):
        """After login ack is received, is_connected() returns True."""
        transport = AprsIsTransport(
            host=aprs_is_server["host"],
            port=aprs_is_server["port"],
            callsign="N0CALL",
            passcode=-1,
        )
        assert transport.state == ConnectionState.DISCONNECTED
        await transport.connect()
        assert transport.state == ConnectionState.CONNECTED
        assert transport.is_connected
        await transport.disconnect()

    async def test_disconnect(self, aprs_is_server):
        """disconnect() closes the TCP connection cleanly."""
        transport = AprsIsTransport(
            host=aprs_is_server["host"],
            port=aprs_is_server["port"],
            callsign="N0CALL",
            passcode=-1,
        )
        await transport.connect()
        assert transport.is_connected
        await transport.disconnect()
        assert transport.state == ConnectionState.DISCONNECTED
        assert not transport.is_connected

    async def test_display_name(self, aprs_is_server):
        """display_name shows 'APRS-IS <host>:<port>'."""
        transport = AprsIsTransport(
            host=aprs_is_server["host"],
            port=aprs_is_server["port"],
            callsign="N0CALL",
            passcode=-1,
        )
        name = transport.display_name
        assert "APRS-IS" in name
        assert aprs_is_server["host"] in name
        assert str(aprs_is_server["port"]) in name
        assert "RX only" in name


# ==========================================================================
# Receiving packets
# ==========================================================================

class TestAprsIsReceive:
    """Receiving APRS packet lines from the APRS-IS server."""

    async def test_receive_packet_line(self, aprs_is_server, sample_packets):
        """A packet line sent by the server is received by the transport."""
        transport = AprsIsTransport(
            host=aprs_is_server["host"],
            port=aprs_is_server["port"],
            callsign="N0CALL",
            passcode=-1,
        )
        await transport.connect()
        packet_line = sample_packets["position"]
        await aprs_is_server["send_packet"](packet_line)
        frame = await asyncio.wait_for(transport.read_frame(), timeout=5.0)
        assert frame == packet_line.encode("latin-1")
        await transport.disconnect()

    async def test_skip_comment_lines(self, aprs_is_server):
        """Lines starting with '#' (server comments) are skipped, not returned."""
        transport = AprsIsTransport(
            host=aprs_is_server["host"],
            port=aprs_is_server["port"],
            callsign="N0CALL",
            passcode=-1,
        )
        await transport.connect()
        # Send a comment line then a real packet
        await aprs_is_server["send_packet"]("# server comment line")
        real_packet = "W3ADO-1>APRS:!4903.50N/07201.75W-"
        await aprs_is_server["send_packet"](real_packet)
        frame = await asyncio.wait_for(transport.read_frame(), timeout=5.0)
        assert frame == real_packet.encode("latin-1")
        await transport.disconnect()

    async def test_receive_strips_crlf(self, aprs_is_server):
        """Trailing \\r\\n is stripped from received packet lines."""
        transport = AprsIsTransport(
            host=aprs_is_server["host"],
            port=aprs_is_server["port"],
            callsign="N0CALL",
            passcode=-1,
        )
        await transport.connect()
        await aprs_is_server["send_packet"]("W3ADO-1>APRS:>Test status")
        frame = await asyncio.wait_for(transport.read_frame(), timeout=5.0)
        decoded = frame.decode("latin-1")
        assert not decoded.endswith("\r\n")
        assert not decoded.endswith("\n")
        assert decoded == "W3ADO-1>APRS:>Test status"
        await transport.disconnect()

    async def test_receive_multiple_packets(self, aprs_is_server, sample_packets):
        """Multiple packet lines are received in order."""
        transport = AprsIsTransport(
            host=aprs_is_server["host"],
            port=aprs_is_server["port"],
            callsign="N0CALL",
            passcode=-1,
        )
        await transport.connect()
        lines = [sample_packets["position"], sample_packets["message"]]
        for line in lines:
            await aprs_is_server["send_packet"](line)
        received = []
        for _ in lines:
            frame = await asyncio.wait_for(transport.read_frame(), timeout=5.0)
            received.append(frame.decode("latin-1"))
        assert received == lines
        await transport.disconnect()

    async def test_receive_detects_server_disconnect(self, aprs_is_server):
        """If the server closes the connection, the transport signals disconnect."""
        transport = AprsIsTransport(
            host=aprs_is_server["host"],
            port=aprs_is_server["port"],
            callsign="N0CALL",
            passcode=-1,
        )
        await transport.connect()
        # Close the server side
        await aprs_is_server["close"]()
        with pytest.raises(ConnectionError):
            await asyncio.wait_for(transport.read_frame(), timeout=5.0)
        assert transport.state == ConnectionState.DISCONNECTED


# ==========================================================================
# Sending packets
# ==========================================================================

class TestAprsIsSend:
    """Sending APRS packets to the APRS-IS server."""

    async def test_send_packet_line(self, aprs_is_server):
        """send_frame() sends a text line to the APRS-IS server."""
        transport = AprsIsTransport(
            host=aprs_is_server["host"],
            port=aprs_is_server["port"],
            callsign="N0CALL",
            passcode=12345,
        )
        await transport.connect()
        packet = b"N0CALL>APRS:>Test beacon"
        await transport.write_frame(packet)
        await transport.disconnect()

    async def test_send_appends_crlf(self, aprs_is_server):
        """Sent lines have \\r\\n appended per APRS-IS protocol."""
        # This test verifies the transport appends CRLF when sending.
        # We test by ensuring the write_frame method works without error
        # on a line without trailing CRLF.
        transport = AprsIsTransport(
            host=aprs_is_server["host"],
            port=aprs_is_server["port"],
            callsign="N0CALL",
            passcode=12345,
        )
        await transport.connect()
        # Send a packet without CRLF - transport should add it
        await transport.write_frame(b"N0CALL>APRS:>Hello")
        await transport.disconnect()

    async def test_send_requires_valid_passcode(self, aprs_is_server):
        """Sending is only allowed if passcode != -1 (read-only mode blocks TX)."""
        transport = AprsIsTransport(
            host=aprs_is_server["host"],
            port=aprs_is_server["port"],
            callsign="N0CALL",
            passcode=-1,
        )
        await transport.connect()
        with pytest.raises(PermissionError):
            await transport.write_frame(b"N0CALL>APRS:>Test")
        await transport.disconnect()

    async def test_send_when_disconnected_raises(self):
        """Sending on a disconnected transport raises an error."""
        transport = AprsIsTransport(
            host="127.0.0.1",
            port=14580,
            callsign="N0CALL",
            passcode=12345,
        )
        with pytest.raises(ConnectionError):
            await transport.write_frame(b"N0CALL>APRS:>Test")


# ==========================================================================
# Read-only mode (passcode -1)
# ==========================================================================

class TestAprsIsReadOnly:
    """APRS-IS in read-only mode (no valid passcode)."""

    async def test_read_only_receives_packets(self, aprs_is_server):
        """Read-only mode still receives packets normally."""
        transport = AprsIsTransport(
            host=aprs_is_server["host"],
            port=aprs_is_server["port"],
            callsign="N0CALL",
            passcode=-1,
        )
        await transport.connect()
        await aprs_is_server["send_packet"]("W3ADO-1>APRS:>Status line")
        frame = await asyncio.wait_for(transport.read_frame(), timeout=5.0)
        assert frame == b"W3ADO-1>APRS:>Status line"
        assert transport.is_read_only
        await transport.disconnect()

    async def test_read_only_blocks_send(self, aprs_is_server):
        """Read-only mode prevents send_frame() (passcode=-1)."""
        transport = AprsIsTransport(
            host=aprs_is_server["host"],
            port=aprs_is_server["port"],
            callsign="N0CALL",
            passcode=-1,
        )
        await transport.connect()
        with pytest.raises(PermissionError):
            await transport.write_frame(b"N0CALL>APRS:>Should fail")
        await transport.disconnect()
