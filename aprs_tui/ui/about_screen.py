"""About and license information screen."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Static

VERSION = "0.1.0"

ABOUT_TEXT = f"""\
[bold #58a6ff]APRS TUI[/bold #58a6ff] [dim]v{VERSION}[/dim]

A terminal user interface for APRS (Automatic Packet Reporting System).
Built for ham radio operators who prefer the command line.

[bold]Source Code & Downloads[/bold]
  [#58a6ff]https://github.com/eusef/eusef-aprs-tui[/#58a6ff]

[bold]Author[/bold]
  Phil Johnston (W7PDJ)
  [#58a6ff]https://philjohnstonii.com[/#58a6ff]
  [#58a6ff]https://mastodon.social/@philj2[/#58a6ff]
  [#58a6ff]https://www.youtube.com/@PhilJohnston[/#58a6ff]

[bold]☕ Support This Project[/bold]
  If you find APRS TUI useful, consider buying me a coffee!
  [#58a6ff]https://ko-fi.com/philj2[/#58a6ff]

[bold]🐛 Report a Bug / Request a Feature[/bold]
  [#58a6ff]https://github.com/eusef/eusef-aprs-tui/issues/new[/#58a6ff]

[bold]License[/bold]
  MIT License - See LICENSE file in repository

[bold]Built With[/bold]
  This application was built with the assistance of Claude (Anthropic).
"""

LIBRARIES = [
    ("Textual", "8.1.1", "MIT", "Terminal UI framework", "https://github.com/Textualize/textual"),
    ("aprslib", "0.7.2", "GPL-2.0", "APRS packet parsing", "https://github.com/rossengeorgiev/aprs-python"),
    ("Pydantic", "2.x", "MIT", "Data validation & config models", "https://github.com/pydantic/pydantic"),
    ("Bleak", "2.1.1", "MIT", "Bluetooth Low Energy (BLE)", "https://github.com/hbldh/bleak"),
    ("pySerial", "3.5", "BSD-3", "Serial port access", "https://github.com/pyserial/pyserial"),
    ("Rich", "14.x", "MIT", "Terminal formatting", "https://github.com/Textualize/rich"),
    ("questionary", "2.1.1", "MIT", "Interactive CLI prompts", "https://github.com/tmbo/questionary"),
    ("tomli-w", "1.2.0", "MIT", "TOML writing", "https://github.com/hukkin/tomli-w"),
    ("platformdirs", "4.x", "MIT", "Platform config directories", "https://github.com/platformdirs/platformdirs"),
    ("zeroconf", "0.131+", "LGPL-2.1", "mDNS service discovery", "https://github.com/python-zeroconf/python-zeroconf"),
]

NOTICE = """\
[bold]Legal Notices[/bold]

[bold]FCC Notice (USA)[/bold]
  Operation of this software with a radio transmitter requires a valid
  amateur radio license issued by the FCC (or equivalent authority in
  your country). Transmitting without a license is illegal.

[bold]APRS[/bold]
  APRS is a registered trademark of Bob Bruninga, WB4APR (SK).

[bold]Open Source Licenses[/bold]
  This software includes components licensed under MIT, BSD, GPL, and
  LGPL licenses. The GPL-licensed aprslib library is used for packet
  parsing. See individual library repositories for full license text.

  [dim]Note: aprslib is licensed under GPL-2.0. If you distribute this
  software with aprslib included, the combined work must comply with
  GPL-2.0 terms. For details, see:
  https://github.com/rossengeorgiev/aprs-python/blob/master/LICENSE[/dim]
"""


class AboutScreen(ModalScreen[None]):
    """Modal overlay showing about info, libraries, and legal notices."""

    DEFAULT_CSS = """
    AboutScreen {
        align: center middle;
    }
    #about-dialog {
        width: 80;
        max-width: 95%;
        height: 85%;
        background: #161b22;
        border: solid #58a6ff;
        border-title-color: #58a6ff;
        padding: 1 2;
    }
    #about-scroll {
        height: 1fr;
    }
    #about-footer {
        height: 1;
        dock: bottom;
        color: #484f58;
        text-align: center;
    }
    """

    BINDINGS = [
        Binding("escape", "close", "Close", priority=True),
        Binding("q", "close", "Close", priority=True),
    ]

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="about-dialog"):
            yield Static(ABOUT_TEXT, markup=True, id="about-text")
            yield Static(self._build_library_table(), markup=True, id="lib-table")
            yield Static(NOTICE, markup=True, id="notice-text")
            yield Static(
                "[dim]Press Esc or q to close  |  j/k to scroll[/dim]",
                id="about-footer",
                markup=True,
            )

    def on_mount(self) -> None:
        self.query_one("#about-dialog").border_title = f"About APRS TUI v{VERSION}"

    def _build_library_table(self) -> str:
        """Build the library table as Rich markup."""
        lines = ["[bold]Open Source Libraries[/bold]\n"]
        header = f"{'Library':<16s}{'Version':<10s}{'License':<12s}Description"
        lines.append(f"  [bold #8b949e]{header}[/bold #8b949e]")
        lines.append(f"  [dim]{'─' * 68}[/dim]")

        for name, version, license_, desc, url in LIBRARIES:
            lines.append(
                f"  [bold #e6edf3]{name:<16s}[/bold #e6edf3]"
                f"[#8b949e]{version:<10s}[/#8b949e]"
                f"[#e3b341]{license_:<12s}[/#e3b341]"
                f"[#8b949e]{desc}[/#8b949e]"
            )
            lines.append(f"  [dim #58a6ff]{url}[/dim #58a6ff]")

        lines.append("")
        return "\n".join(lines)

    def action_close(self) -> None:
        self.dismiss(None)
