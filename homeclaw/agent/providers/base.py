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


class ReasoningBlock(BaseModel):
    """A single reasoning/thinking block from the LLM."""
    type: str = "thinking"  # "thinking" for Anthropic, "reasoning" for OpenAI/OpenRouter
    content: str = ""
    signature: str | None = None  # Anthropic requires this for round-tripping thinking blocks


class Message(BaseModel):
    role: Literal["user", "assistant", "tool"]
    content: str | list[Any]
    tool_call_id: str | None = None
    tool_calls: list["ToolCall"] = []
    reasoning: list[ReasoningBlock] = []


class LLMResponse(BaseModel):
    content: str
    tool_calls: list[ToolCall] = []
    stop_reason: Literal["end_turn", "tool_use", "max_tokens"]
    reasoning: list[ReasoningBlock] = []


class LLMProvider(Protocol):
    context_window: int

    async def complete(
        self,
        messages: list[Message],
        tools: list[ToolDefinition],
        system: str,
        max_tokens: int | None = None,
    ) -> LLMResponse: ...
