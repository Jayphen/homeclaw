"""Anthropic SDK implementation of LLMProvider."""

import logging
from typing import Any, Literal

import anthropic

from homeclaw.agent.providers.base import (
    LLMResponse,
    Message,
    ToolCall,
    ToolDefinition,
)

logger = logging.getLogger(__name__)


class AnthropicProvider:
    def __init__(
        self,
        api_key: str,
        model: str,
        enable_prompt_caching: bool = True,
    ) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self.model = model
        self._enable_caching = enable_prompt_caching

    async def complete(
        self,
        messages: list[Message],
        tools: list[ToolDefinition],
        system: str,
    ) -> LLMResponse:
        api_messages = [_to_api_message(m) for m in messages]
        api_tools = [_to_api_tool(t) for t in tools] if tools else []

        # Build system parameter — with or without cache_control
        system_param: str | list[dict[str, Any]] = system
        if self._enable_caching:
            system_param = _cacheable_system(system)

        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": 4096,
            "system": system_param,
            "messages": api_messages,
        }
        if api_tools:
            kwargs["tools"] = api_tools

        response = await self._client.messages.create(**kwargs)

        _log_cache_usage(response)
        return _parse_response(response)


def _cacheable_system(system: str) -> list[dict[str, Any]]:
    """Wrap system prompt as a text block with cache_control.

    Anthropic caches content up to the last cache_control breakpoint.
    We mark the entire system prompt as cacheable since it changes
    slowly (household context updates every few minutes at most).

    OpenRouter: cache_control IS passed through to Anthropic when routing
    to the Anthropic provider directly. OpenRouter uses sticky routing to
    maximize cache hits across requests. Bedrock/Vertex also support
    explicit cache_control breakpoints. See homeclaw-jal for research.
    """
    return [
        {
            "type": "text",
            "text": system,
            "cache_control": {"type": "ephemeral"},
        }
    ]


def _log_cache_usage(response: anthropic.types.Message) -> None:
    """Log cache hit/miss at debug level."""
    usage = response.usage
    created = usage.cache_creation_input_tokens or 0
    read = usage.cache_read_input_tokens or 0
    if created or read:
        logger.debug(
            "Cache: %d tokens read (hit), %d tokens created (miss), "
            "%d input, %d output",
            read, created, usage.input_tokens, usage.output_tokens,
        )


def _to_api_message(message: Message) -> dict[str, Any]:
    if message.role == "tool":
        return {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": message.tool_call_id,
                    "content": message.content if isinstance(message.content, str) else "",
                }
            ],
        }
    return {
        "role": message.role,
        "content": message.content,
    }


def _to_api_tool(tool: ToolDefinition) -> dict[str, Any]:
    return {
        "name": tool.name,
        "description": tool.description,
        "input_schema": tool.parameters,
    }


def _parse_response(response: anthropic.types.Message) -> LLMResponse:
    content_parts: list[str] = []
    tool_calls: list[ToolCall] = []

    for block in response.content:
        if block.type == "text":
            content_parts.append(block.text)
        elif block.type == "tool_use":
            tool_calls.append(
                ToolCall(
                    id=block.id,
                    name=block.name,
                    arguments=dict(block.input) if isinstance(block.input, dict) else {},
                )
            )

    stop_reason_map: dict[str, Literal["end_turn", "tool_use", "max_tokens"]] = {
        "end_turn": "end_turn",
        "tool_use": "tool_use",
        "max_tokens": "max_tokens",
        "pause_turn": "end_turn",
    }

    return LLMResponse(
        content="\n".join(content_parts),
        tool_calls=tool_calls,
        stop_reason=stop_reason_map.get(response.stop_reason or "end_turn", "end_turn"),
    )
