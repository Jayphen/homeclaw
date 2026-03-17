"""homeclaw configuration — loads from environment variables, .env, and config.json."""

import json
import logging
from pathlib import Path
from typing import Any

from pydantic import model_validator
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict

from homeclaw.agent.context import ContextConfig
from homeclaw.agent.routing import RoutingConfig

logger = logging.getLogger(__name__)

# Fields that the web UI can persist to config.json.
_SAVEABLE_FIELDS = {
    "anthropic_api_key",
    "openai_api_key",
    "openai_base_url",
    "model",
    "telegram_token",
    "telegram_allowed_users",
    "ha_url",
    "ha_token",
    "web_password",
    "enhanced_memory",
}


class _JsonFileSource(PydanticBaseSettingsSource):
    """Load settings from {workspaces}/config.json if it exists."""

    def __init__(self, settings_cls: type[BaseSettings], json_path: Path) -> None:
        super().__init__(settings_cls)
        self._data: dict[str, Any] = {}
        if json_path.is_file():
            try:
                self._data = json.loads(json_path.read_text())
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Failed to read %s: %s", json_path, e)

    def get_field_value(self, field: Any, field_name: str) -> tuple[Any, str, bool]:
        val = self._data.get(field_name)
        return val, field_name, val is not None

    def __call__(self) -> dict[str, Any]:
        return {k: v for k, v in self._data.items() if v is not None}


class HomeclawConfig(BaseSettings):
    # LLM provider — set one of these:
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    openai_base_url: str | None = None

    # Model name — set to match your provider
    model: str = "claude-sonnet-4-6"

    # Telegram
    telegram_token: str | None = None
    telegram_allowed_users: str | None = None  # Comma-separated Telegram user IDs

    @property
    def telegram_allowed_user_ids(self) -> set[int] | None:
        """Parse allowed user IDs, or None if unrestricted."""
        if not self.telegram_allowed_users:
            return None
        ids: set[int] = set()
        for part in self.telegram_allowed_users.split(","):
            part = part.strip()
            if part:
                ids.add(int(part))
        return ids if ids else None

    # Home Assistant (optional)
    ha_url: str | None = None
    ha_token: str | None = None

    # Web UI
    web_port: int = 8080
    web_password: str = ""

    # Paths
    workspaces_path: str = "./workspaces"

    # Memory mode
    enhanced_memory: bool = True

    # Cost routing
    routing: RoutingConfig = RoutingConfig()

    # Context budget
    context: ContextConfig = ContextConfig()

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        # Resolve workspaces path: check init kwargs first, then env/dotenv, then default.
        # Priority: env vars > .env > config.json > defaults
        import os

        ws = os.environ.get("WORKSPACES_PATH", "./workspaces")
        init_data = init_settings.init_kwargs
        if "workspaces_path" in init_data:
            ws = init_data["workspaces_path"]
        json_path = Path(ws).resolve() / "config.json"
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            _JsonFileSource(settings_cls, json_path),
            file_secret_settings,
        )

    @property
    def is_provider_configured(self) -> bool:
        has_anthropic = self.anthropic_api_key is not None
        has_openai = self.openai_api_key is not None or self.openai_base_url is not None
        return has_anthropic or has_openai

    @model_validator(mode="after")
    def check_provider_configured(self) -> "HomeclawConfig":
        # Allow unconfigured state for onboarding — the setup flow will set keys.
        return self

    @property
    def workspaces(self) -> Path:
        return Path(self.workspaces_path)

    @property
    def config_json_path(self) -> Path:
        return self.workspaces.resolve() / "config.json"

    def save(self) -> None:
        """Persist saveable fields to config.json in the workspaces directory."""
        existing: dict[str, Any] = {}
        if self.config_json_path.is_file():
            try:
                existing = json.loads(self.config_json_path.read_text())
            except (json.JSONDecodeError, OSError):
                pass

        for field_name in _SAVEABLE_FIELDS:
            val = getattr(self, field_name)
            if val is not None and val != "":
                existing[field_name] = val
            elif field_name in existing and (val is None or val == ""):
                del existing[field_name]

        self.config_json_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_json_path.write_text(json.dumps(existing, indent=2) + "\n")
