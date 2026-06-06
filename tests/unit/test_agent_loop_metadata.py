"""Tests for AgentLoop debug metadata."""

from __future__ import annotations

from typing import Any

import pytest

from homeclaw.agent.loop import AgentLoop
from homeclaw.agent.providers.base import LLMResponse, Message, ToolDefinition
from homeclaw.agent.tools import ToolRegistry


class _MetadataProvider:
    context_window = 128_000
    model = "test-debug-model"

    async def complete(
        self,
        messages: list[Message],
        tools: list[ToolDefinition],
        system: str,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        return LLMResponse(
            content="done",
            tool_calls=[],
            stop_reason="end_turn",
        )


@pytest.mark.asyncio
async def test_run_metadata_includes_prompt_diagnostics(tmp_path: Any) -> None:
    loop = AgentLoop(
        provider=_MetadataProvider(),
        registry=ToolRegistry(),
        workspaces=tmp_path,
    )
    metadata: dict[str, Any] = {}

    result = await loop.run("hello", person="alice", metadata=metadata)

    assert result == "done"
    assert metadata["model"] == "test-debug-model"
    assert metadata["stop_reason"] == "end_turn"
    assert metadata["call_type"] == "conversation"
    assert metadata["context_window"] == 128_000
    assert metadata["message_count"] >= 1
    assert metadata["history_budget"] > 0
    assert metadata["history_budget"] == 7680
    assert metadata["history_capacity"] > metadata["history_budget"]
    assert metadata["compaction_threshold"] == 8320
    assert metadata["prompt_sections"] == ["base_system_prompt", "context"]
    assert metadata["token_estimates"]["system"] > 0
    assert metadata["token_estimates"]["history"] > 0
    assert metadata["token_estimates"]["total"] >= metadata["token_estimates"]["system"]
