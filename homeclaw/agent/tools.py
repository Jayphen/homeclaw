"""Tool registry, built-in tool definitions, and handlers."""

import logging
from collections.abc import Callable, Coroutine
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated, Any, Literal

from homeclaw import HOUSEHOLD_WORKSPACE
from homeclaw.agent.providers.base import ToolDefinition
from homeclaw.agent.tool_decorator import Desc
from homeclaw.agent.tool_decorator import tool as _tool
from homeclaw.bookmarks.models import Bookmark
from homeclaw.bookmarks.store import (
    delete_bookmark_safe,
    get_categories,
    list_bookmarks,
    save_bookmark_safe,
    search_bookmarks,
    update_bookmark_safe,
)
from homeclaw.contacts.models import Contact, Interaction, InteractionType
from homeclaw.contacts.store import (
    get_contact,
    list_contacts,
    save_contact_safe,
)
from homeclaw.memory.markdown import memory_list_topics, memory_read_topic, memory_save_topic
from homeclaw.pathutil import safe_date, safe_slug

_logger = logging.getLogger(__name__)

# Maximum size for user-supplied content written to disk (100 KB).
MAX_CONTENT_LENGTH = 100_000

# Scope vocabularies — skill tools use "private", decision tools use "personal".
SkillScope = Literal["household", "private"]
DecisionScope = Literal["household", "personal"]

ToolHandler = Callable[..., Coroutine[Any, Any, dict[str, Any]]]


def _check_content_length(content: str, field: str = "content") -> dict[str, Any] | None:
    """Return an error dict if content exceeds MAX_CONTENT_LENGTH, else None."""
    if len(content) > MAX_CONTENT_LENGTH:
        return {"error": f"{field} too large ({len(content)} chars, max {MAX_CONTENT_LENGTH})"}
    return None


# Module-level set of activated skills — shared between read_skill and
# auto-activation in the agent loop.  Persists for the process lifetime.
activated_skills: set[str] = set()


