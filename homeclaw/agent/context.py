"""Context builder — injects household state into every LLM call."""

import logging
from datetime import datetime, timedelta
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

from homeclaw.contacts.store import list_contacts
from homeclaw.memory.markdown import memory_list_topics, memory_read_topic
from homeclaw.memory.semantic import SemanticMemory
from homeclaw.reminders.store import load_reminders
from homeclaw.scheduler.routines import parse_routines_md

HOUSEHOLD_WORKSPACE = "household"
_PROFILE_MAX_LINES = 8

logger = logging.getLogger(__name__)


class ContextConfig(BaseSettings):
    """Token budget and limits for context injection."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    max_contacts_in_context: int = 5
    max_semantic_chunks: int = 8
    max_ha_entities: int = 20
    max_recent_notes_days: int = 3
    max_note_lines: int = 10
    max_decisions: int = 15


def _build_system_info(model: str | None) -> str:
    """Build a compact system info block for agent self-awareness."""
    from importlib.metadata import version as _pkg_version

    try:
        app_version = _pkg_version("homeclaw")
    except Exception:
        app_version = "dev"

    lines = [
        "About you (homeclaw):",
        f"  Version: {app_version}",
    ]
    if model:
        lines.append(f"  Model: {model}")
    lines.append("  Source: https://github.com/Jayphen/homeclaw")
    return "\n".join(lines)


async def build_context(
    message: str,
    person: str,
    workspaces: Path,
    semantic_memory: SemanticMemory | None = None,
    shared_only: bool = False,
    context_config: ContextConfig | None = None,
    model: str | None = None,
    is_admin: bool = True,
) -> str:
    cfg = context_config or ContextConfig()
    parts: list[str] = []

    # --- Priority 1: always keep ---

    # Current time (local timezone so the LLM gives time-aware answers)
    now = datetime.now().astimezone()
    parts.append(f"You are talking to: {person}")
    parts.append(f"Current time: {now.strftime('%Y-%m-%d %H:%M %Z')}")

    # System info — lets the agent answer questions about itself
    parts.append(_build_system_info(model))

    # Household profile — inject a compact summary from household memory topics
    # so the LLM knows who this family is in every conversation.
    profile_lines = _build_household_profile(workspaces)
    if profile_lines:
        parts.append("Household profile:")
        parts.extend(profile_lines)

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

    # --- Priority 2b: recent notes (personal) ---
    if not shared_only:
        recent_notes = _build_recent_notes(workspaces, person, cfg)
        if recent_notes:
            parts.append("Your recent notes:")
            parts.extend(recent_notes)

    # --- Priority 2c: person's memory topics ---
    if not shared_only:
        person_topics = _build_person_memory_summary(workspaces, person)
        if person_topics:
            parts.append("Your memory topics:")
            parts.extend(person_topics)

    # --- Priority 2d: skill catalog ---
    skill_catalog = _build_skill_catalog(workspaces, person, is_admin=is_admin)
    if skill_catalog:
        parts.extend(skill_catalog)

    # --- Priority 2e: scheduled routines ---
    routines = _build_routines_summary(workspaces)
    if routines:
        parts.append("Household routines:")
        parts.extend(routines)

    # --- Priority 2f: recent decisions ---
    decisions = _build_decisions_summary(workspaces, person, cfg, shared_only)
    if decisions:
        parts.append("Settled decisions (do not re-litigate):")
        parts.extend(decisions)

    # --- Priority 3: semantic memory chunks (dropped second) ---
    if semantic_memory and semantic_memory.enabled:
        recalled = await semantic_memory.recall(
            message,
            top_k=cfg.max_semantic_chunks,
            person=person,
            shared_only=shared_only,
        )
        if recalled:
            parts.append("Relevant context from memory:")
            for item in recalled:
                parts.append(f"  {item['text']}")

    result = "\n".join(parts)
    token_count = estimate_tokens(result)
    logger.debug("Context built: %d estimated tokens", token_count)
    return result


def _build_household_profile(workspaces: Path) -> list[str]:
    """Build a compact household profile from household memory topics.

    Reads the first few lines of each household memory file to give the
    LLM grounding about who this family is without blowing the token budget.
    """
    topics = memory_list_topics(workspaces, HOUSEHOLD_WORKSPACE)
    if not topics:
        return []
    lines: list[str] = []
    for topic in topics:
        content = memory_read_topic(workspaces, HOUSEHOLD_WORKSPACE, topic)
        if not content:
            continue
        # Take the first _PROFILE_MAX_LINES non-empty lines (skip the # heading)
        topic_lines = [
            ln.strip() for ln in content.splitlines()
            if ln.strip() and not ln.strip().startswith("#")
        ][:_PROFILE_MAX_LINES]
        if topic_lines:
            lines.append(f"  [{topic}]")
            lines.extend(f"    {ln}" for ln in topic_lines)
    return lines


def _build_recent_notes(
    workspaces: Path, person: str, cfg: ContextConfig,
) -> list[str]:
    """Collect the last N days of daily notes for a person."""
    notes_dir = workspaces / person / "notes"
    if not notes_dir.is_dir():
        return []
    today = datetime.now().date()
    lines: list[str] = []
    for day_offset in range(cfg.max_recent_notes_days):
        date = today - timedelta(days=day_offset)
        path = notes_dir / f"{date}.md"
        if not path.exists():
            continue
        content_lines = [
            ln.strip() for ln in path.read_text().splitlines() if ln.strip()
        ][:cfg.max_note_lines]
        if content_lines:
            lines.append(f"  [{date}]")
            lines.extend(f"    {ln}" for ln in content_lines)
    return lines


def _build_person_memory_summary(workspaces: Path, person: str) -> list[str]:
    """List the person's memory topics so the LLM knows what's available."""
    topics = memory_list_topics(workspaces, person)
    if not topics:
        return []
    return [f"  - {topic}" for topic in topics]


def _build_skill_catalog(
    workspaces: Path, person: str, *, is_admin: bool = True,
) -> list[str]:
    """Build a catalog of available skills for system prompt injection.

    Returns a compact list of skill name + description so the LLM knows
    which skills exist and can call ``read_skill`` to load them on demand.
    """
    from homeclaw.plugins.skills.loader import build_skill_catalog

    catalog = build_skill_catalog(workspaces, person, is_admin=is_admin)
    if not catalog:
        return []

    lines: list[str] = [
        "Available skills (instructions auto-load on first tool use; call read_skill to browse resources):",
    ]
    for entry in catalog:
        scope_tag = f" [{entry.scope}]" if entry.scope != "household" else ""
        extras: list[str] = []
        if entry.has_scripts:
            extras.append("scripts")
        if entry.has_references:
            extras.append("references")
        if entry.has_data:
            extras.append("data")
        if entry.has_http:
            extras.append("http")
        extra_str = f" ({', '.join(extras)})" if extras else ""
        lines.append(f"  - {entry.name}: {entry.description}{scope_tag}{extra_str}")
    return lines


def _build_routines_summary(workspaces: Path) -> list[str]:
    """Build a compact list of scheduled household routines."""
    routines = parse_routines_md(workspaces)
    if not routines:
        return []
    return [f"  - {r.name}: {r.description}" for r in routines]


def _build_decisions_summary(
    workspaces: Path, person: str, cfg: ContextConfig, shared_only: bool,
) -> list[str]:
    """Collect recent decisions — household always, personal in DMs only."""
    lines: list[str] = []

    # Household decisions (always included)
    hh_path = workspaces / HOUSEHOLD_WORKSPACE / "decisions.md"
    if hh_path.exists():
        entries = [
            ln.strip() for ln in hh_path.read_text().splitlines()
            if ln.strip().startswith("- [")
        ]
        lines.extend(f"  {ln}" for ln in entries[-cfg.max_decisions:])

    # Personal decisions (only in DMs)
    if not shared_only:
        personal_path = workspaces / person / "decisions.md"
        if personal_path.exists():
            entries = [
                ln.strip() for ln in personal_path.read_text().splitlines()
                if ln.strip().startswith("- [")
            ]
            lines.extend(f"  {ln}" for ln in entries[-cfg.max_decisions:])

    return lines


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
