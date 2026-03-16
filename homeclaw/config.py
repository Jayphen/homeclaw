"""homeclaw configuration — loads from environment variables and config.json."""

from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from homeclaw.agent.context import ContextConfig
from homeclaw.agent.routing import RoutingConfig


class HomeclawConfig(BaseSettings):
    # LLM provider — set one of these:
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    openai_base_url: str | None = None

    # Model name — set to match your provider
    model: str = "claude-sonnet-4-6"

    # Telegram
    telegram_token: str | None = None

    # Home Assistant (optional)
    ha_url: str | None = None
    ha_token: str | None = None

    # Web UI
    web_port: int = 8080
    web_password: str = ""

    # Paths
    workspaces_path: str = "./workspaces"

    # Memory mode
    enhanced_memory: bool = False

    # Cost routing
    routing: RoutingConfig = RoutingConfig()

    # Context budget
    context: ContextConfig = ContextConfig()

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @model_validator(mode="after")
    def check_provider_configured(self) -> "HomeclawConfig":
        has_anthropic = self.anthropic_api_key is not None
        has_openai = self.openai_api_key is not None or self.openai_base_url is not None
        if not has_anthropic and not has_openai:
            raise ValueError(
                "No LLM provider configured. "
                "Set ANTHROPIC_API_KEY or OPENAI_API_KEY/OPENAI_BASE_URL."
            )
        return self

    @property
    def workspaces(self) -> Path:
        return Path(self.workspaces_path)
