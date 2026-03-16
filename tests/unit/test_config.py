"""Tests for config loading."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from homeclaw.config import HomeclawConfig


def test_config_loads_from_env():
    """Config loads API key from environment variable."""
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key-123"}, clear=False):
        config = HomeclawConfig(workspaces_path="./test-workspaces")
        assert config.anthropic_api_key == "test-key-123"


def test_config_requires_provider():
    """Config raises if no LLM provider is configured."""
    with patch.dict(os.environ, {}, clear=True):
        # Clear any existing env vars that might satisfy the validator
        env = {k: v for k, v in os.environ.items()
               if k not in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "OPENAI_BASE_URL")}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(Exception):
                HomeclawConfig(workspaces_path="./test-workspaces")


def test_config_workspaces_path():
    """Config provides workspaces as a Path."""
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}, clear=False):
        config = HomeclawConfig(workspaces_path="/tmp/test-ws")
        assert config.workspaces == Path("/tmp/test-ws")
