"""Semantic recall layer (Layer 2) — opt-in, uses memsearch for vector search."""

from __future__ import annotations

from typing import Any

from homeclaw import SEMANTIC_INDEX_PATH


class SemanticMemory:
    def __init__(self, workspaces_path: str) -> None:
        self._workspaces_path = workspaces_path
        self._mem: Any = None
        self._enabled = False

    @property
    def enabled(self) -> bool:
        return self._enabled

    async def initialize(self) -> None:
        try:
            from memsearch import MemSearch  # type: ignore[import-not-found]

            self._mem = MemSearch(
                paths=[
                    f"{self._workspaces_path}/household/notes",
                    f"{self._workspaces_path}/household/contacts",
                ],
                milvus_uri=f"{self._workspaces_path}/{SEMANTIC_INDEX_PATH}",
            )
            self._enabled = True
        except Exception:
            self._enabled = False

    async def recall(self, query: str, top_k: int = 3) -> list[str]:
        if not self._enabled or self._mem is None:
            return []
        results: list[dict[str, Any]] = await self._mem.search(query, top_k=top_k)
        return [r["content"] for r in results]
