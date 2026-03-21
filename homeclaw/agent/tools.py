"""Tool registry, built-in tool definitions, and handlers."""

import logging
from collections.abc import Callable, Coroutine
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, get_args

from homeclaw import HOUSEHOLD_WORKSPACE
from homeclaw.agent.providers.base import ToolDefinition
from homeclaw.pathutil import safe_date, safe_slug
from homeclaw.bookmarks.models import Bookmark
from homeclaw.bookmarks.store import (
    delete_bookmark,
    get_categories,
    list_bookmarks,
    save_bookmark,
    search_bookmarks,
    update_bookmark,
)
from homeclaw.contacts.models import Contact, Interaction, InteractionType
from homeclaw.contacts.store import (
    delete_contact,
    get_contact,
    list_contacts,
    save_contact,
)
from homeclaw.memory.markdown import memory_read_topic, memory_save_topic, memory_list_topics

_logger = logging.getLogger(__name__)

# Maximum size for user-supplied content written to disk (100 KB).
MAX_CONTENT_LENGTH = 100_000

ToolHandler = Callable[..., Coroutine[Any, Any, dict[str, Any]]]


def _check_content_length(content: str, field: str = "content") -> dict[str, Any] | None:
    """Return an error dict if content exceeds MAX_CONTENT_LENGTH, else None."""
    if len(content) > MAX_CONTENT_LENGTH:
        return {"error": f"{field} too large ({len(content)} chars, max {MAX_CONTENT_LENGTH})"}
    return None


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

    def remove(self, name: str) -> bool:
        if name not in self._tools:
            return False
        del self._tools[name]
        del self._handlers[name]
        return True


