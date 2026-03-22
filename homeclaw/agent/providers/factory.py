"""Provider factory — returns the correct LLMProvider from config."""

import logging

from homeclaw.agent.providers.base import LLMProvider
from homeclaw.config import HomeclawConfig

logger = logging.getLogger(__name__)


def _resolve_provider_type(config: HomeclawConfig) -> str:
    """Determine the main provider type from config or infer from keys."""
    provider = config.provider
    if not provider:
        if config.anthropic_api_key and not config.openai_api_key:
            provider = "anthropic"
        elif config.openai_api_key or config.openai_base_url:
            provider = "openai"
        elif config.anthropic_api_key:
            provider = "anthropic"
    if not provider:
        raise ValueError(
            "No LLM provider configured. Set PROVIDER and the corresponding API key "
            "(via environment, .env, or the web UI setup)."
        )
    return provider


def _create_anthropic(
    api_key: str,
    model: str,
    base_url: str | None = None,
    enable_prompt_caching: bool = True,
    context_window: int = 200_000,
) -> LLMProvider:
    from homeclaw.agent.providers.anthropic import AnthropicProvider

    return AnthropicProvider(
        api_key=api_key,
        model=model,
        base_url=base_url,
        enable_prompt_caching=enable_prompt_caching,
        context_window=context_window,
    )


def _create_openai(
    api_key: str | None,
    model: str,
    base_url: str | None = None,
    context_window: int = 128_000,
) -> LLMProvider:
    from homeclaw.agent.providers.openai import OpenAIProvider

    direct_openai = not base_url
    return OpenAIProvider(
        api_key=api_key,
        base_url=base_url,
        model=model,
        use_max_completion_tokens=direct_openai,
        context_window=context_window,
    )


def create_provider(config: HomeclawConfig) -> LLMProvider:
    """Create the main (conversation) provider."""
    provider = _resolve_provider_type(config)
    model = config.routing.conversation_model

    if provider == "anthropic":
        if not config.anthropic_api_key:
            raise ValueError("Anthropic provider selected but ANTHROPIC_API_KEY is not set.")
        return _create_anthropic(
            api_key=config.anthropic_api_key,
            model=model,
            base_url=config.anthropic_base_url,
            enable_prompt_caching=config.routing.enable_prompt_caching,
            context_window=config.routing.context_window,
        )

    if provider == "openai":
        if not config.openai_api_key and not config.openai_base_url:
            raise ValueError("OpenAI provider selected but no API key or base URL is set.")
        return _create_openai(
            api_key=config.openai_api_key,
            model=model,
            base_url=config.openai_base_url,
            context_window=config.routing.context_window,
        )

    raise ValueError(f"Unknown provider: {provider!r}")


def create_fast_provider(config: HomeclawConfig) -> LLMProvider | None:
    """Create a separate provider for the fast model, or None to reuse the main one.

    Returns a provider when fast_base_url or fast_api_key or fast_provider is set,
    meaning the fast model needs its own connection.
    """
    if not config.fast_base_url and not config.fast_api_key and not config.fast_provider:
        return None

    main_provider = _resolve_provider_type(config)
    fast_type = config.fast_provider or main_provider
    model = config.routing.fast_model

    if fast_type == "anthropic":
        api_key = config.fast_api_key or config.anthropic_api_key
        if not api_key:
            raise ValueError("Fast model uses Anthropic but no API key is set.")
        base_url = config.fast_base_url or config.anthropic_base_url
        # Disable prompt caching for third-party Anthropic-compatible APIs
        caching = config.routing.enable_prompt_caching and not config.fast_base_url
        return _create_anthropic(
            api_key=api_key,
            model=model,
            base_url=base_url,
            enable_prompt_caching=caching,
            context_window=config.routing.context_window,
        )

    if fast_type == "openai":
        api_key = config.fast_api_key or config.openai_api_key
        base_url = config.fast_base_url or config.openai_base_url
        if not api_key and not base_url:
            raise ValueError("Fast model uses OpenAI but no API key or base URL is set.")
        return _create_openai(
            api_key=api_key,
            model=model,
            base_url=base_url,
            context_window=config.routing.context_window,
        )

    raise ValueError(f"Unknown fast provider: {fast_type!r}")


def create_vision_provider(config: HomeclawConfig) -> LLMProvider | None:
    """Create a separate provider for vision (image) input, or None to reuse the main one.

    Returns a provider when vision_base_url, vision_api_key, or vision_provider
    is set, meaning image messages need a different connection (e.g. Anthropic
    for vision while MiniMax handles text).
    """
    if not config.vision_base_url and not config.vision_api_key and not config.vision_provider:
        return None

    main_provider = _resolve_provider_type(config)
    vision_type = config.vision_provider or main_provider
    model = config.routing.vision_model or config.routing.conversation_model

    if vision_type == "anthropic":
        api_key = config.vision_api_key or config.anthropic_api_key
        if not api_key:
            raise ValueError("Vision model uses Anthropic but no API key is set.")
        base_url = config.vision_base_url or config.anthropic_base_url
        caching = config.routing.enable_prompt_caching and not config.vision_base_url
        return _create_anthropic(
            api_key=api_key,
            model=model,
            base_url=base_url,
            enable_prompt_caching=caching,
            context_window=config.routing.context_window,
        )

    if vision_type == "openai":
        api_key = config.vision_api_key or config.openai_api_key
        base_url = config.vision_base_url or config.openai_base_url
        if not api_key and not base_url:
            raise ValueError("Vision model uses OpenAI but no API key or base URL is set.")
        return _create_openai(
            api_key=api_key,
            model=model,
            base_url=base_url,
            context_window=config.routing.context_window,
        )

    raise ValueError(f"Unknown vision provider: {vision_type!r}")
