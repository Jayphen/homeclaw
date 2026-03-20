"""Channel dispatcher — routes outbound messages to the right channel adapter.

Channel adapters (Telegram, WhatsApp, etc.) register themselves here so
the ``message_send`` tool and scheduler can deliver proactive messages to
household members via their preferred channel.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# person name → preferred channel name (e.g. "telegram", "whatsapp")
_PREFS_FILE = "household/channel_preferences.json"

# Signature: (person_name, text) → delivery result dict
SendFn = Callable[[str, str], Awaitable[dict[str, Any]]]
# Signature: (group_id, text) → delivery result dict
GroupSendFn = Callable[[str, str], Awaitable[dict[str, Any]]]


class _ChannelEntry:
    __slots__ = ("send", "has_person", "send_group", "group_ids")

    def __init__(
        self,
        send: SendFn,
        has_person: Callable[[str], bool],
        send_group: GroupSendFn | None = None,
        group_ids: Callable[[], list[str]] | None = None,
    ) -> None:
        self.send = send
        self.has_person = has_person
        self.send_group = send_group
        self.group_ids = group_ids


class ChannelDispatcher:
    """Global registry of outbound channel adapters."""

    def __init__(self, workspaces: Path) -> None:
        self._workspaces = workspaces
        self._channels: dict[str, _ChannelEntry] = {}

    # -- registration --

    def register(
        self,
        name: str,
        send: SendFn,
        has_person: Callable[[str], bool],
        send_group: GroupSendFn | None = None,
        group_ids: Callable[[], list[str]] | None = None,
    ) -> None:
        """Register a channel adapter for outbound delivery."""
        self._channels[name] = _ChannelEntry(
            send=send, has_person=has_person,
            send_group=send_group, group_ids=group_ids,
        )
        logger.info("Channel dispatcher: registered '%s'", name)

    def unregister(self, name: str) -> None:
        self._channels.pop(name, None)

    # -- preferences --

    def _load_prefs(self) -> dict[str, str]:
        path = self._workspaces / _PREFS_FILE
        if not path.exists():
            return {}
        return json.loads(path.read_text())  # type: ignore[no-any-return]

    def _save_prefs(self, prefs: dict[str, str]) -> None:
        path = self._workspaces / _PREFS_FILE
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(prefs, indent=2) + "\n")

    def get_preference(self, person: str) -> str | None:
        return self._load_prefs().get(person)

    def set_preference(self, person: str, channel: str) -> None:
        prefs = self._load_prefs()
        prefs[person] = channel
        self._save_prefs(prefs)
        logger.info("Channel preference for '%s' set to '%s'", person, channel)

    def set_preference_if_unset(self, person: str, channel: str) -> None:
        """Set preference only if the person doesn't have one yet."""
        prefs = self._load_prefs()
        if person not in prefs:
            prefs[person] = channel
            self._save_prefs(prefs)
            logger.info("Auto-set channel preference for '%s' to '%s'", person, channel)

    def available_channels(self) -> list[str]:
        return list(self._channels)

    # -- delivery --

    async def send(self, person: str, text: str) -> dict[str, Any]:
        """Send a message to a person via their preferred channel.

        Falls back to any channel where the person is registered.
        """
        if not self._channels:
            return {"status": "error", "detail": "No channel adapters registered"}

        # Try preferred channel first
        pref = self.get_preference(person)
        if pref and pref in self._channels:
            entry = self._channels[pref]
            if entry.has_person(person):
                return await entry.send(person, text)

        # Fall back to any channel that knows this person
        for _name, entry in self._channels.items():
            if entry.has_person(person):
                return await entry.send(person, text)

        return {
            "status": "error",
            "detail": f"No channel has '{person}' registered. "
            "They need to /register on Telegram or WhatsApp first.",
        }

    async def send_group(self, group_id: str, text: str) -> dict[str, Any]:
        """Send a message to a group chat."""
        for name, entry in self._channels.items():
            if entry.send_group and entry.group_ids:
                if group_id in entry.group_ids():
                    return await entry.send_group(group_id, text)

        # No specific group found — try sending to the first channel
        # that supports groups at all (household group).
        for name, entry in self._channels.items():
            if entry.send_group and entry.group_ids:
                ids = entry.group_ids()
                if ids:
                    return await entry.send_group(ids[0], text)

        return {
            "status": "error",
            "detail": "No channel has a group chat registered.",
        }

    def list_groups(self) -> list[dict[str, str]]:
        """Return known group IDs across all channels."""
        groups: list[dict[str, str]] = []
        for name, entry in self._channels.items():
            if entry.group_ids:
                for gid in entry.group_ids():
                    groups.append({"channel": name, "group_id": gid})
        return groups
