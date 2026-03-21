"""Unit tests for the channel dispatcher."""

import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from homeclaw.channel.dispatcher import ChannelDispatcher


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_dispatcher(tmp_path: Path) -> ChannelDispatcher:
    workspaces = tmp_path / "workspaces"
    (workspaces / "household").mkdir(parents=True)
    return ChannelDispatcher(workspaces)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestPreferences:
    def test_set_and_get_preference(self, tmp_path: Path) -> None:
        dispatcher = _make_dispatcher(tmp_path)
        dispatcher.set_preference("alice", "telegram")
        assert dispatcher.get_preference("alice") == "telegram"

    def test_set_preference_if_unset_does_not_overwrite(self, tmp_path: Path) -> None:
        dispatcher = _make_dispatcher(tmp_path)
        dispatcher.set_preference("alice", "telegram")
        dispatcher.set_preference_if_unset("alice", "whatsapp")
        assert dispatcher.get_preference("alice") == "telegram"

    def test_set_preference_if_unset_sets_when_missing(self, tmp_path: Path) -> None:
        dispatcher = _make_dispatcher(tmp_path)
        dispatcher.set_preference_if_unset("bob", "whatsapp")
        assert dispatcher.get_preference("bob") == "whatsapp"


class TestRegistration:
    def test_register_and_unregister(self, tmp_path: Path) -> None:
        dispatcher = _make_dispatcher(tmp_path)
        dispatcher.register("telegram", send=AsyncMock(), has_person=lambda p: True)
        assert "telegram" in dispatcher.available_channels()

        dispatcher.unregister("telegram")
        assert "telegram" not in dispatcher.available_channels()

    def test_available_channels(self, tmp_path: Path) -> None:
        dispatcher = _make_dispatcher(tmp_path)
        dispatcher.register("telegram", send=AsyncMock(), has_person=lambda p: True)
        dispatcher.register("whatsapp", send=AsyncMock(), has_person=lambda p: True)
        assert sorted(dispatcher.available_channels()) == ["telegram", "whatsapp"]


class TestSend:
    @pytest.mark.asyncio
    async def test_delivers_to_preferred_channel(self, tmp_path: Path) -> None:
        dispatcher = _make_dispatcher(tmp_path)
        tg_send = AsyncMock(return_value={"status": "sent", "channel": "telegram"})
        wa_send = AsyncMock(return_value={"status": "sent", "channel": "whatsapp"})
        dispatcher.register("telegram", send=tg_send, has_person=lambda p: True)
        dispatcher.register("whatsapp", send=wa_send, has_person=lambda p: True)
        dispatcher.set_preference("alice", "whatsapp")

        result = await dispatcher.send("alice", "dinner at 7")

        wa_send.assert_awaited_once_with("alice", "dinner at 7")
        tg_send.assert_not_awaited()
        assert result["status"] == "sent"

    @pytest.mark.asyncio
    async def test_falls_back_to_any_channel_with_person(self, tmp_path: Path) -> None:
        dispatcher = _make_dispatcher(tmp_path)
        tg_send = AsyncMock(return_value={"status": "sent", "channel": "telegram"})
        dispatcher.register(
            "telegram", send=tg_send, has_person=lambda p: p == "alice",
        )

        result = await dispatcher.send("alice", "hey")

        tg_send.assert_awaited_once_with("alice", "hey")
        assert result["status"] == "sent"

    @pytest.mark.asyncio
    async def test_returns_error_when_no_channel_registered(
        self, tmp_path: Path,
    ) -> None:
        dispatcher = _make_dispatcher(tmp_path)

        result = await dispatcher.send("alice", "hello")

        assert result["status"] == "error"
        assert "No channel" in result["detail"]

    @pytest.mark.asyncio
    async def test_returns_error_when_person_not_found(self, tmp_path: Path) -> None:
        dispatcher = _make_dispatcher(tmp_path)
        tg_send = AsyncMock()
        dispatcher.register(
            "telegram", send=tg_send, has_person=lambda p: False,
        )

        result = await dispatcher.send("unknown", "hello")

        assert result["status"] == "error"
        tg_send.assert_not_awaited()


