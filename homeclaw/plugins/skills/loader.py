"""Skill plugin loader — parses markdown skill files and wraps them as Plugins."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from homeclaw.agent.providers.base import ToolDefinition
from homeclaw.plugins.interface import RoutineDefinition
from homeclaw.plugins.registry import PluginEntry, PluginRegistry, PluginType
from homeclaw.plugins.skills.http_call import HttpCallConfig, http_call

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class SkillParamDef(BaseModel):
    """A single parameter definition parsed from a skill markdown."""

    name: str
    type: str  # "string", "integer", etc.
    required: bool
    description: str


class SkillToolDef(BaseModel):
    """A tool definition parsed from a skill markdown."""

    name: str
    description: str
    parameters: list[SkillParamDef]


class SkillDefinition(BaseModel):
    """Parsed representation of a skill markdown file."""

    name: str
    description: str
    allowed_domains: list[str]
    tools: list[SkillToolDef]
    instructions: str


# ---------------------------------------------------------------------------
# Markdown parser
# ---------------------------------------------------------------------------

_PARAM_RE = re.compile(
    r"^-\s+(\w+)\s+\((\w+),\s*(required|optional)\):\s*(.+)$"
)


def parse_skill_markdown(content: str) -> SkillDefinition:
    """Parse a skill markdown file into a ``SkillDefinition``.

    Uses simple string parsing — no markdown library required.
    """
    lines = content.splitlines()

    name = ""
    description = ""
    allowed_domains: list[str] = []
    tools: list[SkillToolDef] = []
    instructions = ""

    # Parse header: ``# Skill: <name>``
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("# Skill:"):
            name = stripped.removeprefix("# Skill:").strip()
            break

    # Find ``Description:`` line directly after the title
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("Description:"):
            description = stripped.removeprefix("Description:").strip()
            break

    # --- Section splitter ---
    section_map: dict[str, list[str]] = {}
    current_section: str | None = None

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## "):
            current_section = stripped.removeprefix("## ").strip().lower()
            section_map[current_section] = []
        elif current_section is not None:
            section_map[current_section].append(line)

    # --- Allowed Domains ---
    for line in section_map.get("allowed domains", []):
        stripped = line.strip()
        if stripped.startswith("- "):
            domain = stripped.removeprefix("- ").strip()
            if domain:
                allowed_domains.append(domain)

    # --- Tools ---
    tool_lines = section_map.get("tools", [])
    tools = _parse_tools_section(tool_lines)

    # --- Instructions ---
    instr_lines = section_map.get("instructions", [])
    instructions = "\n".join(instr_lines).strip()

    if not name:
        raise ValueError("Skill markdown missing '# Skill: <name>' header")

    return SkillDefinition(
        name=name,
        description=description,
        allowed_domains=allowed_domains,
        tools=tools,
        instructions=instructions,
    )


def _parse_tools_section(lines: list[str]) -> list[SkillToolDef]:
    """Parse the ``## Tools`` section into a list of ``SkillToolDef``."""
    tools: list[SkillToolDef] = []
    current_tool_name: str | None = None
    current_tool_desc = ""
    current_params: list[SkillParamDef] = []

    for line in lines:
        stripped = line.strip()

        # New tool: ``### tool_name``
        if stripped.startswith("### "):
            # Flush previous tool
            if current_tool_name is not None:
                tools.append(
                    SkillToolDef(
                        name=current_tool_name,
                        description=current_tool_desc,
                        parameters=list(current_params),
                    )
                )
            current_tool_name = stripped.removeprefix("### ").strip()
            current_tool_desc = ""
            current_params = []
            continue

        if current_tool_name is None:
            continue

        if stripped.startswith("Description:"):
            current_tool_desc = stripped.removeprefix("Description:").strip()
            continue

        match = _PARAM_RE.match(stripped)
        if match:
            param_name, param_type, req_opt, param_desc = match.groups()
            current_params.append(
                SkillParamDef(
                    name=param_name,
                    type=param_type,
                    required=(req_opt == "required"),
                    description=param_desc,
                )
            )

    # Flush last tool
    if current_tool_name is not None:
        tools.append(
            SkillToolDef(
                name=current_tool_name,
                description=current_tool_desc,
                parameters=list(current_params),
            )
        )

    return tools


