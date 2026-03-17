"""LLM provider abstraction — the agent loop never imports a specific SDK."""

from typing import Any, Literal, Protocol

from pydantic import BaseModel


class ToolDefinition(BaseModel):
    name: str
    description: str
    parameters: dict[str, Any]


class ToolCall(BaseModel):
    id: str
    name: str
    arguments: dict[str, Any]


class Message(BaseModel):
    role: Literal["user", "assistant", "tool"]
    content: str | list[Any]
    tool_call_id: str | None = None
    tool_calls: list["ToolCall"] = []


class LLMResponse(BaseModel):
    content: str
    tool_calls: list[ToolCall] = []
    stop_reason: Literal["end_turn", "tool_use", "max_tokens"]


class LLMProvider(Protocol):
    async def complete(
        self,
        messages: list[Message],
        tools: list[ToolDefinition],
        system: str,
        max_tokens: int | None = None,
    ) -> LLMResponse: ...
