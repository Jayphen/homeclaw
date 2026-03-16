"""Tool registry, built-in tool definitions, and handlers."""

from collections.abc import Callable, Coroutine
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from homeclaw.agent.providers.base import ToolDefinition
from homeclaw.contacts.models import Contact, Interaction
from homeclaw.contacts.store import (
    delete_contact,
    get_contact,
    list_contacts,
    save_contact,
)
from homeclaw.memory.facts import HouseholdMemory, load_memory, save_memory

ToolHandler = Callable[..., Coroutine[Any, Any, dict[str, Any]]]


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}
        self._handlers: dict[str, ToolHandler] = {}

    def register(self, definition: ToolDefinition, handler: ToolHandler) -> None:
        self._tools[definition.name] = definition
        self._handlers[definition.name] = handler

    def get_definitions(self) -> list[ToolDefinition]:
        return list(self._tools.values())

    def get_handler(self, name: str) -> ToolHandler | None:
        return self._handlers.get(name)

    def has_tool(self, name: str) -> bool:
        return name in self._tools


def register_builtin_tools(registry: ToolRegistry, workspaces: Path) -> None:
    """Register all built-in tools with the registry."""

    # --- Contact tools ---

    async def contact_list(**_: Any) -> dict[str, Any]:
        contacts = list_contacts(workspaces)
        return {
            "contacts": [
                {"id": c.id, "name": c.name, "relationship": c.relationship}
                for c in contacts
            ]
        }

    registry.register(
        ToolDefinition(
            name="contact_list",
            description="List all contacts in the household's contact book.",
            parameters={"type": "object", "properties": {}},
        ),
        contact_list,
    )

    async def contact_get(*, id: str, **_: Any) -> dict[str, Any]:
        contact = get_contact(workspaces, id)
        if not contact:
            return {"error": f"Contact '{id}' not found"}
        return contact.model_dump(mode="json")

    registry.register(
        ToolDefinition(
            name="contact_get",
            description="Get full details for a contact by ID.",
            parameters={
                "type": "object",
                "properties": {"id": {"type": "string", "description": "Contact ID"}},
                "required": ["id"],
            },
        ),
        contact_get,
    )

    async def contact_update(
        *,
        id: str,
        name: str | None = None,
        relationship: str | None = None,
        facts: list[str] | None = None,
        **_: Any,
    ) -> dict[str, Any]:
        contact = get_contact(workspaces, id)
        if not contact:
            contact = Contact(id=id, name=name or id, relationship=relationship or "other")
        if name:
            contact.name = name
        if relationship:
            contact.relationship = relationship
        if facts is not None:
            contact.facts = facts
        save_contact(workspaces, contact)
        return {"status": "updated", "id": id}

    registry.register(
        ToolDefinition(
            name="contact_update",
            description="Create or update a contact. Provide fields to change.",
            parameters={
                "type": "object",
                "properties": {
                    "id": {"type": "string", "description": "Contact ID"},
                    "name": {"type": "string", "description": "Contact name"},
                    "relationship": {"type": "string", "description": "Relationship type"},
                    "facts": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Known facts about this person",
                    },
                },
                "required": ["id"],
            },
        ),
        contact_update,
    )

    async def interaction_log(
        *, contact_id: str, type: str, notes: str, **_: Any
    ) -> dict[str, Any]:
        contact = get_contact(workspaces, contact_id)
        if not contact:
            return {"error": f"Contact '{contact_id}' not found"}
        interaction = Interaction(
            date=datetime.now(timezone.utc), type=type, notes=notes
        )
        contact.interactions.append(interaction)
        contact.last_contact = interaction.date
        save_contact(workspaces, contact)
        return {"status": "logged", "contact": contact_id}

    registry.register(
        ToolDefinition(
            name="interaction_log",
            description="Log an interaction with a contact (call, message, meetup).",
            parameters={
                "type": "object",
                "properties": {
                    "contact_id": {"type": "string", "description": "Contact ID"},
                    "type": {
                        "type": "string",
                        "enum": ["call", "message", "meetup", "other"],
                        "description": "Interaction type",
                    },
                    "notes": {"type": "string", "description": "What happened"},
                },
                "required": ["contact_id", "type", "notes"],
            },
        ),
        interaction_log,
    )

    # --- Memory tools ---

    async def memory_read(*, person: str, **_: Any) -> dict[str, Any]:
        memory = load_memory(workspaces, person)
        return memory.model_dump(mode="json")

    registry.register(
        ToolDefinition(
            name="memory_read",
            description="Read stored facts and preferences for a household member.",
            parameters={
                "type": "object",
                "properties": {
                    "person": {"type": "string", "description": "Household member name"},
                },
                "required": ["person"],
            },
        ),
        memory_read,
    )

    async def memory_update(
        *,
        person: str,
        facts: list[str] | None = None,
        preferences: dict[str, str] | None = None,
        **_: Any,
    ) -> dict[str, Any]:
        memory = load_memory(workspaces, person)
        if facts is not None:
            memory.facts = facts
        if preferences is not None:
            memory.preferences = preferences
        save_memory(workspaces, person, memory)
        return {"status": "updated", "person": person}

    registry.register(
        ToolDefinition(
            name="memory_update",
            description="Update stored facts or preferences for a household member.",
            parameters={
                "type": "object",
                "properties": {
                    "person": {"type": "string", "description": "Household member name"},
                    "facts": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Facts to store (replaces existing)",
                    },
                    "preferences": {
                        "type": "object",
                        "description": "Preferences to store (replaces existing)",
                    },
                },
                "required": ["person"],
            },
        ),
        memory_update,
    )

    # --- Note tools ---

    async def note_save(*, person: str, content: str, **_: Any) -> dict[str, Any]:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        notes_dir = workspaces / person / "notes"
        notes_dir.mkdir(parents=True, exist_ok=True)
        path = notes_dir / f"{today}.md"
        if path.exists():
            existing = path.read_text()
            path.write_text(f"{existing}\n\n{content}")
        else:
            path.write_text(content)
        return {"status": "saved", "path": str(path)}

    registry.register(
        ToolDefinition(
            name="note_save",
            description="Save a note for a household member. Appends to today's note file.",
            parameters={
                "type": "object",
                "properties": {
                    "person": {"type": "string", "description": "Household member name"},
                    "content": {"type": "string", "description": "Note content (markdown)"},
                },
                "required": ["person", "content"],
            },
        ),
        note_save,
    )

    async def note_get(
        *, person: str, date: str | None = None, **_: Any
    ) -> dict[str, Any]:
        if date is None:
            date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        path = workspaces / person / "notes" / f"{date}.md"
        if not path.exists():
            return {"content": "", "date": date}
        return {"content": path.read_text(), "date": date}

    registry.register(
        ToolDefinition(
            name="note_get",
            description="Read a note for a household member. Defaults to today.",
            parameters={
                "type": "object",
                "properties": {
                    "person": {"type": "string", "description": "Household member name"},
                    "date": {
                        "type": "string",
                        "description": "Date in YYYY-MM-DD format (defaults to today)",
                    },
                },
                "required": ["person"],
            },
        ),
        note_get,
    )

    # --- Reminder tool ---

    async def reminder_set(
        *, person: str, note: str, date: str, **_: Any
    ) -> dict[str, Any]:
        from datetime import date as date_type

        parts = date.split("-")
        reminder_date = date_type(int(parts[0]), int(parts[1]), int(parts[2]))
        notes_dir = workspaces / person / "notes"
        notes_dir.mkdir(parents=True, exist_ok=True)
        reminders_path = notes_dir / "reminders.md"
        line = f"- [ ] {reminder_date}: {note}\n"
        if reminders_path.exists():
            existing = reminders_path.read_text()
            reminders_path.write_text(f"{existing}{line}")
        else:
            reminders_path.write_text(f"# Reminders\n\n{line}")
        return {"status": "set", "date": str(reminder_date), "note": note}

    registry.register(
        ToolDefinition(
            name="reminder_set",
            description="Set a reminder for a household member on a specific date.",
            parameters={
                "type": "object",
                "properties": {
                    "person": {"type": "string", "description": "Household member name"},
                    "note": {"type": "string", "description": "Reminder text"},
                    "date": {"type": "string", "description": "Date in YYYY-MM-DD format"},
                },
                "required": ["person", "note", "date"],
            },
        ),
        reminder_set,
    )

    # --- Message tool (stub — channel adapters implement delivery) ---

    async def message_send(
        *, person: str, text: str, **_: Any
    ) -> dict[str, Any]:
        return {"status": "queued", "person": person, "text": text}

    registry.register(
        ToolDefinition(
            name="message_send",
            description="Send a message to a household member via their preferred channel.",
            parameters={
                "type": "object",
                "properties": {
                    "person": {"type": "string", "description": "Recipient name"},
                    "text": {"type": "string", "description": "Message text"},
                },
                "required": ["person", "text"],
            },
        ),
        message_send,
    )
