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
            async with httpx.AsyncClient(timeout=30) as client:
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
            async with httpx.AsyncClient(timeout=30) as client:
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
