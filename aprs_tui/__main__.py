"""Entry point for the APRS TUI application.

Usage:
    python -m aprs_tui [--config PATH]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from aprs_tui.config import AppConfig, default_config_path


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="APRS TUI - Terminal APRS Client")
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help=f"Config file path (default: {default_config_path()})",
    )
    args = parser.parse_args()

    # Load config
    config_path = args.config
    try:
        config = AppConfig.load(config_path)
    except FileNotFoundError:
        path = config_path or default_config_path()
        print(f"[ERROR] Config file not found: {path}", file=sys.stderr)
        print("  Run the setup wizard first, or create a config file.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] Invalid config: {e}", file=sys.stderr)
        sys.exit(1)

    # Launch the TUI
    from aprs_tui.app import APRSTuiApp

    app = APRSTuiApp(config)
    app.run()


if __name__ == "__main__":
    main()
