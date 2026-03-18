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

import asyncio

import pytest

from aprs_tui.transport import ConnectionState, KissTcpTransport

# ==========================================================================
# Connection lifecycle
# ==========================================================================

class TestKissTcpConnect:
    """KISS TCP transport connection and disconnection."""

    async def test_connect_to_server(self, kiss_tcp_server):
        """Transport connects to the mock KISS TCP server on the given host:port."""
        transport = KissTcpTransport(kiss_tcp_server["host"], kiss_tcp_server["port"])
        await transport.connect()
        try:
            assert transport.state == ConnectionState.CONNECTED
        finally:
            await transport.disconnect()

    async def test_connect_sets_connected_true(self, kiss_tcp_server):
        """After successful connect, is_connected() returns True."""
        transport = KissTcpTransport(kiss_tcp_server["host"], kiss_tcp_server["port"])
        assert not transport.is_connected
        await transport.connect()
        try:
            assert transport.is_connected
        finally:
            await transport.disconnect()

    async def test_disconnect(self, kiss_tcp_server):
        """disconnect() closes the connection; is_connected() returns False."""
        transport = KissTcpTransport(kiss_tcp_server["host"], kiss_tcp_server["port"])
        await transport.connect()
        assert transport.is_connected
        await transport.disconnect()
        assert not transport.is_connected
        assert transport.state == ConnectionState.DISCONNECTED

    async def test_connect_to_unreachable_host(self):
        """Connecting to a host that is not listening raises a connection error."""
        transport = KissTcpTransport("127.0.0.1", 1)  # Port 1 is unlikely to be open
        with pytest.raises(ConnectionError):
            await transport.connect()
        assert transport.state == ConnectionState.FAILED

    async def test_connect_timeout(self):
        """Connection attempt times out if server does not respond within threshold."""
        # Use a non-routable address to trigger a timeout
        transport = KissTcpTransport("192.0.2.1", 8001)
        with pytest.raises(ConnectionError):
            await transport.connect()

    async def test_display_name(self, kiss_tcp_server):
        """display_name property returns a human-readable string like 'KISS TCP 127.0.0.1:8001'."""
        transport = KissTcpTransport(kiss_tcp_server["host"], kiss_tcp_server["port"])
        expected = f"KISS TCP {kiss_tcp_server['host']}:{kiss_tcp_server['port']}"
        assert transport.display_name == expected


# ==========================================================================
# Receiving KISS frames
# ==========================================================================

class TestKissTcpReceive:
    """Reading KISS frames from the TCP connection."""

    async def test_receive_single_frame(
        self, kiss_tcp_server, sample_kiss_frames, sample_ax25_frames
    ):
        """A single KISS frame sent by the server is received and deframed."""
        transport = KissTcpTransport(kiss_tcp_server["host"], kiss_tcp_server["port"])
        await transport.connect()
        try:
            # Server sends one KISS frame
            await kiss_tcp_server["send"](sample_kiss_frames["position"])
            frame = await asyncio.wait_for(transport.read_frame(), timeout=2.0)
            assert frame == sample_ax25_frames["position"]
        finally:
            await transport.disconnect()

    async def test_receive_multiple_frames(
        self, kiss_tcp_server, sample_kiss_frames, sample_ax25_frames
    ):
        """Multiple concatenated KISS frames are each received individually."""
        transport = KissTcpTransport(kiss_tcp_server["host"], kiss_tcp_server["port"])
        await transport.connect()
        try:
            # Send both frames concatenated in one TCP write
            combined = sample_kiss_frames["position"] + sample_kiss_frames["message"]
            await kiss_tcp_server["send"](combined)

            frame1 = await asyncio.wait_for(transport.read_frame(), timeout=2.0)
            frame2 = await asyncio.wait_for(transport.read_frame(), timeout=2.0)

            assert frame1 == sample_ax25_frames["position"]
            assert frame2 == sample_ax25_frames["message"]
        finally:
            await transport.disconnect()

    async def test_receive_fragmented_frame(
        self, kiss_tcp_server, sample_kiss_frames, sample_ax25_frames
    ):
        """A KISS frame split across two TCP reads is reassembled correctly."""
        transport = KissTcpTransport(kiss_tcp_server["host"], kiss_tcp_server["port"])
        await transport.connect()
        try:
            kiss_data = sample_kiss_frames["position"]
            mid = len(kiss_data) // 2

            # Send first half
            await kiss_tcp_server["send"](kiss_data[:mid])
            # Small delay to ensure separate TCP reads
            await asyncio.sleep(0.05)
            # Send second half
            await kiss_tcp_server["send"](kiss_data[mid:])

            frame = await asyncio.wait_for(transport.read_frame(), timeout=2.0)
            assert frame == sample_ax25_frames["position"]
        finally:
            await transport.disconnect()

    async def test_receive_detects_disconnect(self):
        """When the server closes the connection, read_frame() raises ConnectionError."""
        # Spin up a minimal server that accepts then immediately closes
        accepted = asyncio.Event()
        client_writer_ref: list[asyncio.StreamWriter] = []

        async def handle(reader, writer):
            client_writer_ref.append(writer)
            accepted.set()

        server = await asyncio.start_server(handle, "127.0.0.1", 0)
        host, port = server.sockets[0].getsockname()

        transport = KissTcpTransport(host, port)
        await transport.connect()

        # Wait for server to see the client
        await asyncio.wait_for(accepted.wait(), timeout=2.0)

        # Close the server-side of the connection
        client_writer_ref[0].close()
        await client_writer_ref[0].wait_closed()

        with pytest.raises(ConnectionError):
            await asyncio.wait_for(transport.read_frame(), timeout=5.0)

        await transport.disconnect()
        server.close()
        await server.wait_closed()


