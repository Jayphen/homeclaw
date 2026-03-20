"""Unit tests for the WhatsApp channel adapter."""

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from homeclaw.channel.whatsapp import WhatsAppChannel, _extract_text, _has_image, _split_message


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ev(
    phone: str = "14155551234",
    text: str = "hello",
    is_from_me: bool = False,
    is_group: bool = False,
    chat_user: str = "14155551234",
) -> MagicMock:
    ev = MagicMock()
    ev.Info.MessageSource.IsFromMe = is_from_me
    ev.Info.MessageSource.IsGroup = is_group
    ev.Info.MessageSource.Sender.User = phone
    ev.Info.MessageSource.Chat.User = chat_user
    ev.Message.conversation = text
    ev.Message.extendedTextMessage.text = ""
    ev.Message.imageMessage = None
    return ev


def _make_channel(
    tmp_path: Path,
    user_map: dict[str, str] | None = None,
    allowed_phones: set[str] | None = None,
) -> WhatsAppChannel:
    workspaces = tmp_path / "workspaces"
    (workspaces / "household").mkdir(parents=True)
    if user_map:
        (workspaces / "household" / "whatsapp_users.json").write_text(
            json.dumps(user_map)
        )

    loop_mock = AsyncMock()
    loop_mock.run.return_value = "I'm homeclaw."

    # Bypass __init__ which imports neonize
    channel = object.__new__(WhatsAppChannel)
    channel._loop = loop_mock
    channel._workspaces = workspaces
    channel._allowed_phones = allowed_phones
    channel._user_map = user_map or {}
    channel._user_map_lock = asyncio.Lock()
    channel._client = AsyncMock()
    channel._connect_task = None
    channel._dispatcher = None
    channel._ConnectedEv = object
    channel._MessageEv = object
    channel._PairStatusEv = object
    channel._connected = False
    channel._last_qr = None
    channel._known_groups = set()
    return channel


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


class TestExtractText:
    def test_conversation_field(self) -> None:
        ev = _make_ev(text="hi there")
        assert _extract_text(ev) == "hi there"

    def test_extended_text_message_field(self) -> None:
        ev = _make_ev(text="")
        ev.Message.conversation = ""
        ev.Message.extendedTextMessage.text = "extended text"
        assert _extract_text(ev) == "extended text"

    def test_neither_field_returns_none(self) -> None:
        ev = _make_ev(text="")
        ev.Message.conversation = ""
        ev.Message.extendedTextMessage.text = ""
        assert _extract_text(ev) is None


class TestHasImage:
    def test_with_image(self) -> None:
        ev = _make_ev()
        ev.Message.imageMessage = MagicMock(url="https://example.com/img.jpg")
        assert _has_image(ev) is True

    def test_without_image(self) -> None:
        ev = _make_ev()
        ev.Message.imageMessage = None
        assert _has_image(ev) is False


class TestAllowedPhones:
    def test_allowed(self, tmp_path: Path) -> None:
        channel = _make_channel(tmp_path, allowed_phones={"14155551234"})
        assert channel._is_allowed("14155551234") is True

    def test_disallowed(self, tmp_path: Path) -> None:
        channel = _make_channel(tmp_path, allowed_phones={"14155551234"})
        assert channel._is_allowed("19995550000") is False

    def test_no_allowlist_means_open(self, tmp_path: Path) -> None:
        channel = _make_channel(tmp_path, allowed_phones=None)
        assert channel._is_allowed("19995550000") is True


class TestRegistration:
    @pytest.mark.asyncio
    async def test_register_saves_mapping(self, tmp_path: Path) -> None:
        channel = _make_channel(tmp_path)
        ev = _make_ev(phone="14155551234", text="/register alice")

        await channel._handle_register("14155551234", "/register alice", ev)

        channel._client.reply_message.assert_awaited_once()
        reply = channel._client.reply_message.call_args[0][0]
        assert "alice" in reply

        # Verify persisted
        map_file = tmp_path / "workspaces" / "household" / "whatsapp_users.json"
        saved = json.loads(map_file.read_text())
        assert saved["14155551234"] == "alice"

    @pytest.mark.asyncio
    async def test_register_creates_workspace_dir(self, tmp_path: Path) -> None:
        channel = _make_channel(tmp_path)
        ev = _make_ev(phone="14155551234", text="/register bob")

        await channel._handle_register("14155551234", "/register bob", ev)

        member_dir = tmp_path / "workspaces" / "bob"
        assert member_dir.is_dir()

    @pytest.mark.asyncio
    async def test_register_usage_error_on_missing_name(self, tmp_path: Path) -> None:
        channel = _make_channel(tmp_path)
        ev = _make_ev(text="/register")

        await channel._handle_register("14155551234", "/register", ev)

        reply = channel._client.reply_message.call_args[0][0]
        assert "Usage" in reply


