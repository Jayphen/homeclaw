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

You have access to the household's contacts, bookmarks, notes, reminders, and memory. \
Search these before answering questions — the family has been collecting this information \
for a reason.

In a direct message, notes, memory updates, and reminders always belong to the person \
you are talking to. Use their name for the `person` parameter — never attribute their \
notes or reminders to someone else, even if they mention another household member.

Only your final response (after all tool calls are complete) is shown to the user. \
The user cannot see your intermediate thoughts or tool-call responses. Never reference, \
correct, or apologize for something you said during a tool-call round — the user never saw it.

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
    "skill_update",
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


def _history_path(workspaces: Path, key: str) -> Path:
    # Channel/group histories go under household/channels/ to avoid
    # creating top-level directories that look like member workspaces.
    if key.startswith("group-"):
        hist_dir = workspaces / "household" / "channels" / key
    else:
        hist_dir = workspaces / key
    hist_dir.mkdir(parents=True, exist_ok=True)
    return hist_dir / "history.jsonl"


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
    # Strip tool messages and intermediate assistant messages (those with
    # tool_calls) before persisting.  Intermediate assistant content was never
    # shown to the user, and without accompanying tool results it confuses
    # the model in future conversations (it may reference or "correct"
    # things the user never saw).
    persistent: list[Message] = []
    for m in messages:
        if m.role == "user":
            # Replace image blocks with text placeholders to avoid storing large base64
            persistent.append(m.model_copy(update={"content": _strip_images(m.content)}))
        elif m.role == "assistant" and not m.tool_calls:
            persistent.append(m.model_copy(update={"content": _strip_images(m.content)}))
        # Skip tool messages and intermediate assistant messages (with tool_calls)
    lines = [m.model_dump_json() for m in persistent[-100:]]
    path.write_text("\n".join(lines) + "\n")
