"""Unit tests for the Telegram channel adapter."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from homeclaw.channel.telegram import TelegramChannel, _split_message


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_update(
    user_id: int = 123, text: str = "hello", chat_type: str = "private",
) -> MagicMock:
    update = MagicMock()
    update.effective_user.id = user_id
    update.effective_user.username = "testuser"
    update.effective_chat.id = -100999
    update.effective_chat.type = chat_type
    update.message.text = text
    update.message.reply_text = AsyncMock()
    return update


def _make_channel(
    tmp_path: Path,
    user_map: dict[str, str] | None = None,
    allowed_user_ids: set[int] | None = None,
) -> TelegramChannel:
    workspaces = tmp_path / "workspaces"
    workspaces.mkdir()
    household = workspaces / "household"
    household.mkdir()

    if user_map:
        (household / "telegram_users.json").write_text(json.dumps(user_map))

    loop = AsyncMock()
    loop.run.return_value = "I'm homeclaw."

    return TelegramChannel(
        token="fake-token",
        loop=loop,
        workspaces=workspaces,
        allowed_user_ids=allowed_user_ids,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSplitMessage:
    def test_short_message(self) -> None:
        assert _split_message("hello") == ["hello"]

    def test_long_message_splits_at_newline(self) -> None:
        chunks = _split_message("a" * 50 + "\n" + "b" * 50, max_len=60)
        assert len(chunks) == 2
        assert chunks[0] == "a" * 50
        assert chunks[1] == "b" * 50

    def test_long_message_hard_split(self) -> None:
        text = "x" * 100
        chunks = _split_message(text, max_len=40)
        assert "".join(chunks) == text
        assert all(len(c) <= 40 for c in chunks)


class TestRegistration:
    @pytest.mark.asyncio
    async def test_register_saves_mapping(self, tmp_path: Path) -> None:
        channel = _make_channel(tmp_path)
        update = _make_update(user_id=42, text="/register alice")

        await channel._handle_register(update, None)

        update.message.reply_text.assert_awaited_once()
        reply = update.message.reply_text.call_args[0][0]
        assert "alice" in reply

        # Verify persisted
        map_file = tmp_path / "workspaces" / "household" / "telegram_users.json"
        saved = json.loads(map_file.read_text())
        assert saved["42"] == "alice"

    @pytest.mark.asyncio
    async def test_register_no_name_shows_usage(self, tmp_path: Path) -> None:
        channel = _make_channel(tmp_path)
        update = _make_update(text="/register")

        await channel._handle_register(update, None)

        reply = update.message.reply_text.call_args[0][0]
        assert "Usage" in reply


class TestAllowedUsers:
    @pytest.mark.asyncio
    async def test_allowed_user_can_message(self, tmp_path: Path) -> None:
        channel = _make_channel(
            tmp_path, user_map={"123": "alice"}, allowed_user_ids={123},
        )
        update = _make_update(user_id=123, text="hi")

        await channel._handle_message(update, None)

        channel._loop.run.assert_awaited_once()  # type: ignore[union-attr]

    @pytest.mark.asyncio
    async def test_disallowed_user_silently_dropped(self, tmp_path: Path) -> None:
        channel = _make_channel(
            tmp_path, user_map={"999": "eve"}, allowed_user_ids={123},
        )
        update = _make_update(user_id=999, text="hi")

        await channel._handle_message(update, None)

        channel._loop.run.assert_not_awaited()  # type: ignore[union-attr]
        # No reply sent — silent drop
        update.message.reply_text.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_disallowed_user_cannot_register(self, tmp_path: Path) -> None:
        channel = _make_channel(tmp_path, allowed_user_ids={123})
        update = _make_update(user_id=999, text="/register eve")

        await channel._handle_register(update, None)

        update.message.reply_text.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_no_allowlist_means_open_access(self, tmp_path: Path) -> None:
        channel = _make_channel(tmp_path, user_map={"999": "bob"})
        update = _make_update(user_id=999, text="hi")

        await channel._handle_message(update, None)

        channel._loop.run.assert_awaited_once()  # type: ignore[union-attr]


class TestMessageHandling:
    @pytest.mark.asyncio
    async def test_known_user_gets_response(self, tmp_path: Path) -> None:
        channel = _make_channel(tmp_path, user_map={"123": "alice"})
        update = _make_update(user_id=123, text="what's for dinner?")

        await channel._handle_message(update, None)

        channel._loop.run.assert_awaited_once_with(  # type: ignore[union-attr]
            "what's for dinner?", "alice", channel=None,
        )
        from telegram.constants import ParseMode

        update.message.reply_text.assert_awaited_once_with(
            "I'm homeclaw.", parse_mode=ParseMode.MARKDOWN,
        )

    @pytest.mark.asyncio
    async def test_unknown_user_gets_registration_prompt(self, tmp_path: Path) -> None:
        channel = _make_channel(tmp_path)
        update = _make_update(user_id=999, text="hello")

        await channel._handle_message(update, None)

        reply = update.message.reply_text.call_args[0][0]
        assert "/register" in reply
        channel._loop.run.assert_not_awaited()  # type: ignore[union-attr]

    @pytest.mark.asyncio
    async def test_agent_error_sends_apology(self, tmp_path: Path) -> None:
        channel = _make_channel(tmp_path, user_map={"123": "alice"})
        channel._loop.run.side_effect = RuntimeError("boom")  # type: ignore[union-attr]
        update = _make_update(user_id=123, text="crash me")

        await channel._handle_message(update, None)

        reply = update.message.reply_text.call_args[0][0]
        assert "wrong" in reply.lower()

    @pytest.mark.asyncio
    async def test_group_message_prefixes_speaker_and_passes_channel(
        self, tmp_path: Path,
    ) -> None:
        channel = _make_channel(tmp_path, user_map={"123": "alice"})
        update = _make_update(user_id=123, text="dinner at 7", chat_type="supergroup")

        await channel._handle_message(update, None)

        channel._loop.run.assert_awaited_once_with(  # type: ignore[union-attr]
            "[alice] dinner at 7", "alice", channel="group--100999",
        )

    @pytest.mark.asyncio
    async def test_dm_does_not_pass_channel(self, tmp_path: Path) -> None:
        channel = _make_channel(tmp_path, user_map={"123": "alice"})
        update = _make_update(user_id=123, text="private thing", chat_type="private")

        await channel._handle_message(update, None)

        channel._loop.run.assert_awaited_once_with(  # type: ignore[union-attr]
            "private thing", "alice", channel=None,
        )
