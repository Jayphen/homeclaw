"""Deterministic skill verification checks."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel

if TYPE_CHECKING:
    from homeclaw.plugins.registry import PluginRegistry


class SkillVerificationCheck(BaseModel):
    """Outcome of a single verification step."""

    name: str
    status: Literal["passed", "warning", "failed"]
    detail: str


class SkillVerificationReport(BaseModel):
    """Structured report for a skill verification run."""

    skill_name: str
    owner: str
    scope: str
    source: str
    status: Literal["verified", "warning", "failed"]
    verified_at: datetime
    skill_dir: str
    expected_tools: list[str]
    available_tools: list[str]
    missing_tools: list[str]
    dependency_warnings: list[str]
    checks: list[SkillVerificationCheck]


def verify_skill(
    skill_dir: Path,
    *,
    owner: str,
    scope: str,
    source: str,
    allow_local_network: bool = False,
    plugin_registry: PluginRegistry | None = None,
    expect_registered: bool = False,
) -> SkillVerificationReport:
    """Verify a skill's parse/load/tool/data behavior without LLM involvement."""
    from homeclaw.plugins.skills.deps import check_skill_deps
    from homeclaw.plugins.skills.loader import _load_skill_env, load_skill, skill_md_to_definition

    checks: list[SkillVerificationCheck] = []
    expected_tools: list[str] = []
    available_tools: list[str] = []
    missing_tools: list[str] = []
    dependency_warnings: list[str] = []
    skill_name = skill_dir.name

    skill_md_path = skill_dir / "SKILL.md"
    if not skill_md_path.is_file():
        report = SkillVerificationReport(
            skill_name=skill_name,
            owner=owner,
            scope=scope,
            source=source,
            status="failed",
            verified_at=datetime.now(UTC),
            skill_dir=str(skill_dir),
            expected_tools=[],
            available_tools=[],
            missing_tools=[],
            dependency_warnings=[],
            checks=[
                SkillVerificationCheck(
                    name="skill_md_present",
                    status="failed",
                    detail="Missing SKILL.md",
                ),
            ],
        )
        return report

    try:
        definition = skill_md_to_definition(skill_md_path.read_text())
    except Exception as exc:
        return SkillVerificationReport(
            skill_name=skill_name,
            owner=owner,
            scope=scope,
            source=source,
            status="failed",
            verified_at=datetime.now(UTC),
            skill_dir=str(skill_dir),
            expected_tools=[],
            available_tools=[],
            missing_tools=[],
            dependency_warnings=[],
            checks=[
                SkillVerificationCheck(
                    name="parse_skill_md",
                    status="failed",
                    detail=f"SKILL.md parse failed: {exc}",
                ),
            ],
        )

    skill_name = definition.name
    expected_dir_name = skill_dir.name
    if skill_name == expected_dir_name:
        checks.append(
            SkillVerificationCheck(
                name="skill_name_matches_directory",
                status="passed",
                detail=f"Skill name '{skill_name}' matches directory",
            )
        )
    else:
        checks.append(
            SkillVerificationCheck(
                name="skill_name_matches_directory",
                status="failed",
                detail=(
                    f"Frontmatter name '{skill_name}' does not match directory "
                    f"'{expected_dir_name}'"
                ),
            )
        )

    try:
        plugin = load_skill(
            skill_dir,
            scope,
            allow_local_network=allow_local_network,
        )
        checks.append(
            SkillVerificationCheck(
                name="load_skill",
                status="passed",
                detail="Skill loaded successfully",
            )
        )
    except Exception as exc:
        return SkillVerificationReport(
            skill_name=skill_name,
            owner=owner,
            scope=scope,
            source=source,
            status="failed",
            verified_at=datetime.now(UTC),
            skill_dir=str(skill_dir),
            expected_tools=[],
            available_tools=[],
            missing_tools=[],
            dependency_warnings=[],
            checks=[
                *checks,
                SkillVerificationCheck(
                    name="load_skill",
                    status="failed",
                    detail=f"Skill load failed: {exc}",
                ),
            ],
        )

    expected_tools = [f"{plugin.name}__{tool.name}" for tool in plugin.tools()]
    checks.append(
        SkillVerificationCheck(
            name="expected_tool_set",
            status="passed",
            detail=f"Skill declares {len(expected_tools)} tool(s)",
        )
    )

    deps = check_skill_deps(definition.metadata, skill_env=_load_skill_env(skill_dir))
    dependency_warnings = _dependency_messages(deps)
    if dependency_warnings:
        checks.append(
            SkillVerificationCheck(
                name="dependencies",
                status="warning",
                detail="; ".join(dependency_warnings),
            )
        )
    else:
        checks.append(
            SkillVerificationCheck(
                name="dependencies",
                status="passed",
                detail="All declared dependencies are available",
            )
        )

    if expect_registered and plugin_registry is not None:
        entry = plugin_registry.get_entry(plugin.name)
        available_tools = list(entry.tool_names) if entry is not None else []
        missing_tools = [tool for tool in expected_tools if tool not in available_tools]
        if missing_tools:
            checks.append(
                SkillVerificationCheck(
                    name="registered_tool_set",
                    status="failed",
                    detail=f"Missing registered tools: {', '.join(missing_tools)}",
                )
            )
        else:
            checks.append(
                SkillVerificationCheck(
                    name="registered_tool_set",
                    status="passed",
                    detail=f"Registered {len(available_tools)} expected tool(s)",
                )
            )

    scenario_check = _run_storage_roundtrip(plugin)
    checks.append(scenario_check)

    unexpected_root_files = _unexpected_root_files(skill_dir)
    if unexpected_root_files:
        checks.append(
            SkillVerificationCheck(
                name="skill_root_layout",
                status="warning",
                detail=f"Unexpected root files: {', '.join(unexpected_root_files)}",
            )
        )
    else:
        checks.append(
            SkillVerificationCheck(
                name="skill_root_layout",
                status="passed",
                detail="Skill root layout matches expected conventions",
            )
        )

    status = _report_status(checks)
    return SkillVerificationReport(
        skill_name=skill_name,
        owner=owner,
        scope=scope,
        source=source,
        status=status,
        verified_at=datetime.now(UTC),
        skill_dir=str(skill_dir),
        expected_tools=expected_tools,
        available_tools=available_tools,
        missing_tools=missing_tools,
        dependency_warnings=dependency_warnings,
        checks=checks,
    )