class TestSendImage:
    @pytest.mark.asyncio
    async def test_delivers_image_to_preferred_channel(self, tmp_path: Path) -> None:
        dispatcher = _make_dispatcher(tmp_path)
        tg_img = AsyncMock(return_value={"status": "sent", "channel": "telegram"})
        wa_img = AsyncMock(return_value={"status": "sent", "channel": "whatsapp"})
        dispatcher.register(
            "telegram", send=AsyncMock(), has_person=lambda p: True,
            send_image=tg_img,
        )
        dispatcher.register(
            "whatsapp", send=AsyncMock(), has_person=lambda p: True,
            send_image=wa_img,
        )
        dispatcher.set_preference("alice", "whatsapp")

        result = await dispatcher.send_image("alice", "https://img.test/cat.jpg", "cute cat")

        wa_img.assert_awaited_once_with("alice", "https://img.test/cat.jpg", "cute cat", None)
        tg_img.assert_not_awaited()
        assert result["status"] == "sent"

    @pytest.mark.asyncio
    async def test_falls_back_to_any_channel_with_send_image(self, tmp_path: Path) -> None:
        dispatcher = _make_dispatcher(tmp_path)
        tg_img = AsyncMock(return_value={"status": "sent", "channel": "telegram"})
        dispatcher.register(
            "telegram", send=AsyncMock(), has_person=lambda p: p == "bob",
            send_image=tg_img,
        )

        result = await dispatcher.send_image("bob", "https://img.test/dog.jpg")

        tg_img.assert_awaited_once_with("bob", "https://img.test/dog.jpg", None, None)
        assert result["status"] == "sent"

    @pytest.mark.asyncio
    async def test_returns_error_when_no_channels(self, tmp_path: Path) -> None:
        dispatcher = _make_dispatcher(tmp_path)
        result = await dispatcher.send_image("alice", "https://img.test/x.jpg")
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_returns_error_when_no_image_support(self, tmp_path: Path) -> None:
        dispatcher = _make_dispatcher(tmp_path)
        # Register channel without send_image callback.
        dispatcher.register(
            "telegram", send=AsyncMock(), has_person=lambda p: True,
        )
        result = await dispatcher.send_image("alice", "https://img.test/x.jpg")
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_send_group_image(self, tmp_path: Path) -> None:
        dispatcher = _make_dispatcher(tmp_path)
        wa_group_img = AsyncMock(
            return_value={"status": "sent", "channel": "whatsapp"},
        )
        dispatcher.register(
            "whatsapp", send=AsyncMock(), has_person=lambda p: True,
            send_group=AsyncMock(), group_ids=lambda: ["grp1"],
            send_group_image=wa_group_img,
        )

        result = await dispatcher.send_group_image("grp1", "https://img.test/x.jpg", "hi")

        wa_group_img.assert_awaited_once_with("grp1", "https://img.test/x.jpg", "hi", None)
        assert result["status"] == "sent"

    @pytest.mark.asyncio
    async def test_send_group_image_falls_back(self, tmp_path: Path) -> None:
        dispatcher = _make_dispatcher(tmp_path)
        wa_group_img = AsyncMock(
            return_value={"status": "sent", "channel": "whatsapp"},
        )
        dispatcher.register(
            "whatsapp", send=AsyncMock(), has_person=lambda p: True,
            send_group=AsyncMock(), group_ids=lambda: ["grp1"],
            send_group_image=wa_group_img,
        )

        # Request with empty group_id — should fall back to first group.
        result = await dispatcher.send_group_image("", "https://img.test/x.jpg")

        wa_group_img.assert_awaited_once_with("grp1", "https://img.test/x.jpg", None, None)
        assert result["status"] == "sent"

    @pytest.mark.asyncio
    async def test_passes_image_data_through(self, tmp_path: Path) -> None:
        """Pre-fetched image bytes are forwarded to the channel adapter."""
        dispatcher = _make_dispatcher(tmp_path)
        tg_img = AsyncMock(return_value={"status": "sent", "channel": "telegram"})
        dispatcher.register(
            "telegram", send=AsyncMock(), has_person=lambda p: True,
            send_image=tg_img,
        )

        data = b"\x89PNG fake image bytes"
        result = await dispatcher.send_image(
            "alice", "https://immich.local/thumb.jpg", "photo",
            image_data=data,
        )

        tg_img.assert_awaited_once_with(
            "alice", "https://immich.local/thumb.jpg", "photo", data,
        )
        assert result["status"] == "sent"
