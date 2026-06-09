"""History persistence, windowing, and token estimation for the agent loop.

Owns:
- JSONL append-only history file read/write with consolidation pointer
- Token estimation helpers for messages and tool schemas
- History sanitisation (orphaned tool results, broken chains)
- Live-window truncation (bounds the prompt sent to the LLM)
- Image-stripping and persistable-message preparation
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from homeclaw.agent.context import estimate_tokens
from homeclaw.agent.providers.base import Message
from homeclaw.atomicio import atomic_write_text

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Budget constants
# ---------------------------------------------------------------------------

# Fraction of context window reserved for non-history content (system, tools, output).
RESERVED_FRACTION = 0.35
DEFAULT_CONTEXT_WINDOW = 128_000

# Live prompts should stay compact even when a model has a huge context window.
# Append-only history remains on disk for consolidation; this only limits what
# each request sends to the model.
LIVE_HISTORY_TOKEN_FRACTION = 0.06
LIVE_HISTORY_MAX_MESSAGES = 80

# ---------------------------------------------------------------------------
# Token estimation
# ---------------------------------------------------------------------------


def estimate_message_tokens(msg: Message) -> int:
    """Estimate tokens for a single message."""
    if isinstance(msg.content, str):
        return estimate_tokens(msg.content)
    # Multimodal: estimate text blocks, add flat cost per image
    total = 0
    for block in msg.content:
        if isinstance(block, dict) and block.get("type") == "text":
            total += estimate_tokens(block["text"])
        elif isinstance(block, dict) and block.get("type") == "image":
            total += 1000  # rough estimate for image tokens
    return total


def estimate_tool_tokens(tools: list[Any]) -> int:
    """Estimate prompt tokens contributed by tool schemas."""
    try:
        text = json.dumps(
            [
                tool.model_dump(mode="json") if hasattr(tool, "model_dump") else tool
                for tool in tools
            ],
            default=str,
        )
    except TypeError:
        text = str(tools)
    return estimate_tokens(text)


# ---------------------------------------------------------------------------
# Sanitisation
# ---------------------------------------------------------------------------


def sanitize_history(history: list[Message]) -> list[Message]:
    """Ensure history has valid structure for the LLM API.

    Fixes common issues that cause 400 errors:
    - Orphaned tool results (no preceding assistant with tool_calls)
    - Assistant messages with tool_calls but missing tool results
    - Consecutive same-role messages (merges them)
    """
    if not history:
        return history

    cleaned: list[Message] = []
    i = 0
    while i < len(history):
        msg = history[i]

        # Skip orphaned tool results
        if msg.role == "tool" and (
            not cleaned or cleaned[-1].role != "assistant" or not cleaned[-1].tool_calls
        ):
            i += 1
            continue

        # Assistant with tool_calls: check that tool results follow
        if msg.role == "assistant" and msg.tool_calls:
            expected_ids = {tc.id for tc in msg.tool_calls}
            # Peek ahead for tool results
            j = i + 1
            found_ids: set[str] = set()
            while j < len(history) and history[j].role == "tool":
                tid = history[j].tool_call_id
                if tid:
                    found_ids.add(tid)
                j += 1

            if found_ids >= expected_ids:
                # All tool results present — keep the full chain
                cleaned.append(msg)
                i += 1
                continue

            # Tool results are missing — strip tool_calls so the API
            # sees this as a plain text message instead of a broken chain
            text = msg.content if isinstance(msg.content, str) else ""
            if not text:
                i = j  # skip partial tool results
                continue
            msg = msg.model_copy(update={"tool_calls": []})
            i = j  # skip partial tool results
            # Fall through to merge/append below

        else:
            i += 1

        # Merge consecutive same-role messages
        if cleaned and msg.role == cleaned[-1].role and msg.role in ("user", "assistant"):
            prev = cleaned[-1]
            prev_text = prev.content if isinstance(prev.content, str) else ""
            cur_text = msg.content if isinstance(msg.content, str) else ""
            merged = (prev_text + "\n" + cur_text).strip()
            cleaned[-1] = prev.model_copy(update={"content": merged})
            continue

        cleaned.append(msg)

    # Final pass: drop trailing assistant with pending tool_calls
    while cleaned and cleaned[-1].role == "assistant" and cleaned[-1].tool_calls:
        cleaned.pop()

    return cleaned


def truncate_history(
    history: list[Message],
    system_tokens: int,
    context_window: int,
) -> list[Message]:
    """Drop oldest messages so history fits within the live prompt target."""
    window = context_window
    capacity_budget = int(window * (1 - RESERVED_FRACTION)) - system_tokens
    live_budget = int(window * LIVE_HISTORY_TOKEN_FRACTION)
    budget = min(capacity_budget, live_budget)

    if budget <= 0:
        return history[-2:]  # keep at least current exchange

    # Walk backwards, accumulating tokens until we exceed budget.
    kept: list[Message] = []
    used = 0
    for msg in reversed(history):
        cost = estimate_message_tokens(msg)
        if used + cost > budget and kept:
            break
        kept.append(msg)
        used += cost

    kept.reverse()
    if len(kept) < len(history):
        logger.info(
            "Truncated history from %d to %d messages (%d estimated tokens, budget %d)",
            len(history),
            len(kept),
            used,
            budget,
        )
    return sanitize_history(kept)


# ---------------------------------------------------------------------------
# Pointer-based history — append-only JSONL with consolidation pointer
# ---------------------------------------------------------------------------
# Line 0: metadata  {"_type":"metadata","last_consolidated":N}
# Line 1+: messages  {"role":"user","content":"..."}
# Only messages after last_consolidated are loaded into the LLM context.
# Consolidation extracts facts into memory, then advances the pointer.

_METADATA_TYPE = "metadata"


def history_path(workspaces: Path, key: str) -> Path:
    # Channel/group histories go under household/channels/ to avoid
    # creating top-level directories that look like member workspaces.
    if key.startswith("group-") or key.startswith("web-"):
        hist_dir = workspaces / "household" / "channels" / key
    else:
        hist_dir = workspaces / key
    hist_dir.mkdir(parents=True, exist_ok=True)
    return hist_dir / "history.jsonl"


def read_history_file(path: Path) -> tuple[int, list[Message]]:
    """Read the history file. Returns (last_consolidated, all_messages)."""
    if not path.exists():
        return 0, []

    last_consolidated = 0
    messages: list[Message] = []

    for line in path.read_text().strip().splitlines():
        if not line:
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and data.get("_type") == _METADATA_TYPE:
            last_consolidated = data.get("last_consolidated", 0)
            continue
        try:
            msg = Message.model_validate(data)
            if msg.role in ("user", "assistant", "tool"):
                # Strip stale reasoning/thinking blocks — they only matter
                # within a tool chain, not across persisted turns.  Leaving
                # them causes 400s on OpenRouter and other Anthropic proxies
                # that don't accept Anthropic-specific signature fields.
                if msg.reasoning:
                    msg = msg.model_copy(update={"reasoning": []})
                messages.append(msg)
        except Exception:
            continue

    return last_consolidated, messages


def load_history(
    workspaces: Path,
    person: str,
    max_messages: int = LIVE_HISTORY_MAX_MESSAGES,
) -> list[Message]:
    """Load unconsolidated history — messages after the consolidation pointer."""
    path = history_path(workspaces, person)
    last_consolidated, all_messages = read_history_file(path)
    # Return only messages after the consolidation pointer
    unconsolidated = all_messages[last_consolidated:]
    return sanitize_history(unconsolidated[-max_messages:])


def strip_images(content: str | list[Any]) -> str:
    """Replace image content blocks with a text placeholder for history persistence."""
    if isinstance(content, str):
        return content
    parts: list[str] = []
    for block in content:
        if isinstance(block, dict) and block.get("type") == "text":
            parts.append(block["text"])
        elif isinstance(block, dict) and block.get("type") == "image":
            parts.append("[image]")
    return " ".join(parts) if parts else ""


_MAX_TOOL_RESULT_CHARS = 4000  # cap individual tool results to avoid history bloat


def persistable_messages(messages: list[Message]) -> list[Message]:
    """Prepare messages for persistence — all roles kept, images and reasoning stripped."""
    persistent: list[Message] = []
    for m in messages:
        if m.role == "user":
            persistent.append(m.model_copy(update={"content": strip_images(m.content)}))
        elif m.role == "assistant":
            persistent.append(
                m.model_copy(
                    update={
                        "content": strip_images(m.content),
                        "reasoning": [],  # only needed within tool chains, not across turns
                    }
                )
            )
        elif m.role == "tool":
            # Cap tool results to prevent huge API responses from bloating history
            content = m.content if isinstance(m.content, str) else json.dumps(m.content)
            if len(content) > _MAX_TOOL_RESULT_CHARS:
                content = content[:_MAX_TOOL_RESULT_CHARS] + "\n...(truncated)"
            persistent.append(m.model_copy(update={"content": content}))
    return persistent


def append_turn(workspaces: Path, person: str, new_messages: list[Message]) -> None:
    """Append this turn's new messages to history, preserving all prior messages.

    Persistence is append-only: every message already on disk — consolidated and
    not-yet-consolidated alike — is retained, and only ``new_messages`` (the
    user/assistant/tool messages produced this turn) are added.

    Only the new turn is persisted because the in-memory history the loop works
    with is a *bounded* view: ``load_history`` caps it and ``truncate_history``
    drops the oldest messages to fit the context window. Reconstructing the file
    from that view would silently delete unconsolidated messages that fell
    outside it, losing them before consolidation could fold them into memory.
    """
    new_persistent = persistable_messages(new_messages)
    if not new_persistent:
        return

    path = history_path(workspaces, person)
    last_consolidated, old_messages = read_history_file(path)

    lines = [json.dumps({"_type": _METADATA_TYPE, "last_consolidated": last_consolidated})]
    lines.extend(m.model_dump_json() for m in old_messages)
    lines.extend(m.model_dump_json() for m in new_persistent)
    atomic_write_text(path, "\n".join(lines) + "\n")


def advance_consolidation_pointer(workspaces: Path, person: str, new_pointer: int) -> None:
    """Advance the consolidation pointer without rewriting messages."""
    path = history_path(workspaces, person)
    last_consolidated, all_messages = read_history_file(path)

    if new_pointer <= last_consolidated:
        return

    lines = [json.dumps({"_type": _METADATA_TYPE, "last_consolidated": new_pointer})]
    for msg in all_messages:
        lines.append(msg.model_dump_json())
    atomic_write_text(path, "\n".join(lines) + "\n")


def reset_history(workspaces: Path, key: str) -> int:
    """Start a fresh conversation for *key* (a person name or channel id).

    Advances the consolidation pointer past every message so the next turn
    begins with an empty context window. The append-only history file is kept on
    disk in full — only the live view the LLM sees is cleared. Returns the number
    of messages that were dropped from the live window (0 if already empty).
    """
    path = history_path(workspaces, key)
    last_consolidated, all_messages = read_history_file(path)
    cleared = len(all_messages) - last_consolidated
    if cleared <= 0:
        return 0
    advance_consolidation_pointer(workspaces, key, len(all_messages))
    return cleared
