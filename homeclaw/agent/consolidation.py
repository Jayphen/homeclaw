"""Context consolidation — summarize old conversation turns into memory."""

from __future__ import annotations

import asyncio
import copy
import json
import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from homeclaw.agent.additional_context import strip_additional_context
from homeclaw.agent.providers.base import LLMProvider, Message

if TYPE_CHECKING:
    from homeclaw.agent.routing import RoutingConfig
    from homeclaw.agent.runtime_state import RuntimeObservability
    from homeclaw.locking import LockPool

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Consolidation constants (also read by loop._run_inner for debug metadata)
# ---------------------------------------------------------------------------

# Consolidation triggers when unconsolidated history exceeds this fraction
# of the context window budget (after reserving space for system + output).
CONSOLIDATION_THRESHOLD = 0.10

# Minimum idle time (seconds) before consolidation runs for a session.
CONSOLIDATION_IDLE_SECS = 60

# Maximum messages to consolidate in one chunk.
CONSOLIDATION_CHUNK_SIZE = 20

# Catch up several chunks in one idle pass so production histories do not stay
# bloated for days after crossing the compaction threshold.
CONSOLIDATION_MAX_CHUNKS_PER_RUN = 5

_CONSOLIDATION_PROMPT = """\
You are a conversation summarizer for a household assistant called homeclaw.

Below is a chunk of older conversation between homeclaw and a household member.
Extract the important information and produce a JSON response with two fields:

1. "memory_entries": a list of objects, each with:
   - "topic": a short topic name (e.g. "food", "health", "work", "home", "family")
   - "content": a single line of factual information worth remembering

2. "summary": a 1-3 sentence summary of what was discussed, for the conversation log.

Only extract facts that would be useful in future conversations. Skip small talk,
acknowledgments, and transient requests (like "what time is it").

Respond with ONLY valid JSON, no markdown fences."""


async def consolidate_chunk(
    messages: list[Message],
    person: str,
    provider: LLMProvider,
    *,
    max_tokens: int = 1024,
) -> dict[str, Any]:
    """Consolidate a chunk of messages into memory entries and a summary.

    Uses the LLM to extract facts worth remembering and a brief summary.
    Returns {"memory_entries": [...], "summary": "..."} or {"error": "..."}.
    """
    # Format messages into readable text for the consolidation prompt
    lines: list[str] = []
    for msg in messages:
        role = "User" if msg.role == "user" else "homeclaw"
        text = msg.content if isinstance(msg.content, str) else str(msg.content)
        if msg.role == "user":
            text = strip_additional_context(text)
        lines.append(f"{role}: {text}")

    conversation_text = "\n".join(lines)

    try:
        response = await provider.complete(
            messages=[Message(role="user", content=conversation_text)],
            tools=[],
            system=_CONSOLIDATION_PROMPT,
            max_tokens=max_tokens,
        )
    except Exception as exc:
        logger.warning("Consolidation LLM call failed: %s", exc)
        return {"error": str(exc)}

    # Parse JSON response
    try:
        result = json.loads(response.content)
        if not isinstance(result, dict):
            raise ValueError("Expected a JSON object")
        return result
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning("Consolidation response not valid JSON: %s", exc)
        return {"error": f"Invalid JSON from LLM: {exc}"}


async def save_consolidated_memories(
    entries: list[dict[str, str]],
    person: str,
    workspaces: Path,
) -> int:
    """Save extracted memory entries to the person's memory topics.

    Returns the number of entries saved.
    """
    from homeclaw.memory.markdown import memory_save_topic

    saved = 0
    for entry in entries:
        topic = entry.get("topic", "general")
        content = entry.get("content", "")
        if not content:
            continue
        memory_save_topic(workspaces, person, topic, content)
        saved += 1

    return saved


# ---------------------------------------------------------------------------
# Background consolidation orchestrator
# ---------------------------------------------------------------------------


