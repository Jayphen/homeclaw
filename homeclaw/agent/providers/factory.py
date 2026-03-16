"""Provider factory — returns the correct LLMProvider from config."""

from homeclaw.agent.providers.base import LLMProvider
from homeclaw.config import HomeclawConfig


def create_provider(config: HomeclawConfig) -> LLMProvider:
    if config.anthropic_api_key:
        from homeclaw.agent.providers.anthropic import AnthropicProvider

        return AnthropicProvider(
            api_key=config.anthropic_api_key,
            model=config.model,
            enable_prompt_caching=config.routing.enable_prompt_caching,
        )

    from homeclaw.agent.providers.openai import OpenAIProvider

    return OpenAIProvider(
        api_key=config.openai_api_key,
        base_url=config.openai_base_url,
        model=config.model,
    )
