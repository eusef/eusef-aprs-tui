"""Main Textual TUI application for APRS.

Issue #13: Integration - TUI renders live packet stream.
Wires ConnectionManager + PacketBus + StreamPanel + StatusBar.
"""
from __future__ import annotations

from textual.app import App, ComposeResult
from textual.binding import Binding

from aprs_tui.config import AppConfig
from aprs_tui.core.connection import ConnectionManager
from aprs_tui.core.packet_bus import PacketBus
from aprs_tui.protocol.types import APRSPacket
from aprs_tui.transport.base import ConnectionState
from aprs_tui.transport.kiss_tcp import KissTcpTransport
from aprs_tui.ui.status_bar import StatusBar
from aprs_tui.ui.stream_panel import StreamPanel


class APRSTuiApp(App):
    """APRS Terminal User Interface application."""

    CSS_PATH = "ui/styles.tcss"

    BINDINGS = [
        Binding("q", "quit", "Quit", priority=True),
    ]

    def __init__(self, config: AppConfig, **kwargs) -> None:
        super().__init__(**kwargs)
        self.config = config
        self.callsign = f"{config.station.callsign}-{config.station.ssid}"
        self.packet_bus = PacketBus()
        self._connection_manager: ConnectionManager | None = None

    def compose(self) -> ComposeResult:
        yield StatusBar(self.callsign)
        yield StreamPanel(callsign=self.callsign, id="stream-panel")

    def on_mount(self) -> None:
        self.title = "APRS-TUI"
        self.sub_title = self.callsign
        # Start connection in background
        self.run_worker(self._connect(), exclusive=True)

    async def _connect(self) -> None:
        """Set up transport and connection manager, then start reading."""
        transport = KissTcpTransport(
            self.config.server.host,
            self.config.server.port,
        )

        self._connection_manager = ConnectionManager(
            transport,
            reconnect_interval=self.config.connection.reconnect_interval,
            max_reconnect_attempts=self.config.connection.max_reconnect_attempts,
            health_timeout=self.config.connection.health_timeout,
            on_state_change=self._on_state_change,
            on_packet=self._on_packet,
        )

        status_bar = self.query_one(StatusBar)
        status_bar.update_state(ConnectionState.CONNECTING, transport.display_name)

        try:
            await self._connection_manager.connect()
        except Exception:
            status_bar.update_state(ConnectionState.FAILED, transport.display_name)

    def _on_state_change(self, state: ConnectionState) -> None:
        """Handle connection state changes (called from ConnectionManager)."""
        try:
            status_bar = self.query_one(StatusBar)
            transport_name = ""
            if self._connection_manager:
                transport_name = self._connection_manager.transport.display_name
            self.call_from_thread(status_bar.update_state, state, transport_name)
        except Exception:
            pass

    def _on_packet(self, pkt: APRSPacket) -> None:
        """Handle incoming packets (called from ConnectionManager)."""
        # Publish to bus
        self.packet_bus.publish(pkt)

        # Update UI
        try:
            stream = self.query_one(StreamPanel)
            status_bar = self.query_one(StatusBar)
            self.call_from_thread(stream.add_packet, pkt)
            self.call_from_thread(status_bar.increment_rx)
        except Exception:
            pass

    async def action_quit(self) -> None:
        """Quit the application, disconnecting cleanly."""
        if self._connection_manager:
            await self._connection_manager.disconnect()
        self.exit()
