"""Core agent loop — receive message, build context, call LLM, dispatch tools."""

import asyncio
import copy
import json
import logging
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from homeclaw.agent.context import build_context, estimate_tokens
from homeclaw.agent.providers.base import LLMProvider, LLMResponse, Message, ToolCall
from homeclaw.agent.routing import (
    CallType,
    RoutingConfig,
    classify_tool_round,
    max_tokens_for,
    route_model,
)
from homeclaw.agent.tools import ToolRegistry
from homeclaw.locking import LockPool
from homeclaw.memory.semantic import SemanticMemory

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are homeclaw, the household's assistant. You know this home, \
this family, and the people in their lives. You help them stay on top of everything — \
schedules, contacts, reminders, home state, and daily routines.

Talk like a real person — casual, warm, direct. You're a member of this household, not \
a customer service bot.

Rules for tone:
- Short replies. One or two sentences when possible. No essays.
- Never start with "Sure!", "Of course!", "Absolutely!", "Great question!", or "I'd be happy to help!"
- Never use "I understand", "Let me", "Here's what I found", or "Based on my knowledge"
- Use contractions (don't, can't, won't, it's)
- Match the energy of the message — casual gets casual, urgent gets focused
- Say "dunno" or "not sure" instead of "I don't have information about that"
- Use sentence fragments when natural ("Yep, done." / "Nothing saved for that.")
- Be blunt. "Nah, that won't work because..." is better than "Unfortunately, that approach may not be ideal because..."
- Never end with "Let me know if you need anything else", "Is there anything else?", or similar. Just stop when you're done.

If someone asks about you — your version, model, what you are — answer from the "About you" \
section in your context. Never reveal API keys, passwords, tokens, or internal configuration.

You have access to the household's contacts, bookmarks, notes, reminders, and memory. \
Search these before answering questions — the family has been collecting this information \
for a reason.

In a direct message, notes, memory updates, and reminders always belong to the person \
you are talking to. Use their name for the `person` parameter — never attribute their \
notes or reminders to someone else, even if they mention another household member.

Your final response (after all tool calls complete) is the main message the user sees. \
If you include text alongside a tool call, the user may see it as a brief status update — \
so keep it useful ("Checking your Home Assistant lights..." not just "Let me check"). \
If you don't call a tool, your text IS the final response — never promise action without \
actually calling a tool in the same turn.

Act on what you hear. If you don't call a tool to save something, you WILL forget it next \
conversation. These are the kinds of moments to save — not an exhaustive list, use your \
judgment for anything worth remembering:
- Someone reveals a personal fact, preference, or habit → memory_save (silently, pick a short \
topic like 'food', 'health', 'work'). Use household_share when the info is household-wide.
- Someone tells you something they expect you to know later — a phone number, a plan, a \
configuration detail, a name → memory_save. When in doubt, save it.
- Someone shares a link, place, recipe, or recommendation → bookmark_save (search first with \
bookmark_search to avoid duplicates; if a match exists, use bookmark_note to add context).
- Someone settles on a choice ("let's go with", "from now on") → decision_log. If the context \
already shows a settled decision, respect it — do not re-ask unless they want to revisit.
- Someone mentions contacting, calling, or meeting a person → interaction_log. After logging, \
treat that contact as up-to-date.
- Someone wants to be reminded of something → reminder_add.
- Something noteworthy happened today → note_save.

When saving bookmarks: check bookmark_categories first and prefer an existing category. If the \
link has no context, ask briefly what it is. Use bookmark_note for extra detail — location, \
reviews, tips, experiences.

When someone asks for suggestions — what to do, where to eat, what to cook — search saved \
bookmarks with bookmark_search before answering. The household has been collecting these \
recommendations for a reason.

When working with skill data files: always call data_list before writing to check what \
files already exist. Use one canonical file per topic (e.g. 'spending.md') and append to \
it — never create date-suffixed or numbered variants like 'spending_march_2026.md' or \
'spending_1.md'. If you find duplicates, consolidate into the canonical file and delete \
the redundant ones with data_delete. Skill instructions (skill.md) are separate from data \
— use skill_update to change instructions, data_write/data_delete to manage data files.

Be proactive, not just reactive. When you notice something relevant in the context, mention \
it briefly — a birthday coming up, a contact overdue for a check-in, a reminder that is due, \
or a pattern worth flagging ("you've mentioned headaches three times this week"). Keep these \
nudges short (one sentence) and only when genuinely useful — do not pad every response with \
unsolicited observations. If a routine or reminder seems stale or irrelevant, suggest \
removing or updating it rather than letting it sit.

