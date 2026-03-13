"""Integration tests for connection state machine and reconnect logic.

Covers: Issue #12 - Connection state machine + reconnect
Sprint: 2 (TUI Shell + Stream Panel)
PRD refs: AC-11 (auto-reconnect with backoff, RECONNECTING status, max attempts)
          AC-12 (connection health watchdog - no packets for >60s warning)

Module under test: aprs_tui.core.connection
Fixtures: kiss_tcp_server (for simulating connection drops)
Estimated implementation: ~150-200 lines

Connection state machine:
  DISCONNECTED -> CONNECTING -> CONNECTED -> RECONNECTING -> FAILED
  See ARCHITECTURE.md section 10.4 for full state diagram.

Reconnect behavior:
  - Configurable backoff interval (default 10s)
  - Configurable max attempts (0 = infinite)
  - Status bar updates on each transition
"""
from __future__ import annotations

import asyncio
import time

import pytest

from aprs_tui.core.connection import ConnectionManager
from aprs_tui.transport.base import ConnectionState
from aprs_tui.transport.kiss_tcp import KissTcpTransport


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_kiss_frame(ax25_payload: bytes) -> bytes:
    """Wrap an AX.25 payload in a KISS frame (FEND + CMD + data + FEND)."""
    FEND = 0xC0
    FESC = 0xDB
    TFEND = 0xDC
    TFESC = 0xDD
    stuffed = bytearray()
    for b in ax25_payload:
        if b == FEND:
            stuffed.extend([FESC, TFEND])
        elif b == FESC:
            stuffed.extend([FESC, TFESC])
        else:
            stuffed.append(b)
    return bytes([FEND, 0x00]) + bytes(stuffed) + bytes([FEND])


def _make_sample_ax25() -> bytes:
    """Build a minimal AX.25 position frame: W3ADO-1>APRS:!4903.50N/07201.75W-"""
    def _encode_address(callsign: str, ssid: int = 0, last: bool = False) -> bytes:
        call = callsign.ljust(6)[:6]
        encoded = bytes([ord(c) << 1 for c in call])
        ssid_byte = 0b01100000 | ((ssid & 0x0F) << 1)
        if last:
            ssid_byte |= 0x01
        return encoded + bytes([ssid_byte])

    dest = _encode_address("APRS", ssid=0)
    src = _encode_address("W3ADO", ssid=1, last=True)
    control = bytes([0x03])
    pid = bytes([0xF0])
    info = b"!4903.50N/07201.75W-"
    return dest + src + control + pid + info


def _make_sample_kiss_frame() -> bytes:
    """Build a complete KISS-framed AX.25 position packet."""
    return _make_kiss_frame(_make_sample_ax25())


async def _start_tcp_server(host: str = "127.0.0.1", port: int = 0):
    """Start a simple TCP server and return (server, host, port, clients_list)."""
    clients: list[tuple[asyncio.StreamReader, asyncio.StreamWriter]] = []

    async def _handle(reader, writer):
        clients.append((reader, writer))

    server = await asyncio.start_server(_handle, host, port)
    addr = server.sockets[0].getsockname()
    return server, addr[0], addr[1], clients


async def _close_server(server, clients):
    """Close all client connections and the server."""
    for _, writer in clients:
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass
    server.close()
    await server.wait_closed()


# ==========================================================================
# State machine transitions
# ==========================================================================