def register_builtin_tools(
    registry: ToolRegistry,
    workspaces: Path,
    on_routines_changed: Callable[[], None] | None = None,
    on_routine_run: Callable[[str], Coroutine[Any, Any, str | None]] | None = None,
    config: Any = None,
    plugin_registry: Any = None,  # PluginRegistry | None — avoided to prevent circular import
    dispatcher: Any = None,  # ChannelDispatcher | None — avoided to prevent circular import
) -> None:
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
        nicknames: list[str] | None = None,
        relationship: str | None = None,
        **_: Any,
    ) -> dict[str, Any]:
        contact = get_contact(workspaces, id)
        if not contact:
            contact = Contact(id=id, name=name or id, relationship=relationship or "other")
        if name:
            contact.name = name
        if nicknames is not None:
            contact.nicknames = nicknames
        if relationship:
            contact.relationship = relationship
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
                    "nicknames": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Nicknames or shortened names for this person",
                    },
                    "relationship": {
                        "type": "string",
                        "description": (
                            "Relationship (e.g. 'wife', 'mother', 'friend', 'pet')"
                        ),
                    },
                },
                "required": ["id"],
            },
        ),
        contact_update,
    )

    async def contact_note(
        *, contact_id: str, content: str, **_: Any
    ) -> dict[str, Any]:
        """Add a note about a contact — stored as markdown for semantic search."""
        if err := _check_content_length(content):
            return err
        contact = get_contact(workspaces, contact_id)
        if contact is None:
            return {"error": f"Contact '{contact_id}' not found"}

        notes_dir = workspaces / HOUSEHOLD_WORKSPACE / "contacts" / "notes"
        notes_dir.mkdir(parents=True, exist_ok=True)
        safe_id = safe_slug(contact.id)
        path = notes_dir / f"{safe_id}.md"
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")

        if not path.exists():
            path.write_text(f"# {contact.name}\n\n- [{timestamp}] {content}\n")
        else:
            with path.open("a") as f:
                f.write(f"- [{timestamp}] {content}\n")

        return {"status": "saved", "contact_id": contact.id, "name": contact.name}

    registry.register(
        ToolDefinition(
            name="contact_note",
            description=(
                "Add a note about a contact — a fact, observation, preference, or "
                "anything worth remembering about this person. Notes are searchable "
                "via semantic memory. Use this instead of storing facts on the contact."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "contact_id": {
                        "type": "string",
                        "description": "Contact ID",
                    },
                    "content": {
                        "type": "string",
                        "description": "The note to add about this contact",
                    },
                },
                "required": ["contact_id", "content"],
            },
        ),
        contact_note,
    )

    async def interaction_log(
        *, contact_id: str, type: InteractionType, notes: str, **_: Any
    ) -> dict[str, Any]:
        contact = get_contact(workspaces, contact_id)
        if not contact:
            return {"error": f"Contact '{contact_id}' not found"}
        interaction = Interaction(
            date=datetime.now(timezone.utc), type=type, notes=notes
        )
        contact.interactions.append(interaction)
        # Advance recurring reminders based on the new interaction date
        for reminder in contact.reminders:
            if reminder.interval_days and reminder.next_date:
                today = interaction.date.date()
                while reminder.next_date <= today:
                    reminder.next_date = reminder.next_date + timedelta(
                        days=reminder.interval_days
                    )
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
                        "enum": list(get_args(InteractionType)),
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

    async def memory_save(
        *, person: str, topic: str, content: str, **_: Any
    ) -> dict[str, Any]:
        if err := _check_content_length(content):
            return err
        path = memory_save_topic(workspaces, person, topic, content)
        return {"status": "saved", "topic": topic, "path": str(path)}

    registry.register(
        ToolDefinition(
            name="memory_save",
            description=(
                "Save a piece of knowledge about a household member. Appends to "
                "a topic file — never overwrites. Pick a short topic name "
                "(e.g. 'food', 'health', 'routines', 'work')."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "person": {"type": "string", "description": "Household member name"},
                    "topic": {
                        "type": "string",
                        "description": "Topic name (e.g. 'food', 'health', 'family')",
                    },
                    "content": {
                        "type": "string",
                        "description": "The fact or knowledge to remember",
                    },
                },
                "required": ["person", "topic", "content"],
            },
        ),
        memory_save,
    )

    async def memory_read(
        *, person: str, topic: str | None = None, **_: Any
    ) -> dict[str, Any]:
        if topic:
            text = memory_read_topic(workspaces, person, topic)
            if text is None:
                return {"person": person, "topic": topic, "content": None}
            return {"person": person, "topic": topic, "content": text}
        topics = memory_list_topics(workspaces, person)
        return {"person": person, "topics": topics}

    registry.register(
        ToolDefinition(
            name="memory_read",
            description=(
                "Read stored knowledge about a household member. "
                "Call without topic to list all topics, or with a topic to read it."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "person": {"type": "string", "description": "Household member name"},
                    "topic": {
                        "type": "string",
                        "description": "Topic to read (omit to list all topics)",
                    },
                },
                "required": ["person"],
            },
        ),
        memory_read,
    )

    async def household_share(
        *, topic: str, content: str, **_: Any
    ) -> dict[str, Any]:
        """Share knowledge with the entire household."""
        if err := _check_content_length(content):
            return err
        path = memory_save_topic(workspaces, HOUSEHOLD_WORKSPACE, topic, content)
        return {"status": "shared", "topic": topic, "path": str(path)}

    registry.register(
        ToolDefinition(
            name="household_share",
            description=(
                "Share knowledge with the entire household. Use when a member "
                "explicitly asks to share something with everyone."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "Topic name (e.g. 'house-rules', 'wifi', 'emergency')",
                    },
                    "content": {
                        "type": "string",
                        "description": "The information to share",
                    },
                },
                "required": ["topic", "content"],
            },
        ),
        household_share,
    )

    # --- Note tools ---

    async def note_save(*, person: str, content: str, **_: Any) -> dict[str, Any]:
        if err := _check_content_length(content):
            return err
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        time_str = datetime.now(timezone.utc).strftime("%H:%M")
        notes_dir = workspaces / person / "notes"
        notes_dir.mkdir(parents=True, exist_ok=True)
        path = notes_dir / f"{today}.md"
        entry = f"- [{time_str}] {content}"
        if path.exists():
            existing = path.read_text().rstrip("\n")
            path.write_text(f"{existing}\n{entry}\n")
        else:
            path.write_text(f"{entry}\n")
        return {"status": "saved", "path": str(path)}

    registry.register(
        ToolDefinition(
            name="note_save",
            description=(
                "Append a single note entry to a household member's daily log. "
                "Each call adds one timestamped entry — do NOT include previous "
                "entries, only the new information to record."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "person": {"type": "string", "description": "Household member name"},
                    "content": {
                        "type": "string",
                        "description": (
                            "The new note to append (just the new info, not the full note)"
                        ),
                    },
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
        try:
            date = safe_date(date)
        except ValueError:
            return {"error": f"Invalid date format: {date}"}
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

    # --- Reminder tools ---

    from homeclaw.reminders.store import add_reminder_safe as _add_reminder
    from homeclaw.reminders.store import complete_reminder_safe as _complete_reminder
    from homeclaw.reminders.store import delete_reminder_safe as _delete_reminder
    from homeclaw.reminders.store import load_reminders as _load_reminders

    async def reminder_add(
        *,
        person: str,
        note: str,
        date: str | None = None,
        interval_days: int | None = None,
        **_: Any,
    ) -> dict[str, Any]:
        from datetime import date as date_type
        from uuid import uuid4

        from homeclaw.reminders.models import Reminder

        due_date = None
        if date:
            try:
                due_date = date_type.fromisoformat(safe_date(date))
            except ValueError:
                return {"error": f"Invalid date: {date}. Use YYYY-MM-DD format."}

        reminder = Reminder(
            id=uuid4().hex[:8],
            person=person,
            note=note,
            due_date=due_date,
            interval_days=interval_days,
            created_at=datetime.now(datetime.now().astimezone().tzinfo),
        )
        await _add_reminder(workspaces, reminder)
        return {
            "status": "set",
            "id": reminder.id,
            "note": note,
            "due_date": str(due_date) if due_date else None,
            "interval_days": interval_days,
            "next_due": str(reminder.next_due),
        }

    registry.register(
        ToolDefinition(
            name="reminder_add",
            description=(
                "Set a reminder for a household member. Supports one-shot "
                "(provide date) or recurring (provide interval_days, e.g. 7 for "
                "weekly). Can provide both date + interval for 'starting on X, "
                "repeat every N days'."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "person": {"type": "string", "description": "Household member name"},
                    "note": {"type": "string", "description": "Reminder text"},
                    "date": {
                        "type": "string",
                        "description": "Due date in YYYY-MM-DD (for one-shot or start date)",
                    },
                    "interval_days": {
                        "type": "integer",
                        "description": "Repeat every N days (e.g. 7 for weekly, 14 for biweekly)",
                    },
                },
                "required": ["person", "note"],
            },
        ),
        reminder_add,
    )

    async def reminder_list(*, person: str, **_: Any) -> dict[str, Any]:
        reminders = _load_reminders(workspaces, person)
        active = [r for r in reminders if not r.done]
        return {
            "reminders": [
                {
                    "id": r.id,
                    "note": r.note,
                    "next_due": str(r.next_due) if r.next_due else None,
                    "interval_days": r.interval_days,
                    "recurring": r.interval_days is not None,
                }
                for r in active
            ],
            "count": len(active),
        }

    registry.register(
        ToolDefinition(
            name="reminder_list",
            description="List active reminders for a household member.",
            parameters={
                "type": "object",
                "properties": {
                    "person": {"type": "string", "description": "Household member name"},
                },
                "required": ["person"],
            },
        ),
        reminder_list,
    )

    async def reminder_complete(
        *, person: str, reminder_id: str, **_: Any
    ) -> dict[str, Any]:
        result = await _complete_reminder(workspaces, person, reminder_id)
        if not result:
            return {"error": f"Reminder '{reminder_id}' not found"}
        return {
            "status": "completed",
            "id": result.id,
            "note": result.note,
            "recurring": result.interval_days is not None,
            "next_due": str(result.next_due) if result.next_due else None,
        }

    registry.register(
        ToolDefinition(
            name="reminder_complete",
            description=(
                "Mark a reminder as done. For recurring reminders, this advances "
                "to the next occurrence. For one-shot reminders, marks it complete."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "person": {"type": "string", "description": "Household member name"},
                    "reminder_id": {"type": "string", "description": "Reminder ID"},
                },
                "required": ["person", "reminder_id"],
            },
        ),
        reminder_complete,
    )

    async def reminder_delete(
        *, person: str, reminder_id: str, **_: Any
    ) -> dict[str, Any]:
        if await _delete_reminder(workspaces, person, reminder_id):
            return {"status": "deleted", "id": reminder_id}
        return {"error": f"Reminder '{reminder_id}' not found"}

    registry.register(
        ToolDefinition(
            name="reminder_delete",
            description="Permanently delete a reminder.",
            parameters={
                "type": "object",
                "properties": {
                    "person": {"type": "string", "description": "Household member name"},
                    "reminder_id": {"type": "string", "description": "Reminder ID"},
                },
                "required": ["person", "reminder_id"],
            },
        ),
        reminder_delete,
    )

    # --- Bookmark tools ---

    async def bookmark_save(
        *,
        title: str,
        category: str = "other",
        url: str | None = None,
        tags: list[str] | None = None,
        person: str = "",
        **_: Any,
    ) -> dict[str, Any]:
        from uuid import uuid4

        bookmark = Bookmark(
            id=uuid4().hex[:8],
            url=url,
            title=title,
            category=category,
            tags=tags or [],
            saved_by=person,
            saved_at=datetime.now(timezone.utc),
        )
        saved = save_bookmark(workspaces, bookmark)
        return {"status": "saved", "id": saved.id, "title": saved.title}

    registry.register(
        ToolDefinition(
            name="bookmark_save",
            description=(
                "Save a link or recommendation (restaurant, bar, cafe, recipe, etc.) "
                "to the household's shared bookmarks. Use this when someone shares a "
                "link or mentions a place/recipe they want to remember."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Name of the place or recipe"},
                    "category": {
                        "type": "string",
                        "description": (
                            "Category (e.g. 'place', 'recipe', 'book', 'article')"
                        ),
                    },
                    "url": {"type": "string", "description": "URL if one was shared"},
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Tags (e.g. 'italian', 'rooftop', 'brunch', 'vegan')",
                    },
                    "person": {"type": "string", "description": "Who saved this"},
                },
                "required": ["title"],
            },
        ),
        bookmark_save,
    )

    async def bookmark_list(
        *,
        category: str | None = None,
        tag: str | None = None,
        **_: Any,
    ) -> dict[str, Any]:
        results = list_bookmarks(workspaces, category=category, tag=tag)
        return {
            "bookmarks": [b.model_dump(mode="json") for b in results],
            "count": len(results),
        }

    registry.register(
        ToolDefinition(
            name="bookmark_list",
            description="List saved bookmarks, optionally filtered by category or tag.",
            parameters={
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "description": "Filter by category (e.g. 'place', 'recipe', 'book')",
                    },
                    "tag": {"type": "string", "description": "Filter by tag"},
                },
            },
        ),
        bookmark_list,
    )

    async def bookmark_search(*, query: str, **_: Any) -> dict[str, Any]:
        results = search_bookmarks(workspaces, query)
        return {
            "bookmarks": [b.model_dump(mode="json") for b in results],
            "count": len(results),
        }

    registry.register(
        ToolDefinition(
            name="bookmark_search",
            description=(
                "Search the household's saved bookmarks by keyword. Use this when someone "
                "asks for recommendations, wants to find a saved place or recipe, or is "
                "planning an outing or meal."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query (name, tag, neighborhood, cuisine, etc.)",
                    },
                },
                "required": ["query"],
            },
        ),
        bookmark_search,
    )

    async def bookmark_delete(*, id: str, **_: Any) -> dict[str, Any]:
        if delete_bookmark(workspaces, id):
            return {"status": "deleted", "id": id}
        return {"error": f"Bookmark '{id}' not found"}

    registry.register(
        ToolDefinition(
            name="bookmark_delete",
            description="Delete a saved bookmark by ID.",
            parameters={
                "type": "object",
                "properties": {
                    "id": {"type": "string", "description": "Bookmark ID"},
                },
                "required": ["id"],
            },
        ),
        bookmark_delete,
    )

    async def bookmark_update(
        *,
        id: str,
        url: str | None = None,
        title: str | None = None,
        category: str | None = None,
        tags: list[str] | None = None,
        **_: Any,
    ) -> dict[str, Any]:
        result = update_bookmark(workspaces, id, url=url, title=title, category=category, tags=tags)
        if result is None:
            return {"error": f"Bookmark '{id}' not found"}
        return {"status": "updated", "id": result.id, "title": result.title, "url": result.url}

    registry.register(
        ToolDefinition(
            name="bookmark_update",
            description=(
                "Update an existing bookmark. Use this to add or change the URL, title, "
                "category, or tags on a saved bookmark. Only provide the fields to change."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "id": {"type": "string", "description": "Bookmark ID"},
                    "url": {"type": "string", "description": "New URL"},
                    "title": {"type": "string", "description": "New title"},
                    "category": {"type": "string", "description": "New category"},
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "New tags (replaces existing tags)",
                    },
                },
                "required": ["id"],
            },
        ),
        bookmark_update,
    )

    async def bookmark_categories(**_: Any) -> dict[str, Any]:
        return {"categories": get_categories(workspaces)}

    registry.register(
        ToolDefinition(
            name="bookmark_categories",
            description="List all bookmark categories currently in use.",
            parameters={"type": "object", "properties": {}},
        ),
        bookmark_categories,
    )

    async def bookmark_note(
        *, bookmark_id: str, content: str, **_: Any
    ) -> dict[str, Any]:
        """Add a note to a bookmark — stored as markdown for semantic search."""
        if not content or not content.strip() or content.strip().lower() == "none":
            return {"error": "content must not be empty"}
        if err := _check_content_length(content):
            return err
        # Verify the bookmark exists
        all_bookmarks = list_bookmarks(workspaces)
        bookmark = next((b for b in all_bookmarks if b.id == bookmark_id), None)
        if bookmark is None:
            return {"error": f"Bookmark '{bookmark_id}' not found"}

        notes_dir = workspaces / HOUSEHOLD_WORKSPACE / "bookmarks" / "notes"
        notes_dir.mkdir(parents=True, exist_ok=True)
        safe_id = safe_slug(bookmark_id)
        path = notes_dir / f"{safe_id}.md"
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")

        if not path.exists():
            path.write_text(f"# {bookmark.title}\n\n- [{timestamp}] {content}\n")
        else:
            with path.open("a") as f:
                f.write(f"- [{timestamp}] {content}\n")

        return {"status": "saved", "bookmark_id": bookmark_id, "title": bookmark.title}

    registry.register(
        ToolDefinition(
            name="bookmark_note",
            description=(
                "Add a note to a saved bookmark — a review, tip, experience, or "
                "any context that helps recall it later. Notes are searchable via "
                "semantic memory."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "bookmark_id": {
                        "type": "string",
                        "description": "ID of the bookmark to annotate",
                    },
                    "content": {
                        "type": "string",
                        "description": "The note to add (review, tip, experience)",
                    },
                },
                "required": ["bookmark_id", "content"],
            },
        ),
        bookmark_note,
    )

    async def bookmark_note_edit(
        *, bookmark_id: str, note_index: int, content: str, **_: Any
    ) -> dict[str, Any]:
        """Edit an existing note on a bookmark by its 1-based index."""
        notes_dir = workspaces / HOUSEHOLD_WORKSPACE / "bookmarks" / "notes"
        safe_id = safe_slug(bookmark_id)
        path = notes_dir / f"{safe_id}.md"
        if not path.exists():
            return {"error": f"No notes found for bookmark '{bookmark_id}'"}

        lines = path.read_text().splitlines()
        # Find note lines (start with "- [")
        note_indices: list[int] = []
        for i, line in enumerate(lines):
            if line.startswith("- ["):
                note_indices.append(i)

        if not note_indices:
            return {"error": "No note entries found in file"}
        if note_index < 1 or note_index > len(note_indices):
            return {
                "error": (
                    f"Invalid note_index {note_index}; "
                    f"bookmark has {len(note_indices)} note(s)"
                )
            }

        line_idx = note_indices[note_index - 1]
        old_line = lines[line_idx]
        # Preserve the original timestamp
        bracket_end = old_line.index("] ")
        timestamp_prefix = old_line[: bracket_end + 2]
        lines[line_idx] = f"{timestamp_prefix}{content}"
        path.write_text("\n".join(lines) + "\n")

        return {"status": "updated", "bookmark_id": bookmark_id, "note_index": note_index}

    registry.register(
        ToolDefinition(
            name="bookmark_note_edit",
            description=(
                "Edit an existing note on a bookmark. Use this to correct or update "
                "a previous note rather than appending a new one."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "bookmark_id": {
                        "type": "string",
                        "description": "ID of the bookmark whose note to edit",
                    },
                    "note_index": {
                        "type": "integer",
                        "description": "1-based index of the note to edit (in chronological order)",
                    },
                    "content": {
                        "type": "string",
                        "description": "New content to replace the existing note",
                    },
                },
                "required": ["bookmark_id", "note_index", "content"],
            },
        ),
        bookmark_note_edit,
    )

    async def bookmark_note_delete(
        *, bookmark_id: str, note_index: int, **_: Any
    ) -> dict[str, Any]:
        """Delete a note from a bookmark by its 1-based index."""
        notes_dir = workspaces / HOUSEHOLD_WORKSPACE / "bookmarks" / "notes"
        safe_id = safe_slug(bookmark_id)
        path = notes_dir / f"{safe_id}.md"
        if not path.exists():
            return {"error": f"No notes found for bookmark '{bookmark_id}'"}

        lines = path.read_text().splitlines()
        note_indices: list[int] = []
        for i, line in enumerate(lines):
            if line.startswith("- ["):
                note_indices.append(i)

        if not note_indices:
            return {"error": "No note entries found in file"}
        if note_index < 1 or note_index > len(note_indices):
            return {
                "error": (
                    f"Invalid note_index {note_index}; "
                    f"bookmark has {len(note_indices)} note(s)"
                )
            }

        line_idx = note_indices[note_index - 1]
        del lines[line_idx]
        path.write_text("\n".join(lines) + "\n")

        return {
            "status": "deleted",
            "bookmark_id": bookmark_id,
            "note_index": note_index,
            "remaining_notes": len(note_indices) - 1,
        }

    registry.register(
        ToolDefinition(
            name="bookmark_note_delete",
            description=(
                "Delete a note from a bookmark by its 1-based index. Use this to "
                "remove incorrect, duplicate, or unwanted notes."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "bookmark_id": {
                        "type": "string",
                        "description": "ID of the bookmark whose note to delete",
                    },
                    "note_index": {
                        "type": "integer",
                        "description": "1-based index of the note to delete (in chronological order)",
                    },
                },
                "required": ["bookmark_id", "note_index"],
            },
        ),
        bookmark_note_delete,
    )

    # --- Web tools (via Jina) ---

    def _jina_headers(accept: str = "text/markdown") -> dict[str, str]:
        headers = {"Accept": accept}
        key = config.jina_api_key if config else None
        if key:
            headers["Authorization"] = f"Bearer {key}"
        return headers

    async def web_read(*, url: str, **_: Any) -> dict[str, Any]:
        import httpx

        try:
            transport = httpx.AsyncHTTPTransport(retries=2)
            async with httpx.AsyncClient(timeout=30, transport=transport) as client:
                resp = await client.get(
                    f"https://r.jina.ai/{url}",
                    headers=_jina_headers("text/markdown"),
                )
                resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            return {"error": f"HTTP {e.response.status_code}", "url": url}
        except httpx.RequestError as e:
            return {"error": str(e), "url": url}

        content = resp.text
        # Truncate to avoid blowing up the context window
        max_chars = 12_000
        if len(content) > max_chars:
            content = content[:max_chars] + "\n\n[… truncated]"
        return {"url": url, "content": content}

    registry.register(
        ToolDefinition(
            name="web_read",
            description=(
                "Fetch a web page and return its content as clean markdown. "
                "Use this when someone shares a URL, you need to look up "
                "information from a specific page, or you want to read an "
                "article, news story, or any web content. Always prefer this "
                "over guessing at page contents."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The URL to fetch"},
                },
                "required": ["url"],
            },
        ),
        web_read,
    )

    async def web_search(*, query: str, **_: Any) -> dict[str, Any]:
        import httpx

        if not (config and config.jina_api_key):
            return {"error": "Web search requires JINA_API_KEY to be set", "query": query}

        try:
            transport = httpx.AsyncHTTPTransport(retries=2)
            async with httpx.AsyncClient(timeout=30, transport=transport) as client:
                resp = await client.get(
                    f"https://s.jina.ai/{query}",
                    headers=_jina_headers("application/json"),
                )
                resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            return {"error": f"HTTP {e.response.status_code}", "query": query}
        except httpx.RequestError as e:
            return {"error": str(e), "query": query}

        content = resp.text
        max_chars = 8_000
        if len(content) > max_chars:
            content = content[:max_chars] + "\n\n[… truncated]"
        return {"query": query, "results": content}

    registry.register(
        ToolDefinition(
            name="web_search",
            description=(
                "Search the web and return results. You MUST use this for any "
                "question requiring current information — news, weather, events, "
                "prices, scores, headlines, recent developments. Never guess or "
                "hedge about current events; search first, then summarize the "
                "real results."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query",
                    },
                },
                "required": ["query"],
            },
        ),
        web_search,
    )

    # --- Message tool — delivers via channel dispatcher ---

    async def message_send(
        *, text: str, person: str | None = None, group: bool = False, **_: Any,
    ) -> dict[str, Any]:
        if dispatcher is None:
            return {"status": "queued", "person": person, "text": text}
        if group:
            return await dispatcher.send_group("", text)
        if not person:
            return {"error": "Either 'person' or 'group: true' is required."}
        return await dispatcher.send(person, text)

    registry.register(
        ToolDefinition(
            name="message_send",
            description=(
                "Send a message to a household member or the household group chat. "
                "Set 'person' to message an individual, or 'group' to true to "
                "send to the household group chat."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "person": {
                        "type": "string",
                        "description": "Recipient name (for individual messages)",
                    },
                    "text": {"type": "string", "description": "Message text"},
                    "group": {
                        "type": "boolean",
                        "description": "Send to the household group chat instead",
                    },
                },
                "required": ["text"],
            },
        ),
        message_send,
    )

    # --- Channel preference tool ---

    async def channel_preference_set(
        *, person: str, channel: str, **_: Any
    ) -> dict[str, Any]:
        if dispatcher is None:
            return {"status": "error", "detail": "No channel dispatcher available"}
        available = dispatcher.available_channels()
        if channel not in available:
            return {
                "status": "error",
                "detail": f"Unknown channel '{channel}'. Available: {available}",
            }
        dispatcher.set_preference(person, channel)
        return {"status": "ok", "person": person, "preferred_channel": channel}

    async def channel_preference_get(
        *, person: str, **_: Any
    ) -> dict[str, Any]:
        if dispatcher is None:
            return {"status": "error", "detail": "No channel dispatcher available"}
        pref = dispatcher.get_preference(person)
        return {
            "person": person,
            "preferred_channel": pref,
            "available_channels": dispatcher.available_channels(),
        }

    registry.register(
        ToolDefinition(
            name="channel_preference_set",
            description=(
                "Set a household member's preferred messaging channel "
                "for scheduled updates."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "person": {"type": "string", "description": "Member name"},
                    "channel": {
                        "type": "string",
                        "description": "Channel name (e.g. 'telegram', 'whatsapp')",
                    },
                },
                "required": ["person", "channel"],
            },
        ),
        channel_preference_set,
    )

    registry.register(
        ToolDefinition(
            name="channel_preference_get",
            description="Get a household member's preferred messaging channel.",
            parameters={
                "type": "object",
                "properties": {
                    "person": {"type": "string", "description": "Member name"},
                },
                "required": ["person"],
            },
        ),
        channel_preference_get,
    )

    # --- Routine management tools ---

    from homeclaw.scheduler.routines import add_routine, parse_routines_md, remove_routine

    async def routine_list(**_: Any) -> dict[str, Any]:
        routines = parse_routines_md(workspaces)
        return {
            "routines": [
                {"name": r.name, "description": r.description}
                for r in routines
            ]
        }

    registry.register(
        ToolDefinition(
            name="routine_list",
            description="List all scheduled household routines.",
            parameters={"type": "object", "properties": {}},
        ),
        routine_list,
    )

    async def routine_add(
        *, title: str, schedule: str, action: str, **_: Any
    ) -> dict[str, Any]:
        try:
            add_routine(workspaces, title, schedule, action)
        except ValueError as e:
            return {"error": str(e)}
        if on_routines_changed:
            on_routines_changed()
        return {"status": "added", "title": title, "schedule": schedule}

    registry.register(
        ToolDefinition(
            name="routine_add",
            description=(
                "Add a new scheduled routine for the household. "
                "Schedule can be natural language or a 5-field cron expression "
                "for complex schedules."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Short name for the routine (e.g. 'Weekly grocery check')",
                    },
                    "schedule": {
                        "type": "string",
                        "description": (
                            "When to run. Natural language examples: 'Every weekday at 7:30am', "
                            "'Every Sunday at 10:00am', 'Every 3 days', 'Every other Tuesday at 9am', "
                            "'Monthly on the 1st at 10am', '1st Monday of the month at 9am', "
                            "'Last Friday of the month at 3pm'. "
                            "For complex schedules, use a 5-field cron expression: 'minute hour day month day_of_week' "
                            "(e.g. '30 7 * * 1-5' for weekdays at 7:30am, '0 9 1 * *' for 1st of month at 9am)."
                        ),
                    },
                    "action": {
                        "type": "string",
                        "description": "What the routine should do",
                    },
                },
                "required": ["title", "schedule", "action"],
            },
        ),
        routine_add,
    )

    async def routine_update(
        *, name: str,
        schedule: str | None = None,
        action: str | None = None,
        title: str | None = None,
        **_: Any,
    ) -> dict[str, Any]:
        from homeclaw.scheduler.routines import update_routine
        updated = update_routine(workspaces, name, schedule=schedule, action=action, title=title)
        if not updated:
            return {"error": f"Routine '{name}' not found"}
        if on_routines_changed:
            on_routines_changed()
        return {"status": "updated", "name": name}

    registry.register(
        ToolDefinition(
            name="routine_update",
            description=(
                "Update an existing routine's schedule, action, or title. "
                "Use routine_list first to see available routine names. "
                "Use this when someone wants to change what a routine does "
                "(e.g. 'add news to my morning briefing') or when it runs."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "The routine slug name (e.g. 'morning_briefing')",
                    },
                    "schedule": {
                        "type": "string",
                        "description": "New schedule (optional — omit to keep current)",
                    },
                    "action": {
                        "type": "string",
                        "description": "New action description (optional — omit to keep current)",
                    },
                    "title": {
                        "type": "string",
                        "description": "New title (optional — omit to keep current)",
                    },
                },
                "required": ["name"],
            },
        ),
        routine_update,
    )

    async def routine_remove(*, name: str, **_: Any) -> dict[str, Any]:
        removed = remove_routine(workspaces, name)
        if not removed:
            return {"error": f"Routine '{name}' not found"}
        if on_routines_changed:
            on_routines_changed()
        return {"status": "removed", "name": name}

    registry.register(
        ToolDefinition(
            name="routine_remove",
            description=(
                "Remove a scheduled routine by its slug name. "
                "Use routine_list first to see available routine names."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "The routine slug name (e.g. 'morning_briefing')",
                    },
                },
                "required": ["name"],
            },
        ),
        routine_remove,
    )

    async def routine_run(*, name: str, **_: Any) -> dict[str, Any]:
        if on_routine_run is None:
            return {"error": "Scheduler not available"}
        result = await on_routine_run(name)
        if result is None:
            return {"error": f"Routine '{name}' not found — use routine_list to see available names"}
        if not result:
            return {"status": "error", "name": name, "detail": "Routine ran but produced no output — check logs for errors"}
        return {"status": "completed", "name": name, "result": result}

    registry.register(
        ToolDefinition(
            name="routine_run",
            description=(
                "Manually trigger a scheduled routine to run right now. "
                "Use this when a routine was missed or a user asks to run one immediately. "
                "The routine runs synchronously and returns its full output so you can "
                "confirm it completed successfully."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "The routine slug name (e.g. 'morning_briefing')",
                    },
                },
                "required": ["name"],
            },
        ),
        routine_run,
    )

    # --- Skill tools ---

    async def skill_list(*, person: str, **_: Any) -> dict[str, Any]:
        from homeclaw.plugins.skills.loader import discover_skills, skill_md_to_definition

        locations = discover_skills(workspaces, person)
        skills = []
        for loc in locations:
            try:
                defn = skill_md_to_definition((loc.skill_dir / "SKILL.md").read_text())
                skills.append({
                    "name": loc.name,
                    "scope": loc.scope,
                    "description": defn.description,
                    "allowed_domains": defn.allowed_domains,
                })
            except Exception:
                skills.append({"name": loc.name, "scope": loc.scope, "error": "failed to parse"})
        return {"skills": skills, "count": len(skills)}

    registry.register(
        ToolDefinition(
            name="skill_list",
            description=(
                "List all skill plugins available to this household member — "
                "includes household-wide skills and their own private skills."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "person": {"type": "string", "description": "Household member name"},
                },
                "required": ["person"],
            },
        ),
        skill_list,
    )

    def _skill_allow_local() -> bool:
        if config is None:
            return False
        return bool(getattr(config, "skill_allow_local_network", False))

    def _is_admin(person: str) -> bool:
        """Check if *person* is an admin member."""
        if config is None:
            return True  # No config = dev mode, everyone is admin
        admin_members: list[str] = getattr(config, "admin_members", [])
        return not admin_members or person in admin_members

    def _needs_approval(person: str) -> bool:
        """Check if *person* needs admin approval for skill creation."""
        if _is_admin(person):
            return False
        if config is None:
            return False
        return bool(getattr(config, "skill_approval_required", True))

    def _pending_dir() -> Path:
        return workspaces / "household" / "skills" / ".pending"

    async def skill_create(
        *,
        person: str,
        name: str,
        description: str,
        scope: str,
        allowed_domains: list[str] | None = None,
        instructions: str,
        initial_files: list[dict[str, Any]] | None = None,
        source_notes: list[str] | None = None,
        source_bookmarks: dict[str, Any] | None = None,
        **_: Any,
    ) -> dict[str, Any]:
        from homeclaw.plugins.skills.loader import (
            load_skill,
            render_skill_md,
            slugify_skill_name,
        )
        from homeclaw.plugins.registry import PluginType

        slug = slugify_skill_name(name)
        if not slug:
            return {"error": f"Invalid skill name '{name}' — must contain alphanumeric characters"}

        if scope not in ("household", "private"):
            return {"error": f"Invalid scope '{scope}' — must be 'household' or 'private'"}

        owner = "household" if scope == "household" else person

        # Check if approval is required
        pending = _needs_approval(person)
        if pending:
            skill_dir = _pending_dir() / slug
        else:
            skill_dir = workspaces / owner / "skills" / slug

        # Check for conflicts in both live and pending
        live_dir = workspaces / owner / "skills" / slug
        if live_dir.exists():
            return {"error": f"Skill '{slug}' already exists under {owner}"}
        if not pending and (_pending_dir() / slug).exists():
            return {"error": f"Skill '{slug}' is already pending approval"}

        skill_dir.mkdir(parents=True, exist_ok=True)
        data_dir = skill_dir / "data"
        data_dir.mkdir(exist_ok=True)

        # Write SKILL.md (new YAML frontmatter format)
        metadata: dict[str, str] = {}
        if pending:
            metadata["requested_by"] = person
            metadata["requested_scope"] = scope
            metadata["requested_owner"] = owner
        skill_md = render_skill_md(
            name=slug,
            description=description,
            allowed_domains=allowed_domains or None,
            instructions=instructions,
            metadata=metadata or None,
        )
        (skill_dir / "SKILL.md").write_text(skill_md)

        seeded: list[str] = []

        # Write initial_files into data/
        for f in initial_files or []:
            filename = Path(f["filename"]).name  # strip any path components
            (data_dir / filename).write_text(f["content"])
            seeded.append(filename)

        # Copy from source_notes into data/
        for topic in source_notes or []:
            from homeclaw.memory.markdown import memory_read_topic

            content = memory_read_topic(workspaces, person, topic)
            if content is None:
                content = memory_read_topic(workspaces, HOUSEHOLD_WORKSPACE, topic)
            if content is not None:
                dest = data_dir / f"{topic}.md"
                dest.write_text(content)
                seeded.append(f"{topic}.md")
            else:
                _logger.warning(
                    "skill_create: topic '%s' not found for %s or household",
                    topic, person,
                )

        # Export source_bookmarks as markdown into data/
        if source_bookmarks:
            bm_category = source_bookmarks.get("category")
            bm_ids: list[str] = source_bookmarks.get("ids", [])
            all_bms = list_bookmarks(workspaces, category=bm_category)
            if bm_ids:
                all_bms = [b for b in all_bms if b.id in bm_ids]
            if all_bms:
                lines = ["# Bookmarks", ""]
                for bm in all_bms:
                    lines.append(f"## {bm.title}")
                    lines.append(f"- Category: {bm.category}")
                    if bm.url:
                        lines.append(f"- URL: {bm.url}")
                    if bm.tags:
                        lines.append(f"- Tags: {', '.join(bm.tags)}")
                    if bm.saved_by:
                        lines.append(f"- Saved by: {bm.saved_by}")
                    lines.append("")
                (data_dir / "bookmarks.md").write_text("\n".join(lines))
                seeded.append("bookmarks.md")

        # If pending, return early — don't load into registry
        if pending:
            return {
                "status": "pending_approval",
                "name": slug,
                "scope": scope,
                "requested_by": person,
                "seeded_files": seeded,
                "note": (
                    "Skill created but needs admin approval before it becomes active. "
                    "An admin can approve it with skill_approve."
                ),
            }

        # Hot-load into registry
        loaded = False
        if plugin_registry is not None:
            try:
                plugin = load_skill(skill_dir, owner, allow_local_network=_skill_allow_local())
                plugin_registry.register(plugin, PluginType.SKILL)
                loaded = True
            except Exception as e:
                _logger.exception("skill_create: failed to hot-load skill '%s'", slug)
                return {
                    "status": "created",
                    "name": slug,
                    "scope": scope,
                    "skill_dir": str(skill_dir),
                    "seeded_files": seeded,
                    "loaded": False,
                    "warning": f"Skill created but failed to load: {e}",
                }

        return {
            "status": "created",
            "name": slug,
            "scope": scope,
            "skill_dir": str(skill_dir),
            "seeded_files": seeded,
            "loaded": loaded,
            **({"note": "Restart required to activate skill — no plugin registry available"} if not loaded else {}),
        }

    registry.register(
        ToolDefinition(
            name="skill_create",
            description=(
                "Create a new skill — a self-contained mini-app with its own "
                "data directory. Every skill automatically gets data_list, "
                "data_read, data_write, and data_delete tools (namespaced "
                "as {name}__data_read etc). Setting allowed_domains also "
                "gives the skill an {name}__http_call tool for API access. "
                "Choose 'household' scope to share, 'private' for one person."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "person": {"type": "string", "description": "Household member creating the skill"},
                    "name": {
                        "type": "string",
                        "description": "Skill name (slug-style, e.g. 'weather', 'my_calendar')",
                    },
                    "description": {
                        "type": "string",
                        "description": "Short description of what the skill does",
                    },
                    "scope": {
                        "type": "string",
                        "enum": ["household", "private"],
                        "description": (
                            "Who can use this skill and see its data. "
                            "'household' = shared with all members; "
                            "'private' = only accessible to this person."
                        ),
                    },
                    "allowed_domains": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "Domains the skill is allowed to reach via HTTP. "
                            "Setting this automatically registers a "
                            "{name}__http_call tool for the skill. "
                            "Example: ['api.openweathermap.org']"
                        ),
                    },
                    "instructions": {
                        "type": "string",
                        "description": "Instructions for how to use this skill, injected into the agent's context",
                    },
                    "initial_files": {
                        "type": "array",
                        "description": "Files to seed in the skill's data directory",
                        "items": {
                            "type": "object",
                            "properties": {
                                "filename": {"type": "string", "description": "Filename (e.g. 'notes.md')"},
                                "content": {"type": "string", "description": "File content"},
                            },
                            "required": ["filename", "content"],
                        },
                    },
                    "source_notes": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "Memory topic names to copy into the skill's data directory "
                            "(e.g. ['recipes', 'restaurant-notes']). Checks person's memory first, "
                            "then household memory."
                        ),
                    },
                    "source_bookmarks": {
                        "type": "object",
                        "description": "Export saved bookmarks into the skill's data directory as bookmarks.md",
                        "properties": {
                            "category": {"type": "string", "description": "Filter by category"},
                            "ids": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Specific bookmark IDs to include",
                            },
                        },
                    },
                },
                "required": ["person", "name", "description", "scope", "instructions"],
            },
        ),
        skill_create,
    )

    async def skill_remove(
        *,
        person: str,
        name: str,
        owner: str,
        **_: Any,
    ) -> dict[str, Any]:
        import shutil
        from datetime import datetime, timezone

        skill_dir = workspaces / safe_slug(owner) / "skills" / safe_slug(name)
        if not skill_dir.exists():
            return {"error": f"Skill '{name}' not found under '{owner}'"}

        # Unregister from plugin registry
        unregistered = False
        if plugin_registry is not None:
            unregistered = plugin_registry.unregister(name)

        # Archive: move to .archive/{name}_{timestamp}/
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        archive_root = workspaces / owner / "skills" / ".archive"
        archive_root.mkdir(parents=True, exist_ok=True)
        archive_dir = archive_root / f"{name}_{timestamp}"
        shutil.move(str(skill_dir), str(archive_dir))

        return {
            "status": "archived",
            "name": name,
            "owner": owner,
            "archive_path": str(archive_dir),
            "unregistered": unregistered,
            "note": "Skill data is preserved in the archive. Permanent deletion is only available via the web UI.",
        }

    registry.register(
        ToolDefinition(
            name="skill_remove",
            description=(
                "Remove a skill plugin. The skill is unregistered immediately and its "
                "directory is archived (not permanently deleted). Data can be recovered "
                "or permanently deleted via the web UI."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "person": {"type": "string", "description": "Household member requesting the removal"},
                    "name": {"type": "string", "description": "Skill name to remove"},
                    "owner": {
                        "type": "string",
                        "description": "Who owns the skill: 'household' or a person's name",
                    },
                },
                "required": ["person", "name", "owner"],
            },
        ),
        skill_remove,
    )

    async def skill_update(
        *,
        person: str,
        name: str,
        owner: str,
        instructions: str | None = None,
        description: str | None = None,
        **_: Any,
    ) -> dict[str, Any]:
        from homeclaw.plugins.registry import PluginType
        from homeclaw.plugins.skills.loader import (
            load_skill,
            render_skill_md,
            skill_md_to_definition,
        )

        skill_dir = workspaces / safe_slug(owner) / "skills" / safe_slug(name)
        skill_md_path = skill_dir / "SKILL.md"
        if not skill_md_path.is_file():
            return {"error": f"Skill '{name}' not found under '{owner}'"}

        defn = skill_md_to_definition(skill_md_path.read_text())

        new_desc = description if description is not None else defn.description
        new_instr = instructions if instructions is not None else defn.instructions

        # Always write back as SKILL.md (new format)
        updated_md = render_skill_md(
            name=defn.name,
            description=new_desc,
            allowed_domains=defn.allowed_domains if defn.allowed_domains else None,
            instructions=new_instr,
        )
        new_path = skill_dir / "SKILL.md"
        new_path.write_text(updated_md)

        # Re-register so the plugin picks up the new instructions
        loaded = False
        if plugin_registry is not None:
            plugin_registry.unregister(name)
            try:
                plugin = load_skill(skill_dir, owner, allow_local_network=_skill_allow_local())
                plugin_registry.register(plugin, PluginType.SKILL)
                loaded = True
            except Exception as e:
                _logger.exception("skill_update: failed to re-load skill '%s'", name)
                return {
                    "status": "updated",
                    "name": name,
                    "loaded": False,
                    "warning": f"Skill updated but failed to reload: {e}",
                }

        return {
            "status": "updated",
            "name": name,
            "owner": owner,
            "loaded": loaded,
        }

    registry.register(
        ToolDefinition(
            name="skill_update",
            description=(
                "Update a skill's instructions or description without "
                "recreating it. The skill definition (skill.md) is rewritten "
                "and the skill is reloaded. Does not affect data files."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "person": {
                        "type": "string",
                        "description": "Household member requesting the update",
                    },
                    "name": {
                        "type": "string",
                        "description": "Skill name to update",
                    },
                    "owner": {
                        "type": "string",
                        "description": "Who owns the skill: 'household' or a person's name",
                    },
                    "instructions": {
                        "type": "string",
                        "description": (
                            "New instructions (replaces existing). "
                            "Omit to keep current."
                        ),
                    },
                    "description": {
                        "type": "string",
                        "description": (
                            "New description (replaces existing). "
                            "Omit to keep current."
                        ),
                    },
                },
                "required": ["person", "name", "owner"],
            },
        ),
        skill_update,
    )

    async def skill_migrate(
        *,
        person: str,
        name: str,
        current_owner: str,
        to_scope: str,
        to_person: str | None = None,
        **_: Any,
    ) -> dict[str, Any]:
        import shutil

        from homeclaw.plugins.skills.loader import load_skill
        from homeclaw.plugins.registry import PluginType

        if to_scope not in ("household", "private"):
            return {"error": f"Invalid to_scope '{to_scope}' — must be 'household' or 'private'"}

        if to_scope == "private" and not to_person:
            return {"error": "to_person is required when to_scope is 'private'"}

        new_owner = "household" if to_scope == "household" else safe_slug(to_person or person)

        src_dir = workspaces / safe_slug(current_owner) / "skills" / safe_slug(name)
        if not src_dir.exists():
            return {"error": f"Skill '{name}' not found under '{current_owner}'"}

        dst_dir = workspaces / new_owner / "skills" / safe_slug(name)
        if dst_dir.exists():
            return {"error": f"A skill named '{name}' already exists under '{new_owner}'"}

        # Unregister current instance
        if plugin_registry is not None:
            plugin_registry.unregister(name)

        # Move directory (all data moves with it)
        dst_dir.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src_dir), str(dst_dir))

        # Re-register under new scope
        loaded = False
        if plugin_registry is not None:
            try:
                plugin = load_skill(dst_dir, new_owner, allow_local_network=_skill_allow_local())
                plugin_registry.register(plugin, PluginType.SKILL)
                loaded = True
            except Exception as e:
                _logger.exception("skill_migrate: failed to re-load skill '%s'", name)
                return {
                    "status": "migrated",
                    "name": name,
                    "from_owner": current_owner,
                    "to_owner": new_owner,
                    "loaded": False,
                    "warning": f"Skill moved but failed to reload: {e}",
                }

        return {
            "status": "migrated",
            "name": name,
            "from_owner": current_owner,
            "to_owner": new_owner,
            "skill_dir": str(dst_dir),
            "loaded": loaded,
        }

    registry.register(
        ToolDefinition(
            name="skill_migrate",
            description=(
                "Move a skill from one scope to another — household to private or vice versa. "
                "All skill data (definition + data files) moves with it. "
                "The skill is re-registered immediately under the new scope."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "person": {"type": "string", "description": "Household member requesting the migration"},
                    "name": {"type": "string", "description": "Skill name to migrate"},
                    "current_owner": {
                        "type": "string",
                        "description": "Current owner: 'household' or a person's name",
                    },
                    "to_scope": {
                        "type": "string",
                        "enum": ["household", "private"],
                        "description": "Target scope",
                    },
                    "to_person": {
                        "type": "string",
                        "description": "Required when to_scope is 'private' — which person to move the skill to",
                    },
                },
                "required": ["person", "name", "current_owner", "to_scope"],
            },
        ),
        skill_migrate,
    )

    # --- Skill approval tools ---

    async def skill_pending_list(*, person: str, **_: Any) -> dict[str, Any]:
        from homeclaw.plugins.skills.loader import skill_md_to_definition

        pending = _pending_dir()
        if not pending.is_dir():
            return {"pending": [], "count": 0}

        skills: list[dict[str, Any]] = []
        for child in sorted(pending.iterdir()):
            if not child.is_dir() or child.name.startswith("."):
                continue
            skill_path = child / "SKILL.md"
            if not skill_path.is_file():
                continue
            try:
                defn = skill_md_to_definition(skill_path.read_text())
                skills.append({
                    "name": defn.name,
                    "description": defn.description,
                    "requested_by": defn.metadata.get("requested_by", "unknown"),
                    "requested_scope": defn.metadata.get("requested_scope", "household"),
                })
            except Exception:
                skills.append({"name": child.name, "error": "failed to parse"})
        return {"pending": skills, "count": len(skills)}

    registry.register(
        ToolDefinition(
            name="skill_pending_list",
            description=(
                "List skills waiting for admin approval. "
                "Only relevant when skill_approval_required is enabled."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "person": {"type": "string", "description": "Household member name"},
                },
                "required": ["person"],
            },
        ),
        skill_pending_list,
    )

    async def skill_approve(
        *, person: str, name: str, **_: Any,
    ) -> dict[str, Any]:
        import shutil

        from homeclaw.plugins.registry import PluginType
        from homeclaw.plugins.skills.loader import load_skill, skill_md_to_definition

        if not _is_admin(person):
            return {"error": "Only admins can approve skills"}

        pending_skill = _pending_dir() / safe_slug(name)
        if not pending_skill.is_dir():
            return {"error": f"No pending skill '{name}' found"}

        skill_path = pending_skill / "SKILL.md"
        if not skill_path.is_file():
            return {"error": f"Pending skill '{name}' has no SKILL.md"}

        defn = skill_md_to_definition(skill_path.read_text())
        owner = defn.metadata.get("requested_owner", "household")

        dest = workspaces / owner / "skills" / safe_slug(name)
        if dest.exists():
            return {"error": f"Skill '{name}' already exists under {owner}"}

        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(pending_skill), str(dest))

        # Hot-load
        loaded = False
        if plugin_registry is not None:
            try:
                plugin = load_skill(dest, owner, allow_local_network=_skill_allow_local())
                plugin_registry.register(plugin, PluginType.SKILL)
                loaded = True
            except Exception as exc:
                _logger.exception("skill_approve: failed to load '%s'", name)
                return {
                    "status": "approved",
                    "name": name,
                    "owner": owner,
                    "loaded": False,
                    "warning": f"Approved but failed to load: {exc}",
                }

        return {
            "status": "approved",
            "name": name,
            "owner": owner,
            "approved_by": person,
            "loaded": loaded,
        }

    registry.register(
        ToolDefinition(
            name="skill_approve",
            description=(
                "Approve a pending skill so it becomes active. Admin only."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "person": {"type": "string", "description": "Admin member name"},
                    "name": {"type": "string", "description": "Skill name to approve"},
                },
                "required": ["person", "name"],
            },
        ),
        skill_approve,
    )

    async def skill_reject(
        *, person: str, name: str, reason: str = "", **_: Any,
    ) -> dict[str, Any]:
        import shutil

        if not _is_admin(person):
            return {"error": "Only admins can reject skills"}

        pending_skill = _pending_dir() / safe_slug(name)
        if not pending_skill.is_dir():
            return {"error": f"No pending skill '{name}' found"}

        shutil.rmtree(pending_skill)

        return {
            "status": "rejected",
            "name": name,
            "rejected_by": person,
            "reason": reason or "No reason provided",
        }

    registry.register(
        ToolDefinition(
            name="skill_reject",
            description=(
                "Reject and delete a pending skill. Admin only."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "person": {"type": "string", "description": "Admin member name"},
                    "name": {"type": "string", "description": "Skill name to reject"},
                    "reason": {
                        "type": "string",
                        "description": "Reason for rejection (shown to requester)",
                    },
                },
                "required": ["person", "name"],
            },
        ),
        skill_reject,
    )

    # --- Skill installation from URL ---

    async def skill_install(
        *,
        person: str,
        url: str,
        scope: str = "household",
        **_: Any,
    ) -> dict[str, Any]:
        import httpx

        from homeclaw.plugins.registry import PluginType
        from homeclaw.plugins.skills.loader import load_skill, skill_md_to_definition

        from homeclaw.plugins.skills.github import raw_skill_md_url

        # Determine the SKILL.md download URL
        skill_md_url = raw_skill_md_url(url)
        if skill_md_url is None:
            if url.endswith("SKILL.md") or url.endswith("skill.md"):
                skill_md_url = url
            else:
                return {"error": "URL must point to a GitHub repo or a SKILL.md file"}

        # Fetch the SKILL.md
        try:
            transport = httpx.AsyncHTTPTransport(retries=2)
            async with httpx.AsyncClient(timeout=30, transport=transport) as client:
                resp = await client.get(skill_md_url)
                resp.raise_for_status()
                content = resp.text
        except httpx.HTTPStatusError as e:
            return {"error": f"Failed to fetch SKILL.md: HTTP {e.response.status_code}"}
        except httpx.RequestError as e:
            return {"error": f"Failed to fetch SKILL.md: {e}"}

        # Validate
        try:
            defn = skill_md_to_definition(content)
        except ValueError as e:
            return {"error": f"Invalid SKILL.md: {e}"}

        slug = safe_slug(defn.name)
        if not slug:
            return {"error": f"Invalid skill name in SKILL.md: '{defn.name}'"}

        # Check approval flow
        pending = _needs_approval(person)
        owner = "household" if scope == "household" else person
        if pending:
            skill_dir = _pending_dir() / slug
        else:
            skill_dir = workspaces / owner / "skills" / slug

        live_dir = workspaces / owner / "skills" / slug
        if live_dir.exists():
            return {"error": f"Skill '{slug}' already exists under {owner}"}

        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "SKILL.md").write_text(content)

        # Try to fetch additional files from the repo
        from homeclaw.plugins.skills.github import download_skill_repo
        fetched_extras = await download_skill_repo(url, skill_dir)

        if pending:
            return {
                "status": "pending_approval",
                "name": slug,
                "scope": scope,
                "requested_by": person,
                "fetched_files": ["SKILL.md", *fetched_extras],
            }

        # Hot-load
        loaded = False
        if plugin_registry is not None:
            try:
                plugin = load_skill(
                    skill_dir, owner, allow_local_network=_skill_allow_local(),
                )
                plugin_registry.register(plugin, PluginType.SKILL)
                loaded = True
            except Exception as e:
                _logger.exception("skill_install: failed to load '%s'", slug)
                return {
                    "status": "installed",
                    "name": slug,
                    "loaded": False,
                    "warning": f"Installed but failed to load: {e}",
                }

        from homeclaw.plugins.skills.deps import check_skill_deps
        deps = check_skill_deps(defn.metadata)

        result: dict[str, Any] = {
            "status": "installed",
            "name": slug,
            "scope": scope,
            "loaded": loaded,
            "fetched_files": ["SKILL.md", *fetched_extras],
        }
        if not deps["satisfied"]:
            warnings: list[str] = []
            for b in deps["missing_bins"]:
                warnings.append(f"Missing binary '{b['name']}': {b['hint']}")
            for e in deps["missing_env"]:
                warnings.append(f"Missing env var '{e}'")
            result["warnings"] = warnings
        return result

    registry.register(
        ToolDefinition(
            name="skill_install",
            description=(
                "Install a skill from a URL. Accepts a GitHub repo URL or a "
                "direct link to a SKILL.md file. The skill is downloaded, "
                "validated, and activated. Example: "
                "skill_install(url='https://github.com/user/my-skill')"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "person": {"type": "string", "description": "Household member name"},
                    "url": {
                        "type": "string",
                        "description": (
                            "URL to install from — GitHub repo URL or "
                            "direct link to a SKILL.md file"
                        ),
                    },
                    "scope": {
                        "type": "string",
                        "enum": ["household", "private"],
                        "description": "Who can use this skill (default: household)",
                    },
                },
                "required": ["person", "url"],
            },
        ),
        skill_install,
    )

    # --- Skill file editing ---

    async def skill_edit_file(
        *,
        person: str,
        name: str,
        file: str,
        content: str | None = None,
        find: str | None = None,
        replace: str | None = None,
        **_: Any,
    ) -> dict[str, Any]:
        """Read or edit a file within a skill directory.

        Three modes:
        - Read: omit content, find, replace — returns file contents
        - Write: provide content — overwrites the file
        - Find/replace: provide find + replace — does a targeted substitution
        """
        from homeclaw.plugins.skills.loader import discover_skills

        locations = discover_skills(workspaces, person)
        loc = next((sk for sk in locations if sk.name == name), None)
        if loc is None:
            return {"error": f"Skill '{name}' not found"}

        # Resolve and validate path
        path = (loc.skill_dir / file).resolve()
        if not path.is_relative_to(loc.skill_dir.resolve()):
            return {"error": f"Invalid file path: {file}"}

        # Read mode
        if content is None and find is None:
            if not path.is_file():
                return {"error": f"File not found: {file}"}
            text = path.read_text()
            return {"file": file, "content": text, "size": len(text)}

        # Find/replace mode
        if find is not None:
            if not path.is_file():
                return {"error": f"File not found: {file}"}
            text = path.read_text()
            if find not in text:
                return {"error": f"Text to find not found in {file}"}
            new_text = text.replace(find, replace or "")
            path.write_text(new_text)
            return {
                "file": file,
                "status": "edited",
                "replacements": text.count(find),
                "size": len(new_text),
            }

        # Write mode
        if content is not None:
            if err := _check_content_length(content):
                return err
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
            return {"file": file, "status": "written", "size": len(content)}

        return {"error": "Provide content (write), or find+replace (edit), or nothing (read)"}

    registry.register(
        ToolDefinition(
            name="skill_edit_file",
            description=(
                "Read or edit a file inside a skill. Three modes: "
                "(1) Read: just pass name + file to see contents. "
                "(2) Find/replace: pass find + replace to make a targeted edit "
                "without rewriting the whole file — best for adapting installed skills. "
                "(3) Write: pass content to overwrite the entire file. "
                "Use read_skill first to see available files."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "person": {"type": "string", "description": "Household member name"},
                    "name": {"type": "string", "description": "Skill name"},
                    "file": {
                        "type": "string",
                        "description": "File path relative to skill dir (e.g. 'SKILL.md', 'scripts/check.sh')",
                    },
                    "content": {
                        "type": "string",
                        "description": "Full file content (write mode — overwrites the file)",
                    },
                    "find": {
                        "type": "string",
                        "description": "Text to find (find/replace mode)",
                    },
                    "replace": {
                        "type": "string",
                        "description": "Replacement text (find/replace mode)",
                    },
                },
                "required": ["person", "name", "file"],
            },
        ),
        skill_edit_file,
    )

    # Track activated skills per session to avoid re-injecting
    _activated_skills: set[str] = set()

    async def read_skill(
        *,
        person: str,
        name: str,
        **_: Any,
    ) -> dict[str, Any]:
        from homeclaw.plugins.skills.loader import discover_skills, skill_md_to_definition

        locations = discover_skills(workspaces, person)
        loc = next((sk for sk in locations if sk.name == name), None)
        if loc is None:
            return {"error": f"Skill '{name}' not found"}

        skill_path = loc.skill_dir / "SKILL.md"
        if not skill_path.is_file():
            return {"error": f"No SKILL.md in '{name}'"}

        defn = skill_md_to_definition(skill_path.read_text())

        # List available resource directories
        resources: dict[str, list[str]] = {}
        for subdir in ("scripts", "references", "assets", "data"):
            dir_path = loc.skill_dir / subdir
            if dir_path.is_dir():
                files = sorted(f.name for f in dir_path.iterdir() if f.is_file())
                if files:
                    resources[subdir] = files

        _activated_skills.add(name)

        # List registered plugin tools for this skill (e.g. weather__http_call)
        available_tools: list[str] = []
        if plugin_registry is not None:
            entry = plugin_registry.get_entry(name)
            if entry is not None:
                available_tools = list(entry.tool_names)

        return {
            "name": defn.name,
            "description": defn.description,
            "instructions": defn.instructions,
            "skill_dir": str(loc.skill_dir),
            "scope": loc.scope,
            "resources": resources,
            "tools": available_tools,
            "already_loaded": name in _activated_skills,
        }

    registry.register(
        ToolDefinition(
            name="read_skill",
            description=(
                "Load a skill's full instructions and see its available resources. "
                "Call this before using a skill's tools (data_read, data_write, "
                "http_call, run_skill_script). The skill catalog in your context "
                "lists available skills."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "person": {"type": "string", "description": "Household member name"},
                    "name": {
                        "type": "string",
                        "description": "Skill name (as shown in the skill catalog)",
                    },
                },
                "required": ["person", "name"],
            },
        ),
        read_skill,
    )

    async def run_skill_script(
        *,
        person: str,
        name: str,
        script: str,
        args: list[str] | None = None,
        **_: Any,
    ) -> dict[str, Any]:
        import asyncio

        from homeclaw.plugins.skills.loader import discover_skills

        locations = discover_skills(workspaces, person)
        loc = next((sk for sk in locations if sk.name == name), None)
        if loc is None:
            return {"error": f"Skill '{name}' not found"}

        scripts_dir = loc.skill_dir / "scripts"
        if not scripts_dir.is_dir():
            return {"error": f"Skill '{name}' has no scripts/ directory"}

        # Resolve and validate path (prevent traversal)
        script_path = (scripts_dir / script).resolve()
        if not script_path.is_relative_to(scripts_dir.resolve()):
            return {"error": f"Invalid script path: {script}"}
        if not script_path.is_file():
            return {"error": f"Script not found: {script}"}

        cmd = [str(script_path)] + (args or [])
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(loc.skill_dir),
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
            return {
                "exit_code": proc.returncode,
                "stdout": stdout.decode(errors="replace")[:50_000],
                "stderr": stderr.decode(errors="replace")[:10_000],
            }
        except TimeoutError:
            proc.kill()  # type: ignore[union-attr]
            return {"error": "Script timed out after 30 seconds"}
        except Exception as exc:
            return {"error": f"Failed to run script: {exc}"}

    registry.register(
        ToolDefinition(
            name="run_skill_script",
            description=(
                "Run a script bundled with a skill. Scripts live in the skill's "
                "scripts/ directory and are listed when you read_skill. Only "
                "pre-installed scripts can be run — no arbitrary shell commands."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "person": {"type": "string", "description": "Household member name"},
                    "name": {
                        "type": "string",
                        "description": "Skill name",
                    },
                    "script": {
                        "type": "string",
                        "description": "Script filename (relative to scripts/)",
                    },
                    "args": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Arguments to pass to the script",
                    },
                },
                "required": ["person", "name", "script"],
            },
        ),
        run_skill_script,
    )

    # --- Decision tools ---

    def _decisions_path(scope: str, person: str = "") -> Path:
        owner = "household" if scope == "household" else safe_slug(person)
        return workspaces / owner / "decisions.md"

    async def decision_log(
        *, person: str, decision: str, scope: str = "household", **_: Any
    ) -> dict[str, Any]:
        if err := _check_content_length(decision, "decision"):
            return err
        if scope not in ("household", "personal"):
            return {"error": f"Invalid scope '{scope}' — must be 'household' or 'personal'"}
        path = _decisions_path(scope, person)
        path.parent.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
        entry = f"- [{timestamp}] {decision} — {person}"
        if not path.exists():
            path.write_text(f"# Decisions\n\n{entry}\n")
        else:
            with path.open("a") as f:
                f.write(f"{entry}\n")
        return {"status": "logged", "scope": scope, "decision": decision}

    registry.register(
        ToolDefinition(
            name="decision_log",
            description=(
                "Record a settled household or personal decision so it is not "
                "re-litigated. Use this when someone says 'we decided', 'let's go with', "
                "'from now on', or otherwise settles on a choice. Examples: 'Piano lessons "
                "on Tuesdays', 'Switching to oat milk', 'No screens after 8pm'."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "person": {"type": "string", "description": "Who made or reported this decision"},
                    "decision": {"type": "string", "description": "The decision that was made"},
                    "scope": {
                        "type": "string",
                        "enum": ["household", "personal"],
                        "description": "Whether this applies to the whole household or just this person (default: household)",
                    },
                },
                "required": ["person", "decision"],
            },
        ),
        decision_log,
    )

    async def decision_list(
        *, scope: str = "household", person: str = "", **_: Any
    ) -> dict[str, Any]:
        if scope not in ("household", "personal"):
            return {"error": f"Invalid scope '{scope}' — must be 'household' or 'personal'"}
        path = _decisions_path(scope, person)
        if not path.exists():
            return {"decisions": [], "scope": scope}
        lines = [
            ln.strip() for ln in path.read_text().splitlines()
            if ln.strip().startswith("- [")
        ]
        return {"decisions": lines, "scope": scope, "count": len(lines)}

    registry.register(
        ToolDefinition(
            name="decision_list",
            description="List recorded decisions for the household or a person.",
            parameters={
                "type": "object",
                "properties": {
                    "scope": {
                        "type": "string",
                        "enum": ["household", "personal"],
                        "description": "Which decisions to list (default: household)",
                    },
                    "person": {
                        "type": "string",
                        "description": "Person name (required for personal scope)",
                    },
                },
            },
        ),
        decision_list,
    )

    # --- Settings tools ---

    if config is not None:

        async def settings_get(**_: Any) -> dict[str, Any]:
            from homeclaw.memory.status import get_semantic_status

            return {
                "semantic_status": get_semantic_status(workspaces),
            }

        registry.register(
            ToolDefinition(
                name="settings_get",
                description="Check current homeclaw settings and semantic memory status.",
                parameters={"type": "object", "properties": {}},
            ),
            settings_get,
        )
