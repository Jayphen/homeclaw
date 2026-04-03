"""Tests for deterministic tool policy classification."""

from __future__ import annotations

import pytest

from homeclaw.agent.loop import describe_tool_policies
from homeclaw.agent.runtime_state import InMemoryRuntimeObservability


def test_describe_tool_policies_classifies_enforced_tools() -> None:
    policies = {
        policy.tool_name: policy
        for policy in describe_tool_policies([
            "memory_save",
            "memory_read",
            "message_send",
            "weather__data_write",
            "weather__http_call",
        ])
    }

    assert policies["memory_save"].access == "write"
    assert policies["memory_save"].scope == "household"
    assert "personal_write" in policies["memory_save"].categories
    assert "household_write_confirmation" in policies["memory_save"].categories

    assert policies["memory_read"].access == "read"
    assert policies["memory_read"].scope == "personal"
    assert policies["memory_read"].dm_enforcement is not None

    assert policies["message_send"].routine_behavior == "blocked in routine execution"
    assert policies["weather__data_write"].scope == "skill"
    assert "skill_write" in policies["weather__data_write"].categories
    assert "allowed_domains_enforced" in policies["weather__http_call"].categories


@pytest.mark.asyncio
async def test_runtime_settings_include_tool_policies(monkeypatch: pytest.MonkeyPatch) -> None:
    from homeclaw.api.routes.settings import get_runtime_state

    class FakeLoop:
        def tool_policy_snapshot(self):
            return describe_tool_policies(["memory_read"])

    runtime_observability = InMemoryRuntimeObservability()

    monkeypatch.setattr(
        "homeclaw.api.routes.settings.get_runtime_observability",
        lambda: runtime_observability,
    )
    monkeypatch.setattr(
        "homeclaw.api.routes.settings.get_agent_loop",
        lambda: FakeLoop(),
    )

    result = await get_runtime_state()
    assert result["tool_policies"][0]["tool_name"] == "memory_read"
    assert result["tool_policies"][0]["access"] == "read"
