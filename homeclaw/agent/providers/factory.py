"""Provider factory — returns the correct LLMProvider from config."""

from homeclaw.agent.providers.base import LLMProvider
from homeclaw.config import HomeclawConfig


def create_provider(config: HomeclawConfig) -> LLMProvider:
    model = config.routing.conversation_model

    # Determine provider: explicit setting, or infer from which keys are set.
    provider = config.provider
    if not provider:
        if config.anthropic_api_key and not config.openai_api_key:
            provider = "anthropic"
        elif config.openai_api_key or config.openai_base_url:
            provider = "openai"
        elif config.anthropic_api_key:
            provider = "anthropic"

    if provider == "anthropic":
        if not config.anthropic_api_key:
            raise ValueError("Anthropic provider selected but ANTHROPIC_API_KEY is not set.")
        from homeclaw.agent.providers.anthropic import AnthropicProvider

        return AnthropicProvider(
            api_key=config.anthropic_api_key,
            model=model,
            enable_prompt_caching=config.routing.enable_prompt_caching,
            context_window=config.routing.context_window,
        )

    if provider == "openai":
        if not config.openai_api_key and not config.openai_base_url:
            raise ValueError("OpenAI provider selected but no API key or base URL is set.")
        from homeclaw.agent.providers.openai import OpenAIProvider

        direct_openai = not config.openai_base_url
        return OpenAIProvider(
            api_key=config.openai_api_key,
            base_url=config.openai_base_url,
            model=model,
            use_max_completion_tokens=direct_openai,
            context_window=config.routing.context_window,
        )

    raise ValueError(
        "No LLM provider configured. Set PROVIDER and the corresponding API key "
        "(via environment, .env, or the web UI setup)."
    )
