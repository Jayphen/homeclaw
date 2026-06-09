"""Activity-feed logging and group-chat transcript logging."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from homeclaw.agent.providers.base import LLMProvider, Message

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Activity feed
# ---------------------------------------------------------------------------

# Tools worth surfacing in the activity feed (write/action tools only).
# Read-only tools like contact_list, memory_read, note_get are excluded.
FEED_WORTHY_TOOLS: set[str] = {
    "memory_save",
    "note_save",
    "reminder_add",
    "reminder_complete",
    "reminder_delete",
    "contact_update",
    "contact_note",
    "interaction_log",
    "bookmark_save",
    "bookmark_delete",
    "message_send",
    "image_send",
    "routine_run",
    "routine_add",
    "routine_update",
    "routine_remove",
    "decision_log",
    "skill_create",
    "skill_install",
    "channel_preference_set",
}

_SUMMARISE_PROMPT = """\
You are writing a short activity log entry for a household assistant app.

Given a tool call, write a single concise sentence (max 80 chars) describing \
what happened in plain English. Use past tense. Be specific — include names, \
topics, or titles from the arguments when available.

Examples:
- tool=memory_save args={"topic":"food","person":"alice"} → Saved a food memory for Alice
- tool=reminder_add args={"person":"bob","note":"dentist"} → Added a dentist reminder for Bob
- tool=message_send args={"person":"carol","text":"hi"} → Sent a message to Carol
- tool=bookmark_save args={"title":"Pasta recipe","url":"..."} → Bookmarked "Pasta recipe"

Respond with ONLY the summary sentence, nothing else."""


async def log_tool_event(
    workspaces: Path,
    tool_name: str,
    args: dict[str, Any],
    person: str,
    provider: LLMProvider | None,
) -> None:
    """Append a tool use event to the JSONL feed log.

    Uses the fast LLM to generate a human-readable summary. Falls back to
    a basic description if the provider is unavailable or the call fails.
    """
    if tool_name not in FEED_WORTHY_TOOLS:
        return

    safe_args = {k: str(v)[:100] for k, v in args.items()}
    summary: str | None = None

    if provider is not None:
        try:
            prompt = f"tool={tool_name} args={json.dumps(safe_args, default=str)}"
            resp = await provider.complete(
                messages=[Message(role="user", content=prompt)],
                tools=[],
                system=_SUMMARISE_PROMPT,
                max_tokens=60,
            )
            text = resp.content.strip().rstrip(".")
            if 5 < len(text) < 120:
                summary = text
        except Exception:
            logger.debug("LLM summary failed for %s, using fallback", tool_name)

    if summary is None:
        # Fallback: basic tool name → readable string
        label = tool_name.replace("_", " ")
        summary = f"{label.capitalize()} ({person})"

    log_dir = workspaces / "household" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": datetime.now(UTC).isoformat(),
        "tool": tool_name,
        "summary": summary,
        "person": person,
        "args": safe_args,
    }
    try:
        with open(log_dir / "tool_use.jsonl", "a") as f:
            f.write(json.dumps(entry, default=str) + "\n")
    except OSError:
        logger.debug("Failed to write tool_use.jsonl entry")


# ---------------------------------------------------------------------------
# Group chat transcript
# ---------------------------------------------------------------------------


def append_chat_log(
    workspaces: Path,
    channel: str,
    user_text: str,
    assistant_text: str,
) -> None:
    """Append a group chat exchange to a daily log for memsearch indexing.

    Logs both user messages and homeclaw responses so members can
    reference anything from the group conversation in their DMs.
    Rotated daily so individual files stay small.
    """
    channel_dir = workspaces / "household" / "channels" / channel
    channel_dir.mkdir(parents=True, exist_ok=True)

    today = datetime.now(UTC).strftime("%Y-%m-%d")
    log_path = channel_dir / f"{today}.md"

    timestamp = datetime.now(UTC).strftime("%H:%M")
    entry = f"- [{timestamp}] {user_text}\n- [{timestamp}] homeclaw: {assistant_text}\n"

    with open(log_path, "a") as f:
        f.write(entry)