def write_verification_report(skill_dir: Path, report: SkillVerificationReport) -> None:
    """Persist the latest verification report next to the skill."""
    (skill_dir / "verification.json").write_text(report.model_dump_json(indent=2))


def _dependency_messages(deps: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    for binary in deps.get("missing_bins", []):
        name = binary.get("name", "unknown")
        hint = binary.get("hint", "")
        warnings.append(f"Missing binary '{name}'{': ' + hint if hint else ''}")
    for env_var in deps.get("missing_env", []):
        warnings.append(f"Missing env var '{env_var}'")
    return warnings


def _unexpected_root_files(skill_dir: Path) -> list[str]:
    allowed_root_files = {"SKILL.md", ".env", "verification.json"}
    return sorted(
        child.name
        for child in skill_dir.iterdir()
        if child.is_file() and child.name not in allowed_root_files
    )


def _report_status(
    checks: list[SkillVerificationCheck],
) -> Literal["verified", "warning", "failed"]:
    if any(check.status == "failed" for check in checks):
        return "failed"
    if any(check.status == "warning" for check in checks):
        return "warning"
    return "verified"


def _run_storage_roundtrip(plugin: Any) -> SkillVerificationCheck:
    test_filename = "_homeclaw_verify.txt"
    expected = "verification"
    try:
        write_result = plugin._handle_data_write(test_filename, expected)
        if write_result.get("status") != "written":
            return SkillVerificationCheck(
                name="data_tool_roundtrip",
                status="failed",
                detail=f"data_write returned: {json.dumps(write_result, default=str)}",
            )

        list_result = plugin._handle_data_list()
        files = list_result.get("files", [])
        if test_filename not in files:
            return SkillVerificationCheck(
                name="data_tool_roundtrip",
                status="failed",
                detail="data_list did not include the verification file",
            )

        read_result = plugin._handle_data_read(test_filename)
        if read_result.get("content") != expected:
            return SkillVerificationCheck(
                name="data_tool_roundtrip",
                status="failed",
                detail="data_read returned unexpected content",
            )

        delete_result = plugin._handle_data_delete(test_filename)
        if delete_result.get("status") != "deleted":
            return SkillVerificationCheck(
                name="data_tool_roundtrip",
                status="failed",
                detail=f"data_delete returned: {json.dumps(delete_result, default=str)}",
            )
    except Exception as exc:
        return SkillVerificationCheck(
            name="data_tool_roundtrip",
            status="failed",
            detail=f"Data tool roundtrip failed: {exc}",
        )
    finally:
        cleanup = plugin.data_dir / test_filename
        if cleanup.exists():
            cleanup.unlink()

    return SkillVerificationCheck(
        name="data_tool_roundtrip",
        status="passed",
        detail="data_write/data_list/data_read/data_delete roundtrip succeeded",
    )
