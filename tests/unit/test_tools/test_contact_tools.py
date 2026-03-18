"""Tests for built-in contact tools (contact_list, contact_get, contact_update, interaction_log)."""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from homeclaw.agent.tools import ToolRegistry, register_builtin_tools
from homeclaw.contacts.models import Contact, ContactReminder
from homeclaw.contacts.store import get_contact, save_contact


@pytest.fixture
def registry(dev_workspaces: Path) -> ToolRegistry:
    reg = ToolRegistry()
    register_builtin_tools(reg, dev_workspaces)
    return reg


# ── contact_list ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_contact_list_returns_all_contacts(
    registry: ToolRegistry, dev_workspaces: Path
) -> None:
    handler = registry.get_handler("contact_list")
    assert handler is not None
    result = await handler()
    contacts = result["contacts"]
    ids = {c["id"] for c in contacts}
    assert "sarah-chen" in ids
    assert "james-ko" in ids
    assert "grandma-eleanor" in ids
    # Each entry exposes id, name, and relationship
    for c in contacts:
        assert "id" in c
        assert "name" in c
        assert "relationship" in c


# ── contact_get ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_contact_get_exact_id(registry: ToolRegistry) -> None:
    handler = registry.get_handler("contact_get")
    assert handler is not None
    result = await handler(id="sarah-chen")
    assert result["id"] == "sarah-chen"
    assert result["name"] == "Sarah Chen"
    assert result["relationship"] == "friend"


@pytest.mark.asyncio
async def test_contact_get_fuzzy_grandma(registry: ToolRegistry) -> None:
    handler = registry.get_handler("contact_get")
    assert handler is not None
    result = await handler(id="grandma")
    assert result["id"] == "grandma-eleanor"
    assert result["name"] == "Eleanor"


@pytest.mark.asyncio
async def test_contact_get_nonexistent(registry: ToolRegistry) -> None:
    handler = registry.get_handler("contact_get")
    assert handler is not None
    result = await handler(id="does-not-exist-zzzzz")
    assert "error" in result


# ── contact_update ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_contact_update_creates_new(
    registry: ToolRegistry, dev_workspaces: Path
) -> None:
    handler = registry.get_handler("contact_update")
    assert handler is not None
    result = await handler(id="new-person", name="New Person", relationship="friend")
    assert result["status"] == "updated"
    assert result["id"] == "new-person"
    # Verify it was persisted
    contact = get_contact(dev_workspaces, "new-person")
    assert contact is not None
    assert contact.name == "New Person"
    assert contact.relationship == "friend"


@pytest.mark.asyncio
async def test_contact_update_modifies_facts(
    registry: ToolRegistry, dev_workspaces: Path
) -> None:
    handler = registry.get_handler("contact_update")
    assert handler is not None
    new_facts = ["Loves hiking", "Has two dogs"]
    result = await handler(id="james-ko", facts=new_facts)
    assert result["status"] == "updated"
    contact = get_contact(dev_workspaces, "james-ko")
    assert contact is not None
    # facts are appended, not replaced
    assert "Team lead on the backend team" in contact.facts
    assert "Into rock climbing" in contact.facts
    assert "Loves hiking" in contact.facts
    assert "Has two dogs" in contact.facts


@pytest.mark.asyncio
async def test_contact_update_sets_nicknames(
    registry: ToolRegistry, dev_workspaces: Path
) -> None:
    handler = registry.get_handler("contact_update")
    assert handler is not None
    result = await handler(id="sarah-chen", nicknames=["Sar", "SC"])
    assert result["status"] == "updated"
    contact = get_contact(dev_workspaces, "sarah-chen")
    assert contact is not None
    assert contact.nicknames == ["Sar", "SC"]


# ── interaction_log ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_interaction_log_adds_interaction(
    registry: ToolRegistry, dev_workspaces: Path
) -> None:
    handler = registry.get_handler("interaction_log")
    assert handler is not None
    result = await handler(
        contact_id="james-ko", type="call", notes="Discussed the sprint"
    )
    assert result["status"] == "logged"
    assert result["contact"] == "james-ko"
    contact = get_contact(dev_workspaces, "james-ko")
    assert contact is not None
    assert len(contact.interactions) >= 2  # had 1 + the new one
    assert contact.last_contact is not None


@pytest.mark.asyncio
async def test_interaction_log_nonexistent_contact(registry: ToolRegistry) -> None:
    handler = registry.get_handler("interaction_log")
    assert handler is not None
    result = await handler(
        contact_id="nobody-here-xyz", type="call", notes="Hello?"
    )
    assert "error" in result


@pytest.mark.asyncio
async def test_interaction_log_advances_recurring_reminder(
    registry: ToolRegistry, dev_workspaces: Path
) -> None:
    """Logging an interaction should advance recurring reminders past today."""
    # Set up a contact with a recurring reminder whose next_date is in the past
    contact = get_contact(dev_workspaces, "grandma-eleanor")
    assert contact is not None
    contact.reminders = [
        ContactReminder(interval_days=14, next_date=date(2026, 3, 1), note="Bi-weekly call")
    ]
    save_contact(dev_workspaces, contact)

    handler = registry.get_handler("interaction_log")
    assert handler is not None
    await handler(
        contact_id="grandma-eleanor", type="call", notes="Weekly check-in"
    )

    updated = get_contact(dev_workspaces, "grandma-eleanor")
    assert updated is not None
    assert len(updated.reminders) == 1
    reminder = updated.reminders[0]
    # next_date should have advanced past the interaction date (today)
    assert reminder.next_date is not None
    assert reminder.next_date > date(2026, 3, 1)
