"""Tests for atomic, crash-safe file persistence helpers."""

from __future__ import annotations

import threading
from pathlib import Path

import pytest

from homeclaw.atomicio import atomic_write_json, atomic_write_text, read_json_safe


class TestAtomicWriteText:
    def test_creates_file_and_parent_dirs(self, tmp_path: Path) -> None:
        path = tmp_path / "nested" / "dir" / "out.txt"
        atomic_write_text(path, "hello")
        assert path.read_text() == "hello"

    def test_overwrites_existing(self, tmp_path: Path) -> None:
        path = tmp_path / "out.txt"
        path.write_text("old")
        atomic_write_text(path, "new")
        assert path.read_text() == "new"

    def test_leaves_no_temp_files(self, tmp_path: Path) -> None:
        path = tmp_path / "out.txt"
        atomic_write_text(path, "content")
        # Only the destination file should remain — no .tmp leftovers.
        assert [p.name for p in tmp_path.iterdir()] == ["out.txt"]

    def test_original_preserved_when_write_fails(self, tmp_path: Path) -> None:
        path = tmp_path / "out.txt"
        atomic_write_text(path, "original")

        # A non-str payload makes f.write() raise after the temp file is opened
        # but before os.replace — exercising the cleanup/abort path.
        with pytest.raises(TypeError):
            atomic_write_text(path, 123)  # type: ignore[arg-type]

        # The original file is untouched and no temp leftover remains.
        assert path.read_text() == "original"
        assert sorted(p.name for p in tmp_path.iterdir()) == ["out.txt"]


class TestAtomicWriteJson:
    def test_round_trips(self, tmp_path: Path) -> None:
        path = tmp_path / "data.json"
        atomic_write_json(path, {"a": 1, "b": [2, 3]})
        assert read_json_safe(path) == {"a": 1, "b": [2, 3]}

    def test_trailing_newline(self, tmp_path: Path) -> None:
        path = tmp_path / "data.json"
        atomic_write_json(path, {"x": 1})
        assert path.read_text().endswith("}\n")


class TestReadJsonSafe:
    def test_missing_returns_default(self, tmp_path: Path) -> None:
        assert read_json_safe(tmp_path / "nope.json", {}) == {}

    def test_corrupt_returns_default(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.json"
        path.write_text("{ not valid json")
        assert read_json_safe(path, {"fallback": True}) == {"fallback": True}

    def test_default_is_none_by_default(self, tmp_path: Path) -> None:
        assert read_json_safe(tmp_path / "nope.json") is None


class TestConcurrency:
    def test_readers_never_observe_a_torn_file(self, tmp_path: Path) -> None:
        """A reader running while writes happen must never see a partial file.

        With a bare write_text the destination is truncated mid-write, so a
        concurrent reader can observe corrupt JSON. atomic_write_json swaps the
        file in via os.replace, so every read returns a complete document.
        """
        path = tmp_path / "data.json"
        atomic_write_json(path, {"n": 0})

        stop = threading.Event()
        torn = []

        def reader() -> None:
            while not stop.is_set():
                # Sentinel default: if read_json_safe ever falls back, the
                # reader saw a corrupt/partial file.
                value = read_json_safe(path, default="__TORN__")
                if value == "__TORN__":
                    torn.append(value)

        t = threading.Thread(target=reader)
        t.start()
        try:
            for i in range(1, 400):
                # Payload large enough that a non-atomic write would span
                # multiple blocks and be observably partial.
                atomic_write_json(path, {"n": i, "pad": "x" * 5000})
        finally:
            stop.set()
            t.join()

        assert torn == []
