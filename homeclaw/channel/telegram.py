"""Telegram channel adapter — connects Telegram messages to the agent loop."""

import base64
import json
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from telegram import Update
from telegram.constants import ChatType
from telegram.ext import Application, CommandHandler, MessageHandler, filters

from homeclaw.agent.loop import AgentLoop
from homeclaw.contacts.store import get_contact, save_contact

logger = logging.getLogger(__name__)

# Maps Telegram user IDs to household member names.
# Stored in workspaces/household/telegram_users.json as {"<telegram_id>": "member_name"}.
_USER_MAP_FILE = "household/telegram_users.json"


def _load_user_map(workspaces: Path) -> dict[str, str]:
    path = workspaces / _USER_MAP_FILE
    if not path.exists():
        return {}
    return json.loads(path.read_text())  # type: ignore[no-any-return]


def _save_user_map(workspaces: Path, user_map: dict[str, str]) -> None:
    path = workspaces / _USER_MAP_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(user_map, indent=2) + "\n")


class TelegramChannel:
    """Bridges Telegram <-> AgentLoop."""

    def __init__(
        self,
        token: str,
        loop: AgentLoop,
        workspaces: Path,
        on_tool_call: Any | None = None,
        on_scheduler_start: Callable[[], None] | None = None,
        allowed_user_ids: set[int] | None = None,
    ) -> None:
        self._token = token
        self._loop = loop
        self._workspaces = workspaces
        self._on_tool_call = on_tool_call
        self._on_scheduler_start = on_scheduler_start
        self._allowed_user_ids = allowed_user_ids
        self._user_map = _load_user_map(workspaces)

    def _is_allowed(self, update: Update) -> bool:
        """Check if the Telegram user is in the allowlist (if configured)."""
        if self._allowed_user_ids is None:
            return True
        if update.effective_user is None:
            return False
        return update.effective_user.id in self._allowed_user_ids

    def _resolve_person(self, update: Update) -> str | None:
        """Map a Telegram user to a household member name, or None if unknown."""
        if update.effective_user is None:
            return None
        tid = str(update.effective_user.id)
        return self._user_map.get(tid)

    async def _handle_start(self, update: Update, _context: Any) -> None:
        """Handle /start — greet and show registration status."""
        if update.message is None:
            return
        if not self._is_allowed(update):
            logger.warning("Rejected /start from unauthorized user %s", update.effective_user)
            return
        person = self._resolve_person(update)
        if person:
            await update.message.reply_text(f"Hi {person}! I'm homeclaw, your household assistant.")
        else:
            await update.message.reply_text(
                "Hi! I'm homeclaw. I don't know who you are yet.\n"
                "Use /register <name> to link your Telegram account to a household member."
            )

    async def _handle_register(self, update: Update, _context: Any) -> None:
        """Handle /register <name> — link this Telegram user to a household member."""
        if update.message is None or update.effective_user is None:
            return
        if not self._is_allowed(update):
            logger.warning("Rejected /register from unauthorized user %s", update.effective_user)
            return
        text = (update.message.text or "").strip()
        parts = text.split(maxsplit=1)
        if len(parts) < 2 or not parts[1].strip():
            await update.message.reply_text("Usage: /register <name>")
            return

        name = parts[1].strip().lower()
        tid = str(update.effective_user.id)
        self._user_map[tid] = name
        _save_user_map(self._workspaces, self._user_map)

        # Ensure the member workspace directory exists
        member_dir = self._workspaces / name
        member_dir.mkdir(parents=True, exist_ok=True)

        # Auto-link to existing contact record if one matches
        contact = get_contact(self._workspaces, name)
        if contact and contact.member != name:
            contact.member = name
            save_contact(self._workspaces, contact)
            logger.info("Linked contact '%s' to member workspace '%s'", contact.id, name)

        await update.message.reply_text(f"Registered as '{name}'. You can now chat with me!")
        logger.info(
            "Registered Telegram user %s (id=%s) as '%s'",
            update.effective_user.username, tid, name,
        )

    def _is_group_chat(self, update: Update) -> bool:
        """Return True if the message is from a group or supergroup."""
        chat = update.effective_chat
        return chat is not None and chat.type in (ChatType.GROUP, ChatType.SUPERGROUP)

    async def _handle_message(self, update: Update, _context: Any) -> None:
        """Handle incoming text messages — route through the agent loop."""
        if update.message is None or not update.message.text:
            return
        if not self._is_allowed(update):
            return

        person = self._resolve_person(update)
        if person is None:
            await update.message.reply_text(
                "I don't know who you are. Use /register <name> first."
            )
            return

        user_text = update.message.text
        is_group = self._is_group_chat(update)

        # In group chats, prefix with speaker name and use shared channel history
        if is_group:
            user_text = f"[{person}] {user_text}"
            chat_id = str(update.effective_chat.id) if update.effective_chat else "group"
            channel = f"group-{chat_id}"
        else:
            channel = None

        logger.info("[%s%s] %s", person, f" in {channel}" if channel else "", user_text)
        await self._run_and_reply(update, user_text, person, channel)

    async def _handle_photo(self, update: Update, _context: Any) -> None:
        """Handle incoming photos — download, base64-encode, send as multimodal."""
        if update.message is None or not update.message.photo:
            return
        if not self._is_allowed(update):
            return

        person = self._resolve_person(update)
        if person is None:
            await update.message.reply_text(
                "I don't know who you are. Use /register <name> first."
            )
            return

        # Telegram provides multiple sizes; pick the largest
        photo = update.message.photo[-1]
        file = await photo.get_file()
        photo_bytes = await file.download_as_bytearray()
        b64_data = base64.b64encode(bytes(photo_bytes)).decode("ascii")

        caption = update.message.caption or ""
        is_group = self._is_group_chat(update)
        if is_group:
            caption = f"[{person}] {caption}" if caption else f"[{person}]"
            chat_id = (
                str(update.effective_chat.id)
                if update.effective_chat
                else "group"
            )
            channel: str | None = f"group-{chat_id}"
        else:
            channel = None

        # Build multimodal content blocks
        content: list[dict[str, Any]] = [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/jpeg",
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
            len(photo_bytes) // 1024,
            f": {caption}" if caption else "",
        )
        await self._run_and_reply(update, content, person, channel)

    async def _run_and_reply(
        self,
        update: Update,
        content: str | list[dict[str, Any]],
        person: str,
        channel: str | None,
    ) -> None:
        """Send content through the agent loop and reply with the response."""
        try:
            response = await self._loop.run(content, person, channel=channel)
        except Exception as exc:
            logger.exception("Agent loop failed for message from %s", person)
            # Surface a useful error message to the user
            error_msg = str(exc)
            # Truncate very long error messages
            if len(error_msg) > 300:
                error_msg = error_msg[:300] + "..."
            if update.message:
                await update.message.reply_text(
                    f"Sorry, something went wrong:\n\n{error_msg}"
                )
            return

        if response and update.message:
            # Telegram has a 4096 char limit per message — split if needed
            for chunk in _split_message(response):
                await _send_markdown(update.message, chunk)

    async def _post_init(self, _app: Application) -> None:  # type: ignore[type-arg]
        """Called by python-telegram-bot after the event loop is running."""
        if self._on_scheduler_start:
            self._on_scheduler_start()

    def _build_app(self) -> Application:  # type: ignore[type-arg]
        """Build and configure the Telegram Application."""
        app = (
            Application.builder()
            .token(self._token)
            .post_init(self._post_init)
            .build()
        )
        app.add_handler(CommandHandler("start", self._handle_start))
        app.add_handler(CommandHandler("register", self._handle_register))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message))
        app.add_handler(MessageHandler(filters.PHOTO, self._handle_photo))
        return app

    def run(self) -> None:
        """Build the Telegram application and start polling. Blocks forever."""
        app = self._build_app()
        logger.info("Starting Telegram polling...")
        app.run_polling()

    async def start(self) -> None:
        """Start polling without blocking — for running alongside other async tasks."""
        self._app = self._build_app()
        await self._app.initialize()
        await self._app.start()
        await self._app.updater.start_polling()  # type: ignore[union-attr]
        logger.info("Telegram polling started (non-blocking)")

    async def stop(self) -> None:
        """Stop the non-blocking Telegram polling."""
        if hasattr(self, "_app"):
            await self._app.updater.stop()  # type: ignore[union-attr]
            await self._app.stop()
            await self._app.shutdown()


async def _send_markdown(message: Any, text: str) -> None:
    """Send a message with Markdown formatting, falling back to plain text."""
    from telegram.constants import ParseMode

    try:
        await message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
    except Exception:
        # Telegram's Markdown parser is strict — fall back to plain text
        await message.reply_text(text)


def _split_message(text: str, max_len: int = 4096) -> list[str]:
    """Split a long message into chunks that fit Telegram's limit."""
    if len(text) <= max_len:
        return [text]
    chunks: list[str] = []
    while text:
        if len(text) <= max_len:
            chunks.append(text)
            break
        # Try to split at a newline near the limit
        cut = text.rfind("\n", 0, max_len)
        if cut == -1:
            cut = max_len
        chunks.append(text[:cut])
        text = text[cut:].lstrip("\n")
    return chunks