def load_skill_instructions(workspaces: Path, person: str, skill_name: str) -> str | None:
    """Load a skill's SKILL.md instructions.  Returns None if not found."""
    from homeclaw.plugins.skills.loader import discover_skills, skill_md_to_definition

    locations = discover_skills(workspaces, person)
    loc = next((sk for sk in locations if sk.name == skill_name), None)
    if loc is None:
        return None
    skill_path = loc.skill_dir / "SKILL.md"
    if not skill_path.is_file():
        return None
    defn = skill_md_to_definition(skill_path.read_text())
    activated_skills.add(skill_name)
    return defn.instructions


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

    def _reg(name: str, description: str, **kwargs: Any) -> Callable[[ToolHandler], ToolHandler]:
        """Decorator: auto-generate schema from type hints and register the tool."""
        t = _tool(name, description, **kwargs)

        def wrapper(func: ToolHandler) -> ToolHandler:
            t(func)
            t.register(registry)
            return func

        return wrapper

    # --- Contact tools ---

    @_reg(name="contact_list", description="List all contacts in the household's contact book.")
    async def contact_list(**_: Any) -> dict[str, Any]:
        contacts = list_contacts(workspaces)
        return {
            "contacts": [
                {"id": c.id, "name": c.name, "relationship": c.relationship,
                 "nicknames": c.nicknames}
                for c in contacts
            ]
        }

    @_reg(name="contact_get", description="Get full details for a contact by ID.")
    async def contact_get(
        *,
        id: Annotated[str, Desc("Contact ID")],
        **_: Any,
    ) -> dict[str, Any]:
        contact = get_contact(workspaces, id)
        if not contact:
            return {"error": f"Contact '{id}' not found"}
        return contact.model_dump(mode="json")

    @_reg(name="contact_update", description="Create or update a contact. Provide fields to change.")
    async def contact_update(
        *,
        id: Annotated[str, Desc("Contact ID")],
        name: Annotated[str | None, Desc("Contact name")] = None,
        nicknames: Annotated[list[str] | None, Desc("Nicknames or shortened names for this person")] = None,
        relationship: Annotated[str | None, Desc("Relationship (e.g. 'wife', 'mother', 'friend', 'pet')")] = None,
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
        await save_contact_safe(workspaces, contact)
        return {"status": "updated", "id": id}

    @_reg(
        name="contact_note",
        description=(
            "Add a note about a contact — a fact, observation, preference, or "
            "anything worth remembering about this person. Notes are searchable "
            "via semantic memory. Use this instead of storing facts on the contact. "
            "Set person to save as a private note visible only to that member, "
            "or omit for a shared household note."
        ),
    )
    async def contact_note(
        *,
        contact_id: Annotated[str, Desc("Contact ID")],
        content: Annotated[str, Desc("The note to add about this contact")],
        person: Annotated[str | None, Desc("Member name for a private note, or omit for shared")] = None,
        **_: Any,
    ) -> dict[str, Any]:
        if err := _check_content_length(content):
            return err
        contact = get_contact(workspaces, contact_id)
        if contact is None:
            return {"error": f"Contact '{contact_id}' not found"}

        base = workspaces / person if person and person != HOUSEHOLD_WORKSPACE else workspaces / HOUSEHOLD_WORKSPACE
        notes_dir = base / "contacts" / "notes"
        notes_dir.mkdir(parents=True, exist_ok=True)
        safe_id = safe_slug(contact.id)
        path = notes_dir / f"{safe_id}.md"
        timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M")

        if not path.exists():
            path.write_text(f"# {contact.name}\n\n- [{timestamp}] {content}\n")
        else:
            with path.open("a") as f:
                f.write(f"- [{timestamp}] {content}\n")

        scope = f"private ({person})" if person else "household"
        return {"status": "saved", "contact_id": contact.id, "name": contact.name, "scope": scope}

    @_reg(
        name="interaction_log",
        description="Log an interaction with a contact (call, message, meetup).",
    )
    async def interaction_log(
        *,
        contact_id: Annotated[str, Desc("Contact ID")],
        type: Annotated[InteractionType, Desc("Interaction type")],
        notes: Annotated[str, Desc("What happened")],
        **_: Any,
    ) -> dict[str, Any]:
        contact = get_contact(workspaces, contact_id)
        if not contact:
            return {"error": f"Contact '{contact_id}' not found"}
        interaction = Interaction(
            date=datetime.now(UTC), type=type, notes=notes
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
        await save_contact_safe(workspaces, contact)
        return {"status": "logged", "contact": contact_id}

    # --- Memory tools ---

    @_reg(
        name="memory_save",
        description=(
            "Save a piece of knowledge. Appends to a topic file — never "
            "overwrites. Pick a short topic name (e.g. 'food', 'health', "
            "'routines', 'work'). Set person to a member's name for personal "
            "facts, or 'household' for shared info like house codes, wifi "
            "passwords, shared rules, or anything that applies to the whole home."
        ),
    )
    async def memory_save(
        *,
        person: Annotated[str, Desc("Member name, or 'household' for shared info")],
        topic: Annotated[str, Desc("Topic name (e.g. 'food', 'health', 'family')")],
        content: Annotated[str, Desc("The fact or knowledge to remember")],
        **_: Any,
    ) -> dict[str, Any]:
        if err := _check_content_length(content):
            return err
        path = memory_save_topic(workspaces, person, topic, content)
        return {"status": "saved", "topic": topic, "path": str(path)}

    @_reg(
        name="memory_read",
        description=(
            "Read stored knowledge about a household member. "
            "Call without topic to list all topics, or with a topic to read it."
        ),
    )
    async def memory_read(
        *,
        person: Annotated[str, Desc("Household member name")],
        topic: Annotated[str | None, Desc("Topic to read (omit to list all topics)")] = None,
        **_: Any,
    ) -> dict[str, Any]:
        if topic:
            text = memory_read_topic(workspaces, person, topic)
            if text is None:
                return {"person": person, "topic": topic, "content": None}
            return {"person": person, "topic": topic, "content": text}
        topics = memory_list_topics(workspaces, person)
        return {"person": person, "topics": topics}

    # --- Note tools ---

    @_reg(
        name="note_save",
        description=(
            "Save a journal entry to a household member's daily notes. "
            "Can be short (a quick observation) or long (detailed notes from "
            "a conversation or research session). Each call adds one timestamped "
            "entry — do NOT include previous entries, only the new content."
        ),
    )
    async def note_save(
        *,
        person: Annotated[str, Desc("Household member name")],
        content: Annotated[str, Desc("The note content — can be a sentence or multiple paragraphs")],
        **_: Any,
    ) -> dict[str, Any]:
        if err := _check_content_length(content):
            return err
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        time_str = datetime.now(UTC).strftime("%H:%M")
        notes_dir = workspaces / person / "notes"
        notes_dir.mkdir(parents=True, exist_ok=True)
        path = notes_dir / f"{today}.md"
        # Support multi-line content: first line gets the timestamp bullet,
        # continuation lines are indented under it.
        lines = content.split("\n")
        entry_parts = [f"- [{time_str}] {lines[0]}"]
        for line in lines[1:]:
            entry_parts.append(f"  {line}" if line.strip() else "  ")
        entry = "\n".join(entry_parts)
        if path.exists():
            existing = path.read_text().rstrip("\n")
            path.write_text(f"{existing}\n{entry}\n")
        else:
            path.write_text(f"{entry}\n")
        return {"status": "saved", "path": str(path)}

    @_reg(name="note_get", description="Read a note for a household member. Defaults to today.")
    async def note_get(
        *,
        person: Annotated[str, Desc("Household member name")],
        date: Annotated[str | None, Desc("Date in YYYY-MM-DD format (defaults to today)")] = None,
        **_: Any,
    ) -> dict[str, Any]:
        if date is None:
            date = datetime.now(UTC).strftime("%Y-%m-%d")
        try:
            date = safe_date(date)
        except ValueError:
            return {"error": f"Invalid date format: {date}"}
        path = workspaces / person / "notes" / f"{date}.md"
        if not path.exists():
            return {"content": "", "date": date}
        return {"content": path.read_text(), "date": date}

    # --- Reminder tools ---

    from homeclaw.reminders.store import add_reminder_safe as _add_reminder
    from homeclaw.reminders.store import complete_reminder_safe as _complete_reminder
    from homeclaw.reminders.store import delete_reminder_safe as _delete_reminder
    from homeclaw.reminders.store import load_reminders as _load_reminders

    @_reg(
        name="reminder_add",
        description=(
            "Set a reminder for a household member. Supports one-shot "
            "(provide date) or recurring (provide interval_days, e.g. 7 for "
            "weekly). Can provide both date + interval for 'starting on X, "
            "repeat every N days'."
        ),
    )
    async def reminder_add(
        *,
        person: Annotated[str, Desc("Household member name")],
        note: Annotated[str, Desc("Reminder text")],
        date: Annotated[str | None, Desc("Due date in YYYY-MM-DD (for one-shot or start date)")] = None,
        interval_days: Annotated[int | None, Desc("Repeat every N days (e.g. 7 for weekly, 14 for biweekly)")] = None,
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

    @_reg(name="reminder_list", description="List active reminders for a household member.")
    async def reminder_list(
        *,
        person: Annotated[str, Desc("Household member name")],
        **_: Any,
    ) -> dict[str, Any]:
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

    @_reg(
        name="reminder_complete",
        description=(
            "Mark a reminder as done. For recurring reminders, this advances "
            "to the next occurrence. For one-shot reminders, marks it complete."
        ),
    )
    async def reminder_complete(
        *,
        person: Annotated[str, Desc("Household member name")],
        reminder_id: Annotated[str, Desc("Reminder ID")],
        **_: Any,
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

    @_reg(name="reminder_delete", description="Permanently delete a reminder.")
    async def reminder_delete(
        *,
        person: Annotated[str, Desc("Household member name")],
        reminder_id: Annotated[str, Desc("Reminder ID")],
        **_: Any,
    ) -> dict[str, Any]:
        if await _delete_reminder(workspaces, person, reminder_id):
            return {"status": "deleted", "id": reminder_id}
        return {"error": f"Reminder '{reminder_id}' not found"}

    # --- Bookmark tools ---

    @_reg(
        name="bookmark_save",
        description=(
            "Save a link or recommendation (restaurant, bar, cafe, recipe, etc.) "
            "to the household's shared bookmarks. Use this when someone shares a "
            "link or mentions a place/recipe they want to remember."
        ),
    )
    async def bookmark_save(
        *,
        title: Annotated[str, Desc("Name of the place or recipe")],
        category: Annotated[str, Desc("Category (e.g. 'place', 'recipe', 'book', 'article')")] = "other",
        url: Annotated[str | None, Desc("URL if one was shared")] = None,
        tags: Annotated[list[str] | str | None, Desc("Tags (e.g. 'italian', 'rooftop', 'brunch', 'vegan')")] = None,
        person: Annotated[str, Desc("Who saved this")] = "",
        **_: Any,
    ) -> dict[str, Any]:
        from uuid import uuid4

        # Coerce comma-separated string to list (Gemini sends strings)
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",") if t.strip()]

        bookmark = Bookmark(
            id=uuid4().hex[:8],
            url=url,
            title=title,
            category=category,
            tags=tags or [],
            saved_by=person,
            saved_at=datetime.now(UTC),
        )
        saved = await save_bookmark_safe(workspaces, bookmark)
        return {"status": "saved", "id": saved.id, "title": saved.title}

    @_reg(
        name="bookmark_list",
        description="List saved bookmarks, optionally filtered by category or tag.",
    )
    async def bookmark_list(
        *,
        category: Annotated[str | None, Desc("Filter by category (e.g. 'place', 'recipe', 'book')")] = None,
        tag: Annotated[str | None, Desc("Filter by tag")] = None,
        **_: Any,
    ) -> dict[str, Any]:
        results = list_bookmarks(workspaces, category=category, tag=tag)
        return {
            "bookmarks": [b.model_dump(mode="json") for b in results],
            "count": len(results),
        }

    @_reg(
        name="bookmark_search",
        description=(
            "Search the household's saved bookmarks by keyword. Use this when someone "
            "asks for recommendations, wants to find a saved place or recipe, or is "
            "planning an outing or meal."
        ),
    )
    async def bookmark_search(
        *,
        query: Annotated[str, Desc("Search query (name, tag, neighborhood, cuisine, etc.)")],
        **_: Any,
    ) -> dict[str, Any]:
        results = search_bookmarks(workspaces, query)
        return {
            "bookmarks": [b.model_dump(mode="json") for b in results],
            "count": len(results),
        }

    @_reg(name="bookmark_delete", description="Delete a saved bookmark by ID.")
    async def bookmark_delete(
        *,
        id: Annotated[str, Desc("Bookmark ID")],
        **_: Any,
    ) -> dict[str, Any]:
        if await delete_bookmark_safe(workspaces, id):
            return {"status": "deleted", "id": id}
        return {"error": f"Bookmark '{id}' not found"}

    @_reg(
        name="bookmark_update",
        description=(
            "Update an existing bookmark. Use this to add or change the URL, title, "
            "category, or tags on a saved bookmark. Only provide the fields to change."
        ),
    )
    async def bookmark_update(
        *,
        id: Annotated[str, Desc("Bookmark ID")],
        url: Annotated[str | None, Desc("New URL")] = None,
        title: Annotated[str | None, Desc("New title")] = None,
        category: Annotated[str | None, Desc("New category")] = None,
        tags: Annotated[list[str] | None, Desc("New tags (replaces existing tags)")] = None,
        **_: Any,
    ) -> dict[str, Any]:
        result = await update_bookmark_safe(workspaces, id, url=url, title=title, category=category, tags=tags)
        if result is None:
            return {"error": f"Bookmark '{id}' not found"}
        return {"status": "updated", "id": result.id, "title": result.title, "url": result.url}

    @_reg(name="bookmark_categories", description="List all bookmark categories currently in use.")
    async def bookmark_categories(**_: Any) -> dict[str, Any]:
        return {"categories": get_categories(workspaces)}

    @_reg(
        name="bookmark_note",
        description=(
            "Add a note to a saved bookmark — a review, tip, experience, or "
            "any context that helps recall it later. Notes are searchable via "
            "semantic memory."
        ),
    )
    async def bookmark_note(
        *,
        bookmark_id: Annotated[str, Desc("ID of the bookmark to annotate")],
        content: Annotated[str, Desc("The note to add (review, tip, experience)")],
        **_: Any,
    ) -> dict[str, Any]:
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
        timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M")

        if not path.exists():
            path.write_text(f"# {bookmark.title}\n\n- [{timestamp}] {content}\n")
        else:
            with path.open("a") as f:
                f.write(f"- [{timestamp}] {content}\n")

        return {"status": "saved", "bookmark_id": bookmark_id, "title": bookmark.title}

    @_reg(
        name="bookmark_note_edit",
        description=(
            "Edit an existing note on a bookmark. Use this to correct or update "
            "a previous note rather than appending a new one."
        ),
    )
    async def bookmark_note_edit(
        *,
        bookmark_id: Annotated[str, Desc("ID of the bookmark whose note to edit")],
        note_index: Annotated[int, Desc("1-based index of the note to edit (in chronological order)")],
        content: Annotated[str, Desc("New content to replace the existing note")],
        **_: Any,
    ) -> dict[str, Any]:
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

    @_reg(
        name="bookmark_note_delete",
        description=(
            "Delete a note from a bookmark by its 1-based index. Use this to "
            "remove incorrect, duplicate, or unwanted notes."
        ),
    )
    async def bookmark_note_delete(
        *,
        bookmark_id: Annotated[str, Desc("ID of the bookmark whose note to delete")],
        note_index: Annotated[int, Desc("1-based index of the note to delete (in chronological order)")],
        **_: Any,
    ) -> dict[str, Any]:
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

    # --- Web tools ---

    _WEB_READ_MAX_CHARS = 12_000

    def _content_looks_bad(content: str) -> bool:
        """Heuristic: content is mostly navigation/image chrome, not real text."""
        if len(content) < 200:
            return True
        lines = content.splitlines()
        if not lines:
            return True
        link_or_image_lines = sum(
            1 for line in lines if line.strip().startswith(("[![", "[!", "![", "* [", "*   ["))
        )
        return link_or_image_lines > len(lines) * 0.6

    @_reg(
        name="web_read",
        description=(
            "Fetch a web page and return its content as clean markdown. "
            "Use this when someone shares a URL, you need to look up "
            "information from a specific page, or you want to read an "
            "article, news story, or any web content. Always prefer this "
            "over guessing at page contents."
        ),
    )
    async def web_read(
        *,
        url: Annotated[str, Desc("The URL to fetch")],
        **_: Any,
    ) -> dict[str, Any]:
        from homeclaw.web import web_providers

        primary = config.web_read_provider if config else "jina"
        fallback = config.web_read_fallback if config else None

        result = await web_providers.read(
            url, primary, fallback, content_looks_bad=_content_looks_bad,
        )

        if "error" in result:
            return result

        content = result.get("content", "")
        if len(content) > _WEB_READ_MAX_CHARS:
            content = content[:_WEB_READ_MAX_CHARS] + "\n\n[… truncated]"
        return {"url": url, "content": content}

    @_reg(
        name="web_search",
        description=(
            "Search the web and return result snippets (title, URL, "
            "description). You MUST use this for any question requiring "
            "current information — news, weather, events, prices, scores, "
            "headlines, recent developments. Never guess or hedge about "
            "current events; search first. Results are SHORT SNIPPETS "
            "only — if you need actual page content (live scores, full "
            "articles, detailed data), follow up with web_read on the "
            "most relevant result URL."
        ),
    )
    async def web_search(
        *,
        query: Annotated[str, Desc("The search query")],
        **_: Any,
    ) -> dict[str, Any]:
        from homeclaw.web import web_providers

        primary = config.web_search_provider if config else "jina"
        fallback = config.web_search_fallback if config else None

        result = await web_providers.search(query, primary, fallback)

        # Truncate raw-text results (non-structured fallback from some providers)
        raw = result.get("results")
        if isinstance(raw, str) and len(raw) > _WEB_READ_MAX_CHARS:
            result["results"] = raw[:_WEB_READ_MAX_CHARS] + "\n\n[… truncated]"

        return result

    # --- Message tool — delivers via channel dispatcher ---

    @_reg(
        name="message_send",
        description=(
            "Send a message to a household member or the household group chat. "
            "Set 'person' to message an individual, or 'group' to true to "
            "send to the household group chat."
        ),
    )
    async def message_send(
        *,
        text: Annotated[str, Desc("Message text")],
        person: Annotated[str | None, Desc("Recipient name (for individual messages)")] = None,
        group: Annotated[bool, Desc("Send to the household group chat instead")] = False,
        **_: Any,
    ) -> dict[str, Any]:
        if dispatcher is None:
            return {"status": "queued", "person": person, "text": text}
        if group:
            return await dispatcher.send_group("", text)
        if not person:
            return {"error": "Either 'person' or 'group: true' is required."}
        return await dispatcher.send(person, text)

    @_reg(
        name="image_send",
        description=(
            "Send an image to a household member or the household group chat. "
            "Provide a URL and optional headers — the tool fetches the image "
            "server-side, so you do NOT need to download it yourself first. "
            "For authenticated APIs (e.g. Immich), pass the auth header "
            "directly (e.g. headers={\"x-api-key\": \"...\"}). "
            "Use file_path for images on disk, or base64 for inline data "
            "(raw base64 or data:image/...;base64,... URI). "
            "Max image size: 10 MB."
        ),
    )
    async def image_send(
        *,
        url: Annotated[str | None, Desc("Image URL (use headers if auth is needed)")] = None,
        file_path: Annotated[str | None, Desc("Local file path to an image on disk")] = None,
        base64: Annotated[
            str | None,
            Desc("Base64-encoded image data (raw or data:image/...;base64,... URI)"),
        ] = None,
        headers: Annotated[
            dict[str, str] | None,
            Desc("HTTP headers to send when fetching the URL (e.g. x-api-key)"),
        ] = None,
        person: Annotated[str | None, Desc("Recipient name (for individual messages)")] = None,
        group: Annotated[bool, Desc("Send to the household group chat instead")] = False,
        caption: Annotated[str | None, Desc("Optional caption for the image")] = None,
        **_: Any,
    ) -> dict[str, Any]:
        import base64 as b64mod
        from pathlib import Path as _Path

        import httpx

        _MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 10 MB
        _ALLOWED_CONTENT_TYPES = frozenset({
            "image/jpeg", "image/png", "image/gif", "image/webp",
            "image/svg+xml", "image/bmp", "image/tiff",
        })
        _ALLOWED_EXTENSIONS = frozenset({
            ".jpg", ".jpeg", ".png", ".gif", ".webp",
            ".svg", ".bmp", ".tiff", ".tif",
        })

        sources = sum(1 for s in (url, file_path, base64) if s)
        if sources == 0:
            return {"error": "One of 'url', 'file_path', or 'base64' is required."}
        if sources > 1:
            return {"error": "Provide only one of 'url', 'file_path', or 'base64'."}

        image_data: bytes | None = None

        if base64 is not None:
            # Strip data URI prefix if present
            raw = base64
            if raw.startswith("data:"):
                # data:image/png;base64,iVBOR...
                parts = raw.split(",", 1)
                if len(parts) != 2:
                    return {"error": "Invalid data URI format."}
                header_part = parts[0]
                if "image/" not in header_part:
                    return {"error": f"Data URI is not an image type: {header_part}"}
                raw = parts[1]
            try:
                image_data = b64mod.b64decode(raw, validate=True)
            except Exception:
                return {"error": "Invalid base64 data."}
            if len(image_data) > _MAX_IMAGE_BYTES:
                mb = len(image_data) / (1024 * 1024)
                return {"error": f"Image too large ({mb:.1f} MB). Max is 10 MB."}

        elif file_path is not None:
            p = _Path(file_path)
            if not p.is_file():
                return {"error": f"File not found: {file_path}"}
            if p.suffix.lower() not in _ALLOWED_EXTENSIONS:
                return {"error": f"Unsupported image type: {p.suffix}"}
            size = p.stat().st_size
            if size > _MAX_IMAGE_BYTES:
                mb = size / (1024 * 1024)
                return {"error": f"Image too large ({mb:.1f} MB). Max is 10 MB."}
            image_data = p.read_bytes()

        elif url is not None:
            # Validate and stream-download with size cap
            try:
                async with httpx.AsyncClient(follow_redirects=True) as client:
                    # HEAD first to check content-type and size before downloading
                    head = await client.head(url, headers=headers or {}, timeout=15)
                    ct = head.headers.get("content-type", "").split(";")[0].strip().lower()
                    if ct and ct not in _ALLOWED_CONTENT_TYPES:
                        return {"error": f"URL is not an image (content-type: {ct})."}
                    cl = head.headers.get("content-length")
                    if cl and cl.isdigit() and int(cl) > _MAX_IMAGE_BYTES:
                        mb = int(cl) / (1024 * 1024)
                        return {"error": f"Image too large ({mb:.1f} MB). Max is 10 MB."}

                    # Stream download with hard size cap
                    chunks: list[bytes] = []
                    total = 0
                    async with client.stream(
                        "GET", url, headers=headers or {}, timeout=30,
                    ) as resp:
                        resp.raise_for_status()
                        # Re-check content-type from GET response
                        get_ct = (
                            resp.headers.get("content-type", "")
                            .split(";")[0].strip().lower()
                        )
                        if get_ct and get_ct not in _ALLOWED_CONTENT_TYPES:
                            return {
                                "error": f"URL is not an image (content-type: {get_ct}).",
                            }
                        async for chunk in resp.aiter_bytes(chunk_size=64 * 1024):
                            total += len(chunk)
                            if total > _MAX_IMAGE_BYTES:
                                return {
                                    "error": "Image exceeds 10 MB limit during download.",
                                }
                            chunks.append(chunk)
                    image_data = b"".join(chunks)
            except httpx.HTTPStatusError as exc:
                return {"error": f"Failed to fetch image: HTTP {exc.response.status_code}"}
            except Exception as exc:
                return {"error": f"Failed to fetch image: {exc}"}

        if dispatcher is None:
            return {"status": "queued", "person": person, "url": url or file_path}
        if group:
            return await dispatcher.send_group_image(
                "", url or "", caption, image_data=image_data,
            )
        if not person:
            return {"error": "Either 'person' or 'group: true' is required."}
        return await dispatcher.send_image(
            person, url or "", caption, image_data=image_data,
        )

    # --- Channel preference tool ---

    @_reg(
        name="channel_preference_set",
        description=(
            "Set a household member's preferred messaging channel "
            "for scheduled updates."
        ),
    )
    async def channel_preference_set(
        *,
        person: Annotated[str, Desc("Member name")],
        channel: Annotated[str, Desc("Channel name (e.g. 'telegram', 'whatsapp')")],
        **_: Any,
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

    @_reg(
        name="channel_preference_get",
        description="Get a household member's preferred messaging channel.",
    )
    async def channel_preference_get(
        *,
        person: Annotated[str, Desc("Member name")],
        **_: Any,
    ) -> dict[str, Any]:
        if dispatcher is None:
            return {"status": "error", "detail": "No channel dispatcher available"}
        pref = dispatcher.get_preference(person)
        return {
            "person": person,
            "preferred_channel": pref,
            "available_channels": dispatcher.available_channels(),
        }

    # --- Routine management tools ---

    from homeclaw.scheduler.routines import add_routine, parse_routines_md, remove_routine

    @_reg(name="routine_list", description="List all scheduled household routines.")
    async def routine_list(**_: Any) -> dict[str, Any]:
        routines = parse_routines_md(workspaces)
        return {
            "routines": [
                {
                    "name": r.name,
                    "description": r.description,
                    "target": r.target or "household",
                }
                for r in routines
            ]
        }

    @_reg(
        name="routine_add",
        description=(
            "Add a new scheduled routine. "
            "Schedule can be natural language or a 5-field cron expression. "
            "You MUST provide a target — ask the user who this routine is for "
            "before calling. If target is not provided, the tool will return a "
            "prompt for you to relay to the user."
        ),
    )
    async def routine_add(
        *,
        title: Annotated[str, Desc("Short name for the routine (e.g. 'Weekly grocery check')")],
        schedule: Annotated[str, Desc(
            "When to run. Natural language examples: 'Every weekday at 7:30am', "
            "'Every Sunday at 10:00am', 'Every 3 days', 'Every other Tuesday at 9am', "
            "'Monthly on the 1st at 10am', '1st Monday of the month at 9am', "
            "'Last Friday of the month at 3pm'. "
            "For complex schedules, use a 5-field cron expression: 'minute hour day month day_of_week' "
            "(e.g. '30 7 * * 1-5' for weekdays at 7:30am, '0 9 1 * *' for 1st of month at 9am)."
        )],
        action: Annotated[str, Desc("What the routine should do")],
        target: Annotated[str | None, Desc(
            "Who receives this routine's output. "
            "A person's name (e.g. 'stephen') sends it as a private DM. "
            "'each_member' runs it once per household member and DMs each. "
            "'household' sends it to the shared group chat."
        )] = None,
        person: Annotated[str, Desc("Caller")] = "",
        **_: Any,
    ) -> dict[str, Any]:
        if target is None:
            return {
                "status": "confirm_target",
                "message": (
                    "Who should receive this routine? Ask the user to pick one:\n"
                    f"• Just me ({person}) — sends as a private message\n"
                    "• Each member — runs for everyone and DMs each person\n"
                    "• Household — sends to the shared group chat"
                ),
                "pending": {"title": title, "schedule": schedule, "action": action},
            }
        # Normalise target
        if target.lower() in ("household", "group"):
            target = None
        elif target.lower() == "each_member":
            target = "each_member"
        # else: treat as a person name (lowercase)
        elif target.lower() not in ("each_member",):
            target = target.lower()
        try:
            add_routine(workspaces, title, schedule, action, target=target)
        except ValueError as e:
            return {"error": str(e)}
        if on_routines_changed:
            on_routines_changed()
        return {"status": "added", "title": title, "schedule": schedule, "target": target or "household"}

    @_reg(
        name="routine_update",
        description=(
            "Update an existing routine's schedule, action, title, or target. "
            "Use routine_list first to see available routine names. "
            "Use this when someone wants to change what a routine does "
            "(e.g. 'add news to my morning briefing') or when it runs."
        ),
    )
    async def routine_update(
        *,
        name: Annotated[str, Desc("The routine slug name (e.g. 'morning_briefing')")],
        schedule: Annotated[str | None, Desc("New schedule (optional — omit to keep current)")] = None,
        action: Annotated[str | None, Desc("New action description (optional — omit to keep current)")] = None,
        title: Annotated[str | None, Desc("New title (optional — omit to keep current)")] = None,
        target: Annotated[str | None, Desc(
            "New delivery target (optional — omit to keep current). "
            "A person name for private DM, 'each_member' for all, 'household' for group chat."
        )] = ...,  # type: ignore[assignment]  # sentinel
        **_: Any,
    ) -> dict[str, Any]:
        from homeclaw.scheduler.routines import update_routine
        # Normalise target when explicitly provided
        real_target: str | None | type(Ellipsis) = ...
        if target is not ...:
            if target is not None and target.lower() in ("household", "group"):
                real_target = None
            else:
                real_target = target.lower() if target else target
        updated = update_routine(
            workspaces, name, schedule=schedule, action=action, title=title,
            target=real_target,  # type: ignore[arg-type]
        )
        if not updated:
            return {"error": f"Routine '{name}' not found"}
        if on_routines_changed:
            on_routines_changed()
        return {"status": "updated", "name": name}

    @_reg(
        name="routine_remove",
        description=(
            "Remove a scheduled routine by its slug name. "
            "Use routine_list first to see available routine names."
        ),
    )
    async def routine_remove(
        *,
        name: Annotated[str, Desc("The routine slug name (e.g. 'morning_briefing')")],
        **_: Any,
    ) -> dict[str, Any]:
        removed = remove_routine(workspaces, name)
        if not removed:
            return {"error": f"Routine '{name}' not found"}
        if on_routines_changed:
            on_routines_changed()
        return {"status": "removed", "name": name}

    @_reg(
        name="routine_run",
        description=(
            "Manually trigger a scheduled routine to run right now. "
            "Use this when a routine was missed or a user asks to run one immediately. "
            "The routine runs synchronously and returns its full output so you can "
            "confirm it completed successfully."
        ),
    )
    async def routine_run(
        *,
        name: Annotated[str, Desc("The routine slug name (e.g. 'morning_briefing')")],
        **_: Any,
    ) -> dict[str, Any]:
        if on_routine_run is None:
            return {"error": "Scheduler not available"}
        result = await on_routine_run(name)
        if result is None:
            return {"error": f"Routine '{name}' not found — use routine_list to see available names"}
        if not result:
            return {"status": "error", "name": name, "detail": "Routine ran but produced no output — check logs for errors"}
        return {"status": "completed", "name": name, "result": result}

    # --- Skill tools ---

    @_reg(
        name="skill_list",
        description=(
            "List all skill plugins available to this household member — "
            "includes household-wide skills and their own private skills."
        ),
    )
    async def skill_list(
        *,
        person: Annotated[str, Desc("Household member name")],
        **_: Any,
    ) -> dict[str, Any]:
        from homeclaw.plugins.skills.loader import (
            _is_admin_only,
            discover_skills,
            skill_md_to_definition,
        )

        is_admin = _is_admin(person)
        locations = discover_skills(workspaces, person)
        skills = []
        for loc in locations:
            try:
                defn = skill_md_to_definition((loc.skill_dir / "SKILL.md").read_text())
                if _is_admin_only(defn) and not is_admin:
                    continue
                skills.append({
                    "name": loc.name,
                    "scope": loc.scope,
                    "description": defn.description,
                    "allowed_domains": defn.allowed_domains,
                })
            except Exception:
                skills.append({"name": loc.name, "scope": loc.scope, "error": "failed to parse"})
        return {"skills": skills, "count": len(skills)}

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

    @_reg(
        name="skill_create",
        description=(
            "Create a new skill — a self-contained mini-app with its own "
            "data directory. Every skill automatically gets data_list, "
            "data_read, data_write, and data_delete tools (namespaced "
            "as {name}__data_read etc). Setting allowed_domains also "
            "gives the skill an {name}__http_call tool for API access. "
            "Choose 'household' scope to share, 'private' for one person."
        ),
        schema_overrides={
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
    )
    async def skill_create(
        *,
        person: Annotated[str, Desc("Household member creating the skill")],
        name: Annotated[str, Desc("Skill name (slug-style, e.g. 'weather', 'my_calendar')")],
        description: Annotated[str, Desc("Short description of what the skill does")],
        scope: Annotated[SkillScope, Desc(
            "Who can use this skill and see its data. "
            "'household' = shared with all members; "
            "'private' = only accessible to this person."
        )],
        allowed_domains: Annotated[list[str] | None, Desc(
            "Domains the skill is allowed to reach via HTTP. "
            "Setting this automatically registers a "
            "{name}__http_call tool for the skill. "
            "Example: ['api.openweathermap.org']"
        )] = None,
        instructions: Annotated[str, Desc("Instructions for how to use this skill, injected into the agent's context")] = "",
        initial_files: list[dict[str, Any]] | None = None,
        source_notes: Annotated[list[str] | None, Desc(
            "Memory topic names to copy into the skill's data directory "
            "(e.g. ['recipes', 'restaurant-notes']). Checks person's memory first, "
            "then household memory."
        )] = None,
        source_bookmarks: dict[str, Any] | None = None,
        **_: Any,
    ) -> dict[str, Any]:
        from homeclaw.plugins.registry import PluginType
        from homeclaw.plugins.skills.loader import (
            load_skill,
            render_skill_md,
            slugify_skill_name,
        )

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

    @_reg(
        name="skill_remove",
        description=(
            "Remove a skill plugin. The skill is unregistered immediately and its "
            "directory is archived (not permanently deleted). Data can be recovered "
            "or permanently deleted via the web UI."
        ),
    )
    async def skill_remove(
        *,
        person: Annotated[str, Desc("Household member requesting the removal")],
        name: Annotated[str, Desc("Skill name to remove")],
        owner: Annotated[str, Desc("Who owns the skill: 'household' or a person's name")],
        **_: Any,
    ) -> dict[str, Any]:
        import shutil
        from datetime import datetime

        skill_dir = workspaces / safe_slug(owner) / "skills" / safe_slug(name)
        if not skill_dir.exists():
            return {"error": f"Skill '{name}' not found under '{owner}'"}

        # Unregister from plugin registry
        unregistered = False
        if plugin_registry is not None:
            unregistered = plugin_registry.unregister(name)

        # Archive: move to .archive/{name}_{timestamp}/
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
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

    @_reg(
        name="skill_update",
        description=(
            "Update a skill's instructions or description without "
            "recreating it. The skill definition (skill.md) is rewritten "
            "and the skill is reloaded. Does not affect data files."
        ),
    )
    async def skill_update(
        *,
        person: Annotated[str, Desc("Household member requesting the update")],
        name: Annotated[str, Desc("Skill name to update")],
        owner: Annotated[str, Desc("Who owns the skill: 'household' or a person's name")],
        instructions: Annotated[str | None, Desc("New instructions (replaces existing). Omit to keep current.")] = None,
        description: Annotated[str | None, Desc("New description (replaces existing). Omit to keep current.")] = None,
        allowed_domains: Annotated[list[str] | None, Desc("New allowed domains for http_call. Omit to keep current.")] = None,
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
        new_domains = allowed_domains if allowed_domains is not None else defn.allowed_domains

        # Always write back as SKILL.md (new format)
        updated_md = render_skill_md(
            name=defn.name,
            description=new_desc,
            allowed_domains=new_domains or None,
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

    @_reg(
        name="skill_migrate",
        description=(
            "Move a skill from one scope to another — household to private or vice versa. "
            "All skill data (definition + data files) moves with it. "
            "The skill is re-registered immediately under the new scope."
        ),
    )
    async def skill_migrate(
        *,
        person: Annotated[str, Desc("Household member requesting the migration")],
        name: Annotated[str, Desc("Skill name to migrate")],
        current_owner: Annotated[str, Desc("Current owner: 'household' or a person's name")],
        to_scope: Annotated[SkillScope, Desc("Target scope")],
        to_person: Annotated[str | None, Desc("Required when to_scope is 'private' — which person to move the skill to")] = None,
        **_: Any,
    ) -> dict[str, Any]:
        import shutil

        from homeclaw.plugins.registry import PluginType
        from homeclaw.plugins.skills.loader import load_skill

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

    # --- Skill approval tools ---

    @_reg(
        name="skill_pending_list",
        description=(
            "List skills waiting for admin approval. "
            "Only relevant when skill_approval_required is enabled."
        ),
    )
    async def skill_pending_list(
        *,
        person: Annotated[str, Desc("Household member name")],
        **_: Any,
    ) -> dict[str, Any]:
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

    @_reg(
        name="skill_approve",
        description="Approve a pending skill so it becomes active. Admin only.",
    )
    async def skill_approve(
        *,
        person: Annotated[str, Desc("Admin member name")],
        name: Annotated[str, Desc("Skill name to approve")],
        **_: Any,
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

    @_reg(name="skill_reject", description="Reject and delete a pending skill. Admin only.")
    async def skill_reject(
        *,
        person: Annotated[str, Desc("Admin member name")],
        name: Annotated[str, Desc("Skill name to reject")],
        reason: Annotated[str, Desc("Reason for rejection (shown to requester)")] = "",
        **_: Any,
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

    # --- Skill installation from URL ---

    async def _install_single_skill(
        *,
        person: str,
        url: str,
        skill_md_url: str,
        is_github_repo: bool,
        scope: str,
        workspaces: Path,
        plugin_registry: Any,
    ) -> dict[str, Any]:
        """Install a single skill from a resolved SKILL.md URL."""
        import httpx

        from homeclaw.plugins.registry import PluginType
        from homeclaw.plugins.skills.loader import load_skill, skill_md_to_definition

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

        try:
            defn = skill_md_to_definition(content)
        except ValueError as e:
            return {"error": f"Invalid SKILL.md: {e}"}

        slug = safe_slug(defn.name)
        if not slug:
            return {"error": f"Invalid skill name in SKILL.md: '{defn.name}'"}

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

        fetched_extras: list[str] = []
        if is_github_repo:
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
            dep_warnings: list[str] = []
            for b in deps["missing_bins"]:
                dep_warnings.append(f"Missing binary '{b['name']}': {b['hint']}")
            for ev in deps["missing_env"]:
                dep_warnings.append(f"Missing env var '{ev}'")
            result["warnings"] = dep_warnings
        return result

    @_reg(
        name="skill_install",
        description=(
            "Install a skill from a URL. Accepts GitHub repos (including "
            "multi-skill repos), gists, or any URL that serves a SKILL.md. "
            "For repos with multiple skills in subdirectories, returns the "
            "list of available skills unless install_all is true."
        ),
    )
    async def skill_install(
        *,
        person: Annotated[str, Desc("Household member name")],
        url: Annotated[str, Desc(
            "URL to install from — GitHub repo/subpath URL or "
            "direct link to a SKILL.md file"
        )],
        scope: Annotated[SkillScope, Desc("Who can use this skill (default: household)")] = "household",
        install_all: Annotated[bool, Desc("Install all skills from a multi-skill repo")] = False,
        **_: Any,
    ) -> dict[str, Any]:
        import httpx

        from homeclaw.plugins.skills.github import (
            list_repo_skills,
            normalize_gist_url,
            parse_github_url,
            raw_skill_md_url,
            skill_subpath_url,
        )

        is_github_repo = parse_github_url(url) is not None

        # Check if there's a SKILL.md at the target path
        skill_md_url = raw_skill_md_url(url) if is_github_repo else None
        has_root_skill = False
        if skill_md_url is not None:
            try:
                transport = httpx.AsyncHTTPTransport(retries=2)
                async with httpx.AsyncClient(timeout=30, transport=transport) as client:
                    resp = await client.get(skill_md_url)
                    has_root_skill = resp.status_code == 200
            except httpx.RequestError:
                pass

        # Single-skill: SKILL.md found at target, or not a GitHub repo
        if has_root_skill or not is_github_repo:
            if not is_github_repo:
                skill_md_url = normalize_gist_url(url) or url
            return await _install_single_skill(
                person=person, url=url, skill_md_url=skill_md_url or url,
                is_github_repo=is_github_repo, scope=scope,
                workspaces=workspaces, plugin_registry=plugin_registry,
            )

        # Multi-skill: discover subdirectories
        available = await list_repo_skills(url)
        if not available:
            return {"error": "No SKILL.md files found in this repository"}

        if not install_all:
            return {
                "status": "multiple_skills",
                "url": url,
                "skills": available,
                "hint": "Set install_all=true to install all, or use a more specific URL",
            }

        # Install all discovered skills
        results: list[dict[str, Any]] = []
        for skill_info in available:
            sub_url = skill_subpath_url(url, skill_info["path"])
            sub_skill_md_url = raw_skill_md_url(sub_url)
            r = await _install_single_skill(
                person=person, url=sub_url,
                skill_md_url=sub_skill_md_url or sub_url,
                is_github_repo=True, scope=scope,
                workspaces=workspaces, plugin_registry=plugin_registry,
            )
            results.append(r)

        installed = [r for r in results if r.get("status") == "installed"]
        errors = [r for r in results if "error" in r]
        return {
            "status": "installed_multiple",
            "installed": installed,
            "errors": errors,
            "total": len(results),
        }

    # --- Skill file editing ---

    @_reg(
        name="skill_edit_file",
        description=(
            "Read, edit, or create any file in a skill directory. "
            "Use this for .env files, scripts, references — anything in the skill root. "
            "(1) Read: just pass name + file. "
            "(2) Find/replace: pass find + replace for targeted edits. "
            "(3) Write: pass content to create or overwrite a file. "
            "For .env files: skill_edit_file(name='x', file='.env', content='KEY=value'). "
            "Note: data_write only writes to data/ — use this tool for the skill root."
        ),
    )
    async def skill_edit_file(
        *,
        person: Annotated[str, Desc("Household member name")],
        name: Annotated[str, Desc("Skill name")],
        file: Annotated[str, Desc("File path relative to skill dir (e.g. 'SKILL.md', 'scripts/check.sh')")],
        content: Annotated[str | None, Desc("Full file content (write mode — overwrites the file)")] = None,
        find: Annotated[str | None, Desc("Text to find (find/replace mode)")] = None,
        replace: Annotated[str | None, Desc("Replacement text (find/replace mode)")] = None,
        **_: Any,
    ) -> dict[str, Any]:
        from homeclaw.plugins.skills.loader import discover_skills

        locations = discover_skills(workspaces, person)
        loc = next((sk for sk in locations if sk.name == name), None)
        if loc is None:
            return {"error": f"Skill '{name}' not found"}
        if loc.scope == "builtin":
            return {"error": f"Cannot edit built-in skill '{name}'. Install a copy to household or personal skills first."}

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
            # Safety: warn if overwriting a large file with much shorter content
            if path.is_file():
                old_size = path.stat().st_size
                if old_size > 500 and len(content) < old_size * 0.2:
                    return {
                        "error": (
                            f"Refusing to overwrite {file} ({old_size} bytes) with "
                            f"much shorter content ({len(content)} bytes). This usually "
                            f"means truncation. Use find/replace mode for targeted edits, "
                            f"or pass the full content if you really mean to replace it."
                        ),
                    }
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
            return {"file": file, "status": "written", "size": len(content)}

        return {"error": "Provide content (write), or find+replace (edit), or nothing (read)"}

    @_reg(
        name="read_skill",
        description=(
            "Load a skill's full instructions and see its available resources. "
            "Skill instructions are auto-loaded on first tool use, but call this "
            "to browse a skill's resources, scripts, and data files. "
            "The skill catalog in your context lists available skills."
        ),
    )
    async def read_skill(
        *,
        person: Annotated[str, Desc("Household member name")],
        name: Annotated[str, Desc("Skill name (as shown in the skill catalog)")],
        **_: Any,
    ) -> dict[str, Any]:
        from homeclaw.plugins.skills.loader import (
            _is_admin_only,
            discover_skills,
            skill_md_to_definition,
        )

        locations = discover_skills(workspaces, person)
        loc = next((sk for sk in locations if sk.name == name), None)
        if loc is None:
            return {"error": f"Skill '{name}' not found"}

        skill_path = loc.skill_dir / "SKILL.md"
        if not skill_path.is_file():
            return {"error": f"No SKILL.md in '{name}'"}

        defn = skill_md_to_definition(skill_path.read_text())

        if _is_admin_only(defn) and not _is_admin(person):
            return {"error": f"Skill '{name}' is admin-only"}

        # List available resource directories
        resources: dict[str, list[str]] = {}
        for subdir in ("scripts", "references", "assets", "data"):
            dir_path = loc.skill_dir / subdir
            if dir_path.is_dir():
                files = sorted(f.name for f in dir_path.iterdir() if f.is_file())
                if files:
                    resources[subdir] = files

        activated_skills.add(name)

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
            "already_loaded": name in activated_skills,
        }

    @_reg(
        name="run_skill_script",
        description=(
            "Run a script bundled with a skill. Scripts live in the skill's "
            "scripts/ directory and are listed when you read_skill. Only "
            "pre-installed scripts can be run — no arbitrary shell commands."
        ),
    )
    async def run_skill_script(
        *,
        person: Annotated[str, Desc("Household member name")],
        name: Annotated[str, Desc("Skill name")],
        script: Annotated[str, Desc("Script filename (relative to scripts/)")],
        args: Annotated[list[str] | None, Desc("Arguments to pass to the script")] = None,
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

        # Merge skill .env into subprocess environment
        import os

        from homeclaw.plugins.skills.loader import _load_skill_env

        script_env = {**os.environ, **_load_skill_env(loc.skill_dir)}

        # Use an interpreter based on file extension so scripts don't
        # need the execute permission bit (skill_edit_file creates 0644).
        interpreters: dict[str, list[str]] = {
            ".sh": ["bash"],
            ".bash": ["bash"],
            ".py": ["python3"],
            ".rb": ["ruby"],
            ".js": ["node"],
            ".ts": ["npx", "tsx"],
        }
        suffix = script_path.suffix.lower()
        if suffix in interpreters:
            cmd = [*interpreters[suffix], str(script_path)] + (args or [])
        else:
            # Fall back to direct execution (requires +x)
            cmd = [str(script_path)] + (args or [])
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(loc.skill_dir),
                env=script_env,
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

    # --- Decision tools ---

    def _decisions_path(scope: str, person: str = "") -> Path:
        owner = "household" if scope == "household" else safe_slug(person)
        return workspaces / owner / "decisions.md"

    @_reg(
        name="decision_log",
        description=(
            "Record a settled household or personal decision so it is not "
            "re-litigated. Use this when someone says 'we decided', 'let's go with', "
            "'from now on', or otherwise settles on a choice. Examples: 'Piano lessons "
            "on Tuesdays', 'Switching to oat milk', 'No screens after 8pm'."
        ),
    )
    async def decision_log(
        *,
        person: Annotated[str, Desc("Who made or reported this decision")],
        decision: Annotated[str, Desc("The decision that was made")],
        scope: Annotated[DecisionScope, Desc(
            "Whether this applies to the whole household or just this person (default: household)"
        )] = "household",
        **_: Any,
    ) -> dict[str, Any]:
        if err := _check_content_length(decision, "decision"):
            return err
        if scope not in ("household", "personal"):
            return {"error": f"Invalid scope '{scope}' — must be 'household' or 'personal'"}
        path = _decisions_path(scope, person)
        path.parent.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M")
        entry = f"- [{timestamp}] {decision} — {person}"
        if not path.exists():
            path.write_text(f"# Decisions\n\n{entry}\n")
        else:
            with path.open("a") as f:
                f.write(f"{entry}\n")
        return {"status": "logged", "scope": scope, "decision": decision}

    @_reg(
        name="decision_list",
        description="List recorded decisions for the household or a person.",
    )
    async def decision_list(
        *,
        scope: Annotated[DecisionScope, Desc("Which decisions to list (default: household)")] = "household",
        person: Annotated[str, Desc("Person name (required for personal scope)")] = "",
        **_: Any,
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

    # --- Settings tools ---

    if config is not None:

        @_reg(
            name="settings_get",
            description="Check current homeclaw settings and semantic memory status.",
        )
        async def settings_get(**_: Any) -> dict[str, Any]:
            from homeclaw.memory.status import get_semantic_status

            return {
                "semantic_status": get_semantic_status(workspaces),
            }

    # --- Admin-only tools ---

    @_reg(
        name="log_read",
        description=(
            "Read homeclaw application logs. Admin only. "
            "Returns recent log entries with optional filtering "
            "by level, text search, and date range."
        ),
    )
    async def log_read(
        *,
        person: Annotated[str, Desc("Household member name")],
        level: Annotated[
            str, Desc("Filter by level: DEBUG, INFO, WARNING, ERROR"),
        ] = "",
        search: Annotated[
            str, Desc("Text search in message or logger name"),
        ] = "",
        hours: Annotated[
            int, Desc("How many hours back to search (default 24)"),
        ] = 24,
        limit: Annotated[
            int, Desc("Max entries to return (default 100)"),
        ] = 100,
        **_: Any,
    ) -> dict[str, Any]:
        if not _is_admin(person):
            return {"error": "Only admins can read logs"}

        from homeclaw.api.logbuffer import get_log_entries_from_file

        after = datetime.now(tz=UTC) - timedelta(hours=max(hours, 1))
        entries = get_log_entries_from_file(
            after=after,
            level=level or None,
            search=search or None,
            limit=min(limit, 500),
        )
        return {
            "entries": entries,
            "count": len(entries),
            "hours": hours,
        }