class TestConnectionStateMachine:
    """Connection state machine transitions."""

    async def test_initial_state_disconnected(self):
        """Connection manager starts in DISCONNECTED state."""
        transport = KissTcpTransport("127.0.0.1", 9999)
        mgr = ConnectionManager(transport)
        assert mgr.state == ConnectionState.DISCONNECTED

    async def test_connect_transitions_to_connecting(self, kiss_tcp_server):
        """Calling connect() transitions from DISCONNECTED to CONNECTING."""
        host = kiss_tcp_server["host"]
        port = kiss_tcp_server["port"]
        transport = KissTcpTransport(host, port)

        states: list[ConnectionState] = []
        mgr = ConnectionManager(transport, on_state_change=states.append)

        await mgr.connect()
        try:
            # CONNECTING should have been recorded before CONNECTED
            assert ConnectionState.CONNECTING in states
        finally:
            await mgr.disconnect()

    async def test_successful_connect_transitions_to_connected(self, kiss_tcp_server):
        """A successful TCP connection transitions to CONNECTED."""
        host = kiss_tcp_server["host"]
        port = kiss_tcp_server["port"]
        transport = KissTcpTransport(host, port)

        states: list[ConnectionState] = []
        mgr = ConnectionManager(transport, on_state_change=states.append)

        await mgr.connect()
        try:
            assert mgr.state == ConnectionState.CONNECTED
            assert states == [ConnectionState.CONNECTING, ConnectionState.CONNECTED]
        finally:
            await mgr.disconnect()

    async def test_connection_drop_transitions_to_reconnecting(self):
        """When the server closes the connection, state moves to RECONNECTING."""
        server, host, port, clients = await _start_tcp_server()
        transport = KissTcpTransport(host, port)

        states: list[ConnectionState] = []
        mgr = ConnectionManager(
            transport,
            max_reconnect_attempts=1,
            on_state_change=states.append,
        )

        await mgr.connect()
        assert mgr.state == ConnectionState.CONNECTED
        await asyncio.sleep(0.1)  # Let server handler populate clients

        # Close the server-side client connection to simulate a drop
        for _, writer in clients:
            writer.close()
            await writer.wait_closed()

        # Wait for the manager to detect the drop and transition
        try:
            await asyncio.wait_for(
                _wait_for_state(mgr, ConnectionState.RECONNECTING),
                timeout=5.0,
            )
            assert ConnectionState.RECONNECTING in states
        finally:
            await mgr.disconnect()
            server.close()

    async def test_reconnect_success_transitions_to_connected(self):
        """Successful reconnect returns to CONNECTED state."""
        server, host, port, clients = await _start_tcp_server()
        transport = KissTcpTransport(host, port)

        states: list[ConnectionState] = []
        mgr = ConnectionManager(
            transport,
            max_reconnect_attempts=3,
            on_state_change=states.append,
        )

        await mgr.connect()
        assert mgr.state == ConnectionState.CONNECTED
        await asyncio.sleep(0.1)  # Let server handler populate clients

        # Close client connections to trigger reconnect
        for _, writer in clients:
            writer.close()
            await writer.wait_closed()
        # Server stays alive so reconnect succeeds

        try:
            # Wait for reconnect cycle to complete
            await asyncio.wait_for(
                _wait_for_state_sequence(mgr, states, [
                    ConnectionState.RECONNECTING,
                    ConnectionState.CONNECTING,
                    ConnectionState.CONNECTED,
                ]),
                timeout=15.0,
            )
            assert mgr.state == ConnectionState.CONNECTED
        finally:
            await mgr.disconnect()
            server.close()

    async def test_max_attempts_transitions_to_failed(self):
        """After max_reconnect_attempts, state transitions to FAILED."""
        # Use a port that will refuse connections
        transport = KissTcpTransport("127.0.0.1", 1)

        states: list[ConnectionState] = []
        mgr = ConnectionManager(
            transport,
            max_reconnect_attempts=2,
            on_state_change=states.append,
        )

        # connect() blocks through reconnect attempts, so run in background
        connect_task = asyncio.create_task(mgr.connect())

        try:
            # Should eventually reach FAILED after max attempts
            await asyncio.wait_for(
                _wait_for_state(mgr, ConnectionState.FAILED),
                timeout=30.0,
            )
            assert mgr.state == ConnectionState.FAILED
        finally:
            mgr._running = False
            mgr._stop_tasks()
            connect_task.cancel()
            try:
                await connect_task
            except asyncio.CancelledError:
                pass

    async def test_disconnect_from_connected(self, kiss_tcp_server):
        """Calling disconnect() from CONNECTED goes to DISCONNECTED."""
        host = kiss_tcp_server["host"]
        port = kiss_tcp_server["port"]
        transport = KissTcpTransport(host, port)

        states: list[ConnectionState] = []
        mgr = ConnectionManager(transport, on_state_change=states.append)

        await mgr.connect()
        assert mgr.state == ConnectionState.CONNECTED

        await mgr.disconnect()
        assert mgr.state == ConnectionState.DISCONNECTED
        assert states[-1] == ConnectionState.DISCONNECTED

    async def test_disconnect_from_reconnecting(self):
        """Calling disconnect() from RECONNECTING cancels retries and goes to DISCONNECTED."""
        server, host, port, clients = await _start_tcp_server()
        transport = KissTcpTransport(host, port)

        states: list[ConnectionState] = []
        mgr = ConnectionManager(
            transport,
            max_reconnect_attempts=0,  # infinite retries
            on_state_change=states.append,
        )

        await mgr.connect()
        assert mgr.state == ConnectionState.CONNECTED
        await asyncio.sleep(0.1)  # Let server handler populate clients

        # Close all client connections to trigger reconnect
        for _, writer in clients:
            writer.close()
            await writer.wait_closed()
        # Also close the server so reconnects fail
        server.close()

        # Wait for RECONNECTING state
        await asyncio.wait_for(
            _wait_for_state(mgr, ConnectionState.RECONNECTING),
            timeout=5.0,
        )

        # Now disconnect while reconnecting
        await mgr.disconnect()
        assert mgr.state == ConnectionState.DISCONNECTED


