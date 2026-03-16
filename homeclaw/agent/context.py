"""Context builder — injects household state into every LLM call."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

from homeclaw.contacts.store import list_contacts
from homeclaw.memory.facts import load_memory
from homeclaw.memory.semantic import SemanticMemory


async def build_context(
    message: str,
    person: str,
    workspaces: Path,
    semantic_memory: SemanticMemory | None = None,
) -> str:
    parts: list[str] = []

    # Current time
    now = datetime.now(timezone.utc)
    parts.append(f"Current time: {now.strftime('%Y-%m-%d %H:%M %Z')}")

    # Layer 1 — structured facts (always injected in full)
    memory = load_memory(workspaces, person)
    if memory.facts:
        parts.append(f"Known facts about {person}:")
        for fact in memory.facts:
            parts.append(f"  - {fact}")
    if memory.preferences:
        parts.append(f"Preferences for {person}:")
        for k, v in memory.preferences.items():
            parts.append(f"  - {k}: {v}")

    # Contacts with reminders due in 7 days
    contacts = list_contacts(workspaces)
    upcoming: list[str] = []
    cutoff = (now + timedelta(days=7)).date()
    for contact in contacts:
        for reminder in contact.reminders:
            if reminder.next_date and reminder.next_date <= cutoff:
                note = f" ({reminder.note})" if reminder.note else ""
                upcoming.append(f"  - {contact.name}: due {reminder.next_date}{note}")
    if upcoming:
        parts.append("Upcoming contact reminders:")
        parts.extend(upcoming)

    # Layer 2 — semantic recall (only if enhanced mode enabled)
    if semantic_memory and semantic_memory.enabled:
        recalled = await semantic_memory.recall(message, top_k=3)
        if recalled:
            parts.append("Relevant context from memory:")
            for chunk in recalled:
                parts.append(f"  {chunk}")

    return "\n".join(parts)