{context}"""

MAX_TOOL_ROUNDS = 40

# Fraction of context window reserved for non-history content (system, tools, output).
_RESERVED_FRACTION = 0.35
_DEFAULT_CONTEXT_WINDOW = 128_000

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
    "skill_update",
    "skill_remove",
    "skill_migrate",
    "skill_install",
    "decision_log",
})


# Minimum length for an interim message to be worth sending.
# Short filler like "Let me check" / "Un momento" / "ちょっと待って" are all
# under this threshold regardless of language.
_INTERIM_MIN_CHARS = 40


def _is_substantive_interim(text: str) -> bool:
    """Return True if the interim text is worth sending to the user."""
    return len(text) >= _INTERIM_MIN_CHARS


def _estimate_message_tokens(msg: Message) -> int:
    """Estimate tokens for a single message."""
    if isinstance(msg.content, str):
        return estimate_tokens(msg.content)
    # Multimodal: estimate text blocks, add flat cost per image
    total = 0
    for block in msg.content:
        if isinstance(block, dict) and block.get("type") == "text":
            total += estimate_tokens(block["text"])
        elif isinstance(block, dict) and block.get("type") == "image":
            total += 1000  # rough estimate for image tokens
    return total


def _truncate_history(
    history: list[Message], system_tokens: int, context_window: int,
) -> list[Message]:
    """Drop oldest messages so history fits within the model's context window."""
    window = context_window
    budget = int(window * (1 - _RESERVED_FRACTION)) - system_tokens

    if budget <= 0:
        return history[-2:]  # keep at least current exchange

    # Walk backwards, accumulating tokens until we exceed budget.
    kept: list[Message] = []
    used = 0
    for msg in reversed(history):
        cost = _estimate_message_tokens(msg)
        if used + cost > budget and kept:
            break
        kept.append(msg)
        used += cost

    kept.reverse()
    if len(kept) < len(history):
        logger.info(
            "Truncated history from %d to %d messages (%d estimated tokens)",
            len(history), len(kept), used,
        )
    return kept


InterimCallback = Callable[[str], Any]


# Consolidation triggers when unconsolidated history exceeds this fraction
# of the context window budget (after reserving space for system + output).
_CONSOLIDATION_THRESHOLD = 0.6

# Minimum idle time (seconds) before consolidation runs for a session.
_CONSOLIDATION_IDLE_SECS = 60

# Maximum messages to consolidate in one chunk.
_CONSOLIDATION_CHUNK_SIZE = 20