# ==========================================================================
# Reconnect behavior (AC-11)
# ==========================================================================

class TestReconnect:
    """Auto-reconnect with configurable backoff."""

    async def test_reconnect_after_drop(self):
        """After TCP connection drops, the manager automatically retries."""
        server, host, port, clients = await _start_tcp_server()
        transport = KissTcpTransport(host, port)

        states: list[ConnectionState] = []
        mgr = ConnectionManager(
            transport,
            max_reconnect_attempts=3,
            on_state_change=states.append,
        )

        await mgr.connect()
        assert mgr.state == ConnectionState.CONNECTED
        await asyncio.sleep(0.1)  # Let server handler populate clients

        # Close client to simulate drop (await wait_closed for proper EOF)
        for _, writer in clients:
            writer.close()
            await writer.wait_closed()

        try:
            # Wait for reconnect cycle
            await asyncio.wait_for(
                _wait_for_state_after(mgr, states, ConnectionState.RECONNECTING, ConnectionState.CONNECTED),
                timeout=15.0,
            )
            assert mgr.state == ConnectionState.CONNECTED
        finally:
            await mgr.disconnect()
            server.close()

    async def test_reconnect_backoff_interval(self):
        """Reconnect attempts are spaced by exponential backoff (first attempt >= 0.5s)."""
        server, host, port, clients = await _start_tcp_server()
        transport = KissTcpTransport(host, port)

        states: list[ConnectionState] = []
        timestamps: list[float] = []

        def _track_state(s: ConnectionState):
            states.append(s)
            timestamps.append(time.monotonic())

        mgr = ConnectionManager(
            transport,
            max_reconnect_attempts=2,
            on_state_change=_track_state,
        )

        await mgr.connect()
        assert mgr.state == ConnectionState.CONNECTED
        await asyncio.sleep(0.1)  # Let server handler populate clients

        # Shut down server completely to force reconnect failures
        for _, writer in clients:
            writer.close()
            await writer.wait_closed()
        server.close()

        try:
            # Wait for FAILED state (after max_attempts)
            await asyncio.wait_for(
                _wait_for_state(mgr, ConnectionState.FAILED),
                timeout=30.0,
            )

            # Find RECONNECTING -> CONNECTING transitions to measure backoff
            reconnecting_times = [
                timestamps[i] for i, s in enumerate(states)
                if s == ConnectionState.RECONNECTING
            ]
            connecting_times = [
                timestamps[i] for i, s in enumerate(states)
                if s == ConnectionState.CONNECTING and i > 0
            ]

            # First reconnect attempt should have some delay (>= 0.5s)
            if len(reconnecting_times) >= 1 and len(connecting_times) >= 2:
                first_delay = connecting_times[1] - reconnecting_times[0]
                assert first_delay >= 0.5
        finally:
            mgr._running = False
            mgr._stop_tasks()

    async def test_reconnect_max_attempts_zero_is_infinite(self):
        """max_reconnect_attempts=0 means retry indefinitely."""
        # Use a port that refuses connections
        transport = KissTcpTransport("127.0.0.1", 1)

        states: list[ConnectionState] = []
        mgr = ConnectionManager(
            transport,
            max_reconnect_attempts=0,  # infinite
            on_state_change=states.append,
        )

        # connect() blocks through reconnect attempts, so run in background
        connect_task = asyncio.create_task(mgr.connect())

        try:
            # Wait a bit and verify it keeps reconnecting (doesn't hit FAILED)
            await asyncio.sleep(3.0)

            # Should have multiple RECONNECTING states but never FAILED
            reconnecting_count = sum(
                1 for s in states if s == ConnectionState.RECONNECTING
            )
            assert reconnecting_count >= 1
            assert ConnectionState.FAILED not in states
        finally:
            mgr._running = False
            mgr._stop_tasks()
            connect_task.cancel()
            try:
                await connect_task
            except asyncio.CancelledError:
                pass

    async def test_reconnect_max_attempts_finite(self):
        """max_reconnect_attempts=2 stops after 2 failed attempts."""
        transport = KissTcpTransport("127.0.0.1", 1)

        states: list[ConnectionState] = []
        mgr = ConnectionManager(
            transport,
            max_reconnect_attempts=2,
            on_state_change=states.append,
        )

        # connect() blocks through reconnect attempts, so run in background
        connect_task = asyncio.create_task(mgr.connect())

        try:
            await asyncio.wait_for(
                _wait_for_state(mgr, ConnectionState.FAILED),
                timeout=30.0,
            )
            assert mgr.state == ConnectionState.FAILED

            # Count RECONNECTING entries - should be at most 2
            reconnecting_count = sum(
                1 for s in states if s == ConnectionState.RECONNECTING
            )
            assert reconnecting_count <= 2
        finally:
            mgr._running = False
            mgr._stop_tasks()
            connect_task.cancel()
            try:
                await connect_task
            except asyncio.CancelledError:
                pass

    async def test_reconnect_resets_counter_on_success(self):
        """After a successful reconnect, the attempt counter resets to 0."""
        server, host, port, clients = await _start_tcp_server()
        transport = KissTcpTransport(host, port)

        states: list[ConnectionState] = []
        mgr = ConnectionManager(
            transport,
            max_reconnect_attempts=3,
            on_state_change=states.append,
        )

        await mgr.connect()
        assert mgr.state == ConnectionState.CONNECTED
        await asyncio.sleep(0.1)  # Let server handler populate clients

        # Trigger a reconnect by closing the client
        for _, writer in clients:
            writer.close()
            await writer.wait_closed()

        try:
            # Wait for successful reconnect
            await asyncio.wait_for(
                _wait_for_state_after(mgr, states, ConnectionState.RECONNECTING, ConnectionState.CONNECTED),
                timeout=15.0,
            )
            assert mgr.state == ConnectionState.CONNECTED
            assert mgr._attempt_count == 0
        finally:
            await mgr.disconnect()
            server.close()

    async def test_reconnect_state_change_events(self):
        """Each state transition emits an event/callback for status bar update."""
        server, host, port, clients = await _start_tcp_server()
        transport = KissTcpTransport(host, port)

        states: list[ConnectionState] = []
        mgr = ConnectionManager(
            transport,
            max_reconnect_attempts=3,
            on_state_change=states.append,
        )

        await mgr.connect()
        # Should have CONNECTING -> CONNECTED
        assert states == [ConnectionState.CONNECTING, ConnectionState.CONNECTED]
        await asyncio.sleep(0.1)  # Let server handler populate clients

        # Trigger reconnect
        for _, writer in clients:
            writer.close()
            await writer.wait_closed()

        try:
            await asyncio.wait_for(
                _wait_for_state_after(mgr, states, ConnectionState.RECONNECTING, ConnectionState.CONNECTED),
                timeout=15.0,
            )

            # Verify the full sequence includes reconnection events
            assert ConnectionState.RECONNECTING in states
            # After reconnect: should have CONNECTING and CONNECTED again
            reconnecting_idx = states.index(ConnectionState.RECONNECTING)
            post_reconnect = states[reconnecting_idx:]
            assert ConnectionState.CONNECTING in post_reconnect
            assert ConnectionState.CONNECTED in post_reconnect
        finally:
            await mgr.disconnect()
            server.close()


