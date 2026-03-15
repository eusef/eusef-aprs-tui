"""Main Textual TUI application for APRS.

Issue #13: Integration - TUI renders live packet stream.
Issue #18: Keyboard navigation (j/k, Tab, :, q).
Issue #20: Message panel (inbox + compose).
Issue #21: Message compose flow.
Issue #27: Inline wizard (F2 suspend/resume).
Issue #28: Config reload after wizard return.
Issue #39: Command palette (Ctrl+P / :).
Issue #40: Packet filter (/ key).
Issue #41: Raw packet toggle (r key).
Wires ConnectionManager + PacketBus + StreamPanel + StatusBar.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.command import Provider, Hit, Hits
from textual.containers import Horizontal
from textual.message import Message
from textual.widgets import Footer, Input

from aprs_tui.config import AppConfig, default_config_path
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


class APRSCommandProvider(Provider):
    """Custom command provider for APRS TUI."""

    async def search(self, query: str) -> Hits:
        commands = {
            "config": "Open full configuration wizard",
            "config server": "Configure server connection",
            "config station": "Configure station identity",
            "config beacon": "Configure beacon settings",
            "config aprs-is": "Configure APRS-IS gateway",
            "connect": "Reconnect to server",
            "disconnect": "Disconnect from server",
            "beacon on": "Enable beaconing",
            "beacon off": "Disable beaconing",
            "quit": "Exit the application",
        }

        query_lower = query.lower()
        for cmd, description in commands.items():
            if query_lower in cmd or query_lower in description.lower():
                yield Hit(
                    score=1.0 if cmd.startswith(query_lower) else 0.5,
                    match_display=cmd,
                    command=self._make_command(cmd),
                    text=description,
                )

    def _make_command(self, cmd: str):
        async def run_command():
            app = self.app
            if cmd == "quit":
                await app.action_quit()
            elif cmd == "connect":
                app.run_worker(app._connect(), exclusive=True)
            elif cmd == "disconnect":
                if app._connection_manager:
                    await app._connection_manager.disconnect()
            elif cmd.startswith("config"):
                section = cmd.replace("config", "").strip() or "all"
                await app.action_config(section)
        return run_command


class APRSTuiApp(App):
    """APRS Terminal User Interface application."""

    CSS_PATH = "ui/styles.tcss"

    COMMANDS = {APRSCommandProvider}

    BINDINGS = [
        # Global (priority=True so they work everywhere)
        Binding("q", "quit", "q Quit", priority=True),
        Binding("question_mark", "toggle_help", "? Help", priority=True),
        Binding("ctrl+w", "config('server')", "^W Config", priority=True),
        Binding("b", "toggle_beacon", "b Beacon", priority=True),

        # Navigation
        Binding("tab", "focus_next", "Tab Next"),
        Binding("shift+tab", "focus_previous", "Prev Panel"),

        # Panel scrolling (vim-style)
        Binding("j", "scroll_down", "j/k Scroll", show=False),
        Binding("k", "scroll_up", "Up", show=False),

        # Command palette (vim-style : to open)
        Binding("colon", "command_palette", ": Command", show=False),

        # Compose
        Binding("c", "focus_compose", "c Compose", show=False),

        # Packet filter
        Binding("slash", "open_filter", "/ Filter", show=False),

        # Raw packet toggle
        Binding("r", "toggle_raw", "r Raw", show=False),
    ]

    class PacketReceived(Message):
        """Posted when a new APRS packet is received."""
        def __init__(self, packet: APRSPacket) -> None:
            super().__init__()
            self.packet = packet

    class StateChanged(Message):
        """Posted when connection state changes."""
        def __init__(self, state: ConnectionState, transport_name: str) -> None:
            super().__init__()
            self.state = state
            self.transport_name = transport_name

    def __init__(self, config: AppConfig, config_path: Path | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.config = config
        self._config_path = config_path
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
        protocol = self.config.server.protocol

        if protocol == "kiss-tcp":
            transport = KissTcpTransport(
                self.config.server.host,
                self.config.server.port,
            )
        elif protocol == "kiss-ble":
            from aprs_tui.transport.kiss_ble import KissBleTransport
            # host field stores the BLE address or device name
            transport = KissBleTransport(address=self.config.server.host)
        elif protocol in ("kiss-serial", "kiss-bt"):
            from aprs_tui.transport.kiss_serial import KissSerialTransport
            from aprs_tui.transport.kiss_bt import KissBtTransport
            device = self.config.server.host
            baudrate = self.config.server.port
            if protocol == "kiss-bt":
                transport = KissBtTransport(device=device, baudrate=baudrate)
            else:
                transport = KissSerialTransport(device=device, baudrate=baudrate)
        elif protocol == "aprs-is":
            from aprs_tui.transport.aprs_is import AprsIsTransport
            transport = AprsIsTransport(
                host=self.config.server.host,
                port=self.config.server.port,
                callsign=self.config.station.callsign,
                passcode=self.config.aprs_is.passcode,
                filter_str=self.config.aprs_is.filter,
            )
        else:
            self.notify(f"Unknown protocol: {protocol}", severity="error")
            return

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
        transport_name = ""
        if self._connection_manager:
            transport_name = self._connection_manager.transport.display_name
        self.call_later(self._ui_update_state, state, transport_name)

    def _on_packet(self, pkt: APRSPacket) -> None:
        """Handle incoming packets (called from ConnectionManager)."""
        self.packet_bus.publish(pkt)
        self._station_tracker.update(pkt)
        self._message_tracker.handle_packet(pkt)
        self.call_later(self._ui_update_packet, pkt)

    def _ui_update_state(self, state: ConnectionState, transport_name: str) -> None:
        """Update UI for state change - runs on UI thread."""
        try:
            status_bar = self.query_one(StatusBar)
            status_bar.update_state(state, transport_name)
        except Exception:
            pass

    def _ui_update_packet(self, pkt: APRSPacket) -> None:
        """Update UI for new packet - runs on UI thread."""
        try:
            stream = self.query_one(StreamPanel)
            status_bar = self.query_one(StatusBar)
            station_panel = self.query_one(StationPanel)
            stream.add_packet(pkt)
            status_bar.increment_rx()
            stations = self._station_tracker.get_stations(sort_by=station_panel.sort_key)
            station_panel.refresh_stations(stations)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Message callbacks
    # ------------------------------------------------------------------

    def _on_inbound_message(self, msg: InboundMessage) -> None:
        try:
            panel = self.query_one(MessagePanel)
            panel.add_received_message(msg.source, msg.text, msg.msg_id)
        except Exception:
            pass

    def _on_message_state_change(self, tracked: TrackedMessage) -> None:
        try:
            panel = self.query_one(MessagePanel)
            panel.update_message_state(tracked.msg_id, tracked.state.value)
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

    async def action_config(self, section: str = "server") -> None:
        """Suspend TUI and launch wizard for configuration."""
        wizard_path = Path(__file__).parent.parent / "wizard.py"
        if not wizard_path.exists():
            self.notify("Wizard not found", severity="error")
            return

        config_path = self._config_path
        cmd = [sys.executable, str(wizard_path), "--section", section]
        if config_path:
            cmd.extend(["--config", str(config_path)])

        # Update status bar
        status_bar = self.query_one(StatusBar)
        status_bar.connection_state = "WIZARD"

        async with self.suspend():
            subprocess.run(cmd, check=False)

        # Resume: reload config and reconnect
        await self._reload_config()

    async def _reload_config(self) -> None:
        """Reload config from disk and reconnect if needed."""
        config_path = self._config_path or default_config_path()

        try:
            new_config = AppConfig.load(config_path)
        except Exception as e:
            self.notify(f"Config reload failed: {e}", severity="error")
            return

        old_config = self.config
        self.config = new_config
        self.callsign = f"{new_config.station.callsign}-{new_config.station.ssid}"

        # Update status bar callsign
        status_bar = self.query_one(StatusBar)
        status_bar.callsign = self.callsign

        # Check if server config changed - reconnect if so
        server_changed = (
            old_config.server.host != new_config.server.host
            or old_config.server.port != new_config.server.port
            or old_config.server.protocol != new_config.server.protocol
        )

        if server_changed:
            # Disconnect old connection
            if self._connection_manager:
                await self._connection_manager.disconnect()
            # Reconnect with new config
            self.run_worker(self._connect(), exclusive=True)

        self.notify("Configuration reloaded")

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

    def action_open_filter(self) -> None:
        """Open packet filter (placeholder until full filter input widget)."""
        self.notify("Filter: use command palette (:filter) - coming soon")

    def action_toggle_raw(self) -> None:
        """Toggle raw packet display in the stream panel."""
        stream = self.query_one(StreamPanel)
        stream.toggle_raw()
        state = "ON" if stream._show_raw else "OFF"
        self.notify(f"Raw packets: {state}")
