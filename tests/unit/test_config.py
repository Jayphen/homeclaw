"""Tests for config loading."""

import os
from pathlib import Path
from unittest.mock import patch

import openai
import pytest

from homeclaw.config import HomeclawConfig


def test_config_loads_from_env():
    """Config loads API key from environment variable."""
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key-123"}, clear=False):
        config = HomeclawConfig(workspaces_path="./test-workspaces")
        assert config.anthropic_api_key == "test-key-123"


def test_config_requires_provider():
    """create_provider raises if no LLM provider is configured."""
    from homeclaw.agent.providers.factory import create_provider

    with patch.dict(os.environ, {}, clear=True):
        env = {
            k: v
            for k, v in os.environ.items()
            if k not in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "OPENAI_BASE_URL")
        }
        with patch.dict(os.environ, env, clear=True):
            config = HomeclawConfig(workspaces_path="./test-workspaces")
            with pytest.raises((ValueError, openai.OpenAIError)):
                create_provider(config)


def test_config_workspaces_path():
    """Config provides workspaces as a Path."""
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}, clear=False):
        config = HomeclawConfig(workspaces_path="/tmp/test-ws")
        assert config.workspaces == Path("/tmp/test-ws")


def test_config_treats_openai_compatible_base_url_as_configured():
    """Custom OpenAI-compatible base URLs count as provider configuration."""
    with patch.dict(os.environ, {}, clear=True):
        config = HomeclawConfig(
            workspaces_path="./test-workspaces",
            openai_base_url="https://api.moonshot.ai/v1",
        )
        assert config.is_provider_configured is True