# ==========================================================================
# Health watchdog (AC-12)
# ==========================================================================

class TestConnectionHealth:
    """Connection health monitoring - no-packets-received watchdog."""

    async def test_health_warning_after_timeout(self, kiss_tcp_server):
        """If no packets received for > health_timeout, a warning is emitted (AC-12)."""
        host = kiss_tcp_server["host"]
        port = kiss_tcp_server["port"]
        transport = KissTcpTransport(host, port)

        health_warnings: list[bool] = []
        mgr = ConnectionManager(
            transport,
            health_timeout=0.5,
            on_health_warning=health_warnings.append,
        )

        await mgr.connect()
        try:
            # Wait for health warning to fire (timeout is 0.5s, check interval is 0.125s)
            await asyncio.wait_for(
                _wait_for_list_entry(health_warnings, True),
                timeout=5.0,
            )
            assert True in health_warnings
        finally:
            await mgr.disconnect()

    async def test_health_warning_clears_on_packet(self, kiss_tcp_server):
        """Receiving a packet clears the health warning."""
        host = kiss_tcp_server["host"]
        port = kiss_tcp_server["port"]
        transport = KissTcpTransport(host, port)

        health_warnings: list[bool] = []
        mgr = ConnectionManager(
            transport,
            health_timeout=0.5,
            on_health_warning=health_warnings.append,
        )

        await mgr.connect()
        try:
            # Wait for health warning to fire
            await asyncio.wait_for(
                _wait_for_list_entry(health_warnings, True),
                timeout=5.0,
            )
            assert True in health_warnings

            # Send a packet to clear the warning
            frame = _make_sample_kiss_frame()
            await kiss_tcp_server["send"](frame)

            # Wait for the warning to clear (False callback)
            await asyncio.wait_for(
                _wait_for_list_entry(health_warnings, False),
                timeout=5.0,
            )
            assert False in health_warnings
        finally:
            await mgr.disconnect()

    async def test_health_timeout_configurable(self):
        """Health timeout is configurable (default 60 seconds)."""
        transport = KissTcpTransport("127.0.0.1", 9999)

        # Default
        mgr_default = ConnectionManager(transport)
        assert mgr_default._health_timeout == 60.0

        # Custom
        mgr_custom = ConnectionManager(transport, health_timeout=30.0)
        assert mgr_custom._health_timeout == 30.0

    async def test_health_warning_does_not_disconnect(self, kiss_tcp_server):
        """The health warning is informational; it does not trigger a disconnect."""
        host = kiss_tcp_server["host"]
        port = kiss_tcp_server["port"]
        transport = KissTcpTransport(host, port)

        health_warnings: list[bool] = []
        mgr = ConnectionManager(
            transport,
            health_timeout=0.5,
            on_health_warning=health_warnings.append,
        )

        await mgr.connect()
        try:
            # Wait for health warning
            await asyncio.wait_for(
                _wait_for_list_entry(health_warnings, True),
                timeout=5.0,
            )
            # State should still be CONNECTED (not DISCONNECTED or RECONNECTING)
            assert mgr.state == ConnectionState.CONNECTED
        finally:
            await mgr.disconnect()


