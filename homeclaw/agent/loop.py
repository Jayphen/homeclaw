"""Core agent loop — receive message, build context, call LLM, dispatch tools."""

import json
import logging
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from homeclaw.agent.context import build_context
from homeclaw.agent.providers.base import LLMProvider, LLMResponse, Message, ToolCall
from homeclaw.agent.routing import CallType, RoutingConfig, classify_tool_round, max_tokens_for, route_model
from homeclaw.agent.tools import ToolRegistry
from homeclaw.locking import LockPool
from homeclaw.memory.semantic import SemanticMemory

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are homeclaw, the household's assistant. You know this home, \
this family, and the people in their lives. You help them stay on top of everything — \
schedules, contacts, reminders, home state, and daily routines.

You are reliable, warm, and plainspoken — like a trusted neighbour who happens to have \
perfect memory. You are not a corporate chatbot. Use natural language, not jargon. \
Keep answers short unless detail is asked for. When you don't know something, say so.

You have access to the household's contacts, bookmarks, notes, reminders, and memory. \
Search these before answering questions — the family has been collecting this information \
for a reason.

In a direct message, notes, memory updates, and reminders always belong to the person \
you are talking to. Use their name for the `person` parameter — never attribute their \
notes or reminders to someone else, even if they mention another household member.

When someone mentions they contacted, called, met, or messaged a person, always log it \
with interaction_log so the household's records stay current. After logging, treat that \
contact as up-to-date — do not describe them as overdue.

When someone shares a link (Instagram, website, etc.) or mentions a place, recipe, book, or \
anything they want to remember, search with bookmark_search first to avoid duplicates. If a \
match exists, use bookmark_note to add the new info instead of creating a duplicate. Otherwise \
save it with bookmark_save — extract a title, category, and tags. If the link has no context, \
ask briefly what it is before saving. Before categorizing, call bookmark_categories to see \
what categories already exist and prefer an existing one. If none fits, suggest the new \
category name to the user and confirm before saving. Use bookmark_note to attach any extra \
context — location, reviews, tips, experiences.

When someone asks for suggestions — what to do, where to eat, what to cook — search saved \
bookmarks with bookmark_search before answering. The household has been collecting these \
recommendations for a reason.

Proactively remember personal details (likes, allergies, birthdays, routines, goals) via \
memory_save. Pick a short topic name and it appends — no need to read first. Do this \
silently. Use household_share for household-wide info.

When someone settles on a decision — "let's go with", "we decided", "from now on" — log it \
with decision_log so it sticks. If the context shows a settled decision, respect it and do \
not re-ask or second-guess it unless the person explicitly wants to revisit.

Be proactive, not just reactive. When you notice something relevant in the context, mention \
it briefly — a birthday coming up, a contact overdue for a check-in, a reminder that is due, \
or a pattern worth flagging ("you've mentioned headaches three times this week"). Keep these \
nudges short (one sentence) and only when genuinely useful — do not pad every response with \
unsolicited observations. If a routine or reminder seems stale or irrelevant, suggest \
removing or updating it rather than letting it sit.

