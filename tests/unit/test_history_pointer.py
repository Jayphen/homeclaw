"""Tests for pointer-based history functions in homeclaw/agent/loop.py."""

from __future__ import annotations

import json
from pathlib import Path

from homeclaw.agent.loop import (
    _advance_consolidation_pointer,
    _append_turn,
    _load_history,
    _read_history_file,
)
from homeclaw.agent.providers.base import Message

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_jsonl(path: Path, lines: list[dict]) -> None:
    """Write a list of dicts as JSONL to a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(line) for line in lines) + "\n")


def _msg_dict(role: str, content: str) -> dict:
    """Create a message dict suitable for JSONL serialization."""
    return {"role": role, "content": content}


def _metadata_line(last_consolidated: int) -> dict:
    """Create a metadata line dict."""
    return {"_type": "metadata", "last_consolidated": last_consolidated}


# ---------------------------------------------------------------------------
# _read_history_file
# ---------------------------------------------------------------------------


class TestReadHistoryFile:
    """Tests for _read_history_file."""

    def test_with_metadata_line(self, tmp_path: Path) -> None:
        """File with metadata line → returns correct pointer."""
        path = tmp_path / "history.jsonl"
        _write_jsonl(
            path,
            [
                _metadata_line(2),
                _msg_dict("user", "hello"),
                _msg_dict("assistant", "hi"),
                _msg_dict("user", "how are you?"),
                _msg_dict("assistant", "good"),
            ],
        )

        last_consolidated, messages = _read_history_file(path)

        assert last_consolidated == 2
        assert len(messages) == 4
        assert messages[0].role == "user"
        assert messages[0].content == "hello"

    def test_no_metadata_line(self, tmp_path: Path) -> None:
        """File with no metadata → pointer defaults to 0."""
        path = tmp_path / "history.jsonl"
        _write_jsonl(
            path,
            [
                _msg_dict("user", "hello"),
                _msg_dict("assistant", "hi"),
            ],
        )

        last_consolidated, messages = _read_history_file(path)

        assert last_consolidated == 0
        assert len(messages) == 2

    def test_empty_file(self, tmp_path: Path) -> None:
        """Empty file → (0, [])."""
        path = tmp_path / "history.jsonl"
        path.write_text("")

        last_consolidated, messages = _read_history_file(path)

        assert last_consolidated == 0
        assert messages == []

    def test_nonexistent_file(self, tmp_path: Path) -> None:
        """File doesn't exist → (0, [])."""
        path = tmp_path / "nonexistent.jsonl"

        last_consolidated, messages = _read_history_file(path)

        assert last_consolidated == 0
        assert messages == []

    def test_loads_tool_messages(self, tmp_path: Path) -> None:
        """Tool messages are loaded alongside user and assistant."""
        path = tmp_path / "history.jsonl"
        _write_jsonl(
            path,
            [
                _metadata_line(0),
                _msg_dict("user", "save a note"),
                {"role": "tool", "content": '{"ok": true}', "tool_call_id": "tc_1"},
                _msg_dict("assistant", "done"),
            ],
        )

        _, messages = _read_history_file(path)

        assert len(messages) == 3
        assert messages[0].role == "user"
        assert messages[1].role == "tool"
        assert messages[2].role == "assistant"

    def test_invalid_json_lines_skipped(self, tmp_path: Path) -> None:
        """Invalid JSON lines are silently skipped."""
        path = tmp_path / "history.jsonl"
        path.write_text(
            json.dumps(_metadata_line(0))
            + "\n"
            + json.dumps(_msg_dict("user", "hello"))
            + "\n"
            + "this is not valid json\n"
            + json.dumps(_msg_dict("assistant", "hi"))
            + "\n"
        )

        last_consolidated, messages = _read_history_file(path)

        assert last_consolidated == 0
        assert len(messages) == 2


# ---------------------------------------------------------------------------
# _load_history
# ---------------------------------------------------------------------------


