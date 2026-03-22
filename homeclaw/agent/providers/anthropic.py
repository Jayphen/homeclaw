"""Anthropic SDK implementation of LLMProvider."""

import logging
from typing import Any, Literal

import anthropic
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from homeclaw.agent.providers.base import (
    LLMResponse,
    Message,
    ToolCall,
    ToolDefinition,
)

logger = logging.getLogger(__name__)


def _is_retryable_anthropic(exc: BaseException) -> bool:
    """Return True for transient Anthropic errors worth retrying."""
    if isinstance(exc, anthropic.RateLimitError):
        return True
    if isinstance(exc, anthropic.APIStatusError) and exc.status_code >= 500:
        return True
    if isinstance(exc, anthropic.APIConnectionError):
        return True
    return False


class AnthropicProvider:
    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str | None = None,
        enable_prompt_caching: bool = True,
        context_window: int = 200_000,
    ) -> None:
        kwargs: dict[str, Any] = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self._client = anthropic.AsyncAnthropic(**kwargs)
        self.model = model
        self.context_window = context_window
        self._enable_caching = enable_prompt_caching

    @retry(
        retry=retry_if_exception(_is_retryable_anthropic),
        wait=wait_exponential(multiplier=1, min=1, max=30),
        stop=stop_after_attempt(4),
        before_sleep=lambda rs: logger.warning(
            "Anthropic API error (attempt %d), retrying: %s",
            rs.attempt_number,
            rs.outcome.exception() if rs.outcome else "unknown",
        ),
        reraise=True,
    )
    async def complete(
        self,
        messages: list[Message],
        tools: list[ToolDefinition],
        system: str,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        api_messages = [_to_api_message(m) for m in messages]
        api_tools = [_to_api_tool(t) for t in tools] if tools else []

        # Build system parameter — with or without cache_control
        system_param: str | list[dict[str, Any]] = system
        if self._enable_caching:
            system_param = _cacheable_system(system)

        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_tokens or 4096,
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
