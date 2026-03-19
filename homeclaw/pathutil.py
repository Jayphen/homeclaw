"""Path safety utilities — prevent directory traversal in user-supplied inputs."""

import re
from pathlib import Path


def safe_slug(value: str) -> str:
    """Sanitize a user-supplied string into a safe filesystem slug.

    Strips everything except alphanumeric characters, hyphens, and underscores.
    Used for: topic names, skill names, person names, bookmark/contact IDs.
    """
    slug = re.sub(r"[^a-z0-9_-]", "", value.lower().replace(" ", "-"))
    slug = slug.strip("-_")
    if not slug:
        raise ValueError(f"Invalid name: {value!r} (empty after sanitization)")
    return slug


def safe_date(value: str) -> str:
    """Validate a date string is YYYY-MM-DD format. Returns the validated string.

    Prevents path traversal via date parameters like '../../etc/passwd'.
    """
    from datetime import date

    # fromisoformat validates format and value ranges
    date.fromisoformat(value)
    return value


def safe_path_within(base: Path, *parts: str) -> Path:
    """Build a path from parts and verify it stays within the base directory.

    Raises ValueError if the resolved path escapes the base.
    """
    target = base.joinpath(*parts).resolve()
    base_resolved = base.resolve()
    if not target.is_relative_to(base_resolved):
        raise ValueError(f"Path escapes base directory: {'/'.join(parts)}")
    return target
