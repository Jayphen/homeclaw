"""Core agent loop — receive message, build context, call LLM, dispatch tools."""

import asyncio
import copy
import json
import logging
import re
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from homeclaw.agent.context import HOUSEHOLD_WORKSPACE, build_context, estimate_tokens
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

Daily notes are a journal of what the household is doing. Use note_save liberally — it's the \
household's daily log. Save things like:
- What someone cooked, ate, or is planning to eat
- Activities, outings, errands, or plans mentioned
- Health updates (feeling sick, exercise, sleep)
- Home maintenance or projects in progress
- Visitors, social plans, or events
- Anything the person tells you about their day
- Decisions made, things purchased, or deliveries expected
Keep each note_save entry short (one line). Call it silently — don't announce you're saving \
a note. When in doubt about whether something is "noteworthy enough", save it. The daily log \
is meant to be a rich record of household life, not just major events.

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
    "contact_note",
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

# Tools that write shared/household data. In DMs, the first attempt is
# blocked so the LLM asks the user to confirm. The block fires once per
# tool name per run() call — after the user confirms, the retry goes through.
# Each predicate returns True when the call targets household data.
_HOUSEHOLD_WRITE_TOOLS: dict[str, Callable[[dict[str, Any]], bool]] = {
    # contact_note: blocked when person is absent (default → household)
    "contact_note": lambda args: "person" not in args or args.get("person") is None,
    # memory_save to "household" workspace
    "memory_save": lambda args: args.get("person") == HOUSEHOLD_WORKSPACE,
    # household_share: always blocked on first attempt in DMs
    "household_share": lambda _: True,
}


# Minimum length for an interim message to be worth sending.
# Short filler like "Let me check" / "Un momento" / "ちょっと待って" are all
# under this threshold regardless of language.
_INTERIM_MIN_CHARS = 40

# Phrases that indicate the LLM is planning/deliberating, not addressing the user.
# When 3+ of these appear in a single interim block, it's a self-talk chain.
_SELF_TALK_RE = re.compile(
    r"\b(?:Let me|I need to|I'll |I should|Actually[,: ]|I'm going to"
    r"|I have to|I want to|Let's )\b",
    re.IGNORECASE,
)