# ---------------------------------------------------------------------------
# SkillPlugin — wraps a SkillDefinition to satisfy the Plugin Protocol
# ---------------------------------------------------------------------------


class SkillPlugin:
    """Adapts a ``SkillDefinition`` into the Plugin Protocol.

    Each skill exposes a single ``http_call`` tool that is scoped to the
    skill's allowed domains.  The skill's instructions and tool specs are
    available as attributes so the agent context builder can inject them.
    """

    def __init__(self, definition: SkillDefinition, workspaces: Path) -> None:
        self.name: str = definition.name
        self.description: str = definition.description
        self._definition = definition
        self._config = HttpCallConfig(
            allowed_domains=definition.allowed_domains,
            log_dir=workspaces / "plugins" / definition.name / "logs",
        )

    @property
    def instructions(self) -> str:
        return self._definition.instructions

    @property
    def skill_tools(self) -> list[SkillToolDef]:
        return self._definition.tools

    def tools(self) -> list[ToolDefinition]:
        """Return a single ``http_call`` ToolDefinition scoped to this skill."""
        return [
            ToolDefinition(
                name="http_call",
                description=(
                    f"Make an HTTP request within the '{self.name}' skill. "
                    f"Allowed domains: {', '.join(self._definition.allowed_domains)}. "
                    f"Instructions: {self._definition.instructions}"
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "Full URL to call",
                        },
                        "method": {
                            "type": "string",
                            "enum": ["GET", "POST", "PUT", "DELETE", "PATCH"],
                            "description": "HTTP method (default GET)",
                        },
                        "headers": {
                            "type": "object",
                            "description": "Request headers",
                        },
                        "body": {
                            "type": "string",
                            "description": "Request body (for POST/PUT/PATCH)",
                        },
                    },
                    "required": ["url"],
                },
            )
        ]

    async def handle_tool(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        """Dispatch to ``http_call`` with this skill's config."""
        if name != "http_call":
            return {"error": f"Unknown tool: {name}"}

        return await http_call(
            url=args.get("url", ""),
            method=args.get("method", "GET"),
            headers=args.get("headers"),
            body=args.get("body"),
            config=self._config,
        )

    def routines(self) -> list[RoutineDefinition]:
        """Skills don't have routines."""
        return []


# ---------------------------------------------------------------------------
# Discovery and loading
# ---------------------------------------------------------------------------


def discover_skills(skills_dir: Path) -> list[str]:
    """Return skill names (stem of each .md file) found in *skills_dir*."""
    if not skills_dir.is_dir():
        return []
    return sorted(p.stem for p in skills_dir.glob("*.md"))


def load_skill(skills_dir: Path, name: str, workspaces: Path) -> SkillPlugin:
    """Parse a single skill markdown and return a ``SkillPlugin``."""
    path = skills_dir / f"{name}.md"
    content = path.read_text()
    definition = parse_skill_markdown(content)
    return SkillPlugin(definition, workspaces)


def load_all_skills(
    skills_dir: Path,
    workspaces: Path,
    registry: PluginRegistry,
) -> list[PluginEntry]:
    """Discover, load, and register all skills.

    Returns the list of ``PluginEntry`` objects that were registered.
    """
    entries: list[PluginEntry] = []
    names = discover_skills(skills_dir)
    for name in names:
        try:
            plugin = load_skill(skills_dir, name, workspaces)
            entry = registry.register(plugin, PluginType.SKILL)
            entries.append(entry)
            logger.info("Loaded skill plugin '%s'", name)
        except Exception:
            logger.exception("Failed to load skill '%s'", name)
    return entries
