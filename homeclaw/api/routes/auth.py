"""Auth API routes — login endpoint that returns JWT session tokens."""

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from homeclaw.api.deps import create_session_token, get_config, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginBody(BaseModel):
    member: str
    password: str


@router.post("/login")
async def login(body: LoginBody) -> dict[str, Any]:
    """Exchange credentials for a signed JWT session token.

    All logins are member logins: ``{"member": "alice", "password": "..."}``.
    Admin privileges are determined by the ``admin_members`` config list.
    """
    config = get_config()
    member = body.member.lower()

    expected = config.member_passwords.get(member)
    if expected is None or not verify_password(body.password, expected):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    is_admin = member in config.admin_members
    return create_session_token(member, is_admin=is_admin)
