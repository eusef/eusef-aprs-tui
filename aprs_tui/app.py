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
Issue #75: Responsive layout with terminal size breakpoints.
Wires ConnectionManager + PacketBus + StreamPanel + StatusBar.
"""
from __future__ import annotations

import asyncio
import contextlib
import logging
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.command import Hit, Hits, Provider
from textual.containers import Horizontal
from textual.message import Message
from textual.widgets import Input

from aprs_tui.config import AppConfig, default_config_path
from aprs_tui.core.connection import ConnectionManager
from aprs_tui.core.message_tracker import InboundMessage, MessageTracker, TrackedMessage
from aprs_tui.core.packet_bus import PacketBus
from aprs_tui.core.station_tracker import StationTracker
from aprs_tui.map.panel import MapPanel
from aprs_tui.protocol.types import APRSPacket
from aprs_tui.transport.base import ConnectionState
from aprs_tui.transport.kiss_tcp import KissTcpTransport
from aprs_tui.ui.footer import AppFooter
from aprs_tui.ui.key_reference import KeyReferencePanel
from aprs_tui.ui.message_panel import MessagePanel
from aprs_tui.ui.station_info_screen import StationInfoScreen
from aprs_tui.ui.station_panel import StationPanel
from aprs_tui.ui.status_bar import StatusBar
from aprs_tui.ui.stream_panel import StreamPanel

if TYPE_CHECKING:
    from aprs_tui.ui.chat_screen import ChatScreen

logger = logging.getLogger(__name__)


class APRSCommandProvider(Provider):
    """Custom command provider for APRS TUI."""

    async def search(self, query: str) -> Hits:
        matcher = self.matcher(query)

        commands = [
            ("Config: Full wizard", "config_all"),
            ("Config: Server connection", "config_server"),
            ("Config: Station identity", "config_station"),
            ("Config: Beacon settings", "config_beacon"),
            ("Config: APRS-IS gateway", "config_aprs_is"),
            ("Reconnect to server", "reconnect"),
            ("Disconnect from server", "disconnect"),
            ("Toggle beacon on/off", "beacon"),
            ("Toggle raw packet display", "raw"),
            ("Toggle APRS-IS packets", "aprs_is_toggle"),
            ("Toggle map panel", "map_toggle"),
            ("Map: Switch position (left/right)", "map_position"),
            ("Map: Download offline maps", "map_download"),
            ("Map: List available maps", "map_list"),
            ("Map: Toggle auto-zoom", "map_auto_zoom"),
            ("Quit application", "quit"),
        ]

        for label, action_id in commands:
            score = matcher.match(label)
            if score > 0:
                yield Hit(
                    score=score,
                    match_display=matcher.highlight(label),
                    command=self._run_action(action_id),
                    help=label,
                )

    def _run_action(self, action_id: str):
        async def callback():
            app = self.app
            if action_id == "quit":
                await app.action_quit()
            elif action_id == "reconnect":
                app.run_worker(app._connect(), exclusive=True)
            elif action_id == "disconnect":
                if app._connection_manager:
                    await app._connection_manager.disconnect()
            elif action_id == "beacon":
                app.action_toggle_beacon()
            elif action_id == "raw":
                app.action_toggle_raw()
            elif action_id == "aprs_is_toggle":
                app.action_toggle_aprs_is()
            elif action_id == "map_toggle":
                app.action_toggle_map()
            elif action_id == "map_position":
                app.action_toggle_map_position()
            elif action_id == "map_download":
                await app.action_map_download()
            elif action_id == "map_list":
                app.action_map_list()
            elif action_id == "map_auto_zoom":
                app.action_map_auto_zoom()
            elif action_id.startswith("config_"):
                section = action_id.replace("config_", "")
                if section == "all":
                    section = "all"
                elif section == "aprs_is":
                    section = "aprs-is"
                await app.action_config(section)
        return callback


class APRSTuiApp(App):
    """APRS Terminal User Interface application."""

    CSS_PATH = "ui/styles.tcss"

    ENABLE_COMMAND_PALETTE = False  # Using our own command screen

    BINDINGS = [
        # Shown in footer
        Binding("q", "quit", "Quit", priority=True),
        Binding("question_mark", "show_commands", "Help", priority=True),
        Binding("ctrl+w", "config('all')", "Config", priority=True),
        Binding("b", "toggle_beacon", "Beacon", priority=True),
        Binding("c", "focus_compose", "Compose", priority=True),
        Binding("r", "toggle_raw", "Raw"),
        Binding("i", "toggle_aprs_is", "APRS-IS"),
        Binding("y", "copy_packet", "Copy"),

        # Map toggle
        Binding("m", "toggle_map", "Map"),
        Binding("M", "toggle_map_position", "Map Pos", show=False),

        # About screen
        Binding("a", "show_about", "About"),

        # Hidden (but still active)
        Binding("tab", "focus_next", "Next", show=False),
        Binding("shift+tab", "focus_previous", "Prev", show=False),
        Binding("j", "scroll_down", "Down", show=False),
        Binding("k", "scroll_up", "Up", show=False),
        Binding("colon", "show_commands", "Commands", show=False),
        Binding("x", "cancel_message", "Cancel", show=False),
        Binding("slash", "open_filter", "Filter", show=False),
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
        self._aprs_is_manager: ConnectionManager | None = None
        self._tx_lock = asyncio.Lock()
        self._show_aprs_is = True
        self._station_sort_key = "last_heard"
        self._station_sort_reverse = True
        self._active_chats: dict[str, ChatScreen] = {}  # callsign -> screen
        self._station_tracker = StationTracker(
            own_lat=config.station.latitude or None,
            own_lon=config.station.longitude or None,
        )
        self._message_tracker = MessageTracker(
            own_callsign=self.callsign,
            send_func=self._send_message_frame,
            on_inbound=self._on_inbound_message,
            on_state_change=self._on_message_state_change,
            on_retry=self._on_message_retry,
            on_send_ack=self._on_send_ack,
        )
        self._beacon_manager = None  # Created after connection
        self._direwolf_manager = None  # Managed Direwolf subprocess
        self._map_visible = False  # Map panel toggle state
        self._map_position = config.map.position  # "right" or "left"

    def compose(self) -> ComposeResult:
        yield StatusBar(self.callsign)
        with Horizontal(id="main-panels"):
            yield StreamPanel(callsign=self.callsign, id="stream-panel")
            yield StationPanel(id="station-panel")
            yield MapPanel(
                station_tracker=self._station_tracker,
                own_callsign=self.callsign,
                map_config={
                    "own_lat": self.config.station.latitude,
                    "own_lon": self.config.station.longitude,
                    "auto_zoom_min": self.config.map.auto_zoom_min,
                    "auto_zoom_max": self.config.map.auto_zoom_max,
                    "default_zoom": self.config.map.default_zoom,
                    "show_is_stations": self.config.map.show_is_stations,
                    "show_tracks": self.config.map.show_tracks,
                },
                id="map-panel",
            )
        with Horizontal(id="message-area"):
            yield MessagePanel(callsign=self.callsign, id="message-panel")
            yield KeyReferencePanel(id="key-reference")
        yield AppFooter(id="app-footer")

    def on_mount(self) -> None:
        self.title = "APRS-TUI"
        self.sub_title = self.callsign
        # Map panel starts hidden (CSS: display: none by default, no class)
        # Hide APRS-IS checkbox when primary transport is already APRS-IS
        if self.config.server.protocol == "aprs-is":
            try:
                panel = self.query_one(MessagePanel)
                panel.set_aprs_is_visible(False)
            except Exception:
                pass
        # Start primary connection in background
        self.run_worker(self._connect(), exclusive=True, group="primary")
        # Start APRS-IS independently (don't wait for primary)
        if (self.config.aprs_is.enabled
                and self.config.server.protocol != "aprs-is"):
            self.run_worker(self._connect_aprs_is(), group="aprs-is")

    def on_resize(self, event) -> None:
        """Adapt layout to terminal size using CSS classes."""
        w = event.size.width
        h = event.size.height

        screen = self.screen

        # Width classes
        screen.remove_class("-medium", "-narrow")
        if w < 80:
            screen.add_class("-narrow")
        elif w < 120:
            screen.add_class("-medium")

        # Height classes
        screen.remove_class("-short", "-very-short")
        if h < 24:
            screen.add_class("-very-short")
        elif h < 40:
            screen.add_class("-short")

    async def _connect(self) -> None:
        """Set up transport and connection manager, then start reading."""
        protocol = self.config.server.protocol

        if protocol == "kiss-tcp":
            # Start managed Direwolf if local config exists
            await self._maybe_start_direwolf()

            transport = KissTcpTransport(
                self.config.server.host,
                self.config.server.port,
            )
        elif protocol == "kiss-ble-hybrid":
            from aprs_tui.transport.kiss_ble import KissBleHybridTransport
            transport = KissBleHybridTransport(
                ble_address=self.config.server.host,
                serial_device=self.config.server.serial_device,
                baudrate=self.config.server.port or 9600,
            )
        elif protocol == "kiss-ble":
            from aprs_tui.transport.kiss_ble import KissBleTransport
            # host field stores the BLE address or device name
            transport = KissBleTransport(address=self.config.server.host)
        elif protocol in ("kiss-serial", "kiss-bt"):
            from aprs_tui.transport.kiss_bt import KissBtTransport
            from aprs_tui.transport.kiss_serial import KissSerialTransport
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
            on_health_warning=self._on_health_warning,
        )

        status_bar = self.query_one(StatusBar)
        status_bar.update_state(ConnectionState.CONNECTING, transport.display_name)
        footer = self.query_one(AppFooter)
        footer.update_rf_state(ConnectionState.CONNECTING, transport.display_name)

        try:
            await self._connection_manager.connect()

            # Create beacon manager now that we have a transport
            from aprs_tui.core.beacon import BeaconManager
            bcn_lat = (
                self.config.beacon.latitude
                if self.config.beacon.latitude != 0.0
                else self.config.station.latitude
            )
            bcn_lon = (
                self.config.beacon.longitude
                if self.config.beacon.longitude != 0.0
                else self.config.station.longitude
            )
            self._beacon_manager = BeaconManager(
                callsign=self.callsign,
                latitude=bcn_lat,
                longitude=bcn_lon,
                symbol_table=self.config.station.symbol_table,
                symbol_code=self.config.station.symbol_code,
                comment=self.config.beacon.comment,
                interval=self.config.beacon.interval,
                send_func=self._connection_manager.send_frame,
                on_beacon_sent=lambda: self.call_later(self._on_beacon_sent),
            )

            if self.config.beacon.enabled:
                self._beacon_manager.enable()
        except Exception:
            status_bar.update_state(ConnectionState.FAILED, transport.display_name)
            footer.update_rf_state(ConnectionState.FAILED, transport.display_name)

        # APRS-IS is started independently from on_mount, not here

    async def _maybe_start_direwolf(self) -> None:
        """Start a managed Direwolf instance if a local config exists."""
        app_dir = Path(__file__).parent.parent
        dw_conf = app_dir / "direwolf.conf"
        if not dw_conf.exists():
            return
        # Only manage Direwolf for local connections
        if self.config.server.host not in ("127.0.0.1", "localhost"):
            return

        from aprs_tui.core.direwolf import DirewolfManager

        try:
            self._direwolf_manager = DirewolfManager(config_path=dw_conf)
            self.call_later(self.notify, "Starting Direwolf...")
            ready = await self._direwolf_manager.start_and_wait_ready(
                kiss_port=self.config.server.port,
                timeout=10.0,
            )
            if ready:
                self.call_later(self.notify, "Direwolf ready")
            else:
                self.call_later(
                    self.notify,
                    "Direwolf failed to start — check direwolf.log",
                    severity="error",
                )
        except FileNotFoundError as e:
            self.call_later(self.notify, str(e), severity="error")
            self._direwolf_manager = None

    async def _connect_aprs_is(self) -> None:
        """Connect to APRS-IS as a secondary transport."""
        from aprs_tui.core.dedup import DeduplicationFilter
        from aprs_tui.transport.aprs_is import AprsIsTransport

        aprs_is_transport = AprsIsTransport(
            host=self.config.aprs_is.host,
            port=self.config.aprs_is.port,
            callsign=self.config.station.callsign,
            passcode=self.config.aprs_is.passcode,
            filter_str=self.config.aprs_is.filter,
        )

        # Dedup filter to avoid showing same packet from radio + APRS-IS
        self._dedup = DeduplicationFilter(window=30.0)

        self._aprs_is_manager = ConnectionManager(
            aprs_is_transport,
            reconnect_interval=self.config.connection.reconnect_interval,
            max_reconnect_attempts=self.config.connection.max_reconnect_attempts,
            health_timeout=300,  # APRS-IS is chattier, longer health timeout
            on_state_change=self._on_aprs_is_state_change,
            on_packet=self._on_aprs_is_packet,
        )

        try:
            await self._aprs_is_manager.connect()
            self.call_later(
                self.notify,
                f"APRS-IS connected: {aprs_is_transport.display_name}",
            )
            # Enable APRS-IS send checkbox if passcode allows TX
            if self.config.aprs_is.passcode != -1:
                self.call_later(self._ui_update_aprs_is_checkbox, True)
        except Exception:
            self.call_later(
                self.notify,
                "APRS-IS connection failed",
                severity="warning",
            )

    def _on_aprs_is_state_change(self, state: ConnectionState) -> None:
        """Handle APRS-IS connection state changes."""
        # Enable/disable the APRS-IS send checkbox based on gateway state
        tx_available = (
            state == ConnectionState.CONNECTED
            and self.config.aprs_is.passcode != -1
        )
        self.call_later(self._ui_update_aprs_is_checkbox, tx_available)
        # Update footer APRS-IS state
        self.call_later(self._ui_update_is_state, state)

    def _on_aprs_is_packet(self, pkt: APRSPacket) -> None:
        """Handle packets from APRS-IS (secondary transport)."""
        # Dedup: skip if we already got this packet from radio
        if hasattr(self, '_dedup') and self._dedup.is_duplicate(pkt):
            return

        # Always track stations and messages even if display is hidden
        self.packet_bus.publish(pkt)
        self._station_tracker.update(pkt)
        self._message_tracker.handle_packet(pkt)

        # Always add to stream panel's packet store (for re-render on toggle)
        # but only visually display if APRS-IS is shown
        if self._show_aprs_is:
            self.call_later(self._ui_update_packet, pkt)
        else:
            self.call_later(self._ui_store_hidden_packet, pkt)

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

    def _on_health_warning(self, warning_active: bool) -> None:
        """Handle health warning from ConnectionManager."""
        if warning_active:
            self.call_later(
                self.notify,
                "No packets received for 60s - check radio/antenna",
                severity="warning",
                timeout=10,
            )

    def _ui_update_state(self, state: ConnectionState, transport_name: str) -> None:
        """Update UI for state change - runs on UI thread."""
        try:
            status_bar = self.query_one(StatusBar)
            status_bar.update_state(state, transport_name)
        except Exception:
            pass
        try:
            footer = self.query_one(AppFooter)
            footer.update_rf_state(state, transport_name)
        except Exception:
            pass

    def _ui_update_is_state(self, state: ConnectionState) -> None:
        """Update footer APRS-IS state - runs on UI thread."""
        try:
            footer = self.query_one(AppFooter)
            footer.update_is_state(state)
        except Exception:
            pass

    def _ui_update_aprs_is_checkbox(self, tx_available: bool) -> None:
        """Enable/disable the APRS-IS checkbox based on gateway state."""
        try:
            panel = self.query_one(MessagePanel)
            panel.set_aprs_is_enabled(tx_available)
        except Exception:
            pass

    def _ui_update_packet(self, pkt: APRSPacket) -> None:
        """Update UI for new packet - runs on UI thread."""
        try:
            stream = self.query_one(StreamPanel)
            status_bar = self.query_one(StatusBar)
            stream.add_packet(pkt)
            status_bar.increment_rx()
            self._refresh_stations()
        except Exception:
            pass
        # Increment footer RX counter
        with contextlib.suppress(Exception):
            self.query_one(AppFooter).increment_rx()
        # Always notify map panel so it re-renders with new stations
        with contextlib.suppress(Exception):
            self.query_one("#map-panel", MapPanel).notify_station_update()

    # ------------------------------------------------------------------
    # Message callbacks
    # ------------------------------------------------------------------

    def _on_inbound_message(self, msg: InboundMessage) -> None:
        self.call_later(self._ui_inbound_message, msg)

    def _on_message_state_change(self, tracked: TrackedMessage) -> None:
        self.call_later(self._ui_message_state_change, tracked)

    def _ui_inbound_message(self, msg: InboundMessage) -> None:
        """Show inbound message in panel + notification, route to chat if open."""
        try:
            panel = self.query_one(MessagePanel)
            panel.add_received_message(msg.source, msg.text, msg.msg_id)

            # Route to active chat screen if open
            source = msg.source.upper()
            if source in self._active_chats:
                chat = self._active_chats[source]
                chat.add_message("received", msg.text, msg.msg_id, state="received")

            # Notify with option to open chat
            self.notify(
                f"Message from {msg.source}: {msg.text}  (Tab to stations, Enter to chat)",
            )
            self.bell()
        except Exception:
            pass

    def _on_message_retry(self, tracked: TrackedMessage, attempt: int, remaining: int) -> None:
        """Called every second during retry countdown."""
        max_retries = self._message_tracker._max_retries
        info = f"{attempt}/{max_retries} retry in {remaining}s - press x to cancel"

        # Update the message panel inline every second
        self.call_later(self._ui_update_retry, tracked.msg_id, info)

    def _ui_update_retry(self, msg_id: str, info: str) -> None:
        """Update retry info on message in panel."""
        try:
            panel = self.query_one(MessagePanel)
            panel.update_retry_info(msg_id, info)
        except Exception:
            pass

    def _ui_message_state_change(self, tracked: TrackedMessage) -> None:
        """Update message state in panel + notification."""
        try:
            panel = self.query_one(MessagePanel)
            panel.update_message_state(tracked.msg_id, tracked.state.value)

            state = tracked.state.value
            if state == "acked":
                self.notify(
                    f"Message to {tracked.addressee} delivered (ack #{tracked.msg_id})",
                    severity="information",
                )
            elif state == "rejected":
                self.notify(
                    f"Message to {tracked.addressee} rejected",
                    severity="error",
                )
            elif state == "failed":
                self.notify(
                    f"Message to {tracked.addressee} failed after retries",
                    severity="error",
                )

            # Route to active chat screen
            addr = tracked.addressee.upper()
            if addr in self._active_chats:
                self._active_chats[addr].update_message_state(
                    tracked.msg_id, tracked.state.value
                )
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    async def action_quit(self) -> None:
        """Quit the application, disconnecting cleanly."""
        try:
            # Save all active chats to disk (only if they have messages)
            from aprs_tui.core.chat_store import save_chat
            for callsign, chat in self._active_chats.items():
                if chat.messages:
                    msgs = [m.to_dict() for m in chat.messages]
                    save_chat(callsign, msgs)

            # Stop beacon
            if self._beacon_manager and self._beacon_manager.enabled:
                self._beacon_manager.disable()

            # Cancel all message retry tasks
            self._message_tracker.stop()

            # Disconnect transports with timeout
            for mgr in (self._connection_manager, self._aprs_is_manager):
                if mgr:
                    with contextlib.suppress(TimeoutError, Exception):
                        await asyncio.wait_for(mgr.disconnect(), timeout=3.0)

            # Stop managed Direwolf
            if self._direwolf_manager and self._direwolf_manager.is_running:
                self._direwolf_manager.stop()
        except Exception:
            pass

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
        """Show key bindings help."""
        self.notify(
            "q=Quit  ?=Help  ^W=Config  b=Beacon  c=Compose  r=Raw  "
            "i=APRS-IS  y=Copy  x=Cancel  j/k=Scroll  Tab=Next\n"
            "m=Map(large)  M=Map(small)  "
            "Map: +/-=Zoom  \u2190\u2191\u2192\u2193=Pan  a=AutoZoom  0=Reset  "
            "n/N=Station  g=Legend  t=Tracks",
            timeout=15,
        )

    def action_show_about(self) -> None:
        """Show about screen with version, licenses, and legal info."""
        from aprs_tui.ui.about_screen import AboutScreen
        self.push_screen(AboutScreen())

    def action_show_commands(self) -> None:
        """Show the command palette overlay."""
        from aprs_tui.ui.command_screen import CommandScreen

        def _on_dismiss(result: str | None) -> None:
            if result is None:
                return
            # Map key to action
            key_actions = {
                "q": self.action_quit,
                "?": self.action_toggle_help,
                "b": self.action_toggle_beacon,
                "r": self.action_toggle_raw,
                "i": self.action_toggle_aprs_is,
                "y": self.action_copy_packet,
                "x": self.action_cancel_message,
                "c": self.action_focus_compose,
                "a": self.action_show_about,
            }
            action = key_actions.get(result)
            if action:
                action()
            elif result == "^W":
                self.run_worker(self.action_config("all"))

        self.push_screen(CommandScreen(), callback=_on_dismiss)

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

        # Disconnect before suspending so BLE/serial is released
        if self._beacon_manager and self._beacon_manager.enabled:
            self._beacon_manager.disable()
        if self._connection_manager:
            await self._connection_manager.disconnect()
        if self._aprs_is_manager:
            await self._aprs_is_manager.disconnect()

        # Update status bar
        status_bar = self.query_one(StatusBar)
        status_bar.connection_state = "WIZARD"

        with self.suspend():
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

        self.config = new_config
        self.callsign = f"{new_config.station.callsign}-{new_config.station.ssid}"

        # Update status bar callsign
        status_bar = self.query_one(StatusBar)
        status_bar.callsign = self.callsign

        # Always reconnect after wizard (we disconnected before suspend)
        if self._connection_manager:
            with contextlib.suppress(Exception):
                await self._connection_manager.disconnect()
        self._connection_manager = None
        self._beacon_manager = None
        self.run_worker(self._connect(), exclusive=True)

        self.notify("Configuration reloaded - reconnecting...")

    def action_toggle_beacon(self) -> None:
        """Toggle position beacon on/off."""
        if self._beacon_manager is None:
            self.notify("Beacon not available (not connected)", severity="warning")
            return

        if self._beacon_manager.enabled:
            self._beacon_manager.disable()
            self.notify("Beacon OFF")
        else:
            bcn_lat = (
                self.config.beacon.latitude
                if self.config.beacon.latitude != 0.0
                else self.config.station.latitude
            )
            bcn_lon = (
                self.config.beacon.longitude
                if self.config.beacon.longitude != 0.0
                else self.config.station.longitude
            )
            if bcn_lat == 0.0 and bcn_lon == 0.0:
                self.notify("Set your position first (Ctrl+W → station)", severity="warning")
                return
            self._beacon_manager.enable()
            self.notify(f"Beacon ON - every {self._beacon_manager.interval}s")

    def _on_send_ack(self, source: str, msg_id: str) -> None:
        """Send an ack for a received message. Called from message tracker."""
        from aprs_tui.protocol.encoder import encode_ack

        info = encode_ack(source, msg_id)

        async def _do_ack():
            try:
                await self._send_message_frame(info, via_aprs_is=False)
                self.call_later(
                    self.notify,
                    f"Ack sent to {source} for #{msg_id}",
                    timeout=3,
                )
            except Exception as e:
                logger.error("Failed to send ack: %s", e)

        self.run_worker(_do_ack())

    async def _send_message_frame(self, info: str, via_aprs_is: bool = False) -> None:
        """Send an APRS message info field via the appropriate transport.

        Called by MessageTracker for initial send and retries.
        Routes through APRS-IS (text protocol) or RF (AX.25 binary)
        depending on the via_aprs_is flag and primary transport type.
        Uses a TX lock to prevent simultaneous transmissions.
        """
        async with self._tx_lock:
            if via_aprs_is:
                # Route through secondary APRS-IS gateway
                if not self._aprs_is_manager or self._aprs_is_manager.state.value != "connected":
                    raise ConnectionError("APRS-IS gateway not connected")
                from aprs_tui.protocol.encoder import build_packet
                packet_line = build_packet(self.callsign, "APRS", info, ["TCPIP*"])
                await self._aprs_is_manager.send_frame(packet_line.encode("latin-1"))
            elif self.config.server.protocol == "aprs-is":
                # Primary transport is APRS-IS — send as text packet
                if (
                    not self._connection_manager
                    or self._connection_manager.state.value != "connected"
                ):
                    raise ConnectionError("Not connected")
                from aprs_tui.protocol.encoder import build_packet
                packet_line = build_packet(self.callsign, "APRS", info, ["TCPIP*"])
                await self._connection_manager.send_frame(packet_line.encode("latin-1"))
            else:
                # Primary transport is RF (KISS) — send as AX.25 frame
                if (
                    not self._connection_manager
                    or self._connection_manager.state.value != "connected"
                ):
                    raise ConnectionError("Not connected")
                from aprs_tui.protocol.ax25 import ax25_encode
                ax25_data = ax25_encode(
                    self.callsign, "APRS",
                    ["WIDE1-1", "WIDE2-1"],
                    info.encode("latin-1"),
                )
                await self._connection_manager.send_frame(ax25_data)
                # Wait for radio to release PTT before allowing next TX
                await asyncio.sleep(2.0)

    def _on_beacon_sent(self) -> None:
        """Called when a beacon is transmitted."""
        try:
            status_bar = self.query_one(StatusBar)
            status_bar.increment_tx()
            self.notify("Beacon transmitted", timeout=3)
        except Exception:
            pass
        with contextlib.suppress(Exception):
            self.query_one(AppFooter).increment_tx()

    def on_station_panel_station_selected(self, event: StationPanel.StationSelected) -> None:
        """Highlight packets from selected station in the stream and on the map."""
        try:
            stream = self.query_one(StreamPanel)
            stream.set_highlight_station(event.callsign)
        except Exception:
            pass
        try:
            map_panel = self.query_one(MapPanel)
            map_panel.select_station(event.callsign)
        except Exception:
            pass

    def on_map_panel_station_selected(self, event: MapPanel.StationSelected) -> None:
        """Highlight station in station list and stream when selected on map."""
        with contextlib.suppress(Exception):
            station_panel = self.query_one(StationPanel)
            station_panel.select_callsign(event.callsign)
        with contextlib.suppress(Exception):
            self.query_one(StreamPanel).set_highlight_station(event.callsign)

    def on_map_panel_station_activated(self, event: MapPanel.StationActivated) -> None:
        """Open station info screen when Enter is pressed on a map station."""
        station = self._station_tracker.get_station(event.callsign)
        if station:
            self.push_screen(StationInfoScreen(station))

    def on_station_info_screen_open_chat(self, event: StationInfoScreen.OpenChat) -> None:
        """Open chat when Enter is pressed on the station info screen."""
        self._open_chat(event.callsign)

    def on_station_panel_station_activated(self, event: StationPanel.StationActivated) -> None:
        """Open a chat screen with the selected station."""
        self._open_chat(event.callsign)

    def on_station_panel_sort_changed(self, event: StationPanel.SortChanged) -> None:
        """Update sort state and refresh station list when sort column/direction changes."""
        self._station_sort_key = event.sort_key
        self._station_sort_reverse = event.reverse
        self._refresh_stations()

    def _open_chat(self, callsign: str) -> None:
        """Open or resume a chat screen with a station."""
        from aprs_tui.core.chat_store import load_chat, save_chat
        from aprs_tui.ui.chat_screen import ChatMessage, ChatScreen

        callsign = callsign.upper()

        # Look up positions for mini map
        peer_station = self._station_tracker.get_station(callsign)
        own_lat = self.config.station.latitude
        own_lon = self.config.station.longitude
        peer_lat = peer_station.latitude if peer_station else None
        peer_lon = peer_station.longitude if peer_station else None

        # Reuse in-memory chat if we have one this session
        if callsign in self._active_chats:
            old_chat = self._active_chats[callsign]
            chat = ChatScreen(
                callsign=callsign, own_callsign=self.callsign,
                own_lat=own_lat, own_lon=own_lon,
                peer_lat=peer_lat, peer_lon=peer_lon,
            )
            chat.messages = old_chat.messages
            self._active_chats[callsign] = chat
            self.push_screen(chat)
            return

        # Create new chat screen
        chat = ChatScreen(
            callsign=callsign, own_callsign=self.callsign,
            own_lat=own_lat, own_lon=own_lon,
            peer_lat=peer_lat, peer_lon=peer_lon,
        )

        # Load persisted history from disk
        stored = load_chat(callsign)
        if stored:
            chat.messages = [ChatMessage.from_dict(m) for m in stored]

        # Add any new messages from this session's tracker
        existing_ids = {m.msg_id for m in chat.messages if m.msg_id}
        for msg in self._message_tracker.history:
            if msg.addressee.upper() == callsign and msg.msg_id not in existing_ids:
                chat.add_message("sent", msg.text, msg.msg_id, msg.state.value)
        for msg in self._message_tracker.inbound_messages:
            if msg.source.upper() == callsign and msg.msg_id not in existing_ids:
                chat.add_message("received", msg.text, msg.msg_id, "received")

        # Sort by timestamp
        chat.messages.sort(key=lambda m: m.timestamp)

        self._active_chats[callsign] = chat

        def _on_chat_dismiss(result) -> None:
            # Save chat to disk when closed (only if there are messages)
            if callsign in self._active_chats:
                chat_msgs = self._active_chats[callsign].messages
                if chat_msgs:
                    msgs = [m.to_dict() for m in chat_msgs]
                    save_chat(callsign, msgs)
                self._refresh_stations()  # Update chat indicators

        self.push_screen(chat, callback=_on_chat_dismiss)

    def on_chat_screen_delete_chat(self, event) -> None:
        """Handle chat deletion from a chat screen."""
        from aprs_tui.core.chat_store import delete_chat
        callsign = event.callsign.upper()
        delete_chat(callsign)
        # Remove from active chats so dismiss callback won't re-save
        self._active_chats.pop(callsign, None)
        self.notify(f"Chat with {callsign} deleted")
        self._refresh_stations()

    def on_chat_screen_send_chat_message(self, event) -> None:
        """Handle send from a chat screen."""
        callsign = event.callsign.upper()
        text = event.text

        # Send through message tracker
        msg_id = self._message_tracker.send_message(callsign, text)

        # Add to chat screen
        if callsign in self._active_chats:
            self._active_chats[callsign].add_message(
                "sent", text, msg_id, state="pending"
            )

        # Add to message panel too
        try:
            panel = self.query_one(MessagePanel)
            panel.add_sent_message(callsign, text, msg_id, state="pending")
        except Exception:
            pass

        # Start retry loop
        async def _start():
            self._message_tracker.start_retry_loop(msg_id)
        self.run_worker(_start())

    def action_focus_compose(self) -> None:
        """Focus the message compose To: input and scroll it into view."""
        try:
            panel = self.query_one(MessagePanel)
            to_input = panel.query_one("#msg-to-input", Input)
            to_input.focus()
            panel.scroll_visible()
        except Exception:
            pass

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle Enter pressed in an Input widget."""
        if event.input.id == "msg-text-input":
            self._send_message()
        elif event.input.id == "msg-to-input":
            # Tab to message field on Enter in To: field
            try:
                msg_input = self.query_one("#msg-text-input", Input)
                msg_input.focus()
            except Exception:
                pass

    def _send_message(self) -> None:
        """Send the composed message."""
        try:
            panel = self.query_one(MessagePanel)
            to_call, msg_text, via_aprs_is = panel.get_compose_values()

            if not to_call:
                self.notify("Enter a destination callsign", severity="warning")
                return
            if not msg_text:
                self.notify("Enter a message", severity="warning")
                return

            # Track the message and start retry loop
            msg_id = self._message_tracker.send_message(
                to_call.upper(), msg_text, via_aprs_is=via_aprs_is,
            )

            # Show in panel
            panel.add_sent_message(
                to_call.upper(), msg_text, msg_id,
                state="pending", via_aprs_is=via_aprs_is,
            )
            panel.clear_compose()

            # Start retry loop (handles initial send + retries via _send_message_frame)
            async def _start_retries():
                self._message_tracker.start_retry_loop(msg_id)

            self.run_worker(_start_retries())

            route = " via APRS-IS" if via_aprs_is else ""
            self.notify(f"Sending to {to_call.upper()}{route}: {msg_text}")

            # Return focus to stream
            with contextlib.suppress(Exception):
                self.query_one(StreamPanel).focus()
        except Exception as e:
            self.notify(f"Send failed: {e}", severity="error")

    def action_cancel_message(self) -> None:
        """Cancel all pending outbound messages."""
        pending = self._message_tracker.pending_count
        if pending == 0:
            self.notify("No pending messages to cancel")
            return

        cancelled = 0
        for msg in list(self._message_tracker.history):
            if msg.state.value == "pending" and self._message_tracker.cancel_message(msg.msg_id):
                cancelled += 1

        self.notify(f"Cancelled {cancelled} pending message(s)")

    def _ui_increment_rx(self) -> None:
        """Just increment RX counter without adding to stream."""
        with contextlib.suppress(Exception):
            self.query_one(StatusBar).increment_rx()
        with contextlib.suppress(Exception):
            self.query_one(AppFooter).increment_rx()

    def _ui_store_hidden_packet(self, pkt: APRSPacket) -> None:
        """Store packet in stream panel without displaying it."""
        try:
            stream = self.query_one(StreamPanel)
            stream._all_packets.append(pkt)
            if len(stream._all_packets) > stream._max_lines:
                stream._all_packets = stream._all_packets[-stream._max_lines:]
            status_bar = self.query_one(StatusBar)
            status_bar.increment_rx()
        except Exception:
            pass
        with contextlib.suppress(Exception):
            self.query_one(AppFooter).increment_rx()

    def action_toggle_aprs_is(self) -> None:
        """Toggle APRS-IS packet visibility in stream and map panels."""
        self._show_aprs_is = not self._show_aprs_is

        try:
            stream = self.query_one(StreamPanel)
            stream._hide_transport = "" if self._show_aprs_is else "APRS-IS"
            stream._rerender()
        except Exception:
            pass

        # Sync map panel IS filter with app-level toggle
        try:
            map_panel = self.query_one("#map-panel", MapPanel)
            if map_panel._filters.show_is_stations != self._show_aprs_is:
                map_panel._filters.show_is_stations = self._show_aprs_is
                map_panel._on_filter_changed()
        except Exception:
            pass

        if self._show_aprs_is:
            self.notify("APRS-IS packets: shown")
        else:
            self.notify("APRS-IS packets: hidden (still receiving)")

        self._refresh_stations()

    def _is_aprs_is_packet(self, pkt: APRSPacket) -> bool:
        """Check if a packet came from APRS-IS transport."""
        return "APRS-IS" in (pkt.transport or "")

    def _rerender_stream(self) -> None:
        """Re-render the stream panel respecting APRS-IS visibility."""
        try:
            stream = self.query_one(StreamPanel)
            stream.clear()
            stream._packet_count = 0
            for pkt in stream._all_packets:
                # Skip APRS-IS packets if hidden
                if not self._show_aprs_is and self._is_aprs_is_packet(pkt):
                    continue
                if stream._passes_filter(pkt):
                    stream._packet_count += 1
                    stream.write(stream._format_packet(pkt))
                    if stream._show_raw:
                        from rich.text import Text
                        stream.write(Text(f"  RAW: {pkt.raw}", style="italic #8b949e"))
        except Exception:
            pass

    def _refresh_stations(self) -> None:
        """Refresh station panel, filtering APRS-IS-only stations if hidden."""
        try:
            from aprs_tui.core.chat_store import list_chat_callsigns

            station_panel = self.query_one(StationPanel)
            stations = self._station_tracker.get_stations(
                sort_by=self._station_sort_key,
                reverse=self._station_sort_reverse,
            )

            if not self._show_aprs_is:
                rf_callsigns = set()
                stream = self.query_one(StreamPanel)
                for pkt in stream._all_packets:
                    if not self._is_aprs_is_packet(pkt) and pkt.source:
                        rf_callsigns.add(pkt.source.upper())
                stations = [s for s in stations if s.callsign.upper() in rf_callsigns]

            # Get callsigns with chat history (on disk + in memory)
            chat_calls = list_chat_callsigns()
            chat_calls.update(self._active_chats.keys())

            station_panel.refresh_stations(stations, chat_callsigns=chat_calls)

            # Update map panel chat indicators
            try:
                map_panel = self.query_one(MapPanel)
                map_panel.set_chat_callsigns(chat_calls)
            except Exception:
                pass
        except Exception:
            pass

    def action_copy_packet(self) -> None:
        """Copy the last received packet to clipboard (OSC 52)."""
        try:
            stream = self.query_one(StreamPanel)
            if not stream._all_packets:
                self.notify("No packets to copy")
                return

            last = stream._all_packets[-1]
            text = last.raw or ""

            # OSC 52 clipboard - works in most terminals including over SSH
            import base64
            encoded = base64.b64encode(text.encode()).decode()
            sys.stdout.write(f"\033]52;c;{encoded}\a")
            sys.stdout.flush()

            # Also try pyperclip as fallback
            try:
                import subprocess
                process = subprocess.Popen(
                    ["pbcopy"], stdin=subprocess.PIPE
                )
                process.communicate(text.encode())
            except Exception:
                pass

            self.notify(f"Copied: {text[:60]}...")
        except Exception as e:
            self.notify(f"Copy failed: {e}", severity="error")

    def action_open_filter(self) -> None:
        """Open packet filter (placeholder until full filter input widget)."""
        self.notify("Filter: use command palette (:filter) - coming soon")

    def action_toggle_raw(self) -> None:
        """Toggle raw packet display in the stream panel."""
        stream = self.query_one(StreamPanel)
        stream.toggle_raw()
        state = "ON" if stream._show_raw else "OFF"
        self.notify(f"Raw packets: {state}")

    # ------------------------------------------------------------------
    # Map panel (#52, #53, #68, #72)
    # ------------------------------------------------------------------

    def on_mount_map(self) -> None:
        """Hide map panel initially — shown via m toggle."""
        try:
            map_panel = self.query_one("#map-panel", MapPanel)
            map_panel.display = False
        except Exception:
            pass

    def _show_map(self, position: str) -> None:
        """Show the map in the given position, hiding whatever it replaces."""
        try:
            station_panel = self.query_one("#station-panel", StationPanel)
            stream_panel = self.query_one("#stream-panel", StreamPanel)
            map_panel = self.query_one("#map-panel", MapPanel)
        except Exception:
            self.notify("Map panel not available", severity="warning")
            return

        # First, fully restore previous state
        if self._map_visible:
            map_panel.remove_class("map-left", "map-right")
            if self._map_position == "left":
                stream_panel.display = True
            else:
                station_panel.display = True

        # Now show map in the requested position
        self._map_position = position
        self._map_visible = True

        if position == "left":
            # Map takes the stream's place (large, 2fr)
            stream_panel.display = False
            map_panel.remove_class("map-right")
            map_panel.add_class("map-left")
        else:
            # Map takes the station list's place (small, 1fr)
            station_panel.display = False
            map_panel.remove_class("map-left")
            map_panel.add_class("map-right")

        map_panel.focus()
        map_panel.notify_station_update()

        # Persist position preference
        self.config.map.position = position
        config_path = self._config_path or default_config_path()
        with contextlib.suppress(Exception):
            self.config.save(config_path)

    def _hide_map(self) -> None:
        """Hide the map and restore what it replaced."""
        try:
            station_panel = self.query_one("#station-panel", StationPanel)
            stream_panel = self.query_one("#stream-panel", StreamPanel)
            map_panel = self.query_one("#map-panel", MapPanel)
        except Exception:
            return

        map_panel.remove_class("map-left", "map-right")
        self._map_visible = False

        if self._map_position == "left":
            stream_panel.display = True
            stream_panel.focus()
        else:
            station_panel.display = True
            station_panel.focus()

    def action_toggle_map(self) -> None:
        """m key: Toggle map in the Packet Stream (left/large) position."""
        if self._map_visible and self._map_position == "left":
            self._hide_map()
        else:
            self._show_map("left")

    def action_toggle_map_position(self) -> None:
        """M key: Toggle map in the Station List (right/small) position."""
        if self._map_visible and self._map_position == "right":
            self._hide_map()
        else:
            self._show_map("right")

    def action_map_auto_zoom(self) -> None:
        """Toggle map auto-zoom."""
        try:
            map_panel = self.query_one("#map-panel", MapPanel)
            map_panel.action_toggle_auto_zoom()
            state = "ON" if map_panel.auto_zoom_enabled else "OFF"
            self.notify(f"Map auto-zoom: {state}")
        except Exception:
            pass

    def action_map_list(self) -> None:
        """Show available offline maps."""
        try:
            from aprs_tui.map.registry import MapRegistry
            registry = MapRegistry()
            maps = registry.list_maps()
            if not maps:
                self.notify("No offline maps downloaded. Use :map download")
                return
            lines = [f"  {m.name} (z{m.min_zoom}-{m.max_zoom}, {m.size_mb:.0f}MB)" for m in maps]
            self.notify("Available maps:\n" + "\n".join(lines), timeout=10)
        except Exception as e:
            self.notify(f"Map list error: {e}", severity="error")

    async def action_map_download(self) -> None:
        """Suspend TUI and run interactive map download."""
        download_script = Path(__file__).parent / "map" / "downloader.py"
        if not download_script.exists():
            self.notify("Map downloader not found", severity="error")
            return

        # Run the wizard's map download step
        wizard_path = Path(__file__).parent.parent / "wizard.py"
        cmd = [sys.executable, str(wizard_path), "--section", "map"]
        if self._config_path:
            cmd.extend(["--config", str(self._config_path)])

        with self.suspend():
            subprocess.run(cmd, check=False)

        # Reload map tiles after download
        try:
            map_panel = self.query_one("#map-panel", MapPanel)
            map_panel._try_load_tiles()
            map_panel.refresh()
        except Exception:
            pass

        self.notify("Map data updated")
