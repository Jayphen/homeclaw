"""Tests for deterministic tool policy classification."""

from __future__ import annotations

import pytest

from homeclaw.agent.runtime_state import InMemoryRuntimeObservability
from homeclaw.agent.tool_decorator import ToolPolicy
from homeclaw.agent.tool_policy import describe_tool_policies
from homeclaw.agent.tools import ToolRegistry


def _registry_with(*tool_names: str, **policies: ToolPolicy) -> ToolRegistry:
    """Build a minimal ToolRegistry with the given tool names and optional policies."""
    from homeclaw.agent.providers.base import ToolDefinition

    async def _noop(**_: object) -> dict[str, object]:
        return {}

    registry = ToolRegistry()
    for name in tool_names:
        defn = ToolDefinition(name=name, description="test", parameters={})
        registry.register(defn, _noop, policy=policies.get(name))
    return registry


def test_describe_tool_policies_classifies_enforced_tools() -> None:
    from homeclaw import HOUSEHOLD_WORKSPACE

    registry = _registry_with(
        "memory_save",
        "memory_read",
        "message_send",
        "weather__data_write",
        "weather__http_call",
        **{
            "memory_save": ToolPolicy(
                access="write",
                scope="personal",
                household_confirm=lambda args: args.get("person") == HOUSEHOLD_WORKSPACE,
            ),
            "memory_read": ToolPolicy(access="read", scope="personal"),
            "message_send": ToolPolicy(access="action", routine_blocked=True),
        },
    )
    policies = {p.tool_name: p for p in describe_tool_policies(registry)}

    assert policies["memory_save"].access == "write"
    assert policies["memory_save"].scope == "personal"
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

    registry = _registry_with(
        "memory_read",
        **{"memory_read": ToolPolicy(access="read", scope="personal")},
    )

    class FakeLoop:
        def tool_policy_snapshot(self) -> list[object]:
            return describe_tool_policies(registry)

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
