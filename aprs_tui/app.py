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

import asyncio
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

    COMMANDS = {APRSCommandProvider}

    BINDINGS = [
        # Global (priority=True so they work everywhere)
        Binding("q", "quit", "q Quit", priority=True),
        Binding("question_mark", "toggle_help", "? Help", priority=True),
        Binding("ctrl+w", "config('all')", "^W Config", priority=True),
        Binding("b", "toggle_beacon", "b Beacon", priority=True),

        # Navigation
        Binding("tab", "focus_next", "Tab Next"),
        Binding("shift+tab", "focus_previous", "Prev Panel"),

        # Panel scrolling (vim-style)
        Binding("j", "scroll_down", "j/k Scroll", show=False),
        Binding("k", "scroll_up", "Up", show=False),

        # Command palette (vim-style : to open)
        Binding("colon", "command_palette", ": Command", show=False),

        # Cancel pending message
        Binding("x", "cancel_message", "x Cancel msg", show=False),

        # Compose
        Binding("c", "focus_compose", "c Compose", priority=True),

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
        self._aprs_is_manager: ConnectionManager | None = None
        self._tx_lock = asyncio.Lock()
        self._station_tracker = StationTracker(
            own_lat=getattr(config.station, "latitude", None),
            own_lon=getattr(config.station, "longitude", None),
        )
        self._message_tracker = MessageTracker(
            own_callsign=self.callsign,
            send_func=self._send_message_frame,
            on_inbound=self._on_inbound_message,
            on_state_change=self._on_message_state_change,
            on_retry=self._on_message_retry,
        )
        self._beacon_manager = None  # Created after connection

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
            on_health_warning=self._on_health_warning,
        )

        status_bar = self.query_one(StatusBar)
        status_bar.update_state(ConnectionState.CONNECTING, transport.display_name)

        try:
            await self._connection_manager.connect()

            # Create beacon manager now that we have a transport
            from aprs_tui.core.beacon import BeaconManager
            self._beacon_manager = BeaconManager(
                callsign=self.callsign,
                latitude=self.config.beacon.latitude,
                longitude=self.config.beacon.longitude,
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

        # Start APRS-IS as secondary connection if enabled and primary isn't already APRS-IS
        if (self.config.aprs_is.enabled
                and self.config.server.protocol != "aprs-is"):
            self.run_worker(self._connect_aprs_is())

    async def _connect_aprs_is(self) -> None:
        """Connect to APRS-IS as a secondary transport."""
        from aprs_tui.transport.aprs_is import AprsIsTransport
        from aprs_tui.core.dedup import DeduplicationFilter

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
        except Exception:
            self.call_later(
                self.notify,
                "APRS-IS connection failed",
                severity="warning",
            )

    def _on_aprs_is_state_change(self, state: ConnectionState) -> None:
        """Handle APRS-IS connection state changes."""
        pass  # Primary status bar shows radio; APRS-IS is secondary

    def _on_aprs_is_packet(self, pkt: APRSPacket) -> None:
        """Handle packets from APRS-IS (secondary transport)."""
        # Dedup: skip if we already got this packet from radio
        if hasattr(self, '_dedup') and self._dedup.is_duplicate(pkt):
            return

        self.packet_bus.publish(pkt)
        self._station_tracker.update(pkt)
        self._message_tracker.handle_packet(pkt)
        self.call_later(self._ui_update_packet, pkt)

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
        self.call_later(self._ui_inbound_message, msg)

    def _on_message_state_change(self, tracked: TrackedMessage) -> None:
        self.call_later(self._ui_message_state_change, tracked)

    def _ui_inbound_message(self, msg: InboundMessage) -> None:
        """Show inbound message in panel + notification."""
        try:
            panel = self.query_one(MessagePanel)
            panel.add_received_message(msg.source, msg.text, msg.msg_id)
            self.notify(f"Message from {msg.source}: {msg.text}")
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
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    async def action_quit(self) -> None:
        """Quit the application, disconnecting cleanly."""
        try:
            # Stop beacon
            if self._beacon_manager and self._beacon_manager.enabled:
                self._beacon_manager.disable()

            # Cancel all message retry tasks
            self._message_tracker.stop()

            # Disconnect transports with timeout
            for mgr in (self._connection_manager, self._aprs_is_manager):
                if mgr:
                    try:
                        await asyncio.wait_for(mgr.disconnect(), timeout=3.0)
                    except (asyncio.TimeoutError, Exception):
                        pass
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

        old_config = self.config
        self.config = new_config
        self.callsign = f"{new_config.station.callsign}-{new_config.station.ssid}"

        # Update status bar callsign
        status_bar = self.query_one(StatusBar)
        status_bar.callsign = self.callsign

        # Always reconnect after wizard (we disconnected before suspend)
        if self._connection_manager:
            try:
                await self._connection_manager.disconnect()
            except Exception:
                pass
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
            if self.config.beacon.latitude == 0.0 and self.config.beacon.longitude == 0.0:
                self.notify("Set your position first (Ctrl+W → beacon)", severity="warning")
                return
            self._beacon_manager.enable()
            self.notify(f"Beacon ON - every {self._beacon_manager.interval}s")

    async def _send_message_frame(self, info: str) -> None:
        """Send an APRS message info field as an AX.25 frame via the transport.

        Called by MessageTracker for initial send and retries.
        Uses a TX lock to prevent simultaneous transmissions.
        """
        async with self._tx_lock:
            if not self._connection_manager or self._connection_manager.state.value != "connected":
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
            to_call, msg_text = panel.get_compose_values()

            if not to_call:
                self.notify("Enter a destination callsign", severity="warning")
                return
            if not msg_text:
                self.notify("Enter a message", severity="warning")
                return

            # Track the message and start retry loop
            msg_id = self._message_tracker.send_message(to_call.upper(), msg_text)

            # Show in panel
            panel.add_sent_message(to_call.upper(), msg_text, msg_id, state="pending")
            panel.clear_compose()

            # Start retry loop (handles initial send + retries via _send_message_frame)
            async def _start_retries():
                self._message_tracker.start_retry_loop(msg_id)

            self.run_worker(_start_retries())
            self.notify(f"Sending to {to_call.upper()}: {msg_text}")

            # Return focus to stream
            try:
                self.query_one(StreamPanel).focus()
            except Exception:
                pass
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
            if msg.state.value == "pending":
                if self._message_tracker.cancel_message(msg.msg_id):
                    cancelled += 1

        self.notify(f"Cancelled {cancelled} pending message(s)")

    def action_open_filter(self) -> None:
        """Open packet filter (placeholder until full filter input widget)."""
        self.notify("Filter: use command palette (:filter) - coming soon")

    def action_toggle_raw(self) -> None:
        """Toggle raw packet display in the stream panel."""
        stream = self.query_one(StreamPanel)
        stream.toggle_raw()
        state = "ON" if stream._show_raw else "OFF"
        self.notify(f"Raw packets: {state}")
