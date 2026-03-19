"""Setup API routes — first-run onboarding and configuration."""

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel

from homeclaw.api.deps import (
    clear_setup_token,
    get_config,
    get_on_telegram_configured,
    get_setup_token,
    verify_setup_token,
)
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
async def setup_status() -> dict[str, Any]:
    config = get_config()
    return {
        "provider_configured": config.is_provider_configured,
        "provider": config.provider,
        "has_password": bool(config.web_password),
        "needs_setup_token": get_setup_token() is not None,
        "model": config.model,
        "anthropic_api_key": _mask(config.anthropic_api_key),
        "openai_api_key": _mask(config.openai_api_key),
        "openai_base_url": config.openai_base_url,
        "telegram_configured": config.telegram_token is not None,
        "telegram_allowed_users": config.telegram_allowed_users,
        "whatsapp_configured": config.whatsapp_enabled,
        "whatsapp_connected": _get_whatsapp_connected(),
        "whatsapp_phone_number": config.whatsapp_phone_number,
        "whatsapp_allowed_users": config.whatsapp_allowed_users,
        "jina_api_key": _mask(config.jina_api_key),
        "ha_configured": config.ha_url is not None,
        "conversation_model": config.routing.conversation_model,
        "routine_model": config.routing.routine_model,
    }


class SetupBody(BaseModel):
    setup_token: str | None = None

    # LLM provider
    provider: str | None = None
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    openai_base_url: str | None = None
    model: str | None = None

    # Telegram
    telegram_token: str | None = None
    telegram_allowed_users: str | None = None

    # WhatsApp
    whatsapp_enabled: bool | None = None
    whatsapp_phone_number: str | None = None
    whatsapp_allowed_users: str | None = None

    # Web search
    jina_api_key: str | None = None

    # Home Assistant
    ha_url: str | None = None
    ha_token: str | None = None

    # Routing
    conversation_model: str | None = None
    routine_model: str | None = None

    # Auth
    web_password: str | None = None


@router.post("")
async def setup(request: Request, body: SetupBody) -> dict[str, Any]:
    config = get_config()

    # If no password is set, require the setup token (first-run onboarding).
    if not config.web_password:
        if not body.setup_token or not verify_setup_token(body.setup_token):
            raise HTTPException(status_code=403, detail="Invalid setup token")
    else:
        # After initial setup, accept Bearer auth OR the password in setup_token.
        auth = request.headers.get("Authorization", "")
        bearer_ok = auth == f"Bearer {config.web_password}"
        token_ok = body.setup_token is not None and body.setup_token == config.web_password
        if not bearer_ok and not token_ok:
            raise HTTPException(status_code=401, detail="Unauthorized")

    # Apply changes to the in-memory config.
    if body.provider is not None:
        config.provider = body.provider or None
    if body.anthropic_api_key is not None:
        config.anthropic_api_key = body.anthropic_api_key or None
    if body.openai_api_key is not None:
        config.openai_api_key = body.openai_api_key or None
    if body.openai_base_url is not None:
        config.openai_base_url = body.openai_base_url or None
    if body.model is not None:
        config.model = body.model
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
    if body.conversation_model is not None:
        config.routing.conversation_model = body.conversation_model
    if body.routine_model is not None:
        config.routing.routine_model = body.routine_model
    if body.web_password is not None:
        config.web_password = body.web_password

    await config.save_async()

    # If a password was just set, invalidate the setup token.
    if body.web_password and get_setup_token() is not None:
        clear_setup_token()

    # Start Telegram bot dynamically if token was just configured.
    if body.telegram_token and config.telegram_token:
        on_tg = get_on_telegram_configured()
        if on_tg:
            await on_tg(config.telegram_token)

    return await setup_status()


@router.get("/whatsapp/qr")
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
