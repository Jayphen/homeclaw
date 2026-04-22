"""Tests for provider factory behavior."""

from homeclaw.agent.providers.factory import create_provider
from homeclaw.agent.providers.openai import OpenAIProvider
from homeclaw.config import HomeclawConfig


def test_create_provider_uses_openai_compat_mode_for_kimi_base_url():
    """Kimi should route through the generic OpenAI-compatible transport."""
    config = HomeclawConfig(
        workspaces_path="./test-workspaces",
        provider="openai",
        openai_api_key="test-key",
        openai_base_url="https://api.moonshot.ai/v1",
    )

    provider = create_provider(config)

    assert isinstance(provider, OpenAIProvider)
    assert provider.model == config.routing.conversation_model
    assert provider._use_max_completion_tokens is False