def _is_substantive_interim(text: str) -> bool:
    """Return True if the interim text is worth sending to the user."""
    if len(text) < _INTERIM_MIN_CHARS:
        return False
    # Suppress preamble that just introduces the next tool call
    if text.rstrip().endswith(":"):
        return False
    # Suppress LLM deliberation / self-talk chains (e.g. "Let me try...
    # Actually, I need to... I'll download... Actually, let me...")
    return len(_SELF_TALK_RE.findall(text)) < 3


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
        note_detail_level: str = "normal",
        fast_provider: LLMProvider | None = None,
        vision_provider: LLMProvider | None = None,
    ) -> None:
        self._provider = provider
        self._fast_provider = fast_provider
        self._vision_provider = vision_provider
        self._registry = registry
        self._workspaces = workspaces
        self._semantic_memory = semantic_memory
        self._on_tool_call = on_tool_call
        self._routing = routing
        self._admin_check = admin_check or (lambda _: True)
        self._note_detail_level = note_detail_level
        self._lock_pool = LockPool()
        self._on_interim: InterimCallback | None = None
        self._household_confirmed: set[str] = set()
        # Track last activity per session for idle-based consolidation
        self._last_activity: dict[str, float] = {}
        self._consolidation_task: asyncio.Task[None] | None = None
        self._current_model: str = getattr(provider, "model", "unknown")

    def reload_providers(
        self,
        provider: "LLMProvider",
        fast_provider: "LLMProvider | None" = None,
        vision_provider: "LLMProvider | None" = None,
    ) -> None:
        """Hot-swap providers without restarting the agent loop."""
        self._provider = provider
        self._fast_provider = fast_provider
        self._vision_provider = vision_provider
        self._current_model = getattr(provider, "model", "unknown")

    def _pick_provider(self, call_type: CallType, *, has_images: bool = False) -> LLMProvider:
        """Return the appropriate provider for the call type.

        When *has_images* is True and a vision provider is configured, it takes
        precedence — the main/fast providers may not support image input.
        """
        if has_images and self._vision_provider:
            return self._vision_provider
        if self._fast_provider and call_type in (CallType.TOOL_ONLY, CallType.MEMORY_WRITE):
            return self._fast_provider
        return self._provider

    def _maybe_activate_skill(self, tool_name: str, person: str) -> str | None:
        """Auto-load skill instructions if a skill tool is called without read_skill.

        Returns the skill instructions to prepend to the tool result, or None.
        """
        if "__" not in tool_name:
            return None
        skill_name = tool_name.split("__", 1)[0]

        from homeclaw.agent.tools import activated_skills, load_skill_instructions

        if skill_name in activated_skills:
            return None

        instructions = load_skill_instructions(self._workspaces, person, skill_name)
        if instructions:
            logger.info("Auto-activated skill '%s' for tool %s", skill_name, tool_name)
        return instructions

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
        interim_callback: InterimCallback | None = None,
    ) -> str:
        """Run the agent loop for a message.

        Args:
            user_message: The user's message — either a plain string or a list
                of content blocks (text + images) for multimodal input.
            person: Household member name (for context/memory).
            channel: If set, use shared history keyed by this channel ID
                     and restrict context to household-level facts only.
            call_type: The type of call for model routing.
            interim_callback: Per-call callback for interim responses. Takes
                precedence over the instance-level callback set via
                :meth:`set_interim_callback`. Avoids race conditions when
                multiple callers share the same AgentLoop.
        """
        person = person.lower()
        history_key = channel or person
        async with self._lock_pool.lock_for(history_key):
            result = await self._run_inner(
                user_message, person, channel, call_type, history_key,
                interim_callback=interim_callback,
            )
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
        interim_callback: InterimCallback | None = None,
    ) -> str:
        # Reset per-run state
        self._household_confirmed.clear()

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

        # Inject note-taking level guidance
        level = self._note_detail_level
        if level == "minimal":
            system += (
                "\n\nNote-taking level: MINIMAL. Only save notes for truly significant events "
                "— major decisions, important plans, health emergencies. Skip routine daily activities."
            )
        elif level == "detailed":
            system += (
                "\n\nNote-taking level: DETAILED. Save notes aggressively for almost everything "
                "mentioned — meals, activities, moods, weather observations, conversations, "
                "purchases, plans, ideas, health, exercise, chores. The household wants a rich, "
                "comprehensive daily journal. When in doubt, always save."
            )
        # "normal" gets no extra injection — the base prompt covers it

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

        # Detect if this request includes images — used to route to the
        # vision provider when the main provider lacks image support.
        has_images = isinstance(user_message, list) and any(
            isinstance(b, dict) and b.get("type") == "image" for b in user_message
        )

        # Apply model routing if configured
        current_call_type = call_type
        active_provider = self._provider
        model = getattr(active_provider, "model", "unknown")
        if self._routing:
            model = route_model(call_type, self._routing)
            active_provider = self._pick_provider(current_call_type, has_images=has_images)
            if has_images and self._vision_provider and self._routing.vision_model:
                model = self._routing.vision_model
            if hasattr(active_provider, "model"):
                active_provider.model = model  # type: ignore[attr-defined]
            suffix = " (vision)" if has_images and self._vision_provider else ""
            logger.debug("Routed %s → %s%s", call_type.value, model, suffix)
        self._current_model = model

        for _ in range(MAX_TOOL_ROUNDS):
            token_limit = max_tokens_for(current_call_type, self._routing) if self._routing else None
            response = await active_provider.complete(
                messages=history,
                tools=tools,
                system=system,
                max_tokens=token_limit,
            )

            extra = {"model": model}

            # Log the LLM response — full text and tool details
            if response.tool_calls:
                for tc in response.tool_calls:
                    args_str = json.dumps(tc.arguments, default=str)
                    logger.info("Tool use: %s(%s)", tc.name, args_str, extra=extra)
                if response.content:
                    logger.info("LLM thinking: %s", response.content, extra=extra)
            elif response.content:
                logger.info("LLM response: %s", response.content, extra=extra)

            # Always append the assistant message — include tool_calls and
            # reasoning so providers can round-trip thinking blocks between
            # tool rounds (required by OpenRouter reasoning models, MiniMax, etc.)
            history.append(Message(
                role="assistant",
                content=response.content or "",
                tool_calls=response.tool_calls,
                reasoning=response.reasoning,
            ))

            if response.stop_reason != "tool_use" or not response.tool_calls:
                break

            # Send interim text to user if the LLM said something substantive
            # alongside its tool calls (e.g. "Connecting to Home Assistant...")
            on_interim = interim_callback or self._on_interim
            if response.content and on_interim:
                text = response.content.strip()
                if _is_substantive_interim(text):
                    result = on_interim(text)
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

            # Re-route: use cheaper model/provider for follow-up if tools were simple.
            # When images are present, keep using the vision provider since the
            # image content blocks are still in the conversation history.
            if self._routing:
                tool_names = [tc.name for tc in response.tool_calls]
                current_call_type = classify_tool_round(tool_names)
                model = route_model(current_call_type, self._routing)
                active_provider = self._pick_provider(current_call_type, has_images=has_images)
                if has_images and self._vision_provider and self._routing.vision_model:
                    model = self._routing.vision_model
                if hasattr(active_provider, "model"):
                    active_provider.model = model  # type: ignore[attr-defined]
                    logger.debug("Re-routed after tools %s → %s (%s)", tool_names, model, current_call_type.value)
                self._current_model = model
                extra = {"model": model}

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
            # Allow "household" through — it's an explicit shared-write that the
            # household-write guard below will handle.
            if is_dm and tc.name in _PERSONAL_WRITE_TOOLS and "person" in args:
                requested = args["person"]
                if requested != person and requested != HOUSEHOLD_WORKSPACE:
                    logger.info(
                        "Tool %s: overriding person %r → %r (DM enforcement)",
                        tc.name, requested, person,
                    )
                    args["person"] = person

            # In DMs, block tools that would write to household without
            # explicit user confirmation. Return an error so the LLM asks the
            # user. The block fires once per tool name per run() call — after
            # the user confirms and the LLM retries, it goes through.
            if is_dm and tc.name in _HOUSEHOLD_WRITE_TOOLS:
                check = _HOUSEHOLD_WRITE_TOOLS[tc.name]
                if check(args) and tc.name not in self._household_confirmed:
                    self._household_confirmed.add(tc.name)
                    logger.info(
                        "Tool %s: blocked household write in DM — asking LLM to confirm",
                        tc.name,
                    )
                    results.append({
                        "error": (
                            "This would save to the shared household — visible to all members. "
                            "Ask the user: should this be shared with the household, or kept "
                            "private? If private, use the person parameter with the user's name."
                        ),
                    })
                    continue

            if self._on_tool_call is not None:
                self._on_tool_call(tc.name, args)
            handler = self._registry.get_handler(tc.name)
            if handler is None:
                results.append({"error": f"Unknown tool: {tc.name}"})
                continue
            try:
                # Auto-activate skill: if a skill tool is called without
                # read_skill, load the SKILL.md instructions and prepend
                # them to the tool result so the LLM has full context.
                skill_preamble = self._maybe_activate_skill(tc.name, person)

                result = await handler(**args)
                if skill_preamble:
                    result = {"_skill_instructions": skill_preamble, **result}
                result_str = json.dumps(result, default=str)
                logger.info(
                    "Tool result: %s → %s",
                    tc.name, result_str[:2000],
                    extra={"model": self._current_model},
                )
                results.append(result)
                asyncio.create_task(
                    _log_tool_event(
                        self._workspaces, tc.name, args, person,
                        self._fast_provider or self._provider,
                    ),
                )
            except Exception as e:
                logger.exception("Tool %s failed", tc.name)
                results.append({"error": f"Tool {tc.name} failed: {e}"})
        return results


