"""Telegram channel adapter — connects Telegram messages to the agent loop."""

import asyncio
import base64
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from telegram import Update
from telegram.constants import ChatAction, ChatType
from telegram.ext import Application, CommandHandler, MessageHandler, filters

from homeclaw.agent.loop import AgentLoop
from homeclaw.channel.dispatcher import ChannelDispatcher
from homeclaw.channel.registration import (
    load_user_map,
    register_member,
    register_self,
)

logger = logging.getLogger(__name__)

# Maps Telegram user IDs to household member names.
_USER_MAP_FILE = "telegram_users.json"


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
        dispatcher: ChannelDispatcher | None = None,
    ) -> None:
        self._token = token
        self._loop = loop
        self._workspaces = workspaces
        self._on_tool_call = on_tool_call
        self._on_scheduler_start = on_scheduler_start
        self._allowed_user_ids = allowed_user_ids
        self._user_map = load_user_map(workspaces, _USER_MAP_FILE)
        self._user_map_lock = asyncio.Lock()
        self._dispatcher = dispatcher

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

        tid = str(update.effective_user.id)
        msg = await register_self(
            identifier=tid,
            name=parts[1],
            workspaces=self._workspaces,
            map_file=_USER_MAP_FILE,
            user_map=self._user_map,
            lock=self._user_map_lock,
            channel_name="telegram",
            dispatcher=self._dispatcher,
        )
        await update.message.reply_text(msg)

    async def _handle_register_member(
        self, update: Update, _context: Any,
    ) -> None:
        """Handle /register_member <name> <telegram_id> — admin-only."""
        if update.message is None:
            return

        text = (update.message.text or "").strip()
        parts = text.split()
        if len(parts) < 3:
            await update.message.reply_text(
                "Usage: /register_member <name> <telegram_user_id>\n"
                "Example: /register_member alice 123456789"
            )
            return

        tid = str(update.effective_user.id) if update.effective_user else ""
        ok, msg = await register_member(
            admin_identifier=tid,
            target_identifier=parts[2].strip(),
            name=parts[1],
            workspaces=self._workspaces,
            map_file=_USER_MAP_FILE,
            user_map=self._user_map,
            lock=self._user_map_lock,
            channel_name="telegram",
            dispatcher=self._dispatcher,
            allowed_set=(
                {str(x) for x in self._allowed_user_ids}
                if self._allowed_user_ids is not None else None
            ),
        )
        if ok and self._allowed_user_ids is not None:
            self._allowed_user_ids.add(int(parts[2].strip()))
        await update.message.reply_text(msg)

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

    async def _send_typing_until_done(self, update: Update, done: asyncio.Event) -> None:
        """Send 'typing' chat action every 4s until the done event is set."""
        chat = update.effective_chat
        if chat is None:
            return
        while not done.is_set():
            try:
                await chat.send_action(ChatAction.TYPING)
            except Exception:
                return
            # Telegram typing indicator lasts ~5s; resend every 4s
            try:
                await asyncio.wait_for(done.wait(), timeout=4.0)
            except TimeoutError:
                pass

    async def _run_and_reply(
        self,
        update: Update,
        content: str | list[dict[str, Any]],
        person: str,
        channel: str | None,
    ) -> None:
        """Send content through the agent loop and reply with the response."""
        done = asyncio.Event()
        typing_task = asyncio.create_task(self._send_typing_until_done(update, done))
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
        finally:
            done.set()
            await typing_task

        if response and update.message:
            # Telegram has a 4096 char limit per message — split if needed
            for chunk in _split_message(response):
                await _send_markdown(update.message, chunk)

    def _reverse_user_map(self) -> dict[str, str]:
        """Return person_name → telegram_id mapping."""
        return {name: tid for tid, name in self._user_map.items()}

    def _has_person(self, person: str) -> bool:
        return person in self._reverse_user_map()

    async def _send_to_person(self, person: str, text: str) -> dict[str, Any]:
        """Send a proactive message to a person via Telegram."""
        reverse = self._reverse_user_map()
        tid = reverse.get(person)
        if not tid:
            return {"status": "error", "detail": f"'{person}' not registered on Telegram"}
        if not hasattr(self, "_app"):
            return {"status": "error", "detail": "Telegram bot not running"}
        try:
            for chunk in _split_message(text):
                await _send_markdown(self._app.bot, chunk, chat_id=int(tid))
            return {"status": "sent", "channel": "telegram", "person": person}
        except Exception as exc:
            logger.exception("Failed to send Telegram message to %s", person)
            return {"status": "error", "detail": str(exc)}

    def _register_with_dispatcher(self) -> None:
        if self._dispatcher:
            self._dispatcher.register(
                "telegram",
                send=self._send_to_person,
                has_person=self._has_person,
            )

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
        app.add_handler(CommandHandler("register_member", self._handle_register_member))
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
        self._register_with_dispatcher()
        logger.info("Telegram polling started (non-blocking)")

    async def stop(self) -> None:
        """Stop the non-blocking Telegram polling."""
        if hasattr(self, "_app"):
            await self._app.updater.stop()  # type: ignore[union-attr]
            await self._app.stop()
            await self._app.shutdown()


def _clean_markdown_for_telegram(text: str) -> str:
    """Normalise standard markdown so it renders well in Telegram's legacy Markdown.

    1. Collapse redundant links where the text equals the URL:
       [https://example.com](https://example.com) → https://example.com
    2. Rewrite numbered-list links so the title is the link text:
       "1. Title\n   [url](url)" → "1. [Title](url)"
       "1. Title\n   url"       → "1. [Title](url)"
    """
    import re

    # Collapse [url](same-url) → bare url
    text = re.sub(
        r"\[(?P<url>https?://[^\]]+)\]\((?P=url)\)",
        r"\g<url>",
        text,
    )

    # Rewrite numbered-list items: "N. Title\n   url" → "N. [Title](url)"
    def _rewrite_list_item(m: re.Match[str]) -> str:
        num = m.group("num")
        title = m.group("title").strip()
        url = m.group("url").strip()
        return f"{num}. [{title}]({url})"

    text = re.sub(
        r"(?P<num>\d+)\.\s+(?P<title>[^\n]+?)\n\s+(?P<url>https?://\S+)",
        _rewrite_list_item,
        text,
    )

    return text


def _to_telegram_markdown(text: str) -> str:
    """Convert standard markdown to Telegram MarkdownV2.

    1. Clean up redundant links and rewrite numbered-list URLs
    2. Convert to MarkdownV2 via telegramify-markdown
    """
    import telegramify_markdown

    text = _clean_markdown_for_telegram(text)
    return telegramify_markdown.markdownify(text)


async def _send_markdown(
    message: Any, text: str, *, chat_id: int | None = None
) -> None:
    """Send a message with MarkdownV2 formatting, falling back to plain text.

    If *chat_id* is provided, *message* is treated as a Bot and
    ``send_message`` is used (for proactive outbound messages).
    Otherwise *message* is a Message object and ``reply_text`` is used.
    """
    from telegram.constants import ParseMode

    formatted = _to_telegram_markdown(text)

    if chat_id is not None:
        try:
            await message.send_message(chat_id, formatted, parse_mode=ParseMode.MARKDOWN_V2)
        except Exception:
            await message.send_message(chat_id, text)
    else:
        try:
            await message.reply_text(formatted, parse_mode=ParseMode.MARKDOWN_V2)
        except Exception:
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
