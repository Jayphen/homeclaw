"""Skill plugin loader — parses markdown skill files and wraps them as Plugins."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
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


@dataclass
class SkillLocation:
    """A discovered skill's name, scope, and directory path."""

    name: str
    scope: str  # "household" or person name
    skill_dir: Path


# ---------------------------------------------------------------------------
# Skill markdown renderer
# ---------------------------------------------------------------------------

_NAME_SLUG_RE = re.compile(r"[^a-z0-9_-]")


def slugify_skill_name(name: str) -> str:
    """Convert a skill name to a filesystem-safe slug."""
    return _NAME_SLUG_RE.sub("", name.lower().replace(" ", "_")).strip("_-")


def render_skill_markdown(
    name: str,
    description: str,
    allowed_domains: list[str],
    instructions: str,
    tools: list[dict[str, Any]],
) -> str:
    """Render a skill definition as a markdown file that ``parse_skill_markdown`` can read.

    Args:
        name: Skill slug name (used in the ``# Skill:`` header).
        description: Short description of what the skill does.
        allowed_domains: Domains the skill's http_call is allowed to reach.
        instructions: Free-text instructions injected into the agent's system prompt.
        tools: List of tool dicts, each with ``name``, ``description``, and an
            optional ``params`` list of dicts with ``name``, ``type``,
            ``required`` (bool), and ``description``.
    """
    lines: list[str] = [
        f"# Skill: {name}",
        "",
        f"Description: {description}",
        "",
        "## Allowed Domains",
    ]
    for domain in allowed_domains:
        lines.append(f"- {domain}")

    lines.extend(["", "## Tools", ""])
    for tool in tools:
        lines.append(f"### {tool['name']}")
        lines.append(f"Description: {tool.get('description', '')}")
        params = tool.get("params", [])
        if params:
            lines.append("Parameters:")
            for p in params:
                req = "required" if p.get("required", True) else "optional"
                lines.append(f"- {p['name']} ({p['type']}, {req}): {p['description']}")
        lines.append("")

    lines.extend(["## Instructions", instructions, ""])
    return "\n".join(lines)


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

    Every skill gets ``data_list``, ``data_read``, ``data_write``, and
    ``data_delete`` tools for managing files in its data directory.  Skills
    that declare ``allowed_domains`` also get an ``http_call`` tool scoped
    to those domains.

    Skill definition (``skill.md``) lives in ``skill_dir``.  Data files
    live in ``skill_dir/data/``, keeping instructions separate from data.

    Attributes:
        data_dir: The skill's data directory (``skill_dir/data/``).
        scope: ``"household"`` or a person name — where the skill lives.
    """

    def __init__(self, definition: SkillDefinition, skill_dir: Path, scope: str) -> None:
        self.name: str = definition.name
        self.description: str = definition.description
        self.scope: str = scope
        self.data_dir: Path = skill_dir / "data"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._skill_dir = skill_dir
        self._definition = definition
        self._config = HttpCallConfig(
            allowed_domains=definition.allowed_domains,
            log_dir=skill_dir / "logs",
        )

    @property
    def instructions(self) -> str:
        return self._definition.instructions

    @property
    def skill_tools(self) -> list[SkillToolDef]:
        return self._definition.tools

    def tools(self) -> list[ToolDefinition]:
        """Return tool definitions for this skill.

        Every skill gets ``data_list``, ``data_read``, ``data_write``, and
        ``data_delete`` for managing files in its directory.  If the skill
        declares ``allowed_domains``, it also gets ``http_call``.
        """
        defs: list[ToolDefinition] = [
            ToolDefinition(
                name="data_list",
                description=(
                    f"List data files in the '{self.name}' skill directory. "
                    f"Returns filenames of data files."
                ),
                parameters={
                    "type": "object",
                    "properties": {},
                },
            ),
            ToolDefinition(
                name="data_read",
                description=(
                    f"Read a data file from the '{self.name}' skill directory."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "filename": {
                            "type": "string",
                            "description": (
                                "Name of the file to read (e.g. 'spending.md')"
                            ),
                        },
                    },
                    "required": ["filename"],
                },
            ),
            ToolDefinition(
                name="data_write",
                description=(
                    f"Write or overwrite a data file in the '{self.name}' "
                    f"skill directory. IMPORTANT: Before creating a new file, "
                    f"call data_list first to check for existing files that "
                    f"cover the same topic — update the existing file instead "
                    f"of creating a duplicate."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "filename": {
                            "type": "string",
                            "description": (
                                "Name of the file to write (e.g. 'spending.md')"
                            ),
                        },
                        "content": {
                            "type": "string",
                            "description": "Full file content to write",
                        },
                    },
                    "required": ["filename", "content"],
                },
            ),
            ToolDefinition(
                name="data_delete",
                description=(
                    f"Delete a data file from the '{self.name}' skill "
                    f"directory. Use to remove redundant or obsolete files."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "filename": {
                            "type": "string",
                            "description": (
                                "Name of the file to delete"
                            ),
                        },
                    },
                    "required": ["filename"],
                },
            ),
        ]

        if self._definition.allowed_domains:
            defs.append(
                ToolDefinition(
                    name="http_call",
                    description=(
                        f"Make an HTTP request within the '{self.name}' "
                        f"skill. Allowed domains: "
                        f"{', '.join(self._definition.allowed_domains)}."
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
                                "enum": [
                                    "GET", "POST", "PUT", "DELETE", "PATCH",
                                ],
                                "description": "HTTP method (default GET)",
                            },
                            "headers": {
                                "type": "object",
                                "description": "Request headers",
                            },
                            "body": {
                                "type": "string",
                                "description": (
                                    "Request body (for POST/PUT/PATCH)"
                                ),
                            },
                        },
                        "required": ["url"],
                    },
                )
            )

        return defs

    def _safe_path(self, filename: str) -> Path | None:
        """Resolve *filename* inside the data directory, rejecting traversal."""
        resolved = (self.data_dir / filename).resolve()
        if not resolved.is_relative_to(self.data_dir.resolve()):
            return None
        return resolved

    async def handle_tool(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        """Dispatch tool calls to the appropriate handler."""
        if name == "data_list":
            return self._handle_data_list()
        if name == "data_read":
            return self._handle_data_read(args.get("filename", ""))
        if name == "data_write":
            return self._handle_data_write(
                args.get("filename", ""), args.get("content", ""),
            )
        if name == "data_delete":
            return self._handle_data_delete(args.get("filename", ""))
        if name == "http_call":
            return await http_call(
                url=args.get("url", ""),
                method=args.get("method", "GET"),
                headers=args.get("headers"),
                body=args.get("body"),
                config=self._config,
            )
        return {"error": f"Unknown tool: {name}"}

    def _handle_data_list(self) -> dict[str, Any]:
        files: list[str] = []
        if self.data_dir.is_dir():
            for child in sorted(self.data_dir.iterdir()):
                if child.is_dir():
                    continue
                files.append(child.name)
        return {"files": files}

    def _handle_data_read(self, filename: str) -> dict[str, Any]:
        if not filename:
            return {"error": "filename is required"}
        path = self._safe_path(filename)
        if path is None:
            return {"error": f"Invalid filename: {filename}"}
        if not path.is_file():
            return {"error": f"File not found: {filename}"}
        return {"filename": filename, "content": path.read_text()}

    def _handle_data_write(
        self, filename: str, content: str,
    ) -> dict[str, Any]:
        if not filename:
            return {"error": "filename is required"}
        path = self._safe_path(filename)
        if path is None:
            return {"error": f"Invalid filename: {filename}"}
        path.write_text(content)
        return {
            "filename": filename,
            "size": len(content),
            "status": "written",
        }

    def _handle_data_delete(self, filename: str) -> dict[str, Any]:
        if not filename:
            return {"error": "filename is required"}
        path = self._safe_path(filename)
        if path is None:
            return {"error": f"Invalid filename: {filename}"}
        if not path.is_file():
            return {"error": f"File not found: {filename}"}
        path.unlink()
        return {"filename": filename, "status": "deleted"}

    def routines(self) -> list[RoutineDefinition]:
        """Skills don't have routines."""
        return []


