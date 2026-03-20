"""homeclaw configuration — loads from environment variables, .env, and config.json."""

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

from pydantic import model_validator
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict

from homeclaw.agent.context import ContextConfig
from homeclaw.agent.routing import RoutingConfig

logger = logging.getLogger(__name__)

# Lock for config.json read-modify-write to prevent concurrent clobber.
_config_save_lock = asyncio.Lock()

# Fields that the web UI can persist to config.json.
_SAVEABLE_FIELDS = {
    "provider",
    "anthropic_api_key",
    "openai_api_key",
    "openai_base_url",
    "model",
    "telegram_token",
    "telegram_allowed_users",
    "whatsapp_enabled",
    "whatsapp_phone_number",
    "whatsapp_allowed_users",
    "jina_api_key",
    "ha_url",
    "ha_token",
    "web_password",
    "member_passwords",
    "jwt_secret",
    "timezone",
}

# Routing model fields are saved/loaded via the nested RoutingConfig object.
_ROUTING_FIELDS = {"conversation_model", "routine_model"}


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
    # Explicit provider selection — "anthropic" or "openai"
    provider: str | None = None

    # LLM provider keys
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

    # WhatsApp (via neonize / whatsmeow)
    whatsapp_enabled: bool = False
    whatsapp_phone_number: str | None = None  # Phone number for pair-code auth
    whatsapp_allowed_users: str | None = None  # Comma-separated phone numbers (e.g. "14155551234")

    @property
    def whatsapp_allowed_phone_numbers(self) -> set[str] | None:
        """Parse allowed phone numbers, or None if unrestricted."""
        if not self.whatsapp_allowed_users:
            return None
        numbers: set[str] = set()
        for part in self.whatsapp_allowed_users.split(","):
            part = part.strip()
            if part:
                numbers.add(part)
        return numbers if numbers else None

    # Web search (Jina)
    jina_api_key: str | None = None

    # Home Assistant (optional)
    ha_url: str | None = None
    ha_token: str | None = None

    # Web UI
    web_port: int = 8080
    web_password: str = ""
    member_passwords: dict[str, str] = {}  # {member_name: password}
    jwt_secret: str = ""  # Auto-generated on first login; signs session tokens

    # Embedding provider for semantic memory ("local" or "openai")
    embedding_provider: str | None = None

    # Marketplace
    marketplace_url: str | None = None

    # Timezone for schedules and log display (IANA, e.g. "America/New_York")
    timezone: str | None = None

    # Paths
    workspaces_path: str = "./workspaces"

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
    def _load_routing_overrides(self) -> "HomeclawConfig":
        """Load routing model overrides from config.json if present."""
        try:
            path = self.workspaces.resolve() / "config.json"
            if path.is_file():
                data = json.loads(path.read_text())
                for field_name in _ROUTING_FIELDS:
                    if field_name in data:
                        setattr(self.routing, field_name, data[field_name])
        except (json.JSONDecodeError, OSError):
            pass
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

        # Routing fields (nested on RoutingConfig, not top-level)
        for field_name in _ROUTING_FIELDS:
            existing[field_name] = getattr(self.routing, field_name)

        self.config_json_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_json_path.write_text(json.dumps(existing, indent=2) + "\n")

    async def save_async(self) -> None:
        """Persist config with a lock to prevent concurrent write races."""
        async with _config_save_lock:
            self.save()