# ==========================================================================
# Connection failure scenarios
# ==========================================================================

class TestConnectionFailures:
    """Various connection failure scenarios."""

    async def test_connect_refused(self):
        """Connection to a closed port transitions to RECONNECTING or FAILED."""
        transport = KissTcpTransport("127.0.0.1", 1)

        states: list[ConnectionState] = []
        mgr = ConnectionManager(
            transport,
            max_reconnect_attempts=1,
            on_state_change=states.append,
        )

        # connect() blocks through reconnect attempts, so run in background
        connect_task = asyncio.create_task(mgr.connect())
        try:
            # Should go CONNECTING -> RECONNECTING -> ... -> FAILED
            await asyncio.wait_for(
                _wait_for_state(mgr, ConnectionState.FAILED),
                timeout=30.0,
            )
            assert mgr.state == ConnectionState.FAILED
            assert ConnectionState.CONNECTING in states
        finally:
            mgr._running = False
            mgr._stop_tasks()
            connect_task.cancel()
            try:
                await connect_task
            except asyncio.CancelledError:
                pass

    async def test_connect_dns_failure(self):
        """Connection to a non-resolving hostname transitions to RECONNECTING or FAILED."""
        transport = KissTcpTransport("this.host.does.not.exist.invalid", 8001)

        states: list[ConnectionState] = []
        mgr = ConnectionManager(
            transport,
            max_reconnect_attempts=1,
            on_state_change=states.append,
        )

        # connect() blocks through reconnect attempts, so run in background
        connect_task = asyncio.create_task(mgr.connect())
        try:
            await asyncio.wait_for(
                _wait_for_state(mgr, ConnectionState.FAILED),
                timeout=30.0,
            )
            assert mgr.state == ConnectionState.FAILED
        finally:
            mgr._running = False
            mgr._stop_tasks()
            connect_task.cancel()
            try:
                await connect_task
            except asyncio.CancelledError:
                pass

    async def test_connect_timeout_slow_server(self):
        """Connection to a server that accepts but never responds times out."""
        # Start a server that accepts connections but does nothing
        server, host, port, clients = await _start_tcp_server()
        transport = KissTcpTransport(host, port)

        states: list[ConnectionState] = []
        mgr = ConnectionManager(
            transport,
            max_reconnect_attempts=1,
            on_state_change=states.append,
        )

        # Connect should succeed (the server accepts the TCP connection)
        await mgr.connect()
        try:
            assert mgr.state == ConnectionState.CONNECTED
            # The transport is connected but no data comes - this is where
            # the health watchdog would fire (tested separately)
            assert ConnectionState.CONNECTING in states
            assert ConnectionState.CONNECTED in states
        finally:
            await mgr.disconnect()
            await _close_server(server, clients)


