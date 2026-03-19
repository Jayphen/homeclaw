"""Semantic recall layer — uses memsearch to index and search workspace content.

Indexes all markdown and JSON files under the workspaces directory so that
notes, memory, contacts, and bookmarks are all searchable. Replaces the
old always-on Layer 1 injection with on-demand semantic recall.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from homeclaw import SEMANTIC_INDEX_PATH

logger = logging.getLogger(__name__)


class SemanticMemory:
    def __init__(
        self,
        workspaces_path: str,
        embedding_provider: str = "local",
        embedding_api_key: str | None = None,
    ) -> None:
        self._workspaces_path = workspaces_path
        self._embedding_provider = embedding_provider
        self._embedding_api_key = embedding_api_key
        self._mem: Any = None
        self._watcher: Any = None
        self._enabled = False

    @property
    def enabled(self) -> bool:
        return self._enabled

    def _collect_paths(self) -> list[str]:
        """Collect all workspace subdirectories that contain indexable content."""
        ws = Path(self._workspaces_path)
        paths: list[str] = []
        if not ws.is_dir():
            return paths
        for child in ws.iterdir():
            if not child.is_dir() or child.name.startswith("."):
                continue
            paths.append(str(child))
        return paths

    async def initialize(self) -> None:
        try:
            from memsearch import MemSearch  # type: ignore[import-not-found]

            paths = self._collect_paths()
            if not paths:
                logger.warning("No workspace directories found to index")
                return

            provider = self._embedding_provider
            if provider == "local":
                logger.info(
                    "Loading local embedding model (first run downloads ~80 MB)…"
                )
            else:
                logger.info("Initializing %s embedding provider…", provider)

            kwargs: dict[str, Any] = {
                "paths": paths,
                "milvus_uri": f"{self._workspaces_path}/{SEMANTIC_INDEX_PATH}",
                "embedding_provider": self._embedding_provider,
            }
            if self._embedding_api_key:
                kwargs["embedding_api_key"] = self._embedding_api_key
            try:
                self._mem = MemSearch(**kwargs)
            except ValueError as ve:
                if "dimension mismatch" in str(ve).lower():
                    logger.warning(
                        "Embedding dimension changed — dropping old index and re-indexing"
                    )
                    from pymilvus import MilvusClient  # type: ignore[import-not-found]

                    milvus_uri = kwargs["milvus_uri"]
                    client = MilvusClient(uri=milvus_uri)
                    client.drop_collection("memsearch_chunks")
                    client.close()
                    self._mem = MemSearch(**kwargs)
                else:
                    raise

            logger.info("Indexing %d workspace paths…", len(paths))
            n = await self._mem.index()
            self._watcher = self._mem.watch()
            self._enabled = True
            logger.info(
                "Semantic memory ready — %d chunks indexed, watching %d paths",
                n, len(paths),
            )
        except ImportError as exc:
            if "memsearch" in str(exc):
                logger.debug("memsearch not installed — semantic memory disabled")
            else:
                logger.warning(
                    "Semantic memory disabled — missing dependency: %s", exc,
                )
            self._enabled = False
        except Exception:
            logger.exception("Failed to initialize semantic memory")
            self._enabled = False

    def stop(self) -> None:
        """Stop the file watcher."""
        if self._watcher is not None:
            self._watcher.stop()
            self._watcher = None

    async def recall(
        self,
        query: str,
        top_k: int = 3,
        person: str | None = None,
        shared_only: bool = False,
    ) -> list[dict[str, Any]]:
        """Return recall results as {text, score} dicts.

        Args:
            query: The search query.
            top_k: Max results to return.
            person: If set, include results from this person's workspace
                and the household workspace. Other members' data is excluded.
            shared_only: If True, only return household-level results.
        """
        if not self._enabled or self._mem is None:
            return []
        # Fetch extra results so we have enough after filtering
        results: list[dict[str, Any]] = await self._mem.search(query, top_k=top_k * 3)

        household_prefix = f"{self._workspaces_path}/household"
        person_prefix = f"{self._workspaces_path}/{person}" if person else None

        filtered: list[dict[str, Any]] = []
        for r in results:
            source = r.get("source", "")
            if source.startswith(household_prefix):
                filtered.append(r)
            elif not shared_only and person_prefix and source.startswith(person_prefix):
                filtered.append(r)
            # Other members' data is silently excluded

        return [
            {"text": r["content"], "score": r.get("score", 0.0)}
            for r in filtered[:top_k]
        ]
