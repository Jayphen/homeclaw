"""Setup API routes — first-run onboarding and configuration."""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel

from homeclaw.api.deps import (
    AdminDep,
    AuthDep,
    clear_setup_token,
    create_session_token,
    get_agent_loop,
    get_config,
    get_on_telegram_configured,
    get_setup_token,
    hash_password,
    list_member_workspaces,
    require_admin,
    require_auth,
    verify_setup_token,
)

logger = logging.getLogger(__name__)
from homeclaw.api.deps import (
    get_whatsapp_connected as _get_whatsapp_connected,
)
from homeclaw.api.deps import (
    get_whatsapp_qr as _get_whatsapp_qr,
)

router = APIRouter(prefix="/api/setup", tags=["setup"])


def _mask(value: str | None) -> str | None:
    """Mask a secret value for display — never return the full key."""
    if not value:
        return None
    if len(value) <= 8:
        return "***"
    return value[:4] + "***" + value[-4:]


@router.get("/status")
async def setup_status(request: Request) -> dict[str, Any]:
    config = get_config()

    from importlib.metadata import version as _pkg_version

    try:
        app_version = _pkg_version("homeclaw")
    except Exception:
        app_version = "dev"

    workspaces = config.workspaces.resolve()
    members = list_member_workspaces(workspaces)
    members_with_passwords = [
        m for m in members if m in config.member_passwords
    ]

    # Minimal info is always available without auth — the UI needs this
    # to decide whether to show the login screen or onboarding flow.
    # NOTE: Do NOT leak member names here — only expose a count so the
    # UI knows whether to show the member login flow.
    base: dict[str, Any] = {
        "version": app_version,
        "has_password": bool(config.web_password) or bool(config.member_passwords),
        "needs_setup_token": get_setup_token() is not None,
        "provider_configured": config.is_provider_configured,
        "has_member_accounts": bool(config.member_passwords),
    }

    # Full config details require auth (when any password is set).
    if config.web_password or config.member_passwords:
        try:
            await require_auth(request)
        except HTTPException:
            return base

    base.update({
        "members": members,
        "members_with_passwords": members_with_passwords,
        "admin_members": config.admin_members,
        "provider": config.provider,
        "model": config.model,
        "anthropic_api_key": _mask(config.anthropic_api_key),
        "anthropic_base_url": config.anthropic_base_url,
        "openai_api_key": _mask(config.openai_api_key),
        "openai_base_url": config.openai_base_url,
        "fast_provider": config.fast_provider,
        "fast_api_key": _mask(config.fast_api_key),
        "fast_base_url": config.fast_base_url,
        "vision_provider": config.vision_provider,
        "vision_api_key": _mask(config.vision_api_key),
        "vision_base_url": config.vision_base_url,
        "telegram_configured": config.telegram_token is not None,
        "telegram_allowed_users": config.telegram_allowed_users,
        "whatsapp_configured": config.whatsapp_enabled,
        "whatsapp_connected": _get_whatsapp_connected(),
        "whatsapp_phone_number": config.whatsapp_phone_number,
        "whatsapp_allowed_users": config.whatsapp_allowed_users,
        "jina_api_key": _mask(config.jina_api_key),
        "tavily_api_key": _mask(config.tavily_api_key),
        "web_read_provider": config.web_read_provider,
        "web_read_fallback": config.web_read_fallback,
        "ha_configured": config.ha_url is not None,
        "conversation_model": config.routing.conversation_model,
        "fast_model": config.routing.fast_model,
        "vision_model": config.routing.vision_model,
        "timezone": config.timezone,
        "note_detail_level": config.note_detail_level,
        "provider_mode": config.provider_mode,
    })
    return base


class SetupBody(BaseModel):
    setup_token: str | None = None

    # LLM provider
    provider: str | None = None
    anthropic_api_key: str | None = None
    anthropic_base_url: str | None = None
    openai_api_key: str | None = None
    openai_base_url: str | None = None
    fast_provider: str | None = None
    fast_api_key: str | None = None
    fast_base_url: str | None = None
    vision_provider: str | None = None
    vision_api_key: str | None = None
    vision_base_url: str | None = None
    model: str | None = None
    provider_mode: str | None = None

    # Telegram
    telegram_token: str | None = None
    telegram_allowed_users: str | None = None

    # WhatsApp
    whatsapp_enabled: bool | None = None
    whatsapp_phone_number: str | None = None
    whatsapp_allowed_users: str | None = None

    # Web search
    jina_api_key: str | None = None
    tavily_api_key: str | None = None
    web_read_provider: str | None = None
    web_read_fallback: str | None = None

    # Home Assistant
    ha_url: str | None = None
    ha_token: str | None = None

    # Routing
    conversation_model: str | None = None
    fast_model: str | None = None
    vision_model: str | None = None

    # Timezone
    timezone: str | None = None

    # Note-taking
    note_detail_level: str | None = None

    # Auth
    web_password: str | None = None