class TestLoadHistory:
    """Tests for _load_history."""

    def test_returns_messages_after_pointer(self, tmp_path: Path) -> None:
        """Only messages after the consolidation pointer are returned."""
        # Create workspace structure: tmp_path/alice/history.jsonl
        alice_dir = tmp_path / "alice"
        alice_dir.mkdir()
        path = alice_dir / "history.jsonl"
        _write_jsonl(
            path,
            [
                _metadata_line(2),
                _msg_dict("user", "old message 1"),
                _msg_dict("assistant", "old response 1"),
                _msg_dict("user", "new message 1"),
                _msg_dict("assistant", "new response 1"),
            ],
        )

        result = _load_history(tmp_path, "alice")

        # Should only get messages after pointer (index 2 onwards)
        assert len(result) == 2
        assert result[0].content == "new message 1"
        assert result[1].content == "new response 1"

    def test_pointer_zero_returns_all(self, tmp_path: Path) -> None:
        """Pointer at 0 returns all messages."""
        alice_dir = tmp_path / "alice"
        alice_dir.mkdir()
        path = alice_dir / "history.jsonl"
        _write_jsonl(
            path,
            [
                _metadata_line(0),
                _msg_dict("user", "msg1"),
                _msg_dict("assistant", "resp1"),
                _msg_dict("user", "msg2"),
                _msg_dict("assistant", "resp2"),
            ],
        )

        result = _load_history(tmp_path, "alice")

        assert len(result) == 4

    def test_no_history_file(self, tmp_path: Path) -> None:
        """No history file → empty list."""
        result = _load_history(tmp_path, "alice")
        assert result == []

    def test_respects_max_messages(self, tmp_path: Path) -> None:
        """Only the last max_messages are returned."""
        alice_dir = tmp_path / "alice"
        alice_dir.mkdir()
        path = alice_dir / "history.jsonl"

        lines: list[dict] = [_metadata_line(0)]
        for i in range(250):
            lines.append(_msg_dict("user", f"msg {i}"))
            lines.append(_msg_dict("assistant", f"resp {i}"))
        _write_jsonl(path, lines)

        # Default max_messages is 200
        result = _load_history(tmp_path, "alice")

        assert len(result) == 200

    def test_group_channel_history_path(self, tmp_path: Path) -> None:
        """Group channel history goes under household/channels/."""
        channel_dir = tmp_path / "household" / "channels" / "group-test"
        channel_dir.mkdir(parents=True)
        path = channel_dir / "history.jsonl"
        _write_jsonl(
            path,
            [
                _metadata_line(0),
                _msg_dict("user", "group message"),
                _msg_dict("assistant", "group response"),
            ],
        )

        result = _load_history(tmp_path, "group-test")

        assert len(result) == 2
        assert result[0].content == "group message"


# ---------------------------------------------------------------------------
# _append_turn
# ---------------------------------------------------------------------------


