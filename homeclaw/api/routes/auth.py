"""Auth API routes — login endpoint that returns JWT session tokens."""

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from homeclaw.api.deps import create_session_token, get_config, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginBody(BaseModel):
    member: str | None = None
    password: str


@router.post("/login")
async def login(body: LoginBody) -> dict[str, Any]:
    """Exchange credentials for a signed JWT session token.

    - Admin login:  ``{"password": "..."}``
    - Member login: ``{"member": "alice", "password": "..."}``
    """
    config = get_config()

    if body.member is not None:
        # Member login
        expected = config.member_passwords.get(body.member)
        if expected is None or not verify_password(body.password, expected):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        return create_session_token(body.member, is_admin=False)

    # Admin login
    if not config.web_password:
        raise HTTPException(
            status_code=400, detail="No admin password configured",
        )
    if not verify_password(body.password, config.web_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return create_session_token(None, is_admin=True)