# Tools worth surfacing in the activity feed (write/action tools only).
# Read-only tools like contact_list, memory_read, note_get are excluded.
_FEED_WORTHY_TOOLS: set[str] = {
    "memory_save",
    "note_save",
    "reminder_add",
    "reminder_complete",
    "reminder_delete",
    "contact_update",
    "contact_note",
    "interaction_log",
    "bookmark_save",
    "bookmark_delete",
    "message_send",
    "image_send",
    "routine_run",
    "routine_add",
    "routine_update",
    "routine_remove",
    "decision_log",
    "household_share",
    "skill_create",
    "skill_install",
    "channel_preference_set",
}

_SUMMARISE_PROMPT = """\
You are writing a short activity log entry for a household assistant app.

Given a tool call, write a single concise sentence (max 80 chars) describing \
what happened in plain English. Use past tense. Be specific — include names, \
topics, or titles from the arguments when available.

Examples:
- tool=memory_save args={"topic":"food","person":"alice"} → Saved a food memory for Alice
- tool=reminder_add args={"person":"bob","note":"dentist"} → Added a dentist reminder for Bob
- tool=message_send args={"person":"carol","text":"hi"} → Sent a message to Carol
- tool=bookmark_save args={"title":"Pasta recipe","url":"..."} → Bookmarked "Pasta recipe"

Respond with ONLY the summary sentence, nothing else."""


