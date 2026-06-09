"""Core agent loop — receive message, build context, call LLM, dispatch tools."""

import asyncio
import json
import logging
from collections.abc import Callable
from typing import Any

from homeclaw.agent.activity_log import append_chat_log, log_tool_event
from homeclaw.agent.additional_context import build_additional_context
from homeclaw.agent.consolidation import CONSOLIDATION_THRESHOLD, SessionConsolidator
from homeclaw.agent.context import HOUSEHOLD_WORKSPACE, build_context, estimate_tokens
from homeclaw.agent.history import (
    DEFAULT_CONTEXT_WINDOW,
    LIVE_HISTORY_TOKEN_FRACTION,
    RESERVED_FRACTION,
    append_turn,
    estimate_message_tokens,
    estimate_tool_tokens,
    load_history,
    reset_history,
    truncate_history,
)
from homeclaw.agent.interim import PROGRESS_INTERVAL, is_substantive_interim
from homeclaw.agent.prompts import (
    ROUTINE_PREAMBLE,
    append_additional_context,
    build_system_prompt,
)
from homeclaw.agent.providers.base import LLMProvider, LLMResponse, Message, ToolCall
from homeclaw.agent.routing import (
    CallType,
    RoutingConfig,
    classify_tool_round,
    max_tokens_for,
    route_model,
)
from homeclaw.agent.runtime_state import (
    PromptSnapshot,
    RuntimeObservability,
    SkillActivationEvent,
    ToolPolicyEntry,
    now_utc,
)
from homeclaw.agent.tool_policy import describe_tool_policies
from homeclaw.agent.tools import ToolRegistry
from homeclaw.locking import LockPool
from homeclaw.memory.semantic import SemanticMemory

logger = logging.getLogger(__name__)

MAX_TOOL_ROUNDS = 40

InterimCallback = Callable[[str], Any]


