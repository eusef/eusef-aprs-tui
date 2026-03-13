"""Main Textual TUI application for APRS.

Issue #13: Integration - TUI renders live packet stream.
Issue #18: Keyboard navigation (j/k, Tab, :, q).
Issue #20: Message panel (inbox + compose).
Issue #21: Message compose flow.
Wires ConnectionManager + PacketBus + StreamPanel + StatusBar.
"""
from __future__ import annotations

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import Footer, Input

from aprs_tui.config import AppConfig
from aprs_tui.core.connection import ConnectionManager
from aprs_tui.core.message_tracker import MessageTracker, InboundMessage, TrackedMessage
from aprs_tui.core.packet_bus import PacketBus
from aprs_tui.core.station_tracker import StationTracker
from aprs_tui.protocol.types import APRSPacket
from aprs_tui.transport.base import ConnectionState
from aprs_tui.transport.kiss_tcp import KissTcpTransport
from aprs_tui.ui.message_panel import MessagePanel
from aprs_tui.ui.station_panel import StationPanel
from aprs_tui.ui.status_bar import StatusBar
from aprs_tui.ui.stream_panel import StreamPanel


class APRSTuiApp(App):
    """APRS Terminal User Interface application."""

    CSS_PATH = "ui/styles.tcss"

    BINDINGS = [
        # Global (priority=True so they work everywhere)
        Binding("q", "quit", "Quit", priority=True),
        Binding("f1", "toggle_help", "Help", priority=True),
        Binding("f2", "config_stub", "Config", priority=True),
        Binding("f5", "toggle_beacon", "Beacon", priority=True),

        # Navigation
        Binding("tab", "focus_next", "Next Panel"),
        Binding("shift+tab", "focus_previous", "Prev Panel"),

        # Panel scrolling
        Binding("j", "scroll_down", "Down", show=False),
        Binding("k", "scroll_up", "Up", show=False),

        # Quick actions
        Binding("question_mark", "toggle_help", "Help", show=False),

        # Compose
        Binding("c", "focus_compose", "Compose", show=False),
    ]

    def __init__(self, config: AppConfig, **kwargs) -> None:
        super().__init__(**kwargs)
        self.config = config
        self.callsign = f"{config.station.callsign}-{config.station.ssid}"
        self.packet_bus = PacketBus()
        self._connection_manager: ConnectionManager | None = None
        self._station_tracker = StationTracker(
            own_lat=getattr(config.station, "latitude", None),
            own_lon=getattr(config.station, "longitude", None),
        )
        self._message_tracker = MessageTracker(
            own_callsign=self.callsign,
            on_inbound=self._on_inbound_message,
            on_state_change=self._on_message_state_change,
        )

    def compose(self) -> ComposeResult:
        yield StatusBar(self.callsign)
        with Horizontal(id="main-panels"):
            yield StreamPanel(callsign=self.callsign, id="stream-panel")
            yield StationPanel(id="station-panel")
        yield MessagePanel(callsign=self.callsign, id="message-panel")
        yield Footer()

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

        # Update station tracker
        self._station_tracker.update(pkt)

        # Update message tracker
        self._message_tracker.handle_packet(pkt)

        # Update UI
        try:
            stream = self.query_one(StreamPanel)
            status_bar = self.query_one(StatusBar)
            station_panel = self.query_one(StationPanel)
            self.call_from_thread(stream.add_packet, pkt)
            self.call_from_thread(status_bar.increment_rx)
            stations = self._station_tracker.get_stations(
                sort_by=station_panel.sort_key
            )
            self.call_from_thread(station_panel.refresh_stations, stations)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Message callbacks
    # ------------------------------------------------------------------

    def _on_inbound_message(self, msg: InboundMessage) -> None:
        try:
            panel = self.query_one(MessagePanel)
            self.call_from_thread(panel.add_received_message, msg.source, msg.text, msg.msg_id)
        except Exception:
            pass

    def _on_message_state_change(self, tracked: TrackedMessage) -> None:
        try:
            panel = self.query_one(MessagePanel)
            self.call_from_thread(panel.update_message_state, tracked.msg_id, tracked.state.value)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    async def action_quit(self) -> None:
        """Quit the application, disconnecting cleanly."""
        if self._connection_manager:
            await self._connection_manager.disconnect()
        self.exit()

    def action_scroll_down(self) -> None:
        """Scroll the focused panel down (vim j key)."""
        focused = self.focused
        if focused is not None and hasattr(focused, "scroll_down"):
            focused.scroll_down()

    def action_scroll_up(self) -> None:
        """Scroll the focused panel up (vim k key)."""
        focused = self.focused
        if focused is not None and hasattr(focused, "scroll_up"):
            focused.scroll_up()

    def action_toggle_help(self) -> None:
        """Toggle help overlay (stub for now)."""
        self.notify("Help: j/k=scroll  Tab=switch panel  q=quit  ?=help")

    def action_config_stub(self) -> None:
        """F2 config placeholder (implemented in Sprint 5)."""
        self.notify("Configuration wizard not yet available (Sprint 5)")

    def action_toggle_beacon(self) -> None:
        """F5 beacon toggle placeholder."""
        self.notify("Beacon toggle not yet connected")

    def action_focus_compose(self) -> None:
        """Focus the message compose To: input."""
        try:
            panel = self.query_one(MessagePanel)
            to_input = panel.query_one("#msg-to-input", Input)
            to_input.focus()
        except Exception:
            pass
