"""Markdown-based memory store — one file per topic per person.

Files live at workspaces/{person}/memory/{topic}.md and are indexed by
memsearch for semantic recall. Each entry is appended with a timestamp,
so history is preserved and the agent never has to read-then-merge.
"""

from datetime import datetime, timezone
from pathlib import Path


def _memory_dir(workspaces: Path, person: str) -> Path:
    d = workspaces / person / "memory"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _slugify(topic: str) -> str:
    """Turn a topic name into a safe filename slug."""
    from homeclaw.pathutil import safe_slug

    return safe_slug(topic)


def memory_save_topic(
    workspaces: Path, person: str, topic: str, content: str
) -> Path:
    """Append a memory entry to a topic file. Creates the file if needed."""
    d = _memory_dir(workspaces, person)
    slug = _slugify(topic)
    path = d / f"{slug}.md"
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")

    if not path.exists():
        path.write_text(f"# {topic}\n\n- [{timestamp}] {content}\n")
    else:
        with path.open("a") as f:
            f.write(f"- [{timestamp}] {content}\n")
    return path


def memory_read_topic(workspaces: Path, person: str, topic: str) -> str | None:
    """Read a topic file's contents. Returns None if it doesn't exist."""
    d = _memory_dir(workspaces, person)
    slug = _slugify(topic)
    path = d / f"{slug}.md"
    if not path.exists():
        return None
    return path.read_text()


def memory_list_topics(workspaces: Path, person: str) -> list[str]:
    """List all memory topic filenames for a person."""
    d = workspaces / person / "memory"
    if not d.is_dir():
        return []
    return sorted(f.stem for f in d.iterdir() if f.suffix == ".md")
