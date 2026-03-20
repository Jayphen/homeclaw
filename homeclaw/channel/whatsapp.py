"""WhatsApp channel adapter — connects WhatsApp messages to the agent loop via neonize.

Requires the optional [whatsapp] extra:  pip install homeclaw[whatsapp]
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import logging
from pathlib import Path
from typing import Any

from homeclaw.agent.loop import AgentLoop
from homeclaw.channel.dispatcher import ChannelDispatcher
from homeclaw.channel.registration import (
    load_user_map,
    register_member,
    register_self,
)

logger = logging.getLogger(__name__)

# Maps phone numbers to household member names.
_USER_MAP_FILE = "whatsapp_users.json"
def _load_known_groups(workspaces: Path) -> set[str]:
    """Discover group IDs from existing channel history directories."""
    channels_dir = workspaces / "household" / "channels"
    if not channels_dir.is_dir():
        return set()
    return {
        d.name.removeprefix("group-")
        for d in channels_dir.iterdir()
        if d.is_dir() and d.name.startswith("group-")
    }


def _extract_text(ev: Any) -> str | None:
    """Extract plain text from a WhatsApp MessageEv protobuf."""
    return (
        ev.Message.conversation
        or ev.Message.extendedTextMessage.text
        or None
    )


def _has_image(ev: Any) -> bool:
    """Return True if the message contains an image."""
    try:
        img = ev.Message.imageMessage
        return bool(img and img.url)
    except AttributeError:
        return False


def _md_to_whatsapp(text: str) -> str:
    """Convert markdown formatting to WhatsApp-compatible formatting.

    WhatsApp uses: *bold*, _italic_, ~strikethrough~, ```code```.
    Markdown uses: **bold**, *italic*, ~~strike~~, ```code```.
    """
    import re

    lines = text.split("\n")
    result: list[str] = []

    in_code_block = False
    for line in lines:
        # Pass through code blocks unchanged
        if line.strip().startswith("```"):
            in_code_block = not in_code_block
            result.append(line)
            continue
        if in_code_block:
            result.append(line)
            continue

        # Headings → bold
        line = re.sub(r"^#{1,6}\s+(.+)$", r"*\1*", line)

        # Unordered list markers → bullet
        line = re.sub(r"^(\s*)[-*+]\s+", r"\1• ", line)

        # Links: [text](url) → text (url)
        line = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1 (\2)", line)

        # Bold: **text** or __text__ → *text*
        line = re.sub(r"\*\*(.+?)\*\*", r"*\1*", line)
        line = re.sub(r"__(.+?)__", r"*\1*", line)

        # Italic: remaining single *text* → _text_
        # Only match *text* that isn't already WhatsApp bold from above.
        # We skip this since WhatsApp _italic_ conflicts with markdown's
        # _italic_ — they're the same, so no conversion needed.

        # Strikethrough: ~~text~~ → ~text~
        line = re.sub(r"~~(.+?)~~", r"~\1~", line)

        result.append(line)

    return "\n".join(result)


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
        phone_number: str | None = None,
    ) -> None:
        # Runtime import — neonize is an optional dependency.
        from neonize.aioze.client import NewAClient  # type: ignore[import-untyped]
        from neonize.aioze.events import (  # type: ignore[import-untyped]
            ConnectedEv,
            DisconnectedEv,
            MessageEv,
            PairStatusEv,
        )

        self._loop = loop
        self._workspaces = workspaces
        self._allowed_phones = allowed_phones
        self._user_map = load_user_map(workspaces, _USER_MAP_FILE)
        self._user_map_lock = asyncio.Lock()

        db_dir = workspaces / "household"
        db_dir.mkdir(parents=True, exist_ok=True)
        self._client: Any = NewAClient(str(db_dir / "whatsapp.db"))
        self._connect_task: asyncio.Task[None] | None = None
        self._dispatcher = dispatcher

        self._connected = False
        self._last_qr: bytes | None = None  # Raw QR data for web UI
        self._known_groups: set[str] = _load_known_groups(workspaces)
        # Track which user IDs are LIDs (server="lid") vs phone numbers
        # (server="s.whatsapp.net") so outbound messages use the right JID.
        self._lid_users: set[str] = set()

        # Store event types so _register_handlers can reference them
        self._ConnectedEv = ConnectedEv
        self._DisconnectedEv = DisconnectedEv
        self._MessageEv = MessageEv
        self._PairStatusEv = PairStatusEv

        self._register_handlers()

        # QR code capture: neonize passes raw QR bytes via the qr callback.
        # We store them so the web UI can serve the QR as an image.
        @self._client.event.qr
        async def _on_qr(_: Any, qr_data: bytes) -> None:
            self._last_qr = qr_data
            logger.info("WhatsApp QR code received — scan it or view at /api/whatsapp/qr")

        # Pair-code auth: if a phone number is configured, register the
        # paircode callback so neonize uses numeric code auth instead of QR.
        # The user enters the code on their phone — no camera needed.
        if phone_number:
            @self._client.paircode
            async def _on_paircode(
                _: Any, code: str, connected: bool = False,
            ) -> None:
                if connected:
                    logger.info("WhatsApp pair code accepted")
                else:
                    logger.info(
                        "\n"
                        "╔══════════════════════════════════════╗\n"
                        "║  WhatsApp pair code: %-16s ║\n"
                        "║                                     ║\n"
                        "║  Enter this on your phone:           ║\n"
                        "║  Settings → Linked Devices → Link    ║\n"
                        "║  → Link with phone number instead    ║\n"
                        "╚══════════════════════════════════════╝",
                        code,
                    )

    @property
    def connected(self) -> bool:
        """Whether the WhatsApp client is currently connected."""
        return self._connected

    @property
    def pending_qr(self) -> bytes | None:
        """Raw QR code data if awaiting scan, or None if already paired."""
        if self._connected:
            return None
        return self._last_qr

    def _register_handlers(self) -> None:
        @self._client.event(self._ConnectedEv)
        async def _on_connected(_: Any, __: Any) -> None:
            self._connected = True
            logger.info("WhatsApp connected")

        @self._client.event(self._DisconnectedEv)
        async def _on_disconnected(_: Any, __: Any) -> None:
            self._connected = False
            logger.warning("WhatsApp disconnected — will reconnect automatically")

        @self._client.event(self._PairStatusEv)
        async def _on_pair_status(_: Any, ev: Any) -> None:
            logger.info("WhatsApp paired as +%s", ev.ID.User)

        @self._client.event(self._MessageEv)
        async def _on_message(_: Any, ev: Any) -> None:
            try:
                await self._handle_message(ev)
            except Exception:
                logger.exception("Unhandled error in WhatsApp message handler")

    def _is_allowed(self, phone: str) -> bool:
        if self._allowed_phones is None:
            return True
        # Normalize incoming phone to match the normalized allowed list
        normalized = phone.translate(str.maketrans("", "", "+- ()")).strip()
        return normalized in self._allowed_phones

    def _resolve_person(self, phone: str) -> str | None:
        return self._user_map.get(phone)

    async def _handle_message(self, ev: Any) -> None:
        """Route an incoming WhatsApp message through the agent loop."""
        logger.debug(
            "WhatsApp raw message: from_me=%s sender=%s chat=%s",
            ev.Info.MessageSource.IsFromMe,
            ev.Info.MessageSource.Sender,
            ev.Info.MessageSource.Chat,
        )
        if ev.Info.MessageSource.IsFromMe:
            return

        sender = ev.Info.MessageSource.Sender
        phone: str = sender.User
        if getattr(sender, "Server", "") == "lid":
            self._lid_users.add(phone)

        if not self._is_allowed(phone):
            logger.warning(
                "Rejected message from unauthorized phone %s — "
                "add this number to whatsapp_allowed_users in Settings",
                phone,
            )
            return

        # Image messages are handled separately
        if _has_image(ev):
            await self._handle_photo(ev, phone)
            return

        text = _extract_text(ev)
        if not text:
            return
        text = text.strip()

        if text.startswith("/register_member "):
            await self._handle_register_member(phone, text, ev)
            return

        if text.startswith("/register "):
            await self._handle_register(phone, text, ev)
            return

        person = self._resolve_person(phone)
        if person is None:
            await self._client.reply_message(
                f"I don't know who you are yet. Ask an admin to register "
                f"you with: /register_member <yourname> {phone}",
                ev,
            )
            return

        is_group: bool = ev.Info.MessageSource.IsGroup
        chat: Any = ev.Info.MessageSource.Chat
        if is_group:
            self._known_groups.add(chat.User)
            user_text = f"[{person}] {text}"
            channel: str | None = f"group-{chat.User}"
        else:
            user_text = text
            channel = None

        logger.info("[%s%s] %s", person, f" in {channel}" if channel else "", user_text)
        await self._run_and_reply(ev, user_text, person, channel)

    async def _handle_photo(self, ev: Any, phone: str) -> None:
        """Handle incoming image — download, base64-encode, send as multimodal."""
        person = self._resolve_person(phone)
        if person is None:
            await self._client.reply_message(
                "I don't know who you are. Send /register <name> first.", ev
            )
            return

        try:
            image_bytes = await self._client.download_any(ev.Message)
        except Exception:
            logger.exception("Failed to download WhatsApp image from %s", person)
            await self._client.reply_message(
                "Sorry, I couldn't download that image.", ev
            )
            return

        b64_data = base64.b64encode(image_bytes).decode("ascii")
        mimetype = ev.Message.imageMessage.mimetype or "image/jpeg"
        caption = ev.Message.imageMessage.caption or ""

        is_group: bool = ev.Info.MessageSource.IsGroup
        chat: Any = ev.Info.MessageSource.Chat
        if is_group:
            caption = f"[{person}] {caption}" if caption else f"[{person}]"
            channel: str | None = f"group-{chat.User}"
        else:
            channel = None

        content: list[dict[str, Any]] = [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": mimetype,
                    "data": b64_data,
                },
            },
        ]
        if caption:
            content.append({"type": "text", "text": caption})
        else:
            content.append({"type": "text", "text": "[shared a photo]"})

        logger.info(
            "[%s%s] photo (%d KB)%s",
            person,
            f" in {channel}" if channel else "",
            len(image_bytes) // 1024,
            f": {caption}" if caption else "",
        )
        await self._run_and_reply(ev, content, person, channel)

    async def _handle_register(self, phone: str, text: str, ev: Any) -> None:
        """Handle /register <name> — link this WhatsApp number to a household member."""
        parts = text.split(maxsplit=1)
        if len(parts) < 2 or not parts[1].strip():
            await self._client.reply_message("Usage: /register <name>", ev)
            return

        msg = await register_self(
            identifier=phone,
            name=parts[1],
            workspaces=self._workspaces,
            map_file=_USER_MAP_FILE,
            user_map=self._user_map,
            lock=self._user_map_lock,
            channel_name="whatsapp",
            dispatcher=self._dispatcher,
        )
        await self._client.reply_message(msg, ev)

    async def _handle_register_member(
        self, phone: str, text: str, ev: Any,
    ) -> None:
        """Handle /register_member <name> <phone> — admin-only."""
        parts = text.split()
        if len(parts) < 3:
            await self._client.reply_message(
                "Usage: /register_member <name> <phone>\n"
                "Example: /register_member alice 61412345678",
                ev,
            )
            return

        target_phone = parts[2].strip().translate(
            str.maketrans("", "", "+- ()")
        )
        ok, msg = await register_member(
            admin_identifier=phone,
            target_identifier=target_phone,
            name=parts[1],
            workspaces=self._workspaces,
            map_file=_USER_MAP_FILE,
            user_map=self._user_map,
            lock=self._user_map_lock,
            channel_name="whatsapp",
            dispatcher=self._dispatcher,
            allowed_set=self._allowed_phones,
        )
        await self._client.reply_message(msg, ev)

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
            formatted = _md_to_whatsapp(response)
            for chunk in _split_message(formatted):
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
            server = "lid" if phone in self._lid_users else "s.whatsapp.net"
            jid = build_jid(phone, server=server)
            formatted = _md_to_whatsapp(text)
            for chunk in _split_message(formatted):
                await self._client.send_message(jid, chunk)
            return {"status": "sent", "channel": "whatsapp", "person": person}
        except Exception as exc:
            logger.exception("Failed to send WhatsApp message to %s", person)
            return {"status": "error", "detail": str(exc)}

    async def _send_to_group(self, group_id: str, text: str) -> dict[str, Any]:
        """Send a message to a WhatsApp group chat."""
        from neonize.utils.jid import build_jid  # type: ignore[import-untyped]

        try:
            # build_jid with a @g.us suffix creates a proper group JID
            gid = build_jid(group_id, server="g.us")
            formatted = _md_to_whatsapp(text)
            for chunk in _split_message(formatted):
                await self._client.send_message(gid, chunk)
            return {"status": "sent", "channel": "whatsapp", "group": group_id}
        except Exception as exc:
            logger.exception("Failed to send WhatsApp group message to %s", group_id)
            return {"status": "error", "detail": str(exc)}

    def _list_groups(self) -> list[str]:
        return list(self._known_groups)

    def _register_with_dispatcher(self) -> None:
        if self._dispatcher:
            self._dispatcher.register(
                "whatsapp",
                send=self._send_to_person,
                has_person=self._has_person,
                send_group=self._send_to_group,
                group_ids=self._list_groups,
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
