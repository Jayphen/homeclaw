"""Tests for the semantic memory startup wrapper."""

from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from homeclaw import SEMANTIC_INDEX_PATH
from homeclaw.memory.semantic import SemanticMemory


@pytest.mark.asyncio
async def test_quarantines_incompatible_milvus_lite_db_and_rebuilds(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    workspaces = tmp_path / "workspaces"
    (workspaces / "household" / "memory").mkdir(parents=True)
    (workspaces / "household" / "memory" / "general.md").write_text("# General\n")

    index_path = workspaces / SEMANTIC_INDEX_PATH
    index_path.parent.mkdir()
    index_path.write_bytes(b"old incompatible milvus lite db")

    calls = 0

    class FakeMemSearch:
        def __init__(self, **kwargs: Any) -> None:
            nonlocal calls
            calls += 1
            self.kwargs = kwargs
            if calls == 1:
                raise RuntimeError(
                    "Failed to open the local Milvus Lite database. "
                    "Move the existing .db file aside."
                )

        async def index(self) -> int:
            return 3

        def watch(self) -> object:
            return object()

    fake_memsearch = ModuleType("memsearch")
    fake_memsearch.MemSearch = FakeMemSearch  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "memsearch", fake_memsearch)

    semantic = SemanticMemory(str(workspaces))
    await semantic.initialize()

    assert semantic.enabled is True
    assert calls == 2
    assert not index_path.exists()
    quarantined = list(index_path.parent.glob("milvus.db.corrupt-*"))
    assert len(quarantined) == 1
    assert quarantined[0].read_bytes() == b"old incompatible milvus lite db"