async def _log_tool_event(
    workspaces: Path,
    tool_name: str,
    args: dict[str, Any],
    person: str,
    provider: LLMProvider | None,
) -> None:
    """Append a tool use event to the JSONL feed log.

    Uses the fast LLM to generate a human-readable summary. Falls back to
    a basic description if the provider is unavailable or the call fails.
    """
    if tool_name not in _FEED_WORTHY_TOOLS:
        return

    safe_args = {k: str(v)[:100] for k, v in args.items()}
    summary: str | None = None

    if provider is not None:
        try:
            prompt = f"tool={tool_name} args={json.dumps(safe_args, default=str)}"
            resp = await provider.complete(
                messages=[Message(role="user", content=prompt)],
                tools=[],
                system=_SUMMARISE_PROMPT,
                max_tokens=60,
            )
            text = resp.content.strip().rstrip(".")
            if 5 < len(text) < 120:
                summary = text
        except Exception:
            logger.debug("LLM summary failed for %s, using fallback", tool_name)

    if summary is None:
        # Fallback: basic tool name → readable string
        label = tool_name.replace("_", " ")
        summary = f"{label.capitalize()} ({person})"

    log_dir = workspaces / "household" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": datetime.now(UTC).isoformat(),
        "tool": tool_name,
        "summary": summary,
        "person": person,
        "args": safe_args,
    }
    try:
        with open(log_dir / "tool_use.jsonl", "a") as f:
            f.write(json.dumps(entry, default=str) + "\n")
    except OSError:
        logger.debug("Failed to write tool_use.jsonl entry")


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
            if msg.role in ("user", "assistant", "tool"):
                # Strip stale reasoning/thinking blocks — they only matter
                # within a tool chain, not across persisted turns.  Leaving
                # them causes 400s on OpenRouter and other Anthropic proxies
                # that don't accept Anthropic-specific signature fields.
                if msg.reasoning:
                    msg = msg.model_copy(update={"reasoning": []})
                messages.append(msg)
        except Exception:
            continue

    return last_consolidated, messages


def _load_history(workspaces: Path, person: str, max_messages: int = 200) -> list[Message]:
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


_MAX_TOOL_RESULT_CHARS = 4000  # cap individual tool results to avoid history bloat


def _persistable_messages(messages: list[Message]) -> list[Message]:
    """Prepare messages for persistence — all roles kept, images and reasoning stripped."""
    persistent: list[Message] = []
    for m in messages:
        if m.role == "user":
            persistent.append(m.model_copy(update={"content": _strip_images(m.content)}))
        elif m.role == "assistant":
            persistent.append(m.model_copy(update={
                "content": _strip_images(m.content),
                "reasoning": [],  # only needed within tool chains, not across turns
            }))
        elif m.role == "tool":
            # Cap tool results to prevent huge API responses from bloating history
            content = m.content if isinstance(m.content, str) else json.dumps(m.content)
            if len(content) > _MAX_TOOL_RESULT_CHARS:
                content = content[:_MAX_TOOL_RESULT_CHARS] + "\n...(truncated)"
            persistent.append(m.model_copy(update={"content": content}))
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