class TestMessageHandling:
    @pytest.mark.asyncio
    async def test_known_user_gets_response(self, tmp_path: Path) -> None:
        channel = _make_channel(tmp_path, user_map={"14155551234": "alice"})
        ev = _make_ev(phone="14155551234", text="what's for dinner?")

        await channel._handle_message(ev)

        channel._loop.run.assert_awaited_once_with(
            "what's for dinner?", "alice", channel=None,
        )
        channel._client.reply_message.assert_awaited_once_with(
            "I'm homeclaw.", ev,
        )

    @pytest.mark.asyncio
    async def test_unknown_user_gets_register_prompt(self, tmp_path: Path) -> None:
        channel = _make_channel(tmp_path)
        ev = _make_ev(phone="19995550000", text="hello")

        await channel._handle_message(ev)

        reply = channel._client.reply_message.call_args[0][0]
        assert "/register" in reply
        channel._loop.run.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_agent_error_sends_apology(self, tmp_path: Path) -> None:
        channel = _make_channel(tmp_path, user_map={"14155551234": "alice"})
        channel._loop.run.side_effect = RuntimeError("boom")
        ev = _make_ev(phone="14155551234", text="crash me")

        await channel._handle_message(ev)

        reply = channel._client.reply_message.call_args[0][0]
        assert "wrong" in reply.lower()

    @pytest.mark.asyncio
    async def test_group_message_prefixes_speaker(self, tmp_path: Path) -> None:
        channel = _make_channel(tmp_path, user_map={"14155551234": "alice"})
        ev = _make_ev(
            phone="14155551234",
            text="dinner at 7",
            is_group=True,
            chat_user="120363001234567890",
        )

        await channel._handle_message(ev)

        channel._loop.run.assert_awaited_once_with(
            "[alice] dinner at 7", "alice", channel="group-120363001234567890",
        )


class TestPhotoHandling:
    @pytest.mark.asyncio
    async def test_downloads_and_sends_multimodal(self, tmp_path: Path) -> None:
        channel = _make_channel(tmp_path, user_map={"14155551234": "alice"})
        ev = _make_ev(phone="14155551234", text="")
        ev.Message.conversation = ""
        ev.Message.imageMessage = MagicMock(
            url="https://example.com/img.jpg",
            mimetype="image/png",
            caption="look at this",
        )

        channel._client.download_any.return_value = b"\x89PNG fake image data"

        await channel._handle_message(ev)

        channel._client.download_any.assert_awaited_once_with(ev.Message)
        channel._loop.run.assert_awaited_once()
        content_arg = channel._loop.run.call_args[0][0]
        assert isinstance(content_arg, list)
        assert content_arg[0]["type"] == "image"
        assert content_arg[1]["type"] == "text"
        assert "look at this" in content_arg[1]["text"]

    @pytest.mark.asyncio
    async def test_download_failure_sends_apology(self, tmp_path: Path) -> None:
        channel = _make_channel(tmp_path, user_map={"14155551234": "alice"})
        ev = _make_ev(phone="14155551234", text="")
        ev.Message.conversation = ""
        ev.Message.imageMessage = MagicMock(
            url="https://example.com/img.jpg",
            mimetype="image/jpeg",
            caption="",
        )

        channel._client.download_any.side_effect = RuntimeError("network error")

        await channel._handle_message(ev)

        reply = channel._client.reply_message.call_args[0][0]
        assert "couldn't download" in reply.lower()
        channel._loop.run.assert_not_awaited()
