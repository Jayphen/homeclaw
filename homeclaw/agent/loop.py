"""Core agent loop — receive message, build context, call LLM, dispatch tools."""

import json
import logging
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from homeclaw.agent.context import build_context
from homeclaw.agent.providers.base import LLMProvider, LLMResponse, Message, ToolCall
from homeclaw.agent.tools import ToolRegistry
from homeclaw.memory.semantic import SemanticMemory

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are homeclaw, an AI assistant for a household. You know the home, \
the family, and the people in their lives. You help the household stay on top of everything — \
schedules, contacts, reminders, home state, and daily routines.

Be warm, concise, and practical. You are speaking with a household member, not a developer.

{context}"""

MAX_TOOL_ROUNDS = 10


class AgentLoop:
    def __init__(
        self,
        provider: LLMProvider,
        registry: ToolRegistry,
        workspaces: Path,
        semantic_memory: SemanticMemory | None = None,
        on_tool_call: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> None:
        self._provider = provider
        self._registry = registry
        self._workspaces = workspaces
        self._semantic_memory = semantic_memory
        self._on_tool_call = on_tool_call

    async def run(self, user_message: str, person: str) -> str:
        context = await build_context(
            message=user_message,
            person=person,
            workspaces=self._workspaces,
            semantic_memory=self._semantic_memory,
        )
        system = SYSTEM_PROMPT.format(context=context)

        history = _load_history(self._workspaces, person)
        history.append(Message(role="user", content=user_message))

        tools = self._registry.get_definitions()
        response: LLMResponse | None = None

        for _ in range(MAX_TOOL_ROUNDS):
            response = await self._provider.complete(
                messages=history,
                tools=tools,
                system=system,
            )

            if response.content:
                history.append(Message(role="assistant", content=response.content))

            if response.stop_reason != "tool_use" or not response.tool_calls:
                break

            # Dispatch tool calls
            tool_results = await self._dispatch_tools(response.tool_calls)
            for tc, result in zip(response.tool_calls, tool_results):
                history.append(
                    Message(
                        role="tool",
                        content=json.dumps(result),
                        tool_call_id=tc.id,
                    )
                )

        _save_history(self._workspaces, person, history)
        return response.content if response else ""

    async def _dispatch_tools(
        self, tool_calls: list[ToolCall]
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for tc in tool_calls:
            if self._on_tool_call is not None:
                self._on_tool_call(tc.name, tc.arguments)
            handler = self._registry.get_handler(tc.name)
            if handler is None:
                results.append({"error": f"Unknown tool: {tc.name}"})
                continue
            try:
                result = await handler(**tc.arguments)
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
            messages.append(Message.model_validate_json(line))
    return messages[-max_messages:]


def _save_history(workspaces: Path, person: str, messages: list[Message]) -> None:
    path = _history_path(workspaces, person)
    lines = [m.model_dump_json() for m in messages[-100:]]
    path.write_text("\n".join(lines) + "\n")
