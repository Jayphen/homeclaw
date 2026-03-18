#!/usr/bin/env python3
"""Migrate bookmark notes, neighborhood, and city to markdown sidecar files.

Run:  python scripts/migrate_bookmarks.py [workspaces_path]

Defaults to ./workspaces. Idempotent — skips bookmarks that already have a
notes file. Strips migrated fields from bookmarks.json.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def migrate(workspaces: Path) -> None:
    bm_file = workspaces / "household" / "bookmarks" / "bookmarks.json"
    if not bm_file.exists():
        print("No bookmarks.json found — nothing to migrate.")
        return

    notes_dir = workspaces / "household" / "bookmarks" / "notes"
    notes_dir.mkdir(parents=True, exist_ok=True)

    bookmarks = json.loads(bm_file.read_text())
    migrated = 0

    for bm in bookmarks:
        bid = bm.get("id", "")
        title = bm.get("title", bid)
        notes = bm.pop("notes", "")
        neighborhood = bm.pop("neighborhood", "")
        city = bm.pop("city", "")

        # Build markdown content from all freeform fields
        lines: list[str] = []
        location = ", ".join(filter(None, [neighborhood, city]))
        if location:
            ts = (bm.get("saved_at") or "")[:16].replace("T", " ") or "unknown"
            lines.append(f"- [{ts}] Location: {location}")
        if notes:
            ts = (bm.get("saved_at") or "")[:16].replace("T", " ") or "unknown"
            lines.append(f"- [{ts}] {notes}")

        if not lines:
            continue

        path = notes_dir / f"{bid}.md"
        if path.exists():
            # Append to existing notes file
            with path.open("a") as f:
                f.write("\n".join(lines) + "\n")
        else:
            path.write_text(f"# {title}\n\n" + "\n".join(lines) + "\n")

        migrated += 1

    bm_file.write_text(json.dumps(bookmarks, indent=2) + "\n")
    print(f"Migrated {migrated} bookmarks to markdown notes.")


if __name__ == "__main__":
    ws = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("./workspaces")
    migrate(ws.resolve())