class AgentLoop:
    def __init__(
        self,
        provider: LLMProvider,
        registry: ToolRegistry,
        workspaces: Any,
        semantic_memory: SemanticMemory | None = None,
        on_tool_call: Callable[[str, dict[str, Any]], None] | None = None,
        routing: RoutingConfig | None = None,
        admin_check: Callable[[str], bool] | None = None,
        note_detail_level: str = "normal",
        fast_provider: LLMProvider | None = None,
        vision_provider: LLMProvider | None = None,
        runtime_observability: RuntimeObservability | None = None,
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
        self._current_model: str = getattr(provider, "model", "unknown")
        self._runtime_observability = runtime_observability
        self._consolidator = SessionConsolidator(
            workspaces=workspaces,
            lock_pool=self._lock_pool,
            routing=routing,
            runtime_observability=runtime_observability,
        )
        self._consolidator.set_provider(provider)

    def reload_providers(
        self,
        provider: "LLMProvider",
        fast_provider: "LLMProvider | None" = None,
        vision_provider: "LLMProvider | None" = None,
        note_detail_level: str | None = None,
    ) -> None:
        """Hot-swap providers without restarting the agent loop."""
        self._provider = provider
        self._fast_provider = fast_provider
        self._vision_provider = vision_provider
        self._current_model = getattr(provider, "model", "unknown")
        if note_detail_level is not None:
            self._note_detail_level = note_detail_level
        self._consolidator.set_provider(provider)

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
            if self._runtime_observability is not None:
                self._runtime_observability.record_skill_activation(
                    SkillActivationEvent(
                        skill_name=skill_name,
                        person=person,
                        reason="auto_tool_use",
                        tool_name=tool_name,
                        activated_at=now_utc(),
                    )
                )
        return instructions

    def set_interim_callback(self, callback: InterimCallback | None) -> None:
        """Set a callback for interim responses during tool rounds.

        The callback is called with the text content when the LLM produces
        text alongside tool calls (e.g. "Trying to connect to HA...").
        The text is sent to the user immediately before tool execution continues.
        Can be sync or async.
        """
        self._on_interim = callback

    def tool_policy_snapshot(self) -> list[ToolPolicyEntry]:
        """Return deterministic policy classifications for current tools."""
        return describe_tool_policies(self._registry)

    def start_background_consolidation(self) -> None:
        """Start the background consolidation loop (call once at startup)."""
        self._consolidator.start()

    async def run(
        self,
        user_message: str | list[Any],
        person: str,
        channel: str | None = None,
        call_type: CallType = CallType.CONVERSATION,
        interim_callback: InterimCallback | None = None,
        metadata: dict[str, Any] | None = None,
        source_channel: str | None = None,
        persist_history: bool = True,
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
            metadata: If provided, populated with debug info (model, tools,
                rounds, duration_ms) after execution completes.
            source_channel: User-facing channel label for per-turn context
                (e.g. telegram_dm, whatsapp_group, web).
            persist_history: When false, run with an empty conversation window
                and do not append the turn to history. Scheduled routines use
                this so previous routine outputs never become future prompt
                context.
        """
        person = person.lower()
        history_key = channel or person
        async with self._lock_pool.lock_for(history_key):
            result = await self._run_inner(
                user_message,
                person,
                channel,
                call_type,
                history_key,
                interim_callback=interim_callback,
                metadata=metadata,
                source_channel=source_channel,
                persist_history=persist_history,
            )
            if persist_history:
                # Record activity for idle-based consolidation.
                self._consolidator.touch(history_key)
            return result

    async def reset_conversation(self, person: str, channel: str | None = None) -> int:
        """Start a fresh conversation for a person/channel (the ``/new`` command).

        Mirrors :meth:`run`'s key derivation and takes the same per-session lock
        so a reset cannot race a turn in flight. The append-only history file is
        preserved on disk; only the live context window is cleared. Returns the
        number of messages dropped from the live window.
        """
        person = person.lower()
        history_key = channel or person
        async with self._lock_pool.lock_for(history_key):
            cleared = reset_history(self._workspaces, history_key)
            self._consolidator.touch(history_key)
            return cleared

    async def _run_inner(
        self,
        user_message: str | list[Any],
        person: str,
        channel: str | None,
        call_type: CallType,
        history_key: str,
        interim_callback: InterimCallback | None = None,
        metadata: dict[str, Any] | None = None,
        source_channel: str | None = None,
        persist_history: bool = True,
    ) -> str:
        import time

        t0 = time.monotonic()
        tool_names_used: list[str] = []
        tool_rounds = 0
        rounds_since_interim = 0

        # Reset per-run state
        self._household_confirmed.clear()

        # Extract text portion for context building
        if isinstance(user_message, str):
            text_for_context = user_message
        else:
            text_for_context = " ".join(
                block["text"]
                for block in user_message
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
        system, prompt_sections = build_system_prompt(context, self._note_detail_level)

        history = load_history(self._workspaces, history_key) if persist_history else []

        # Prepend routine preamble so the LLM knows to use web tools
        if call_type == CallType.ROUTINE and isinstance(user_message, str):
            user_message = ROUTINE_PREAMBLE + user_message

        if call_type == CallType.CONVERSATION:
            additional_context = build_additional_context(
                workspaces=self._workspaces,
                person=person,
                channel_label=source_channel,
                include_sender=channel is not None,
            )
            user_message = append_additional_context(user_message, additional_context)

        user_turn_message = Message(role="user", content=user_message)
        history.append(user_turn_message)
        # Persistence is append-only and must NOT be driven by the (bounded,
        # truncated) LLM context window — track only this turn's new messages so
        # unconsolidated history truncated out of the window is never lost on save.
        new_messages: list[Message] = [user_turn_message]

        # Truncate history to fit within the model's context window.
        context_window = getattr(self._provider, "context_window", DEFAULT_CONTEXT_WINDOW)
        system_tokens = estimate_tokens(system)
        history_capacity = int(context_window * (1 - RESERVED_FRACTION)) - system_tokens
        live_history_budget = min(
            history_capacity,
            int(context_window * LIVE_HISTORY_TOKEN_FRACTION),
        )
        compaction_threshold = int(
            int(context_window * (1 - RESERVED_FRACTION)) * CONSOLIDATION_THRESHOLD
        )
        history = truncate_history(history, system_tokens, context_window)

        tools = self._registry.get_definitions()
        history_tokens = sum(estimate_message_tokens(message) for message in history)
        tool_tokens = estimate_tool_tokens(tools)
        total_tokens = system_tokens + history_tokens + tool_tokens
        prompt_debug = {
            "call_type": call_type.value,
            "context_window": context_window,
            "message_count": len(history),
            "history_budget": live_history_budget,
            "history_capacity": history_capacity,
            "compaction_threshold": compaction_threshold,
            "token_estimates": {
                "system": system_tokens,
                "history": history_tokens,
                "tools": tool_tokens,
                "total": total_tokens,
            },
            "prompt_sections": [section.name for section in prompt_sections],
        }
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
        if self._runtime_observability is not None:
            self._runtime_observability.record_prompt_snapshot(
                PromptSnapshot(
                    history_key=history_key,
                    person=person,
                    channel=channel,
                    call_type=call_type.value,
                    model=model,
                    tool_count=len(tools),
                    system_token_estimate=system_tokens,
                    history_token_estimate=history_tokens,
                    tool_token_estimate=tool_tokens,
                    total_token_estimate=total_tokens,
                    message_count=len(history),
                    sections=prompt_sections,
                    captured_at=now_utc(),
                )
            )

        for _ in range(MAX_TOOL_ROUNDS):
            token_limit = (
                max_tokens_for(current_call_type, self._routing) if self._routing else None
            )
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
            assistant_message = Message(
                role="assistant",
                content=response.content or "",
                tool_calls=response.tool_calls,
                reasoning=response.reasoning,
            )
            history.append(assistant_message)
            new_messages.append(assistant_message)

            if response.stop_reason != "tool_use" or not response.tool_calls:
                break

            # Send interim text to user if the LLM said something substantive
            # alongside its tool calls (e.g. "Connecting to Home Assistant...")
            on_interim = interim_callback or self._on_interim
            interim_sent = False
            if response.content and on_interim:
                text = response.content.strip()
                if is_substantive_interim(text):
                    result = on_interim(text)
                    # Support both sync and async callbacks
                    if hasattr(result, "__await__"):
                        await result
                    interim_sent = True

            # Dispatch tool calls
            tool_rounds += 1
            tool_names_used.extend(tc.name for tc in response.tool_calls)
            tool_results = await self._dispatch_tools(
                response.tool_calls,
                person=person,
                channel=channel,
                call_type=call_type,
            )
            for tc, result in zip(response.tool_calls, tool_results, strict=False):
                tool_message = Message(
                    role="tool",
                    content=json.dumps(result),
                    tool_call_id=tc.id,
                )
                history.append(tool_message)
                new_messages.append(tool_message)

            # Track consecutive silent rounds and send a proactive heartbeat
            # so the user knows the agent is still working during long operations
            # (e.g. bulk db_execute calls that produce no LLM-generated text).
            if interim_sent:
                rounds_since_interim = 0
            else:
                rounds_since_interim += 1
                if rounds_since_interim >= PROGRESS_INTERVAL and on_interim:
                    tool_summary = ", ".join(dict.fromkeys(tc.name for tc in response.tool_calls))
                    progress_text = f"Still working… (step {tool_rounds}, using {tool_summary})"
                    prog_result = on_interim(progress_text)
                    if hasattr(prog_result, "__await__"):
                        await prog_result
                    rounds_since_interim = 0

            # After the vision model's first response, strip image blocks
            # from history so subsequent rounds can use the fast model.
            # The vision model's text response already captures what it saw.
            if has_images:
                from homeclaw.agent.history import strip_images

                for i, msg in enumerate(history):
                    if isinstance(msg.content, list) and any(
                        isinstance(b, dict) and b.get("type") == "image" for b in msg.content
                    ):
                        history[i] = msg.model_copy(
                            update={"content": strip_images(msg.content)},
                        )
                has_images = False

            # Re-route: use cheaper model/provider for follow-up tool rounds.
            if self._routing:
                tool_names = [tc.name for tc in response.tool_calls]
                if any("error" in result for result in tool_results):
                    current_call_type = CallType.CONVERSATION
                else:
                    current_call_type = classify_tool_round(tool_names)
                model = route_model(current_call_type, self._routing)
                active_provider = self._pick_provider(current_call_type, has_images=has_images)
                if hasattr(active_provider, "model"):
                    active_provider.model = model  # type: ignore[attr-defined]
                    logger.debug(
                        "Re-routed after tools %s → %s (%s)",
                        tool_names,
                        model,
                        current_call_type.value,
                    )
                self._current_model = model
                extra = {"model": model}

        if response and response.stop_reason == "max_tokens":
            logger.warning("LLM output truncated at max_tokens — suppressing raw content")
            if persist_history:
                append_turn(self._workspaces, history_key, new_messages)
            if metadata is not None:
                metadata.update(
                    model=self._current_model,
                    tools=tool_names_used,
                    tool_rounds=tool_rounds,
                    stop_reason=response.stop_reason,
                    duration_ms=int((time.monotonic() - t0) * 1000),
                    **prompt_debug,
                )
            return (
                "Sorry, I ran out of output space before finishing. "
                "The data might be too large for a single response — "
                "try breaking it into smaller requests, or start a fresh conversation."
            )

        if response and response.stop_reason == "tool_use":
            logger.warning(
                "Agent loop exhausted %d tool rounds without completing", MAX_TOOL_ROUNDS
            )
            # Surface the exhaustion to the user instead of returning partial content.
            if persist_history:
                append_turn(self._workspaces, history_key, new_messages)
            if metadata is not None:
                metadata.update(
                    model=self._current_model,
                    tools=tool_names_used,
                    tool_rounds=tool_rounds,
                    stop_reason=response.stop_reason,
                    duration_ms=int((time.monotonic() - t0) * 1000),
                    **prompt_debug,
                )
            return (
                response.content + "\n\n"
                "(I ran out of tool rounds before finishing — "
                "please try a simpler request or ask me to continue.)"
                if response.content
                else "Sorry, I wasn't able to complete that — I ran out of steps. "
                "Try a simpler request or ask me to continue."
            )

        if persist_history:
            append_turn(self._workspaces, history_key, new_messages)

        # Log group chat exchanges so memsearch can index them — lets
        # members reference group conversations from private DMs.
        if channel and channel.startswith("group-") and response and response.content:
            append_chat_log(
                self._workspaces,
                channel,
                text_for_context,
                response.content,
            )

        if metadata is not None:
            metadata.update(
                model=self._current_model,
                tools=tool_names_used,
                tool_rounds=tool_rounds,
                stop_reason=response.stop_reason if response else None,
                duration_ms=int((time.monotonic() - t0) * 1000),
                **prompt_debug,
            )

        return response.content if response else ""

    async def _dispatch_tools(
        self,
        tool_calls: list[ToolCall],
        person: str,
        channel: str | None,
        call_type: CallType = CallType.CONVERSATION,
    ) -> list[dict[str, Any]]:
        is_dm = channel is None
        results: list[dict[str, Any]] = []
        for tc in tool_calls:
            policy = self._registry.get_policy(tc.name)

            # Routines: block tools that deliver output via the channel dispatcher
            # to prevent double-sends (scheduler handles delivery).
            if call_type == CallType.ROUTINE and policy is not None and policy.routine_blocked:
                results.append(
                    {
                        "status": "skipped",
                        "reason": "Routine output is delivered automatically by the scheduler.",
                    }
                )
                continue

            args = dict(tc.arguments)

            # Normalize person names to lowercase to prevent duplicate workspaces.
            if "person" in args and isinstance(args["person"], str):
                args["person"] = args["person"].lower()

            # Admin-only enforcement: block non-admins before the handler runs.
            if policy is not None and policy.admin_only and not self._admin_check(person):
                results.append({"error": f"Tool '{tc.name}' requires admin access."})
                continue

            # In DMs, force personal-scope tools to the authenticated caller.
            # Allow "household" through — it's an explicit shared-write that the
            # household-confirm guard below will handle.
            if is_dm and policy is not None and policy.scope == "personal" and "person" in args:
                requested = args["person"]
                if requested != person and requested != HOUSEHOLD_WORKSPACE:
                    label = (
                        "DM write enforcement"
                        if policy.access == "write"
                        else "DM read enforcement"
                    )
                    logger.info(
                        "Tool %s: overriding person %r → %r (%s)",
                        tc.name,
                        requested,
                        person,
                        label,
                    )
                    args["person"] = person

            # In DMs, block tools that would write to shared household data without
            # explicit user confirmation. The block fires once per tool per run()
            # call — after the user confirms and the LLM retries, it goes through.
            if (
                is_dm
                and policy is not None
                and policy.household_confirm is not None
                and policy.household_confirm(args)
                and tc.name not in self._household_confirmed
            ):
                self._household_confirmed.add(tc.name)
                logger.info(
                    "Tool %s: blocked household write in DM — asking LLM to confirm",
                    tc.name,
                )
                results.append(
                    {
                        "error": (
                            "This would save to the shared household — visible to all members. "
                            "Ask the user: should this be shared with the household, or kept "
                            "private? If private, use the person parameter with the user's name."
                        ),
                    }
                )
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
                    tc.name,
                    result_str[:2000],
                    extra={"model": self._current_model},
                )
                results.append(result)
                asyncio.create_task(
                    log_tool_event(
                        self._workspaces,
                        tc.name,
                        args,
                        person,
                        self._fast_provider or self._provider,
                    ),
                )
            except Exception as e:
                logger.exception("Tool %s failed", tc.name)
                results.append({"error": f"Tool {tc.name} failed: {e}"})
        return results
