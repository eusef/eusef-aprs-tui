"""Integration tests for KISS-over-TCP transport (transport/kiss_tcp.py).

Covers: Issue #2 - Transport ABC + KISS TCP implementation
        Issue #7 - Integration: TCP connect, KISS deframe, AX.25 decode, APRS parse
Sprint: 1 (Foundation)
PRD refs: AC-02 (KISS TCP connection - connect, status bar, decoded packets)

Module under test: aprs_tui.transport.kiss_tcp
Fixtures: kiss_tcp_server (local mock KISS TCP server)
Estimated implementation: ~100-150 lines

These tests verify the full KISS TCP pipeline: TCP connection, KISS deframing,
and frame delivery. Uses a local TCP server (kiss_tcp_server fixture) that
sends real KISS-framed data.
"""
from __future__ import annotations

import pytest


# ==========================================================================
# Connection lifecycle
# ==========================================================================

class TestKissTcpConnect:
    """KISS TCP transport connection and disconnection."""

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    async def test_connect_to_server(self, kiss_tcp_server):
        """Transport connects to the mock KISS TCP server on the given host:port."""
        pass

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    async def test_connect_sets_connected_true(self, kiss_tcp_server):
        """After successful connect, is_connected() returns True."""
        pass

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    async def test_disconnect(self, kiss_tcp_server):
        """disconnect() closes the connection; is_connected() returns False."""
        pass

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    async def test_connect_to_unreachable_host(self):
        """Connecting to a host that is not listening raises a connection error."""
        pass

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    async def test_connect_timeout(self):
        """Connection attempt times out if server does not respond within threshold."""
        pass

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    async def test_display_name(self, kiss_tcp_server):
        """display_name property returns a human-readable string like 'KISS TCP 127.0.0.1:8001'."""
        pass


# ==========================================================================
# Receiving KISS frames
# ==========================================================================

class TestKissTcpReceive:
    """Reading KISS frames from the TCP connection."""

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    async def test_receive_single_frame(self, kiss_tcp_server, sample_kiss_frames):
        """A single KISS frame sent by the server is received and deframed."""
        pass

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    async def test_receive_multiple_frames(self, kiss_tcp_server, sample_kiss_frames):
        """Multiple concatenated KISS frames are each received individually."""
        pass

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    async def test_receive_fragmented_frame(self, kiss_tcp_server, sample_kiss_frames):
        """A KISS frame split across two TCP reads is reassembled correctly."""
        pass

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    async def test_receive_detects_disconnect(self, kiss_tcp_server):
        """When the server closes the connection, read_frame() signals disconnect."""
        pass


# ==========================================================================
# Sending KISS frames
# ==========================================================================

class TestKissTcpSend:
    """Sending KISS-framed data to the TCP server."""

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    async def test_send_frame(self, kiss_tcp_server, sample_ax25_frames):
        """send_frame() wraps AX.25 data in KISS framing and sends via TCP."""
        pass

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    async def test_send_frame_received_by_server(self, kiss_tcp_server, sample_ax25_frames):
        """Data sent via send_frame() is received by the mock server."""
        pass

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    async def test_send_when_disconnected_raises(self):
        """Sending on a disconnected transport raises an error."""
        pass


# ==========================================================================
# Full pipeline integration (Issue #7)
# ==========================================================================

class TestKissTcpPipeline:
    """End-to-end: TCP receive -> KISS deframe -> AX.25 decode -> aprslib parse."""

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    async def test_full_pipeline_position_packet(self, kiss_tcp_server, sample_kiss_frames):
        """A KISS-framed position packet received over TCP is decoded to APRSPacket
        with info_type='position' and valid lat/lon."""
        pass

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    async def test_full_pipeline_message_packet(self, kiss_tcp_server, sample_kiss_frames):
        """A KISS-framed message packet is decoded with correct addressee and text."""
        pass

    @pytest.mark.skip(reason="Sprint 1: Not implemented yet")
    async def test_full_pipeline_parse_error(self, kiss_tcp_server):
        """A malformed packet passes through the pipeline without crashing;
        APRSPacket has parse_error set."""
        pass
