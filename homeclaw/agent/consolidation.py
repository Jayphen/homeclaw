"""Context consolidation — summarize old conversation turns into memory."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from homeclaw.agent.context import estimate_tokens
from homeclaw.agent.providers.base import LLMProvider, Message

logger = logging.getLogger(__name__)

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
        # Return the raw text as summary fallback
        return {
            "memory_entries": [],
            "summary": response.content[:500] if response.content else "",
        }


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