# ==========================================================================
# Sending KISS frames
# ==========================================================================

class TestKissTcpSend:
    """Sending KISS-framed data to the TCP server."""

    async def test_send_frame(self, kiss_tcp_server, sample_ax25_frames, sample_kiss_frames):
        """send_frame() wraps AX.25 data in KISS framing and sends via TCP."""
        transport = KissTcpTransport(kiss_tcp_server["host"], kiss_tcp_server["port"])
        await transport.connect()
        try:
            await transport.write_frame(sample_ax25_frames["position"])
            # Read from the server side and verify KISS framing
            received = await asyncio.wait_for(
                kiss_tcp_server["receive"](), timeout=2.0
            )
            assert received == sample_kiss_frames["position"]
        finally:
            await transport.disconnect()

    async def test_send_frame_received_by_server(self, kiss_tcp_server, sample_ax25_frames):
        """Data sent via send_frame() is received by the mock server."""
        transport = KissTcpTransport(kiss_tcp_server["host"], kiss_tcp_server["port"])
        await transport.connect()
        try:
            await transport.write_frame(sample_ax25_frames["message"])
            received = await asyncio.wait_for(
                kiss_tcp_server["receive"](), timeout=2.0
            )
            # Verify we received something non-empty
            assert len(received) > 0
            # Verify it starts and ends with FEND (0xC0)
            assert received[0] == 0xC0
            assert received[-1] == 0xC0
        finally:
            await transport.disconnect()

    async def test_send_when_disconnected_raises(self):
        """Sending on a disconnected transport raises an error."""
        transport = KissTcpTransport("127.0.0.1", 8001)
        with pytest.raises(ConnectionError):
            await transport.write_frame(b"\x00\x01\x02")


# ==========================================================================
# Full pipeline integration (Issue #7)
# ==========================================================================

class TestKissTcpPipeline:
    """End-to-end: TCP receive -> KISS deframe -> AX.25 decode -> aprslib parse."""

    async def test_full_pipeline_position_packet(
        self, kiss_tcp_server, sample_kiss_frames, sample_ax25_frames
    ):
        """A KISS-framed position packet received over TCP is decoded to APRSPacket
        with info_type='position' and valid lat/lon."""
        from aprs_tui.protocol.ax25 import ax25_decode, ax25_to_text
        from aprs_tui.protocol.decoder import decode_packet

        transport = KissTcpTransport(kiss_tcp_server["host"], kiss_tcp_server["port"])
        await transport.connect()
        try:
            await kiss_tcp_server["send"](sample_kiss_frames["position"])
            raw_frame = await asyncio.wait_for(transport.read_frame(), timeout=2.0)

            # AX.25 decode
            ax25 = ax25_decode(raw_frame)
            text_line = ax25_to_text(ax25)

            # APRS decode
            pkt = decode_packet(text_line)
            assert pkt.info_type == "position"
            assert pkt.latitude is not None
            assert pkt.longitude is not None
            assert pkt.source == "W3ADO-1"
            assert pkt.parse_error is None
        finally:
            await transport.disconnect()

    async def test_full_pipeline_message_packet(
        self, kiss_tcp_server, sample_kiss_frames, sample_ax25_frames
    ):
        """A KISS-framed message packet is decoded with correct addressee and text."""
        from aprs_tui.protocol.ax25 import ax25_decode, ax25_to_text
        from aprs_tui.protocol.decoder import decode_packet

        transport = KissTcpTransport(kiss_tcp_server["host"], kiss_tcp_server["port"])
        await transport.connect()
        try:
            await kiss_tcp_server["send"](sample_kiss_frames["message"])
            raw_frame = await asyncio.wait_for(transport.read_frame(), timeout=2.0)

            ax25 = ax25_decode(raw_frame)
            text_line = ax25_to_text(ax25)

            pkt = decode_packet(text_line)
            assert pkt.info_type == "message"
            assert pkt.addressee == "N0CALL"
            assert pkt.message_text == "Hello"
            assert pkt.message_id == "001"
            assert pkt.parse_error is None
        finally:
            await transport.disconnect()

    async def test_full_pipeline_parse_error(self, kiss_tcp_server, sample_ax25_frames):
        """A malformed packet passes through the pipeline without crashing;
        APRSPacket has parse_error set."""
        from aprs_tui.protocol.ax25 import ax25_decode, ax25_to_text, encode_address
        from aprs_tui.protocol.decoder import decode_packet
        from aprs_tui.protocol.kiss import kiss_frame

        # Build a valid AX.25 frame with an unparseable APRS info field
        dest = encode_address("APRS", 0)
        src = encode_address("N0CALL", 0, last=True)
        info = b"!!!INVALID_APRS_DATA!!!"
        ax25_binary = dest + src + bytes([0x03, 0xF0]) + info

        # Wrap in KISS and send
        kiss_data = kiss_frame(ax25_binary)
        transport = KissTcpTransport(kiss_tcp_server["host"], kiss_tcp_server["port"])
        await transport.connect()
        try:
            await kiss_tcp_server["send"](kiss_data)
            raw_frame = await asyncio.wait_for(transport.read_frame(), timeout=2.0)

            ax25 = ax25_decode(raw_frame)
            text_line = ax25_to_text(ax25)

            # Should not crash
            pkt = decode_packet(text_line)
            assert pkt.parse_error is not None
            assert pkt.raw == text_line
        finally:
            await transport.disconnect()