@router.post("")
async def setup(request: Request, body: SetupBody) -> dict[str, Any]:
    config = get_config()

    # First-run onboarding: no passwords set yet — require setup token.
    if not config.web_password and not config.member_passwords:
        if not body.setup_token or not verify_setup_token(body.setup_token):
            raise HTTPException(status_code=403, detail="Invalid setup token")
    else:
        # After initial setup, require admin auth (JWT, Bearer password, etc.)
        await require_admin(request)

    # Apply changes to the in-memory config.
    if body.provider is not None:
        config.provider = body.provider or None
    if body.anthropic_api_key is not None:
        config.anthropic_api_key = body.anthropic_api_key or None
    if body.anthropic_base_url is not None:
        config.anthropic_base_url = body.anthropic_base_url or None
    if body.openai_api_key is not None:
        config.openai_api_key = body.openai_api_key or None
    if body.openai_base_url is not None:
        config.openai_base_url = body.openai_base_url or None
    if body.fast_provider is not None:
        config.fast_provider = body.fast_provider or None
    if body.fast_api_key is not None:
        config.fast_api_key = body.fast_api_key or None
    if body.fast_base_url is not None:
        config.fast_base_url = body.fast_base_url or None
    if body.vision_provider is not None:
        config.vision_provider = body.vision_provider or None
    if body.vision_api_key is not None:
        config.vision_api_key = body.vision_api_key or None
    if body.vision_base_url is not None:
        config.vision_base_url = body.vision_base_url or None
    if body.model is not None:
        config.model = body.model
    if body.provider_mode is not None:
        config.provider_mode = body.provider_mode or None
    if body.telegram_token is not None:
        config.telegram_token = body.telegram_token or None
    if body.telegram_allowed_users is not None:
        config.telegram_allowed_users = body.telegram_allowed_users or None
    if body.whatsapp_enabled is not None:
        config.whatsapp_enabled = body.whatsapp_enabled
    if body.whatsapp_phone_number is not None:
        config.whatsapp_phone_number = body.whatsapp_phone_number or None
    if body.whatsapp_allowed_users is not None:
        config.whatsapp_allowed_users = body.whatsapp_allowed_users or None
    if body.ha_url is not None:
        config.ha_url = body.ha_url or None
    if body.ha_token is not None:
        config.ha_token = body.ha_token or None
    if body.jina_api_key is not None:
        config.jina_api_key = body.jina_api_key or None
    if body.tavily_api_key is not None:
        config.tavily_api_key = body.tavily_api_key or None
    if body.web_read_provider is not None:
        config.web_read_provider = body.web_read_provider or "jina"
    if body.web_read_fallback is not None:
        config.web_read_fallback = body.web_read_fallback or None
    if body.conversation_model is not None:
        config.routing.conversation_model = body.conversation_model
    if body.fast_model is not None:
        config.routing.fast_model = body.fast_model
    if body.vision_model is not None:
        config.routing.vision_model = body.vision_model
    if body.timezone is not None:
        config.timezone = body.timezone or None
    if body.note_detail_level is not None:
        config.note_detail_level = body.note_detail_level
    if body.web_password is not None:
        config.web_password = hash_password(body.web_password) if body.web_password else ""

    await config.save_async()

    # If a password was just set, invalidate the setup token.
    if body.web_password and get_setup_token() is not None:
        clear_setup_token()

    # Hot-update note_detail_level on the agent loop if changed.
    if body.note_detail_level is not None:
        loop = get_agent_loop()
        if loop is not None:
            loop._note_detail_level = body.note_detail_level

    # Hot-reload LLM providers if any provider-related field changed.
    _provider_fields = {
        "provider", "anthropic_api_key", "anthropic_base_url",
        "openai_api_key", "openai_base_url",
        "fast_provider", "fast_api_key", "fast_base_url",
        "vision_provider", "vision_api_key", "vision_base_url",
        "model", "conversation_model", "fast_model", "vision_model",
    }
    if any(getattr(body, f, None) is not None for f in _provider_fields):
        loop = get_agent_loop()
        if loop is not None:
            try:
                from homeclaw.agent.providers.factory import (
                    create_fast_provider,
                    create_provider,
                    create_vision_provider,
                )

                loop.reload_providers(
                    provider=create_provider(config),
                    fast_provider=create_fast_provider(config),
                    vision_provider=create_vision_provider(config),
                    note_detail_level=config.note_detail_level,
                )
                logger.info("Hot-reloaded LLM providers")
            except Exception:
                logger.warning("Failed to reload providers", exc_info=True)

    # Start Telegram bot dynamically if token was just configured.
    if body.telegram_token and config.telegram_token:
        on_tg = get_on_telegram_configured()
        if on_tg:
            await on_tg(config.telegram_token)

    return await setup_status(request)