class SessionConsolidator:
    """Background worker that consolidates idle sessions.

    Owns the idle-activity tracker, the asyncio background task, and the
    cheap consolidation provider.  ``AgentLoop`` delegates the background
    work here so it can stay focused on the request/response cycle.
    """

    def __init__(
        self,
        workspaces: Path,
        lock_pool: LockPool,
        routing: RoutingConfig | None = None,
        runtime_observability: RuntimeObservability | None = None,
    ) -> None:
        self._workspaces = workspaces
        self._lock_pool = lock_pool
        self._routing = routing
        self._runtime_observability = runtime_observability
        self._provider: LLMProvider | None = None
        self._last_activity: dict[str, float] = {}
        self._task: asyncio.Task[None] | None = None

    def set_provider(self, provider: LLMProvider) -> None:
        """Update the provider used for consolidation LLM calls."""
        self._provider = provider

    def touch(self, history_key: str) -> None:
        """Record activity for *history_key* to reset the idle timer."""
        self._last_activity[history_key] = time.monotonic()

    def start(self) -> None:
        """Start the background consolidation loop (idempotent)."""
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._loop())
            logger.info("Background consolidation loop started")

    async def _loop(self) -> None:
        """Background loop that consolidates idle sessions."""
        while True:
            await asyncio.sleep(30)
            now = time.monotonic()
            for key, last in list(self._last_activity.items()):
                if now - last < CONSOLIDATION_IDLE_SECS:
                    continue
                try:
                    await self._consolidate_session(key)
                except Exception:
                    logger.exception("Consolidation failed for '%s'", key)
                finally:
                    # Don't re-consolidate until next activity
                    self._last_activity.pop(key, None)

    async def _consolidate_session(self, history_key: str) -> None:
        """Consolidate old messages in a session if over budget."""
        from homeclaw.agent.history import (
            DEFAULT_CONTEXT_WINDOW,
            RESERVED_FRACTION,
            advance_consolidation_pointer,
            estimate_message_tokens,
            history_path,
            read_history_file,
        )
        from homeclaw.agent.runtime_state import ConsolidationEvent, now_utc

        if self._provider is None:
            return

        path = history_path(self._workspaces, history_key)
        person = history_key.split("-")[0] if "-" in history_key else history_key

        # Use a shallow copy so we can set the cheap model without mutating
        # the shared instance (which may be mid-request).
        consolidation_provider = copy.copy(self._provider)
        if self._routing:
            from homeclaw.agent.routing import CallType as CT
            from homeclaw.agent.routing import route_model

            cheap_model = route_model(CT.ROUTINE, self._routing)
            if hasattr(consolidation_provider, "model"):
                consolidation_provider.model = cheap_model  # type: ignore[attr-defined]

        context_window = getattr(self._provider, "context_window", DEFAULT_CONTEXT_WINDOW)
        budget = int(context_window * (1 - RESERVED_FRACTION))
        current_model = getattr(consolidation_provider, "model", "unknown")

        def _record(
            status: str,
            reason: str,
            *,
            unconsolidated_messages: int,
            history_tokens: int,
            chunk_size: int = 0,
            saved_entries: int = 0,
        ) -> None:
            if self._runtime_observability is None:
                return
            self._runtime_observability.record_consolidation(
                ConsolidationEvent(
                    history_key=history_key,
                    person=person,
                    status=status,  # type: ignore[arg-type]
                    reason=reason,
                    unconsolidated_messages=unconsolidated_messages,
                    history_tokens=history_tokens,
                    chunk_size=chunk_size,
                    saved_entries=saved_entries,
                    model=current_model,
                    recorded_at=now_utc(),
                )
            )

        chunks_processed = 0
        total_saved = 0

        while chunks_processed < CONSOLIDATION_MAX_CHUNKS_PER_RUN:
            last_consolidated, all_messages = read_history_file(path)
            unconsolidated = all_messages[last_consolidated:]
            history_tokens = sum(estimate_message_tokens(m) for m in unconsolidated)

            if history_tokens < budget * CONSOLIDATION_THRESHOLD:
                _record(
                    "skipped" if chunks_processed == 0 else "succeeded",
                    "history_below_threshold" if chunks_processed == 0 else "target_reached",
                    unconsolidated_messages=len(unconsolidated),
                    history_tokens=history_tokens,
                    saved_entries=total_saved,
                )
                return  # Not enough to warrant more consolidation

            # Consolidate the oldest chunk, preserving the newest two messages
            # as active conversational context.
            chunk_end = min(CONSOLIDATION_CHUNK_SIZE, len(unconsolidated) - 2)
            if chunk_end < 2:
                _record(
                    "skipped",
                    "not_enough_messages",
                    unconsolidated_messages=len(unconsolidated),
                    history_tokens=history_tokens,
                )
                return  # Need at least a couple messages to consolidate

            chunk = unconsolidated[:chunk_end]
            result = await consolidate_chunk(chunk, person, consolidation_provider)

            if "error" in result:
                logger.warning(
                    "Consolidation failed for '%s': %s — will retry next cycle",
                    history_key,
                    result["error"],
                )
                _record(
                    "failed",
                    f"provider_error:{result['error']}",
                    unconsolidated_messages=len(unconsolidated),
                    history_tokens=history_tokens,
                    chunk_size=len(chunk),
                    saved_entries=total_saved,
                )
                return  # Don't advance pointer — retry next cycle

            # A valid summary with no durable facts is still a successful
            # consolidation. Otherwise low-signal early chat can pin the pointer
            # forever and keep every later turn in the live prompt.
            entries_raw = result.get("memory_entries", [])
            entries = entries_raw if isinstance(entries_raw, list) else []
            summary = result.get("summary")
            has_summary = isinstance(summary, str) and bool(summary.strip())
            if not entries and not has_summary:
                logger.info(
                    "Consolidation returned no entries or summary for '%s' — will retry",
                    history_key,
                )
                _record(
                    "failed",
                    "empty_consolidation_result",
                    unconsolidated_messages=len(unconsolidated),
                    history_tokens=history_tokens,
                    chunk_size=len(chunk),
                    saved_entries=total_saved,
                )
                return

            saved = await save_consolidated_memories(entries, person, self._workspaces)
            total_saved += saved
            chunks_processed += 1
            logger.info(
                "Consolidated %d messages → %d memory entries for '%s'",
                len(chunk),
                saved,
                history_key,
            )

            # Advance after a valid extraction/summary. The advance re-reads the
            # file fresh, so turns saved while the LLM extraction ran are
            # preserved rather than overwritten.
            async with self._lock_pool.lock_for(history_key):
                advance_consolidation_pointer(
                    self._workspaces, history_key, last_consolidated + chunk_end
                )
            _record(
                "succeeded",
                "ok" if saved else "summary_only",
                unconsolidated_messages=len(unconsolidated),
                history_tokens=history_tokens,
                chunk_size=len(chunk),
                saved_entries=saved,
            )

        last_consolidated, all_messages = read_history_file(path)
        unconsolidated = all_messages[last_consolidated:]
        history_tokens = sum(estimate_message_tokens(m) for m in unconsolidated)
        _record(
            "succeeded",
            "max_chunks_per_run",
            unconsolidated_messages=len(unconsolidated),
            history_tokens=history_tokens,
            saved_entries=total_saved,
        )
