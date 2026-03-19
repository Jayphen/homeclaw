"""Per-call model routing — selects the appropriate model for each LLM call type."""

from enum import Enum

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class CallType(Enum):
    CONVERSATION = "conversation"  # user message, needs reasoning
    ROUTINE = "routine"  # scheduled heartbeat task (initial call uses conversation model)
    TOOL_ONLY = "tool_only"  # simple tool call, no reasoning needed
    MEMORY_WRITE = "memory_write"  # saving a fact or note


class RoutingConfig(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Primary: used for conversations requiring reasoning
    conversation_model: str = "claude-sonnet-4-6"

    # Cheap: used for scheduled routines and simple tool calls
    routine_model: str = "claude-haiku-4-5"

    # Whether to use OpenRouter (dev) or direct providers (hosted)
    use_openrouter: bool = False
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    # Prompt caching (Anthropic direct only)
    enable_prompt_caching: bool = True

    # Batch routines (Anthropic direct only)
    enable_batch_routines: bool = True

    # Output token limits
    max_output_tokens: int = 4096
    routine_max_output_tokens: int = 2048

    @model_validator(mode="after")
    def _apply_provider_defaults(self) -> "RoutingConfig":
        """Adjust features based on provider mode."""
        if self.use_openrouter:
            self.enable_prompt_caching = False
            self.enable_batch_routines = False
        return self


# Tools that require reasoning to synthesize results — keep Sonnet.
_REASONING_TOOLS = frozenset({"web_read", "web_search"})

# Tools that write to memory/household state — Haiku is fine for follow-up.
_MEMORY_WRITE_TOOLS = frozenset({
    "memory_update", "household_share", "note_save",
})


def classify_tool_round(tool_names: list[str]) -> CallType:
    """Classify a set of dispatched tool calls to pick the model for the next round.

    After the first LLM call (always CONVERSATION), subsequent rounds can use
    a cheaper model if the tools are simple read/write operations.
    """
    names = set(tool_names)
    if names & _REASONING_TOOLS:
        return CallType.CONVERSATION
    if names and names <= _MEMORY_WRITE_TOOLS:
        return CallType.MEMORY_WRITE
    return CallType.TOOL_ONLY


def route_model(call_type: CallType, config: RoutingConfig) -> str:
    """Return the model name to use for a given call type.

    Routines use the conversation model for the initial call so the LLM is
    capable enough to decide which tools to invoke (e.g. web_search).  After
    tool dispatch, classify_tool_round downgrades to the routine model for
    simple follow-up rounds.
    """
    if call_type in (CallType.TOOL_ONLY, CallType.MEMORY_WRITE):
        return config.routine_model
    return config.conversation_model


def max_tokens_for(call_type: CallType, config: RoutingConfig) -> int:
    """Return the max output tokens for a given call type."""
    if call_type in (CallType.TOOL_ONLY, CallType.MEMORY_WRITE):
        return config.routine_max_output_tokens
    return config.max_output_tokens
