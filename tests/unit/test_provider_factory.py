"""Tests for provider factory behavior."""

import pytest

from homeclaw.agent.providers.factory import create_provider
from homeclaw.agent.providers.openai import OpenAIProvider
from homeclaw.config import HomeclawConfig


@pytest.mark.parametrize(
    ("base_url", "model"),
    [
        ("https://api.moonshot.ai/v1", "kimi-k2.6"),
        ("https://generativelanguage.googleapis.com/v1beta/openai/", "gemini-2.5-flash"),
    ],
)
def test_create_provider_uses_openai_compat_mode_for_custom_base_urls(
    base_url: str,
    model: str,
) -> None:
    """OpenAI-compatible providers should keep using max_tokens semantics."""
    config = HomeclawConfig(
        workspaces_path="./test-workspaces",
        provider="openai",
        openai_api_key="test-key",
        openai_base_url=base_url,
        model=model,
    )

    provider = create_provider(config)

    assert isinstance(provider, OpenAIProvider)
    assert provider.model == config.routing.conversation_model
    assert provider._use_max_completion_tokens is False
