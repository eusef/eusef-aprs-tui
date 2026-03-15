"""Entry point for the APRS TUI application.

Usage:
    python -m aprs_tui [--config PATH] [--log-level LEVEL]

Issue #26: First-run detection + wizard auto-launch.
Issue #42: Packet logging + --log-level CLI argument.
"""
from __future__ import annotations

import argparse
import logging
import subprocess
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
    parser.add_argument(
        "--log-level",
        default="WARNING",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Set logging level (default: WARNING)",
    )
    args = parser.parse_args()

    # Set up logging - write to file, not stderr (stderr corrupts the TUI)
    from platformdirs import user_data_dir
    log_dir = Path(user_data_dir("aprs-tui"))
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        filename=str(log_dir / "aprs-tui.log"),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    # Load config
    config_path = args.config
    try:
        config = AppConfig.load(config_path)
    except FileNotFoundError:
        path = config_path or default_config_path()
        print(f"No configuration found at {path}")
        print("Launching setup wizard...\n")

        # Launch wizard as subprocess
        wizard_path = Path(__file__).parent.parent / "wizard.py"
        if not wizard_path.exists():
            print(f"[ERROR] Wizard not found at {wizard_path}", file=sys.stderr)
            print("  Create a config file manually or run the wizard.", file=sys.stderr)
            sys.exit(1)

        result = subprocess.run(
            [sys.executable, str(wizard_path), "--config", str(path)],
            check=False,
        )

        if result.returncode != 0:
            print("Wizard was cancelled or failed.")
            sys.exit(1)

        # Try loading config again after wizard
        try:
            config = AppConfig.load(config_path)
        except Exception as e:
            print(f"[ERROR] Config still invalid after wizard: {e}", file=sys.stderr)
            sys.exit(1)
    except Exception as e:
        print(f"[ERROR] Invalid config: {e}", file=sys.stderr)
        sys.exit(1)

    # Launch the TUI
    from aprs_tui.app import APRSTuiApp

    app = APRSTuiApp(config, config_path=config_path)
    app.run()


if __name__ == "__main__":
    main()
