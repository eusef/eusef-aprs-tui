"""Persistent chat storage - saves conversations to JSON files."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from platformdirs import user_data_dir

logger = logging.getLogger(__name__)


def _chat_dir() -> Path:
    """Get the chat storage directory."""
    d = Path(user_data_dir("aprs-tui")) / "chats"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _chat_file(callsign: str) -> Path:
    """Get the file path for a callsign's chat history."""
    safe = callsign.upper().replace("/", "_").replace("\\", "_")
    return _chat_dir() / f"{safe}.json"


def save_chat(callsign: str, messages: list[dict]) -> None:
    """Save chat messages to disk.

    Args:
        callsign: The peer callsign
        messages: List of message dicts with keys:
                  direction, text, msg_id, state, timestamp
    """
    path = _chat_file(callsign)
    try:
        path.write_text(json.dumps(messages, indent=2))
        logger.debug("Saved %d messages for %s", len(messages), callsign)
    except Exception as e:
        logger.error("Failed to save chat for %s: %s", callsign, e)


def load_chat(callsign: str) -> list[dict]:
    """Load chat messages from disk.

    Returns list of message dicts, or empty list if no history.
    """
    path = _chat_file(callsign)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text())
        logger.debug("Loaded %d messages for %s", len(data), callsign)
        return data
    except Exception as e:
        logger.error("Failed to load chat for %s: %s", callsign, e)
        return []


def list_chat_callsigns() -> set[str]:
    """Return set of callsigns that have chat history on disk."""
    try:
        return {
            f.stem.upper()
            for f in _chat_dir().glob("*.json")
            if f.stat().st_size > 2  # skip empty files
        }
    except Exception:
        return set()


def delete_chat(callsign: str) -> None:
    """Delete chat history for a callsign."""
    path = _chat_file(callsign)
    try:
        path.unlink(missing_ok=True)
    except Exception:
        pass
