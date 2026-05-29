"""Atomic, crash-safe file persistence helpers.

Every persisted JSON/JSONL file in the codebase was previously written with a
bare ``path.write_text(...)``. That truncates the target before writing, so a
crash mid-write corrupts the whole file, and a concurrent reader can observe a
half-written file. These helpers write to a temp file in the same directory and
``os.replace`` it into place — an atomic, same-filesystem rename — so a reader
always sees either the old or the new file, never a partial one.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


def atomic_write_text(path: Path, text: str) -> None:
    """Write ``text`` to ``path`` atomically (temp file + ``os.replace``).

    The temp file is created in the destination directory so the replace is a
    same-filesystem rename. On any failure the temp file is removed and the
    original ``path`` is left untouched.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def atomic_write_json(path: Path, obj: Any, *, indent: int | None = 2) -> None:
    """Serialize ``obj`` as JSON and write it atomically with a trailing newline."""
    atomic_write_text(path, json.dumps(obj, indent=indent) + "\n")


def read_json_safe(path: Path, default: Any = None) -> Any:
    """Read and parse JSON, returning ``default`` on a missing/corrupt/unreadable file."""
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return default