{context}"""

MAX_TOOL_ROUNDS = 10

# Extra instructions prepended to the user message for scheduled routines so
# the model actively uses web tools instead of hedging with stale training data.
_ROUTINE_PREAMBLE = (
    "You are executing a scheduled routine. For ANY information that requires "
    "current data (news, weather, headlines, events, prices, scores, etc.) you "
    "MUST use the web_search and web_read tools — do NOT try to answer from "
    "memory or training data. Make multiple searches if the routine covers "
    "several topics. Summarize the real results concisely.\n\n"
)

# Tools that write to a person's workspace. In DMs, the `person` argument
# is forced to the authenticated caller so the LLM can't accidentally
# attribute notes/memory/reminders to someone else.
_PERSONAL_WRITE_TOOLS = frozenset({
    "note_save",
    "memory_save",
    "reminder_add",
    "reminder_complete",
    "reminder_delete",
    "bookmark_save",
    "skill_create",
    "skill_remove",
    "skill_migrate",
    "decision_log",
})


class AgentLoop:
    def __init__(
        self,
        provider: LLMProvider,
        registry: ToolRegistry,
        workspaces: Path,
        semantic_memory: SemanticMemory | None = None,
        on_tool_call: Callable[[str, dict[str, Any]], None] | None = None,
        routing: RoutingConfig | None = None,
    ) -> None:
        self._provider = provider
        self._registry = registry
        self._workspaces = workspaces
        self._semantic_memory = semantic_memory
        self._on_tool_call = on_tool_call
        self._routing = routing
        self._lock_pool = LockPool()

    async def run(
        self,
        user_message: str | list[Any],
        person: str,
        channel: str | None = None,
        call_type: CallType = CallType.CONVERSATION,
    ) -> str:
        """Run the agent loop for a message.

        Args:
            user_message: The user's message — either a plain string or a list
                of content blocks (text + images) for multimodal input.
            person: Household member name (for context/memory).
            channel: If set, use shared history keyed by this channel ID
                     and restrict context to household-level facts only.
            call_type: The type of call for model routing.
        """
        person = person.lower()
        history_key = channel or person
        async with self._lock_pool.lock_for(history_key):
            return await self._run_inner(user_message, person, channel, call_type, history_key)

    async def _run_inner(
        self,
        user_message: str | list[Any],
        person: str,
        channel: str | None,
        call_type: CallType,
        history_key: str,
    ) -> str:
        # Extract text portion for context building
        if isinstance(user_message, str):
            text_for_context = user_message
        else:
            text_for_context = " ".join(
                block["text"] for block in user_message
                if isinstance(block, dict) and block.get("type") == "text"
            )

        shared_only = channel is not None
        context = await build_context(
            message=text_for_context,
            person=person,
            workspaces=self._workspaces,
            semantic_memory=self._semantic_memory,
            shared_only=shared_only,
        )
        system = SYSTEM_PROMPT.format(context=context)

        history = _load_history(self._workspaces, history_key)

        # Prepend routine preamble so the LLM knows to use web tools
        if call_type == CallType.ROUTINE and isinstance(user_message, str):
            user_message = _ROUTINE_PREAMBLE + user_message

        history.append(Message(role="user", content=user_message))

        tools = self._registry.get_definitions()
        response: LLMResponse | None = None

        # Apply model routing if configured
        current_call_type = call_type
        if self._routing:
            model = route_model(call_type, self._routing)
            if hasattr(self._provider, "model"):
                self._provider.model = model  # type: ignore[attr-defined]
            logger.debug("Routed %s → %s", call_type.value, model)

        for _ in range(MAX_TOOL_ROUNDS):
            token_limit = max_tokens_for(current_call_type, self._routing) if self._routing else None
            response = await self._provider.complete(
                messages=history,
                tools=tools,
                system=system,
                max_tokens=token_limit,
            )

            # Always append the assistant message — include tool_calls so the
            # API can match subsequent tool result messages to their tool_use blocks.
            history.append(Message(
                role="assistant",
                content=response.content or "",
                tool_calls=response.tool_calls,
            ))

            if response.stop_reason != "tool_use" or not response.tool_calls:
                break

            # Dispatch tool calls
            tool_results = await self._dispatch_tools(
                response.tool_calls, person=person, channel=channel,
            )
            for tc, result in zip(response.tool_calls, tool_results):
                history.append(
                    Message(
                        role="tool",
                        content=json.dumps(result),
                        tool_call_id=tc.id,
                    )
                )

            # Re-route: use cheaper model for follow-up if tools were simple
            if self._routing:
                tool_names = [tc.name for tc in response.tool_calls]
                current_call_type = classify_tool_round(tool_names)
                model = route_model(current_call_type, self._routing)
                if hasattr(self._provider, "model"):
                    self._provider.model = model  # type: ignore[attr-defined]
                    logger.debug("Re-routed after tools %s → %s (%s)", tool_names, model, current_call_type.value)

        if response and response.stop_reason == "tool_use":
            logger.warning(
                "Agent loop exhausted %d tool rounds without completing", MAX_TOOL_ROUNDS
            )
            # Surface the exhaustion to the user instead of returning partial content.
            _save_history(self._workspaces, history_key, history)
            return (
                response.content + "\n\n"
                "(I ran out of tool rounds before finishing — "
                "please try a simpler request or ask me to continue.)"
                if response.content
                else "Sorry, I wasn't able to complete that — I ran out of steps. "
                "Try a simpler request or ask me to continue."
            )

        _save_history(self._workspaces, history_key, history)
        return response.content if response else ""

    async def _dispatch_tools(
        self,
        tool_calls: list[ToolCall],
        person: str,
        channel: str | None,
    ) -> list[dict[str, Any]]:
        is_dm = channel is None
        results: list[dict[str, Any]] = []
        for tc in tool_calls:
            args = dict(tc.arguments)

            # Normalize person names to lowercase to prevent duplicate workspaces.
            if "person" in args and isinstance(args["person"], str):
                args["person"] = args["person"].lower()

            # In DMs, force personal-write tools to use the authenticated caller.
            if is_dm and tc.name in _PERSONAL_WRITE_TOOLS and "person" in args:
                requested = args["person"]
                if requested != person:
                    logger.info(
                        "Tool %s: overriding person %r → %r (DM enforcement)",
                        tc.name, requested, person,
                    )
                    args["person"] = person

            if self._on_tool_call is not None:
                self._on_tool_call(tc.name, args)
            handler = self._registry.get_handler(tc.name)
            if handler is None:
                results.append({"error": f"Unknown tool: {tc.name}"})
                continue
            try:
                result = await handler(**args)
                results.append(result)
            except Exception as e:
                logger.exception("Tool %s failed", tc.name)
                results.append({"error": f"Tool {tc.name} failed: {e}"})
        return results


def _history_path(workspaces: Path, person: str) -> Path:
    person_dir = workspaces / person
    person_dir.mkdir(parents=True, exist_ok=True)
    return person_dir / "history.jsonl"


def _load_history(workspaces: Path, person: str, max_messages: int = 50) -> list[Message]:
    path = _history_path(workspaces, person)
    if not path.exists():
        return []
    messages: list[Message] = []
    for line in path.read_text().strip().splitlines():
        if line:
            msg = Message.model_validate_json(line)
            # Only persist user/assistant turns — tool messages reference IDs
            # that are only valid within a single run() call.
            if msg.role in ("user", "assistant"):
                messages.append(msg)
    return messages[-max_messages:]


def _strip_images(content: str | list[Any]) -> str:
    """Replace image content blocks with a text placeholder for history persistence."""
    if isinstance(content, str):
        return content
    parts: list[str] = []
    for block in content:
        if isinstance(block, dict) and block.get("type") == "text":
            parts.append(block["text"])
        elif isinstance(block, dict) and block.get("type") == "image":
            parts.append("[image]")
    return " ".join(parts) if parts else ""


def _save_history(workspaces: Path, person: str, messages: list[Message]) -> None:
    path = _history_path(workspaces, person)
    # Strip tool messages before persisting — they contain ephemeral tool_call_ids
    # that will be rejected by the API if replayed in a later session.
    persistent: list[Message] = []
    for m in messages:
        if m.role not in ("user", "assistant"):
            continue
        # Replace image blocks with text placeholders to avoid storing large base64
        persistent.append(m.model_copy(update={"content": _strip_images(m.content)}))
    lines = [m.model_dump_json() for m in persistent[-100:]]
    path.write_text("\n".join(lines) + "\n")
