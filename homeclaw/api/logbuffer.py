"""In-memory ring buffer + persistent JSONL file for application logs.

Captures log records from the root logger so the web UI can display
recent activity without reading files or stdout.  The file handler
writes one JSON object per line for date-range queries and downloads.
"""

import json
import logging
import os
from collections import deque
from datetime import UTC, datetime, timedelta, tzinfo
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


def _log_entry(record: logging.LogRecord, tz: tzinfo) -> dict[str, Any]:
    msg = record.getMessage()
    if record.exc_info and record.exc_info[1] is not None:
        # Append the traceback so exceptions show up in the UI and log file
        fmt = logging.Formatter()
        msg = msg + "\n" + fmt.formatException(record.exc_info)
    entry: dict[str, Any] = {
        "ts": datetime.fromtimestamp(
            record.created, tz=tz,
        ).isoformat(),
        "level": record.levelname,
        "logger": record.name,
        "message": msg,
    }
    # Propagate extra tags (e.g. model name from agent loop)
    model = getattr(record, "model", None)
    if model:
        entry["model"] = model
    return entry


class LogBuffer(logging.Handler):
    """A logging handler that keeps the last *maxlen* formatted records."""

    def __init__(self, maxlen: int = 500, tz: tzinfo | None = None) -> None:
        super().__init__()
        self._records: deque[dict[str, Any]] = deque(maxlen=maxlen)
        self._tz: tzinfo = tz or UTC

    def emit(self, record: logging.LogRecord) -> None:
        self._records.append(_log_entry(record, self._tz))

    def get_entries(
        self, limit: int = 200, level: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return recent log entries, newest first."""
        entries = list(self._records)
        if level:
            entries = [
                e for e in entries if e["level"] == level.upper()
            ]
        return list(reversed(entries[-limit:]))


class LogFileHandler(RotatingFileHandler):
    """Writes log records as JSONL for persistent querying."""

    def __init__(
        self,
        path: Path,
        tz: tzinfo | None = None,
        max_bytes: int = 5 * 1024 * 1024,
        backup_count: int = 3,
    ) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        super().__init__(
            str(path),
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        self._tz: tzinfo = tz or UTC

    def emit(self, record: logging.LogRecord) -> None:
        try:
            entry = _log_entry(record, self._tz)
            msg = json.dumps(entry, default=str)
            # Create a shallow copy so we don't corrupt the record
            # for other handlers (ring buffer, stderr).
            rec = logging.makeLogRecord(record.__dict__)
            rec.msg = msg
            rec.args = None
            super().emit(rec)
        except Exception:
            self.handleError(record)


def read_log_file(
    path: Path,
    after: datetime | None = None,
    before: datetime | None = None,
    level: str | None = None,
    search: str | None = None,
    limit: int = 5000,
) -> list[dict[str, Any]]:
    """Read JSONL log file with filtering. Returns newest first."""
    entries: list[dict[str, Any]] = []
    paths = _rotated_paths(path)
    for p in paths:
        if not p.exists():
            continue
        with open(p) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if level and entry.get("level") != level.upper():
                    continue
                ts_str = entry.get("ts", "")
                if after or before:
                    try:
                        ts = datetime.fromisoformat(ts_str)
                        if after and ts < after:
                            continue
                        if before and ts > before:
                            continue
                    except (ValueError, TypeError):
                        continue
                if search:
                    q = search.lower()
                    msg = entry.get("message", "").lower()
                    name = entry.get("logger", "").lower()
                    if q not in msg and q not in name:
                        continue
                entries.append(entry)
    entries.sort(key=lambda e: e.get("ts", ""), reverse=True)
    return entries[:limit]


def _rotated_paths(base: Path) -> list[Path]:
    """Return the base log file + any rotated backups, newest first."""
    paths = [base]
    for i in range(1, 10):
        rotated = base.with_suffix(f".log.{i}")
        if rotated.exists():
            paths.append(rotated)
        else:
            break
    return paths


_buffer: LogBuffer | None = None
_log_file_path: Path | None = None


def install_log_buffer(
    maxlen: int = 500,
    timezone: str | None = None,
    log_dir: Path | None = None,
) -> LogBuffer:
    """Install the log buffer on the root logger. Idempotent."""
    global _buffer, _log_file_path
    if _buffer is not None:
        return _buffer
    tz = ZoneInfo(timezone) if timezone else None
    root = logging.getLogger()

    # In-memory ring buffer
    _buffer = LogBuffer(maxlen=maxlen, tz=tz)
    _buffer.setLevel(logging.DEBUG)
    root.addHandler(_buffer)

    # Persistent JSONL file
    if log_dir is None:
        log_dir = Path(
            os.environ.get("HOMECLAW_WORKSPACES", "workspaces"),
        ) / "household" / "logs"
    _log_file_path = log_dir / "homeclaw.log"
    file_handler = LogFileHandler(_log_file_path, tz=tz)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter("%(message)s"))
    root.addHandler(file_handler)

    return _buffer


def get_log_buffer() -> LogBuffer | None:
    return _buffer


def get_log_file_path() -> Path | None:
    return _log_file_path


def get_log_entries_from_file(
    after: datetime | None = None,
    before: datetime | None = None,
    level: str | None = None,
    search: str | None = None,
    limit: int = 5000,
) -> list[dict[str, Any]]:
    """Read persisted log entries with date-range filtering.

    Defaults to the past 24 hours if no range is specified.
    """
    if _log_file_path is None:
        return []
    if after is None and before is None:
        tz = getattr(_buffer, "_tz", UTC) if _buffer else UTC
        after = datetime.now(tz=tz) - timedelta(hours=24)
    return read_log_file(
        _log_file_path,
        after=after,
        before=before,
        level=level,
        search=search,
        limit=limit,
    )
