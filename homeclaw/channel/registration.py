"""Shared member registration logic for channel adapters.

Prevents drift between Telegram, WhatsApp, and future channel adapters
by centralizing the register/register_member commands.
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

from homeclaw.channel.dispatcher import ChannelDispatcher
from homeclaw.contacts.store import get_contact, save_contact

logger = logging.getLogger(__name__)


def load_user_map(workspaces: Path, map_file: str) -> dict[str, str]:
    """Load {identifier: member_name} map from a JSON file."""
    path = workspaces / "household" / map_file
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())  # type: ignore[no-any-return]
    except (json.JSONDecodeError, OSError):
        return {}


def save_user_map(
    workspaces: Path, map_file: str, user_map: dict[str, str],
) -> None:
    """Persist the user map to disk."""
    path = workspaces / "household" / map_file
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(user_map, indent=2) + "\n")


def is_admin(person: str | None) -> bool:
    """Check if a member name is in the admin list."""
    if person is None:
        return False
    from homeclaw.api.deps import get_config
    try:
        return person in get_config().admin_members
    except RuntimeError:
        return False


async def register_self(
    *,
    identifier: str,
    name: str,
    workspaces: Path,
    map_file: str,
    user_map: dict[str, str],
    lock: asyncio.Lock,
    channel_name: str,
    dispatcher: ChannelDispatcher | None,
) -> str:
    """Register the caller's own identifier as a household member.

    Returns a confirmation message string.
    """
    name = name.strip().lower()

    async with lock:
        user_map[identifier] = name
        save_user_map(workspaces, map_file, user_map)

        member_dir = workspaces / name
        member_dir.mkdir(parents=True, exist_ok=True)

        contact = get_contact(workspaces, name)
        if contact and contact.member != name:
            contact.member = name
            save_contact(workspaces, contact)
            logger.info(
                "Linked contact '%s' to member workspace '%s'",
                contact.id, name,
            )

    if dispatcher:
        dispatcher.set_preference_if_unset(name, channel_name)

    logger.info(
        "Registered %s user %s as '%s'", channel_name, identifier, name,
    )
    return f"Registered as '{name}'. You can now chat with me!"


async def register_member(
    *,
    admin_identifier: str,
    target_identifier: str,
    name: str,
    workspaces: Path,
    map_file: str,
    user_map: dict[str, str],
    lock: asyncio.Lock,
    channel_name: str,
    dispatcher: ChannelDispatcher | None,
    allowed_set: set[Any] | None = None,
) -> tuple[bool, str]:
    """Admin registers another member by identifier.

    Returns (success, message).
    """
    admin_person = user_map.get(admin_identifier)
    if not is_admin(admin_person):
        return False, "Only admins can use /register_member."

    name = name.strip().lower()

    async with lock:
        user_map[target_identifier] = name
        save_user_map(workspaces, map_file, user_map)
        (workspaces / name).mkdir(parents=True, exist_ok=True)

    if dispatcher:
        dispatcher.set_preference_if_unset(name, channel_name)

    if allowed_set is not None:
        allowed_set.add(target_identifier)

    logger.info(
        "Admin registered member '%s' with %s ID %s",
        name, channel_name, target_identifier,
    )
    return True, f"Registered '{name}' with {channel_name} ID {target_identifier}."