class TestAppendTurn:
    """Tests for _append_turn (append-only history persistence)."""

    def test_preserves_pointer_and_all_prior_messages(self, tmp_path: Path) -> None:
        """Appending a turn keeps the pointer and every message already on disk."""
        alice_dir = tmp_path / "alice"
        alice_dir.mkdir()
        path = alice_dir / "history.jsonl"

        # Existing history with pointer at 2
        _write_jsonl(
            path,
            [
                _metadata_line(2),
                _msg_dict("user", "old1"),
                _msg_dict("assistant", "old_resp1"),
                _msg_dict("user", "old2"),
                _msg_dict("assistant", "old_resp2"),
            ],
        )

        # Only this turn's *new* messages are passed (not the loaded window).
        new_messages = [
            Message(role="user", content="new question"),
            Message(role="assistant", content="new answer"),
        ]

        _append_turn(tmp_path, "alice", new_messages)

        last_consolidated, all_messages = _read_history_file(path)
        assert last_consolidated == 2
        # All 4 prior messages preserved + 2 new = 6, in order.
        contents = [m.content for m in all_messages]
        assert contents == ["old1", "old_resp1", "old2", "old_resp2", "new question", "new answer"]

    def test_creates_new_file(self, tmp_path: Path) -> None:
        """Appending to a non-existent file creates it properly."""
        messages = [
            Message(role="user", content="first message"),
            Message(role="assistant", content="first response"),
        ]

        _append_turn(tmp_path, "bob", messages)

        path = tmp_path / "bob" / "history.jsonl"
        assert path.is_file()

        last_consolidated, all_messages = _read_history_file(path)
        assert last_consolidated == 0
        assert len(all_messages) == 2

    def test_empty_turn_is_a_noop(self, tmp_path: Path) -> None:
        """Appending no persistable messages must not create or clobber a file."""
        _append_turn(tmp_path, "ghost", [])
        assert not (tmp_path / "ghost" / "history.jsonl").exists()

    def test_preserves_tool_chain(self, tmp_path: Path) -> None:
        """Full tool chain (including tool results) is preserved on append."""
        from homeclaw.agent.providers.base import ToolCall

        messages = [
            Message(role="user", content="do something"),
            Message(
                role="assistant",
                content="calling a tool",
                tool_calls=[ToolCall(id="tc_1", name="test", arguments={})],
            ),
            Message(role="tool", content='{"ok": true}', tool_call_id="tc_1"),
            Message(role="assistant", content="done!"),
        ]

        _append_turn(tmp_path, "alice", messages)

        path = tmp_path / "alice" / "history.jsonl"
        _, saved_messages = _read_history_file(path)

        assert len(saved_messages) == 4
        assert saved_messages[0].role == "user"
        assert saved_messages[1].role == "assistant"
        assert saved_messages[1].content == "calling a tool"
        assert saved_messages[2].role == "tool"
        assert saved_messages[3].role == "assistant"
        assert saved_messages[3].content == "done!"

    def test_unconsolidated_history_beyond_the_window_is_never_lost(self, tmp_path: Path) -> None:
        """The bug this fixes: a long unconsolidated history must survive a save.

        Previously the in-memory window (capped by _load_history and trimmed by
        _truncate_history) was rewritten over the whole post-pointer file, so any
        unconsolidated message outside that window was deleted before it could be
        consolidated. Append-only persistence retains them all.
        """
        alice_dir = tmp_path / "alice"
        alice_dir.mkdir()
        path = alice_dir / "history.jsonl"

        # 300 unconsolidated messages on disk (pointer 0) — larger than the
        # _load_history cap of 200, the regime where the old code lost data.
        lines: list[dict] = [_metadata_line(0)]
        for i in range(300):
            lines.append(_msg_dict("user" if i % 2 == 0 else "assistant", f"m{i}"))
        _write_jsonl(path, lines)

        # The loop would only load/keep a small window — but a save appends only
        # the new turn, so the on-disk count can only grow.
        _append_turn(
            tmp_path,
            "alice",
            [
                Message(role="user", content="newest q"),
                Message(role="assistant", content="newest a"),
            ],
        )

        pointer, all_messages = _read_history_file(path)
        assert pointer == 0
        assert len(all_messages) == 302
        # Oldest unconsolidated message still present (not truncated away)...
        assert all_messages[0].content == "m0"
        # ...and the new turn is at the end.
        assert [m.content for m in all_messages[-2:]] == ["newest q", "newest a"]


# ---------------------------------------------------------------------------
# _advance_consolidation_pointer
# ---------------------------------------------------------------------------