class MemberPasswordBody(BaseModel):
    member: str
    password: str


@router.post("/members/password")
async def set_member_password(
    request: Request, body: MemberPasswordBody,
) -> dict[str, Any]:
    """Set or update a member's web UI password.

    Admin-only, EXCEPT when no admin members exist yet (bootstrap).
    In that case, the first member to get a password is auto-promoted
    to admin.
    """
    config = get_config()
    body.member = body.member.lower()
    bootstrapping = not config.admin_members

    if not bootstrapping:
        await require_admin(request)

    workspaces = config.workspaces.resolve()
    members = list_member_workspaces(workspaces)

    if body.member not in members:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown member '{body.member}'. "
            f"Available: {', '.join(members)}",
        )

    if not body.password.strip():
        # Remove password (disable account)
        config.member_passwords.pop(body.member, None)
    else:
        config.member_passwords[body.member] = hash_password(body.password)

    # Auto-promote first member to admin if none exist
    if bootstrapping and body.password.strip():
        config.admin_members.append(body.member)

    await config.save_async()

    is_admin = body.member in config.admin_members
    result: dict[str, Any] = {
        "status": "updated",
        "member": body.member,
        "has_password": body.member in config.member_passwords,
        "is_admin": is_admin,
    }

    # Return a session token during bootstrap so the user is logged in
    if bootstrapping and body.password.strip():
        token_data = create_session_token(body.member, is_admin=True)
        result["token"] = token_data["token"]

    return result


class MemberAdminBody(BaseModel):
    member: str
    is_admin: bool


@router.post("/members/admin", dependencies=[AdminDep])
async def set_member_admin(
    request: Request, body: MemberAdminBody,
) -> dict[str, Any]:
    """Grant or revoke admin privileges for a member. Admin only."""
    config = get_config()
    body.member = body.member.lower()
    workspaces = config.workspaces.resolve()
    members = list_member_workspaces(workspaces)

    if body.member not in members:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown member '{body.member}'. "
            f"Available: {', '.join(members)}",
        )

    if body.is_admin and body.member not in config.admin_members:
        config.admin_members.append(body.member)
    elif not body.is_admin and body.member in config.admin_members:
        config.admin_members.remove(body.member)

    await config.save_async()
    return {
        "status": "updated",
        "member": body.member,
        "is_admin": body.member in config.admin_members,
    }


@router.get("/whatsapp/qr", dependencies=[AuthDep])
async def whatsapp_qr() -> Response:
    """Serve the WhatsApp QR code as a PNG image for scanning in the browser.

    Returns 204 if no QR is pending (already paired or WhatsApp not enabled).
    """
    qr_data = _get_whatsapp_qr()
    if qr_data is None:
        return Response(status_code=204)

    # neonize provides raw QR string data — generate a PNG via qrcode lib
    try:
        import io

        import qrcode  # type: ignore[import-untyped]

        img = qrcode.make(qr_data.decode("utf-8") if isinstance(qr_data, bytes) else qr_data)
        buf = io.BytesIO()
        img.save(buf, format="PNG")  # type: ignore[call-arg]
        return Response(content=buf.getvalue(), media_type="image/png")
    except ImportError:
        # qrcode not installed — return the raw data as text
        return Response(
            content=qr_data if isinstance(qr_data, bytes) else qr_data.encode(),
            media_type="text/plain",
        )