# ---------------------------------------------------------------------------
# Discovery and loading
# ---------------------------------------------------------------------------


def discover_skills(workspaces: Path, person: str) -> list[SkillLocation]:
    """Discover all skills visible to *person*.

    Scans both ``workspaces/household/skills/`` and
    ``workspaces/{person}/skills/`` for subdirectories that contain a
    ``skill.md`` file.  Hidden directories (starting with ``.``) are skipped
    so that ``.archive/`` is never treated as a skill.

    Returns a list of :class:`SkillLocation` objects sorted by scope then name
    (household first, then personal).
    """
    locations: list[SkillLocation] = []

    scopes: list[tuple[str, Path]] = [
        ("household", workspaces / "household" / "skills"),
    ]
    if person != "household":
        scopes.append((person, workspaces / person / "skills"))

    for scope, skills_dir in scopes:
        if not skills_dir.is_dir():
            continue
        for child in sorted(skills_dir.iterdir()):
            if (
                child.is_dir()
                and not child.name.startswith(".")
                and (child / "skill.md").is_file()
            ):
                locations.append(SkillLocation(name=child.name, scope=scope, skill_dir=child))

    return locations


def _migrate_skill_data(skill_dir: Path) -> None:
    """Migrate legacy skills that stored data alongside skill.md.

    Moves all non-directory files (except ``skill.md``) from the skill
    root into a ``data/`` subdirectory.  Idempotent — does nothing if
    ``data/`` already exists and contains files, or if there's nothing
    to migrate.
    """
    data_dir = skill_dir / "data"
    if data_dir.is_dir() and any(data_dir.iterdir()):
        return  # Already migrated

    files_to_move = [
        f for f in skill_dir.iterdir()
        if f.is_file() and f.name != "skill.md"
    ]
    if not files_to_move:
        return

    data_dir.mkdir(exist_ok=True)
    for f in files_to_move:
        dest = data_dir / f.name
        f.rename(dest)
    logger.info(
        "Migrated %d data files into %s",
        len(files_to_move), data_dir,
    )


def load_skill(skill_dir: Path, scope: str) -> SkillPlugin:
    """Parse ``skill.md`` inside *skill_dir* and return a ``SkillPlugin``."""
    _migrate_skill_data(skill_dir)
    path = skill_dir / "skill.md"
    content = path.read_text()
    definition = parse_skill_markdown(content)
    return SkillPlugin(definition, skill_dir, scope)


def load_all_skills(
    workspaces: Path,
    person: str,
    registry: PluginRegistry,
) -> list[PluginEntry]:
    """Discover, load, and register all skills visible to *person*.

    Loads household skills and the person's private skills.  Errors for
    individual skills are logged but do not prevent others from loading.
    Returns the list of ``PluginEntry`` objects that were registered.
    """
    entries: list[PluginEntry] = []
    locations = discover_skills(workspaces, person)

    for loc in locations:
        try:
            plugin = load_skill(loc.skill_dir, loc.scope)
            entry = registry.register(plugin, PluginType.SKILL)
            entries.append(entry)
            logger.info("Loaded skill plugin '%s' (scope: %s)", loc.name, loc.scope)
        except Exception:
            logger.exception("Failed to load skill '%s'", loc.name)

    return entries
