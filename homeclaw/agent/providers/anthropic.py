"""Anthropic SDK implementation of LLMProvider."""

from typing import Any, Literal

import anthropic

from homeclaw.agent.providers.base import (
    LLMResponse,
    Message,
    ToolCall,
    ToolDefinition,
)


class AnthropicProvider:
    def __init__(self, api_key: str, model: str) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._model = model

    async def complete(
        self,
        messages: list[Message],
        tools: list[ToolDefinition],
        system: str,
    ) -> LLMResponse:
        api_messages = [_to_api_message(m) for m in messages]
        api_tools = [_to_api_tool(t) for t in tools] if tools else []

        kwargs: dict[str, Any] = {
            "model": self._model,
            "max_tokens": 4096,
            "system": system,
            "messages": api_messages,
        }
        if api_tools:
            kwargs["tools"] = api_tools

        response = await self._client.messages.create(**kwargs)

        return _parse_response(response)


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