class AgentLoop:
    def __init__(
        self,
        provider: LLMProvider,
        registry: ToolRegistry,
        workspaces: Path,
        semantic_memory: SemanticMemory | None = None,
        on_tool_call: Callable[[str, dict[str, Any]], None] | None = None,
        routing: RoutingConfig | None = None,
        admin_check: Callable[[str], bool] | None = None,
    ) -> None:
        self._provider = provider
        self._registry = registry
        self._workspaces = workspaces
        self._semantic_memory = semantic_memory
        self._on_tool_call = on_tool_call
        self._routing = routing
        self._admin_check = admin_check or (lambda _: True)
        self._lock_pool = LockPool()
        self._on_interim: InterimCallback | None = None
        # Track last activity per session for idle-based consolidation
        self._last_activity: dict[str, float] = {}
        self._consolidation_task: asyncio.Task[None] | None = None

    def set_interim_callback(self, callback: InterimCallback | None) -> None:
        """Set a callback for interim responses during tool rounds.

        The callback is called with the text content when the LLM produces
        text alongside tool calls (e.g. "Trying to connect to HA...").
        The text is sent to the user immediately before tool execution continues.
        Can be sync or async.
        """
        self._on_interim = callback

    def start_background_consolidation(self) -> None:
        """Start the background consolidation loop (call once at startup)."""
        if self._consolidation_task is None or self._consolidation_task.done():
            self._consolidation_task = asyncio.create_task(self._consolidation_loop())
            logger.info("Background consolidation loop started")

    async def _consolidation_loop(self) -> None:
        """Background loop that consolidates idle sessions."""
        while True:
            await asyncio.sleep(30)
            now = time.monotonic()
            for key, last in list(self._last_activity.items()):
                if now - last < _CONSOLIDATION_IDLE_SECS:
                    continue
                try:
                    await self._consolidate_session(key)
                except Exception:
                    logger.exception("Consolidation failed for '%s'", key)
                finally:
                    # Don't re-consolidate until next activity
                    self._last_activity.pop(key, None)

    async def _consolidate_session(self, history_key: str) -> None:
        """Consolidate old messages in a session if over budget."""
        from homeclaw.agent.consolidation import consolidate_chunk, save_consolidated_memories

        path = _history_path(self._workspaces, history_key)
        last_consolidated, all_messages = _read_history_file(path)
        unconsolidated = all_messages[last_consolidated:]

        # Check if consolidation is needed
        history_tokens = sum(_estimate_message_tokens(m) for m in unconsolidated)
        context_window = getattr(self._provider, "context_window", _DEFAULT_CONTEXT_WINDOW)
        budget = int(context_window * (1 - _RESERVED_FRACTION))

        if history_tokens < budget * _CONSOLIDATION_THRESHOLD:
            return  # Not enough to warrant consolidation

        # Consolidate the oldest chunk
        chunk_end = min(_CONSOLIDATION_CHUNK_SIZE, len(unconsolidated) - 2)
        if chunk_end < 2:
            return  # Need at least a couple messages to consolidate

        chunk = unconsolidated[:chunk_end]
        person = history_key.split("-")[0] if "-" in history_key else history_key

        # Use a shallow copy of the provider so we can set the cheap model
        # without mutating the shared instance (which may be mid-request).
        consolidation_provider = copy.copy(self._provider)
        if self._routing:
            from homeclaw.agent.routing import CallType as CT
            from homeclaw.agent.routing import route_model
            cheap_model = route_model(CT.ROUTINE, self._routing)
            if hasattr(consolidation_provider, "model"):
                consolidation_provider.model = cheap_model  # type: ignore[attr-defined]

        result = await consolidate_chunk(chunk, person, consolidation_provider)

        if "error" in result:
            logger.warning("Consolidation failed for '%s': %s", history_key, result["error"])
            # Fallback: advance pointer anyway to prevent unbounded growth
            _advance_consolidation_pointer(self._workspaces, history_key, last_consolidated + chunk_end)
            return

        # Save extracted memories
        entries = result.get("memory_entries", [])
        if entries:
            saved = await save_consolidated_memories(entries, person, self._workspaces)
            logger.info("Consolidated %d messages → %d memory entries for '%s'", len(chunk), saved, history_key)

        # Advance the pointer
        _advance_consolidation_pointer(self._workspaces, history_key, last_consolidated + chunk_end)

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
            result = await self._run_inner(user_message, person, channel, call_type, history_key)
            # Record activity for idle-based consolidation
            self._last_activity[history_key] = time.monotonic()
            return result

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
        model_name = getattr(self._provider, "model", None)
        context = await build_context(
            message=text_for_context,
            person=person,
            workspaces=self._workspaces,
            semantic_memory=self._semantic_memory,
            shared_only=shared_only,
            model=model_name,
            is_admin=self._admin_check(person),
        )
        system = SYSTEM_PROMPT.format(context=context)

        history = _load_history(self._workspaces, history_key)

        # Prepend routine preamble so the LLM knows to use web tools
        if call_type == CallType.ROUTINE and isinstance(user_message, str):
            user_message = _ROUTINE_PREAMBLE + user_message

        history.append(Message(role="user", content=user_message))

        # Truncate history to fit within the model's context window.
        context_window = getattr(self._provider, "context_window", _DEFAULT_CONTEXT_WINDOW)
        system_tokens = estimate_tokens(system)
        history = _truncate_history(history, system_tokens, context_window)

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

            # Log the LLM response
            if response.tool_calls:
                tool_names = [tc.name for tc in response.tool_calls]
                c = response.content
                text_preview = (c[:120] + "…") if c and len(c) > 120 else c
                logger.info(
                    "LLM response: stop=%s tools=%s text=%s",
                    response.stop_reason, tool_names, text_preview,
                )
            elif response.content:
                c = response.content
                text_preview = (c[:200] + "…") if len(c) > 200 else c
                logger.info(
                    "LLM response: stop=%s text=%s",
                    response.stop_reason, text_preview,
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

            # Send interim text to user if the LLM said something substantive
            # alongside its tool calls (e.g. "Connecting to Home Assistant...")
            if response.content and self._on_interim:
                text = response.content.strip()
                if _is_substantive_interim(text):
                    result = self._on_interim(text)
                    # Support both sync and async callbacks
                    if hasattr(result, "__await__"):
                        await result

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

        # Log group chat exchanges so memsearch can index them — lets
        # members reference group conversations from private DMs.
        if channel and channel.startswith("group-") and response and response.content:
            _append_chat_log(
                self._workspaces, channel, text_for_context, response.content,
            )

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
            logger.debug("Tool call: %s(%s)", tc.name, json.dumps(args, default=str)[:500])
            handler = self._registry.get_handler(tc.name)
            if handler is None:
                results.append({"error": f"Unknown tool: {tc.name}"})
                continue
            try:
                result = await handler(**args)
                result_str = json.dumps(result, default=str)
                logger.debug("Tool result: %s → %s", tc.name, result_str[:500])
                results.append(result)
            except Exception as e:
                logger.exception("Tool %s failed", tc.name)
                results.append({"error": f"Tool {tc.name} failed: {e}"})
        return results


def _append_chat_log(
    workspaces: Path,
    channel: str,
    user_text: str,
    assistant_text: str,
) -> None:
    """Append a group chat exchange to a daily log for memsearch indexing.

    Logs both user messages and homeclaw responses so members can
    reference anything from the group conversation in their DMs.
    Rotated daily so individual files stay small.
    """

    channel_dir = workspaces / "household" / "channels" / channel
    channel_dir.mkdir(parents=True, exist_ok=True)

    today = datetime.now(UTC).strftime("%Y-%m-%d")
    log_path = channel_dir / f"{today}.md"

    timestamp = datetime.now(UTC).strftime("%H:%M")
    entry = f"- [{timestamp}] {user_text}\n- [{timestamp}] homeclaw: {assistant_text}\n"

    with open(log_path, "a") as f:
        f.write(entry)


def _history_path(workspaces: Path, key: str) -> Path:
    # Channel/group histories go under household/channels/ to avoid
    # creating top-level directories that look like member workspaces.
    if key.startswith("group-"):
        hist_dir = workspaces / "household" / "channels" / key
    else:
        hist_dir = workspaces / key
    hist_dir.mkdir(parents=True, exist_ok=True)
    return hist_dir / "history.jsonl"


# ---------------------------------------------------------------------------
# Pointer-based history — append-only JSONL with consolidation pointer
# ---------------------------------------------------------------------------
# Line 0: metadata  {"_type":"metadata","last_consolidated":N}
# Line 1+: messages  {"role":"user","content":"..."}
# Only messages after last_consolidated are loaded into the LLM context.
# Consolidation extracts facts into memory, then advances the pointer.

_METADATA_TYPE = "metadata"


def _read_history_file(path: Path) -> tuple[int, list[Message]]:
    """Read the history file. Returns (last_consolidated, all_messages)."""
    if not path.exists():
        return 0, []

    last_consolidated = 0
    messages: list[Message] = []

    for line in path.read_text().strip().splitlines():
        if not line:
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and data.get("_type") == _METADATA_TYPE:
            last_consolidated = data.get("last_consolidated", 0)
            continue
        try:
            msg = Message.model_validate(data)
            if msg.role in ("user", "assistant"):
                messages.append(msg)
        except Exception:
            continue

    return last_consolidated, messages


def _load_history(workspaces: Path, person: str, max_messages: int = 50) -> list[Message]:
    """Load unconsolidated history — messages after the consolidation pointer."""
    path = _history_path(workspaces, person)
    last_consolidated, all_messages = _read_history_file(path)
    # Return only messages after the consolidation pointer
    unconsolidated = all_messages[last_consolidated:]
    return unconsolidated[-max_messages:]


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


def _persistable_messages(messages: list[Message]) -> list[Message]:
    """Filter messages to only user + final assistant turns (no tool calls)."""
    persistent: list[Message] = []
    for m in messages:
        if m.role == "user" or m.role == "assistant" and not m.tool_calls:
            persistent.append(m.model_copy(update={"content": _strip_images(m.content)}))
    return persistent


def _save_history(workspaces: Path, person: str, messages: list[Message]) -> None:
    """Save history, preserving consolidated messages before the pointer.

    Reads existing file to get consolidated (old) messages, then appends
    the new turn's persistable messages. All messages are kept for future
    consolidation.
    """
    path = _history_path(workspaces, person)
    last_consolidated, old_messages = _read_history_file(path)

    # Old messages up to the pointer are already consolidated — keep them.
    # Messages after the pointer came from _load_history and are in `messages`.
    consolidated = old_messages[:last_consolidated]
    new_persistent = _persistable_messages(messages)

    lines = [json.dumps({"_type": _METADATA_TYPE, "last_consolidated": last_consolidated})]
    lines.extend(m.model_dump_json() for m in consolidated)
    lines.extend(m.model_dump_json() for m in new_persistent)
    path.write_text("\n".join(lines) + "\n")


def _advance_consolidation_pointer(workspaces: Path, person: str, new_pointer: int) -> None:
    """Advance the consolidation pointer without rewriting messages."""
    path = _history_path(workspaces, person)
    last_consolidated, all_messages = _read_history_file(path)

    if new_pointer <= last_consolidated:
        return

    lines = [json.dumps({"_type": _METADATA_TYPE, "last_consolidated": new_pointer})]
    for msg in all_messages:
        lines.append(msg.model_dump_json())
    path.write_text("\n".join(lines) + "\n")