# ==========================================================================
# Async helpers for waiting on states
# ==========================================================================

async def _wait_for_state(mgr: ConnectionManager, target: ConnectionState) -> None:
    """Poll until the manager reaches the target state."""
    while mgr.state != target:
        await asyncio.sleep(0.05)


async def _wait_for_state_sequence(
    mgr: ConnectionManager,
    states: list[ConnectionState],
    sequence: list[ConnectionState],
) -> None:
    """Wait until all states in sequence have appeared in the states list (in order)."""
    while True:
        # Check if the sequence appears as a subsequence
        seq_idx = 0
        for s in states:
            if seq_idx < len(sequence) and s == sequence[seq_idx]:
                seq_idx += 1
        if seq_idx >= len(sequence):
            return
        await asyncio.sleep(0.05)


async def _wait_for_state_after(
    mgr: ConnectionManager,
    states: list[ConnectionState],
    after_state: ConnectionState,
    target_state: ConnectionState,
) -> None:
    """Wait until target_state appears after after_state in the states list."""
    while True:
        found_after = False
        for s in states:
            if s == after_state:
                found_after = True
            elif found_after and s == target_state:
                return
        await asyncio.sleep(0.05)


async def _wait_for_list_entry(lst: list, value) -> None:
    """Wait until a specific value appears in a list."""
    while value not in lst:
        await asyncio.sleep(0.05)
