"""Per-call model routing — selects the appropriate model for each LLM call type."""

from enum import Enum

from pydantic import BaseModel


class CallType(Enum):
    CONVERSATION = "conversation"  # user message, needs reasoning
    ROUTINE = "routine"  # scheduled heartbeat task
    TOOL_ONLY = "tool_only"  # simple tool call, no reasoning needed
    MEMORY_WRITE = "memory_write"  # saving a fact or note


class RoutingConfig(BaseModel):
    # Primary: used for conversations requiring reasoning
    conversation_model: str = "anthropic/claude-sonnet-4-6"

    # Cheap: used for scheduled routines and simple tool calls
    routine_model: str = "anthropic/claude-haiku-4-5-20251001"

    # Whether to use OpenRouter (dev) or direct providers (hosted)
    use_openrouter: bool = True
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    # Prompt caching (Anthropic direct only)
    enable_prompt_caching: bool = True

    # Batch routines (Anthropic direct only)
    enable_batch_routines: bool = True

    # Output token limits
    max_output_tokens: int = 1024
    routine_max_output_tokens: int = 512


def route_model(call_type: CallType, config: RoutingConfig) -> str:
    """Return the model name to use for a given call type."""
    if call_type in (CallType.ROUTINE, CallType.TOOL_ONLY, CallType.MEMORY_WRITE):
        return config.routine_model
    return config.conversation_model


def max_tokens_for(call_type: CallType, config: RoutingConfig) -> int:
    """Return the max output tokens for a given call type."""
    if call_type == CallType.ROUTINE:
        return config.routine_max_output_tokens
    return config.max_output_tokens
