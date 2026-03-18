"""Managed Direwolf subprocess for local software TNC operation.

Starts Direwolf as a child process when the app uses kiss-tcp with a
local direwolf.conf. Stops it cleanly on app exit. No system services,
no launchd — fully self-contained.
"""
from __future__ import annotations

import asyncio
import logging
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


class DirewolfManager:
    """Manages a local Direwolf process tied to the app lifecycle.

    Args:
        config_path: Path to the direwolf.conf file
        direwolf_bin: Path to the direwolf binary (auto-detected if None)
    """

    def __init__(
        self,
        config_path: Path,
        direwolf_bin: str | None = None,
    ) -> None:
        self._config_path = config_path
        self._direwolf_bin = direwolf_bin or self._find_direwolf()
        self._process: subprocess.Popen | None = None
        self._log_path = config_path.parent / "direwolf.log"

    @staticmethod
    def _find_direwolf() -> str:
        """Find the direwolf binary on the system."""
        path = shutil.which("direwolf")
        if path:
            return path
        # Common macOS locations
        for candidate in [
            "/opt/local/bin/direwolf",      # MacPorts
            "/opt/homebrew/bin/direwolf",    # Homebrew Apple Silicon
            "/usr/local/bin/direwolf",       # Homebrew Intel
        ]:
            if Path(candidate).exists():
                return candidate
        raise FileNotFoundError(
            "Direwolf not found. Install via: brew install direwolf"
        )

    @staticmethod
    def has_local_config(app_dir: Path) -> bool:
        """Check if a local direwolf.conf exists in the app directory."""
        return (app_dir / "direwolf.conf").exists()

    @property
    def is_running(self) -> bool:
        return self._process is not None and self._process.poll() is None

    @property
    def log_path(self) -> Path:
        return self._log_path

    def start(self) -> None:
        """Start Direwolf as a child process."""
        if self.is_running:
            logger.info("Direwolf already running (pid %d)", self._process.pid)
            return

        if not self._config_path.exists():
            raise FileNotFoundError(f"Direwolf config not found: {self._config_path}")

        logger.info("Starting Direwolf: %s -c %s", self._direwolf_bin, self._config_path)

        # Open log file for stdout/stderr
        with open(self._log_path, "a") as log_file:
            self._process = subprocess.Popen(
                [self._direwolf_bin, "-c", str(self._config_path), "-t", "0"],
                stdout=log_file,
                stderr=log_file,
                # Start in its own process group so we can kill it cleanly
                preexec_fn=None,
            )

        logger.info("Direwolf started (pid %d), log: %s", self._process.pid, self._log_path)

    def stop(self, timeout: float = 5.0) -> None:
        """Stop the Direwolf process gracefully."""
        if not self.is_running:
            return

        pid = self._process.pid
        logger.info("Stopping Direwolf (pid %d)...", pid)

        try:
            self._process.terminate()
            try:
                self._process.wait(timeout=timeout)
                logger.info("Direwolf stopped gracefully")
            except subprocess.TimeoutExpired:
                logger.warning("Direwolf did not stop gracefully, killing...")
                self._process.kill()
                self._process.wait(timeout=2.0)
                logger.info("Direwolf killed")
        except Exception as e:
            logger.error("Error stopping Direwolf: %s", e)
        finally:
            self._process = None

    async def start_and_wait_ready(self, kiss_port: int = 8001, timeout: float = 10.0) -> bool:
        """Start Direwolf and wait until the KISS TCP port is accepting connections.

        Returns True if Direwolf is ready, False on timeout.
        """
        self.start()

        # Poll until KISS port is open
        deadline = asyncio.get_event_loop().time() + timeout
        while asyncio.get_event_loop().time() < deadline:
            if not self.is_running:
                exit_code = self._process.returncode if self._process else "?"
                logger.error("Direwolf exited unexpectedly (exit code: %s)", exit_code)
                return False

            try:
                _, writer = await asyncio.wait_for(
                    asyncio.open_connection("127.0.0.1", kiss_port),
                    timeout=1.0,
                )
                writer.close()
                await writer.wait_closed()
                logger.info("Direwolf KISS port %d is ready", kiss_port)
                return True
            except (TimeoutError, ConnectionRefusedError, OSError):
                await asyncio.sleep(0.5)

        logger.error("Direwolf KISS port %d not ready after %.0fs", kiss_port, timeout)
        return False
