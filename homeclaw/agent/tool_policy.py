"""Tool-policy classification for the observability API."""

from __future__ import annotations

from homeclaw.agent.runtime_state import ToolPolicyEntry
from homeclaw.agent.tool_decorator import ToolPolicy
from homeclaw.agent.tools import ToolManifest


def _policy_to_entry(tool_name: str, policy: ToolPolicy | None) -> ToolPolicyEntry:
    """Convert a ToolPolicy to a ToolPolicyEntry for the observability API."""
    skill_read_suffixes = {"data_list", "data_read", "get_env"}
    skill_write_suffixes = {"data_write", "data_delete"}

    categories: list[str] = []
    dm_enforcement: str | None = None
    routine_behavior: str | None = None

    # Skill namespaced tools: classify by naming convention.
    if "__" in tool_name:
        categories.append("skill_namespaced")
        suffix = tool_name.split("__", 1)[1]
        if suffix in skill_read_suffixes:
            categories.append("skill_read")
        elif suffix in skill_write_suffixes:
            categories.append("skill_write")
        elif suffix == "http_call":
            categories.extend(["skill_network", "allowed_domains_enforced"])
        else:
            categories.append("skill_action")
        # Skill tools have no explicit ToolPolicy — derive from convention
        if suffix in skill_read_suffixes:
            access = "read"
        elif suffix in skill_write_suffixes:
            access = "write"
        else:
            access = "action"
        return ToolPolicyEntry(
            tool_name=tool_name,
            access=access,  # type: ignore[arg-type]
            scope="skill",
            categories=categories,
            dm_enforcement=None,
            routine_behavior=None,
        )

    if policy is None:
        return ToolPolicyEntry(
            tool_name=tool_name,
            access="unknown",
            scope="general",
            categories=[],
            dm_enforcement=None,
            routine_behavior=None,
        )

    access = policy.access
    scope = policy.scope

    if policy.scope == "personal" and policy.access == "write":
        categories.append("personal_write")
        dm_enforcement = "forces person to authenticated caller in DMs"
    if policy.scope == "personal" and policy.access == "read":
        categories.append("personal_read")
        dm_enforcement = "forces person to authenticated caller in DMs"
    if policy.household_confirm is not None:
        categories.append("household_write_confirmation")
        dm_enforcement = "first DM attempt blocked until explicit confirmation"
    if policy.admin_only:
        categories.append("admin_only")
    if policy.routine_blocked:
        categories.append("routine_blocked")
        routine_behavior = "blocked in routine execution"

    return ToolPolicyEntry(
        tool_name=tool_name,
        access=access,  # type: ignore[arg-type]
        scope=scope,  # type: ignore[arg-type]
        categories=categories,
        dm_enforcement=dm_enforcement,
        routine_behavior=routine_behavior,
    )


def describe_tool_policies(manifest: ToolManifest) -> list[ToolPolicyEntry]:
    """Return deterministic policy classifications for all registered tools."""
    tool_names = sorted(defn.name for defn in manifest.get_definitions())
    return [_policy_to_entry(name, manifest.get_policy(name)) for name in tool_names]
