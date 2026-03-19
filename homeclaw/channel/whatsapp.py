"""WhatsApp channel adapter — connects WhatsApp messages to the agent loop via neonize.

Requires the optional [whatsapp] extra:  pip install homeclaw[whatsapp]
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from pathlib import Path
from typing import Any

from homeclaw.agent.loop import AgentLoop
from homeclaw.channel.dispatcher import ChannelDispatcher
from homeclaw.contacts.store import get_contact, save_contact

logger = logging.getLogger(__name__)

# Maps phone numbers to household member names.
# Stored as {"<phone>": "member_name"} in workspaces/household/whatsapp_users.json.
_USER_MAP_FILE = "household/whatsapp_users.json"


def _load_user_map(workspaces: Path) -> dict[str, str]:
    path = workspaces / _USER_MAP_FILE
    if not path.exists():
        return {}
    return json.loads(path.read_text())  # type: ignore[no-any-return]


def _save_user_map(workspaces: Path, user_map: dict[str, str]) -> None:
    path = workspaces / _USER_MAP_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(user_map, indent=2) + "\n")


def _extract_text(ev: Any) -> str | None:
    """Extract plain text from a WhatsApp MessageEv protobuf."""
    return (
        ev.Message.conversation
        or ev.Message.extendedTextMessage.text
        or None
    )


class WhatsAppChannel:
    """Bridges WhatsApp <-> AgentLoop via neonize (whatsmeow Python bindings).

    On first run, a QR code is printed to the terminal/logs. Scan it with
    WhatsApp on your phone (Settings → Linked Devices → Link a Device).
    Credentials are persisted to workspaces/household/whatsapp.db and
    reused on subsequent starts — no re-scan needed.
    """

    def __init__(
        self,
        loop: AgentLoop,
        workspaces: Path,
        allowed_phones: set[str] | None = None,
        dispatcher: ChannelDispatcher | None = None,
    ) -> None:
        # Runtime import — neonize is an optional dependency.
        from neonize.aioze.client import NewAClient  # type: ignore[import-untyped]
        from neonize.aioze.events import (  # type: ignore[import-untyped]
            ConnectedEv,
            MessageEv,
            PairStatusEv,
        )

        self._loop = loop
        self._workspaces = workspaces
        self._allowed_phones = allowed_phones
        self._user_map = _load_user_map(workspaces)
        self._user_map_lock = asyncio.Lock()

        db_dir = workspaces / "household"
        db_dir.mkdir(parents=True, exist_ok=True)
        self._client: Any = NewAClient(str(db_dir / "whatsapp.db"))
        self._connect_task: asyncio.Task[None] | None = None
        self._dispatcher = dispatcher

        # Store event types so _register_handlers can reference them
        self._ConnectedEv = ConnectedEv
        self._MessageEv = MessageEv
        self._PairStatusEv = PairStatusEv

        self._register_handlers()

    def _register_handlers(self) -> None:
        @self._client.event(self._ConnectedEv)
        async def _on_connected(_: Any, __: Any) -> None:
            logger.info("WhatsApp connected")

        @self._client.event(self._PairStatusEv)
        async def _on_pair_status(_: Any, ev: Any) -> None:
            logger.info("WhatsApp paired as +%s", ev.ID.User)

        @self._client.event(self._MessageEv)
        async def _on_message(_: Any, ev: Any) -> None:
            await self._handle_message(ev)

    def _is_allowed(self, phone: str) -> bool:
        if self._allowed_phones is None:
            return True
        return phone in self._allowed_phones

    def _resolve_person(self, phone: str) -> str | None:
        return self._user_map.get(phone)

    async def _handle_message(self, ev: Any) -> None:
        """Route an incoming WhatsApp message through the agent loop."""
        if ev.Info.MessageSource.IsFromMe:
            return

        phone: str = ev.Info.MessageSource.Sender.User
        chat: Any = ev.Info.MessageSource.Chat

        if not self._is_allowed(phone):
            logger.warning("Rejected message from unauthorized phone %s", phone)
            return

        text = _extract_text(ev)
        if not text:
            return
        text = text.strip()

        if text.startswith("/register "):
            await self._handle_register(phone, text, ev)
            return

        person = self._resolve_person(phone)
        if person is None:
            await self._client.reply_message(
                "I don't know who you are. Send /register <name> first.", ev
            )
            return

        is_group: bool = ev.Info.MessageSource.IsGroup
        if is_group:
            user_text = f"[{person}] {text}"
            channel: str | None = f"group-{chat.User}"
        else:
            user_text = text
            channel = None

        logger.info("[%s%s] %s", person, f" in {channel}" if channel else "", user_text)
        await self._run_and_reply(ev, user_text, person, channel)

    async def _handle_register(self, phone: str, text: str, ev: Any) -> None:
        """Handle /register <name> — link this WhatsApp number to a household member."""
        parts = text.split(maxsplit=1)
        if len(parts) < 2 or not parts[1].strip():
            await self._client.reply_message("Usage: /register <name>", ev)
            return

        name = parts[1].strip().lower()

        async with self._user_map_lock:
            self._user_map[phone] = name
            _save_user_map(self._workspaces, self._user_map)

            member_dir = self._workspaces / name
            member_dir.mkdir(parents=True, exist_ok=True)

            contact = get_contact(self._workspaces, name)
            if contact and contact.member != name:
                contact.member = name
                save_contact(self._workspaces, contact)
                logger.info("Linked contact '%s' to member workspace '%s'", contact.id, name)

        if self._dispatcher:
            self._dispatcher.set_preference_if_unset(name, "whatsapp")

        await self._client.reply_message(
            f"Registered as '{name}'. You can now chat with me!", ev
        )
        logger.info("Registered WhatsApp user +%s as '%s'", phone, name)

    async def _run_and_reply(
        self,
        ev: Any,
        content: str | list[dict[str, Any]],
        person: str,
        channel: str | None,
    ) -> None:
        """Run content through the agent loop and reply with the response."""
        try:
            response = await self._loop.run(content, person, channel=channel)
        except Exception as exc:
            logger.exception("Agent loop failed for message from %s", person)
            error_msg = str(exc)
            if len(error_msg) > 300:
                error_msg = error_msg[:300] + "..."
            await self._client.reply_message(
                f"Sorry, something went wrong:\n\n{error_msg}", ev
            )
            return

        if response:
            for chunk in _split_message(response):
                await self._client.reply_message(chunk, ev)

    def _reverse_user_map(self) -> dict[str, str]:
        """Return person_name → phone mapping."""
        return {name: phone for phone, name in self._user_map.items()}

    def _has_person(self, person: str) -> bool:
        return person in self._reverse_user_map()

    async def _send_to_person(self, person: str, text: str) -> dict[str, Any]:
        """Send a proactive message to a person via WhatsApp."""
        from neonize.utils.jid import build_jid  # type: ignore[import-untyped]

        reverse = self._reverse_user_map()
        phone = reverse.get(person)
        if not phone:
            return {"status": "error", "detail": f"'{person}' not registered on WhatsApp"}
        try:
            jid = build_jid(phone)
            for chunk in _split_message(text):
                await self._client.send_message(jid, chunk)
            return {"status": "sent", "channel": "whatsapp", "person": person}
        except Exception as exc:
            logger.exception("Failed to send WhatsApp message to %s", person)
            return {"status": "error", "detail": str(exc)}

    def _register_with_dispatcher(self) -> None:
        if self._dispatcher:
            self._dispatcher.register(
                "whatsapp",
                send=self._send_to_person,
                has_person=self._has_person,
            )

    async def start(self) -> None:
        """Connect to WhatsApp. Non-blocking — QR code shown in logs on first run."""
        self._connect_task = asyncio.create_task(self._run_connect())
        self._register_with_dispatcher()
        logger.info(
            "WhatsApp channel connecting — scan the QR code in logs if this is a first run"
        )

    async def _run_connect(self) -> None:
        try:
            await self._client.connect()
            await self._client.idle()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("WhatsApp connection error")

    async def stop(self) -> None:
        """Disconnect from WhatsApp."""
        try:
            await self._client.stop()
        except Exception:
            logger.debug("WhatsApp stop raised an error (expected during shutdown)")
        if self._connect_task and not self._connect_task.done():
            self._connect_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._connect_task


def _split_message(text: str, max_len: int = 4000) -> list[str]:
    """Split a long message into chunks that fit WhatsApp's practical limit."""
    if len(text) <= max_len:
        return [text]
    chunks: list[str] = []
    while text:
        if len(text) <= max_len:
            chunks.append(text)
            break
        cut = text.rfind("\n", 0, max_len)
        if cut == -1:
            cut = max_len
        chunks.append(text[:cut])
        text = text[cut:].lstrip("\n")
    return chunks