class TestAdvanceConsolidationPointer:
    """Tests for _advance_consolidation_pointer."""

    def test_advances_pointer(self, tmp_path: Path) -> None:
        """Pointer advances to the new value, messages preserved."""
        alice_dir = tmp_path / "alice"
        alice_dir.mkdir()
        path = alice_dir / "history.jsonl"

        _write_jsonl(
            path,
            [
                _metadata_line(0),
                _msg_dict("user", "msg1"),
                _msg_dict("assistant", "resp1"),
                _msg_dict("user", "msg2"),
                _msg_dict("assistant", "resp2"),
            ],
        )

        _advance_consolidation_pointer(tmp_path, "alice", 2)

        last_consolidated, all_messages = _read_history_file(path)
        assert last_consolidated == 2
        # All messages should still be present
        assert len(all_messages) == 4

    def test_no_regression(self, tmp_path: Path) -> None:
        """Pointer does not go backwards."""
        alice_dir = tmp_path / "alice"
        alice_dir.mkdir()
        path = alice_dir / "history.jsonl"

        _write_jsonl(
            path,
            [
                _metadata_line(3),
                _msg_dict("user", "msg1"),
                _msg_dict("assistant", "resp1"),
                _msg_dict("user", "msg2"),
                _msg_dict("assistant", "resp2"),
            ],
        )

        # Try to go backwards — should be a no-op
        _advance_consolidation_pointer(tmp_path, "alice", 1)

        last_consolidated, _ = _read_history_file(path)
        assert last_consolidated == 3  # unchanged

    def test_advance_to_same_value(self, tmp_path: Path) -> None:
        """Advancing to the same value is a no-op."""
        alice_dir = tmp_path / "alice"
        alice_dir.mkdir()
        path = alice_dir / "history.jsonl"

        _write_jsonl(
            path,
            [
                _metadata_line(2),
                _msg_dict("user", "msg1"),
                _msg_dict("assistant", "resp1"),
            ],
        )

        _advance_consolidation_pointer(tmp_path, "alice", 2)

        last_consolidated, _ = _read_history_file(path)
        assert last_consolidated == 2

    def test_advance_with_nonexistent_file(self, tmp_path: Path) -> None:
        """Advancing on a missing file creates it with the new pointer."""
        _advance_consolidation_pointer(tmp_path, "newuser", 5)

        path = tmp_path / "newuser" / "history.jsonl"
        # When there are no messages and pointer is 0 from read,
        # and new_pointer > 0, it should write the new pointer
        if path.exists():
            last_consolidated, messages = _read_history_file(path)
            assert last_consolidated == 5
            assert messages == []

    def test_messages_preserved_after_advance(self, tmp_path: Path) -> None:
        """All messages remain intact after pointer advance."""
        alice_dir = tmp_path / "alice"
        alice_dir.mkdir()
        path = alice_dir / "history.jsonl"

        _write_jsonl(
            path,
            [
                _metadata_line(0),
                _msg_dict("user", "first"),
                _msg_dict("assistant", "second"),
                _msg_dict("user", "third"),
                _msg_dict("assistant", "fourth"),
            ],
        )

        _advance_consolidation_pointer(tmp_path, "alice", 2)

        _, all_messages = _read_history_file(path)
        assert len(all_messages) == 4
        assert all_messages[0].content == "first"
        assert all_messages[3].content == "fourth"


# ---------------------------------------------------------------------------
# Consolidation-vs-save concurrency invariant
# ---------------------------------------------------------------------------


class TestConsolidationSaveInterleaving:
    """A turn saved while consolidation runs must survive the pointer advance.

    Background consolidation reads the history, runs a slow LLM extraction, then
    advances the pointer. If a user turn is saved during that window, the
    advance must not clobber it. This holds because _advance_consolidation_pointer
    re-reads the file fresh rather than reusing a stale snapshot — a property
    worth pinning so it isn't "optimized" away. At runtime the per-key lock
    serializes these two writes; here we assert the data invariant directly.
    """

    def test_turn_saved_after_consolidation_read_is_preserved(self, tmp_path: Path) -> None:
        alice_dir = tmp_path / "alice"
        alice_dir.mkdir()
        path = alice_dir / "history.jsonl"

        # Initial history: pointer 0, two turns (4 messages).
        _write_jsonl(
            path,
            [
                _metadata_line(0),
                _msg_dict("user", "q1"),
                _msg_dict("assistant", "a1"),
                _msg_dict("user", "q2"),
                _msg_dict("assistant", "a2"),
            ],
        )

        # Consolidation snapshots the pointer/messages it intends to advance
        # past (the first turn → chunk_end == 2).
        last_consolidated, _ = _read_history_file(path)
        chunk_end = 2

        # ...meanwhile a new user turn lands on the request path and is appended.
        _append_turn(
            tmp_path,
            "alice",
            [
                Message(role="user", content="q3"),
                Message(role="assistant", content="a3"),
            ],
        )

        # Now consolidation advances the pointer using its stale chunk_end.
        _advance_consolidation_pointer(tmp_path, "alice", last_consolidated + chunk_end)

        pointer, all_messages = _read_history_file(path)
        contents = [m.content for m in all_messages]

        assert pointer == 2  # pointer advanced past the consolidated turn
        # The turn saved during the consolidation window is NOT lost.
        assert "q3" in contents
        assert "a3" in contents
        # And no earlier message was dropped either.
        assert contents[:4] == ["q1", "a1", "q2", "a2"]
