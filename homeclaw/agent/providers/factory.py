"""Provider factory — returns the correct LLMProvider from config."""

from homeclaw.agent.providers.base import LLMProvider
from homeclaw.config import HomeclawConfig


def create_provider(config: HomeclawConfig) -> LLMProvider:
    # Use the routing conversation model as the initial model when routing is
    # configured, since the agent loop will override it per-call anyway.
    # This avoids config.model (which may be stale) from ever hitting the API.
    model = config.routing.conversation_model

    if config.anthropic_api_key:
        from homeclaw.agent.providers.anthropic import AnthropicProvider

        return AnthropicProvider(
            api_key=config.anthropic_api_key,
            model=model,
            enable_prompt_caching=config.routing.enable_prompt_caching,
        )

    if not config.openai_api_key and not config.openai_base_url:
        raise ValueError(
            "No LLM provider configured. Set ANTHROPIC_API_KEY or OPENAI_API_KEY "
            "(via environment, .env, or the web UI setup)."
        )

    from homeclaw.agent.providers.openai import OpenAIProvider

    # Direct OpenAI (no base_url) needs max_completion_tokens for reasoning models.
    # Proxies like OpenRouter expect max_tokens.
    direct_openai = not config.openai_base_url
    return OpenAIProvider(
        api_key=config.openai_api_key,
        base_url=config.openai_base_url,
        model=model,
        use_max_completion_tokens=direct_openai,
    )
