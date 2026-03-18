"""Context builder — injects household state into every LLM call."""

import logging
from datetime import datetime, timedelta
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

from homeclaw import HOUSEHOLD_WORKSPACE
from homeclaw.contacts.store import list_contacts
from homeclaw.memory.facts import load_memory
from homeclaw.memory.semantic import SemanticMemory
from homeclaw.reminders.store import load_reminders

logger = logging.getLogger(__name__)


class ContextConfig(BaseSettings):
    """Token budget and limits for context injection."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    max_facts_per_person: int = 20
    max_contacts_in_context: int = 5
    max_semantic_chunks: int = 3
    max_ha_entities: int = 20


async def build_context(
    message: str,
    person: str,
    workspaces: Path,
    semantic_memory: SemanticMemory | None = None,
    shared_only: bool = False,
    context_config: ContextConfig | None = None,
) -> str:
    cfg = context_config or ContextConfig()
    parts: list[str] = []

    # --- Priority 1: always keep ---

    # Current time (local timezone so the LLM gives time-aware answers)
    now = datetime.now().astimezone()
    parts.append(f"Current time: {now.strftime('%Y-%m-%d %H:%M %Z')}")

    # Household-level facts (always injected — shared knowledge)
    household_memory = load_memory(workspaces, HOUSEHOLD_WORKSPACE)
    if household_memory.facts:
        parts.append("Household facts:")
        for fact in household_memory.facts[: cfg.max_facts_per_person]:
            parts.append(f"  - {fact}")

    # Personal facts (only in DMs — never in group context)
    if not shared_only:
        memory = load_memory(workspaces, person)
        if memory.facts:
            parts.append(f"Known facts about {person}:")
            for fact in memory.facts[: cfg.max_facts_per_person]:
                parts.append(f"  - {fact}")
        if memory.preferences:
            parts.append(f"Preferences for {person}:")
            for k, v in memory.preferences.items():
                parts.append(f"  - {k}: {v}")

    # Active reminders due today (never dropped)
    contacts = list_contacts(workspaces)
    today = now.date()
    today_reminders: list[str] = []
    upcoming_reminders: list[str] = []
    cutoff = (now + timedelta(days=7)).date()
    for contact in contacts:
        for reminder in contact.reminders:
            if not reminder.next_date:
                continue
            note = f" ({reminder.note})" if reminder.note else ""
            entry = f"  - {contact.name}: due {reminder.next_date}{note}"
            if reminder.next_date <= today:
                today_reminders.append(entry)
            elif reminder.next_date <= cutoff:
                upcoming_reminders.append(entry)

    if today_reminders:
        parts.append("Contact reminders due today:")
        parts.extend(today_reminders)

    # --- Priority 4: contacts beyond top N most urgent (dropped third) ---
    capped_upcoming = upcoming_reminders[: cfg.max_contacts_in_context]
    if capped_upcoming:
        parts.append("Upcoming contact reminders:")
        parts.extend(capped_upcoming)

    # Personal reminders (one-shot and recurring)
    if not shared_only:
        member_reminders = load_reminders(workspaces, person)
        due_now: list[str] = []
        due_soon: list[str] = []
        for r in member_reminders:
            if r.done:
                continue
            nd = r.next_due
            if nd is None:
                continue
            label = f"  - {r.note} (id: {r.id})"
            if r.interval_days:
                label += f" [every {r.interval_days}d]"
            if nd <= today:
                due_now.append(label)
            elif nd <= cutoff:
                due_soon.append(label)
        if due_now:
            parts.append("Your reminders due now:")
            parts.extend(due_now)
        if due_soon:
            parts.append("Your upcoming reminders:")
            parts.extend(due_soon)

    # --- Priority 3: semantic memory chunks (dropped second) ---
    if semantic_memory and semantic_memory.enabled:
        recalled = await semantic_memory.recall(
            message, top_k=cfg.max_semantic_chunks
        )
        if recalled:
            parts.append("Relevant context from memory:")
            for chunk in recalled:
                parts.append(f"  {chunk}")

    result = "\n".join(parts)
    token_count = estimate_tokens(result)
    logger.debug("Context built: %d estimated tokens", token_count)
    return result


def estimate_tokens(text: str) -> int:
    """Estimate token count for a string.

    Uses word-based heuristic (~1.3 tokens per whitespace-delimited word).
    Accurate to within ~10% for English text. Swap for tiktoken or
    anthropic.messages.count_tokens() when precise billing is needed.
    """
    if not text:
        return 0
    words = text.split()
    return int(len(words) * 1.3)
