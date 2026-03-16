"""OpenAI-compatible LLM provider — covers OpenAI, Ollama, OpenRouter, Groq, etc."""

import json
from typing import Any, Literal

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletion
from openai.types.chat.chat_completion_message_tool_call import ChatCompletionMessageToolCall

from homeclaw.agent.providers.base import (
    LLMResponse,
    Message,
    ToolCall,
    ToolDefinition,
)


class OpenAIProvider:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str = "gpt-4o",
    ) -> None:
        kwargs: dict[str, Any] = {}
        if api_key:
            kwargs["api_key"] = api_key
        if base_url:
            kwargs["base_url"] = base_url
        self._client = AsyncOpenAI(**kwargs)
        self.model = model

    async def complete(
        self,
        messages: list[Message],
        tools: list[ToolDefinition],
        system: str,
    ) -> LLMResponse:
        api_messages: list[dict[str, Any]] = [{"role": "system", "content": system}]
        api_messages.extend(_to_api_message(m) for m in messages)

        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": api_messages,
        }
        if tools:
            kwargs["tools"] = [_to_api_tool(t) for t in tools]

        response = await self._client.chat.completions.create(**kwargs)
        return _parse_response(response)


def _to_api_message(message: Message) -> dict[str, Any]:
    if message.role == "tool":
        return {
            "role": "tool",
            "tool_call_id": message.tool_call_id or "",
            "content": message.content if isinstance(message.content, str) else "",
        }
    if message.role == "assistant":
        msg: dict[str, Any] = {
            "role": "assistant",
            "content": message.content if isinstance(message.content, str) else "",
        }
        if message.tool_calls:
            msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": json.dumps(tc.arguments),
                    },
                }
                for tc in message.tool_calls
            ]
        return msg
    if isinstance(message.content, str):
        return {"role": "user", "content": message.content}
    # Multimodal: convert content blocks to OpenAI format
    parts: list[dict[str, Any]] = []
    for block in message.content:
        if isinstance(block, dict) and block.get("type") == "text":
            parts.append({"type": "text", "text": block["text"]})
        elif isinstance(block, dict) and block.get("type") == "image":
            source = block.get("source", {})
            media_type = source.get("media_type", "image/jpeg")
            data = source.get("data", "")
            parts.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:{media_type};base64,{data}",
                },
            })
    return {"role": "user", "content": parts if parts else ""}


def _to_api_tool(tool: ToolDefinition) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters,
        },
    }


def _parse_response(response: ChatCompletion) -> LLMResponse:
    choice = response.choices[0]
    message = choice.message

    content = message.content or ""
    tool_calls: list[ToolCall] = []

    if message.tool_calls:
        for tc in message.tool_calls:
            if not isinstance(tc, ChatCompletionMessageToolCall):
                continue
            try:
                arguments = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                arguments = {}
            tool_calls.append(
                ToolCall(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=arguments,
                )
            )

    finish_reason_map: dict[str, Literal["end_turn", "tool_use", "max_tokens"]] = {
        "stop": "end_turn",
        "tool_calls": "tool_use",
        "length": "max_tokens",
    }

    return LLMResponse(
        content=content,
        tool_calls=tool_calls,
        stop_reason=finish_reason_map.get(choice.finish_reason or "stop", "end_turn"),
    )
