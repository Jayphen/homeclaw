"""Tool registry, built-in tool definitions, and handlers."""

from collections.abc import Callable, Coroutine
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from homeclaw.agent.providers.base import ToolDefinition
from homeclaw.bookmarks.models import Bookmark
from homeclaw.bookmarks.store import (
    delete_bookmark,
    get_categories,
    list_bookmarks,
    save_bookmark,
    search_bookmarks,
)
from homeclaw.contacts.models import Contact, Interaction, InteractionType
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
    config: Any = None,
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
        facts: list[str] | None = None,
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
        if facts is not None:
            # Append new facts, deduplicating against existing ones
            existing = {f.lower() for f in contact.facts}
            for f in facts:
                if f.lower() not in existing:
                    contact.facts.append(f)
                    existing.add(f.lower())
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
                    "facts": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "New facts to add (appended to existing, not replaced)",
                    },
                },
                "required": ["id"],
            },
        ),
        contact_update,
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
        contact.last_contact = interaction.date
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

    async def household_share(*, fact: str, **_: Any) -> dict[str, Any]:
        """Share a fact with the entire household."""
        memory = load_memory(workspaces, "household")
        memory.facts.append(fact)
        save_memory(workspaces, "household", memory)
        return {"status": "shared", "fact": fact}

    registry.register(
        ToolDefinition(
            name="household_share",
            description=(
                "Share a fact with the entire household. Use this when a member "
                "explicitly asks to share something with everyone. The fact will "
                "be visible to all members in both private and group chats."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "fact": {
                        "type": "string",
                        "description": "The fact to share with the household",
                    },
                },
                "required": ["fact"],
            },
        ),
        household_share,
    )

    # --- Note tools ---

    async def note_save(*, person: str, content: str, **_: Any) -> dict[str, Any]:
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

    from homeclaw.reminders.store import add_reminder as _add_reminder
    from homeclaw.reminders.store import complete_reminder as _complete_reminder
    from homeclaw.reminders.store import delete_reminder as _delete_reminder
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
            parts = date.split("-")
            due_date = date_type(int(parts[0]), int(parts[1]), int(parts[2]))

        reminder = Reminder(
            id=uuid4().hex[:8],
            person=person,
            note=note,
            due_date=due_date,
            interval_days=interval_days,
            created_at=datetime.now(datetime.now().astimezone().tzinfo),
        )
        _add_reminder(workspaces, reminder)
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
        result = _complete_reminder(workspaces, person, reminder_id)
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
        if _delete_reminder(workspaces, person, reminder_id):
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
        notes: str = "",
        neighborhood: str = "",
        city: str = "",
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
            notes=notes,
            saved_by=person,
            saved_at=datetime.now(timezone.utc),
            neighborhood=neighborhood,
            city=city,
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
                    "notes": {"type": "string", "description": "Extra context or description"},
                    "neighborhood": {"type": "string", "description": "Neighborhood or area"},
                    "city": {"type": "string", "description": "City"},
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

    # --- Web tools (via Jina) ---

    import os

    jina_api_key = os.environ.get("JINA_API_KEY")

    def _jina_headers(accept: str = "text/markdown") -> dict[str, str]:
        headers = {"Accept": accept}
        if jina_api_key:
            headers["Authorization"] = f"Bearer {jina_api_key}"
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
                "Use this when someone shares a URL or you need to look up "
                "information from a specific page."
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

        if not jina_api_key:
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
                "Search the web and return results. Use this when someone asks "
                "a question that needs current information, wants to research "
                "something, or needs to find a specific resource online."
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
                "Schedule must be natural language like 'Every weekday at 7:30am', "
                "'Every Sunday at 10:00am', or 'Every 3 days'."
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
                            "When to run. Examples: 'Every weekday at 7:30am', "
                            "'Every Sunday at 10:00am', 'Every 3 days', 'Every Monday at 9:00am'"
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

    # --- Settings tools ---

    if config is not None:

        async def settings_get(**_: Any) -> dict[str, Any]:
            memsearch_installed = False
            try:
                import memsearch  # type: ignore[import-not-found]  # noqa: F401

                memsearch_installed = True
            except ImportError:
                pass
            return {
                "enhanced_memory": config.enhanced_memory,
                "memsearch_installed": memsearch_installed,
                "semantic_ready": config.enhanced_memory and memsearch_installed,
            }

        registry.register(
            ToolDefinition(
                name="settings_get",
                description=(
                    "Check current homeclaw settings, including whether "
                    "semantic memory is enabled."
                ),
                parameters={"type": "object", "properties": {}},
            ),
            settings_get,
        )

        async def settings_update(
            *, enhanced_memory: bool | None = None, **_: Any,
        ) -> dict[str, Any]:
            if enhanced_memory is not None:
                config.enhanced_memory = enhanced_memory
            memsearch_installed = False
            try:
                import memsearch  # type: ignore[import-not-found]  # noqa: F401

                memsearch_installed = True
            except ImportError:
                pass
            status = "enabled" if config.enhanced_memory else "disabled"
            if config.enhanced_memory and not memsearch_installed:
                return {
                    "status": status,
                    "enhanced_memory": config.enhanced_memory,
                    "memsearch_installed": False,
                    "note": (
                        "Enhanced memory is toggled on but the memsearch package is not installed. "
                        "Install it with: pip install homeclaw[semantic]"
                    ),
                }
            return {
                "status": status,
                "enhanced_memory": config.enhanced_memory,
                "memsearch_installed": memsearch_installed,
                "semantic_ready": config.enhanced_memory and memsearch_installed,
            }

        registry.register(
            ToolDefinition(
                name="settings_update",
                description=(
                    "Update homeclaw settings. Currently supports toggling enhanced "
                    "(semantic) memory on or off. Use when a user asks to enable or "
                    "disable semantic memory / enhanced recall."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "enhanced_memory": {
                            "type": "boolean",
                            "description": "Enable or disable semantic memory",
                        },
                    },
                },
            ),
            settings_update,
        )
