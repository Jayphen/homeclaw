"""In-memory ring buffer for application logs.

Captures log records from the root logger so the web UI can display
recent activity without reading files or stdout.
"""

import logging
from collections import deque
from datetime import UTC, datetime
from typing import Any


class LogBuffer(logging.Handler):
    """A logging handler that keeps the last *maxlen* formatted records."""

    def __init__(self, maxlen: int = 500) -> None:
        super().__init__()
        self._records: deque[dict[str, Any]] = deque(maxlen=maxlen)

    def emit(self, record: logging.LogRecord) -> None:
        self._records.append({
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        })

    def get_entries(self, limit: int = 200, level: str | None = None) -> list[dict[str, Any]]:
        """Return recent log entries, newest first."""
        entries = list(self._records)
        if level:
            entries = [e for e in entries if e["level"] == level.upper()]
        return list(reversed(entries[-limit:]))


_buffer: LogBuffer | None = None


def install_log_buffer(maxlen: int = 500) -> LogBuffer:
    """Install the log buffer on the root logger. Idempotent."""
    global _buffer
    if _buffer is not None:
        return _buffer
    _buffer = LogBuffer(maxlen=maxlen)
    _buffer.setLevel(logging.DEBUG)
    logging.getLogger().addHandler(_buffer)
    return _buffer


def get_log_buffer() -> LogBuffer | None:
    return _buffer
