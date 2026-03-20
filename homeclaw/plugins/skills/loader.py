"""Skill plugin loader — parses SKILL.md (YAML frontmatter) and legacy skill.md files."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel

from homeclaw.agent.providers.base import ToolDefinition
from homeclaw.plugins.interface import RoutineDefinition
from homeclaw.plugins.registry import PluginEntry, PluginRegistry, PluginType
from homeclaw.plugins.skills.http_call import HttpCallConfig, http_call

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class SkillFrontmatter(BaseModel):
    """YAML frontmatter parsed from a SKILL.md file (AgentSkills spec)."""

    name: str
    description: str = ""
    license: str | None = None
    compatibility: str | None = None
    metadata: dict[str, str] = {}
    allowed_tools: list[str] = []
    # homeclaw extensions (not in AgentSkills spec)
    allowed_domains: list[str] = []


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
    """Parsed representation of a skill file (new SKILL.md or legacy skill.md)."""

    name: str
    description: str
    allowed_domains: list[str] = []
    tools: list[SkillToolDef] = []
    instructions: str = ""
    # New AgentSkills fields
    license: str | None = None
    compatibility: str | None = None
    metadata: dict[str, str] = {}
    allowed_tools: list[str] = []


@dataclass
class SkillLocation:
    """A discovered skill's name, scope, and directory path."""

    name: str
    scope: str  # "household" or person name
    skill_dir: Path
    skill_file: str = "SKILL.md"  # which file was found


@dataclass
class SkillCatalogEntry:
    """Lightweight catalog entry — name + description for system prompt injection."""

    name: str
    description: str
    scope: str
    has_scripts: bool = False
    has_references: bool = False
    has_data: bool = False


# ---------------------------------------------------------------------------
# YAML frontmatter parser (new SKILL.md format)
# ---------------------------------------------------------------------------

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def parse_skill_md(content: str) -> tuple[SkillFrontmatter, str]:
    """Parse a SKILL.md file into frontmatter and markdown body.

    Returns (frontmatter, body) where body is the markdown after the ``---`` block.
    Raises ``ValueError`` if frontmatter is missing or invalid.
    """
    match = _FRONTMATTER_RE.match(content)
    if not match:
        raise ValueError("SKILL.md missing YAML frontmatter (--- delimiters)")

    raw_yaml = match.group(1)
    body = content[match.end():]

    try:
        data = yaml.safe_load(raw_yaml) or {}
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML frontmatter: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError("YAML frontmatter must be a mapping")

    if "name" not in data:
        raise ValueError("SKILL.md frontmatter missing required 'name' field")

    # Normalize allowed-tools from space-delimited string to list
    allowed_tools = data.pop("allowed-tools", None) or []
    if isinstance(allowed_tools, str):
        allowed_tools = allowed_tools.split()

    # Normalize allowed-domains from YAML (homeclaw extension)
    allowed_domains = data.pop("allowed-domains", None) or data.pop("allowed_domains", None) or []

    frontmatter = SkillFrontmatter(
        name=data.get("name", ""),
        description=data.get("description", ""),
        license=data.get("license"),
        compatibility=data.get("compatibility"),
        metadata=data.get("metadata") or {},
        allowed_tools=allowed_tools,
        allowed_domains=allowed_domains,
    )

    return frontmatter, body.strip()


def skill_md_to_definition(content: str) -> SkillDefinition:
    """Parse a SKILL.md file into a full ``SkillDefinition``."""
    fm, body = parse_skill_md(content)
    return SkillDefinition(
        name=fm.name,
        description=fm.description,
        allowed_domains=fm.allowed_domains,
        tools=[],  # new format doesn't embed tool defs in markdown
        instructions=body,
        license=fm.license,
        compatibility=fm.compatibility,
        metadata=fm.metadata,
        allowed_tools=fm.allowed_tools,
    )


# ---------------------------------------------------------------------------
# Skill SKILL.md renderer (new format)
# ---------------------------------------------------------------------------

_NAME_SLUG_RE = re.compile(r"[^a-z0-9_-]")


def slugify_skill_name(name: str) -> str:
    """Convert a skill name to a filesystem-safe slug."""
    return _NAME_SLUG_RE.sub("", name.lower().replace(" ", "_")).strip("_-")


def render_skill_md(
    name: str,
    description: str,
    allowed_domains: list[str] | None = None,
    instructions: str = "",
    metadata: dict[str, str] | None = None,
) -> str:
    """Render a SKILL.md file with YAML frontmatter + markdown body."""
    fm: dict[str, Any] = {"name": name, "description": description}
    if allowed_domains:
        fm["allowed-domains"] = allowed_domains
    if metadata:
        fm["metadata"] = metadata
    yaml_str = yaml.dump(fm, default_flow_style=False, sort_keys=False, allow_unicode=True)
    lines = ["---", yaml_str.rstrip(), "---", ""]
    if instructions:
        lines.append(instructions)
        lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Legacy skill.md parser (backward compatibility)
# ---------------------------------------------------------------------------

_PARAM_RE = re.compile(
    r"^-\s+(\w+)\s+\((\w+),\s*(required|optional)\):\s*(.+)$"
)


def render_skill_markdown(
    name: str,
    description: str,
    allowed_domains: list[str],
    instructions: str,
    tools: list[dict[str, Any]],
) -> str:
    """Render a legacy skill.md file.

    .. deprecated::
        Use ``render_skill_md`` for new skills. This is kept for backward
        compatibility with existing code that still creates legacy format.
    """
    return render_skill_md(
        name=name,
        description=description,
        allowed_domains=allowed_domains,
        instructions=instructions,
    )


def parse_skill_markdown(content: str) -> SkillDefinition:
    """Parse a legacy skill.md file into a ``SkillDefinition``.

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
# Format-agnostic parser — tries SKILL.md first, falls back to legacy
# ---------------------------------------------------------------------------


def parse_skill_file(content: str) -> SkillDefinition:
    """Parse a skill file in either SKILL.md (YAML frontmatter) or legacy skill.md format.

    Tries YAML frontmatter first, then falls back to the legacy section parser.
    """
    if content.startswith("---"):
        return skill_md_to_definition(content)
    return parse_skill_markdown(content)


# ---------------------------------------------------------------------------
# Migration — legacy skill.md → SKILL.md
# ---------------------------------------------------------------------------


def migrate_legacy_skill(skill_dir: Path) -> bool:
    """Convert legacy skill.md to SKILL.md in *skill_dir*.

    Uses directory listing to check exact filenames (handles case-insensitive
    filesystems like macOS/Windows). On case-insensitive FS, ``skill.md`` is
    renamed in place to ``SKILL.md``. On case-sensitive FS, ``SKILL.md`` is
    written alongside ``skill.md`` (kept as backup).

    Returns True if migration was performed, False otherwise.
    """
    actual_skill_file = _find_skill_file(skill_dir)
    if actual_skill_file is None or actual_skill_file == "SKILL.md":
        return False

    legacy_path = skill_dir / "skill.md"
    try:
        defn = parse_skill_markdown(legacy_path.read_text())
    except Exception:
        logger.warning("Cannot migrate '%s' — failed to parse legacy format", legacy_path)
        return False

    new_content = render_skill_md(
        name=defn.name,
        description=defn.description,
        allowed_domains=defn.allowed_domains if defn.allowed_domains else None,
        instructions=defn.instructions,
    )

    new_path = skill_dir / "SKILL.md"
    # On case-insensitive FS, writing to SKILL.md would overwrite skill.md.
    # Rename first to preserve the content, then write.
    if legacy_path.resolve() == new_path.resolve():
        # Case-insensitive FS — rename in place
        legacy_path.rename(new_path)
        new_path.write_text(new_content)
    else:
        # Case-sensitive FS — write alongside, keep legacy as backup
        new_path.write_text(new_content)

    logger.info("Migrated legacy skill.md → SKILL.md in %s", skill_dir)
    return True


# ---------------------------------------------------------------------------
# SkillPlugin — wraps a SkillDefinition to satisfy the Plugin Protocol
# ---------------------------------------------------------------------------


class SkillPlugin:
    """Adapts a ``SkillDefinition`` into the Plugin Protocol.

    Every skill gets ``data_list``, ``data_read``, ``data_write``, and
    ``data_delete`` tools for managing files in its data directory.  Skills
    that declare ``allowed_domains`` also get an ``http_call`` tool scoped
    to those domains.

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

    @property
    def skill_dir(self) -> Path:
        return self._skill_dir

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


def _find_skill_file(skill_dir: Path) -> str | None:
    """Find the skill definition file in *skill_dir*.

    Uses actual directory listing to distinguish ``SKILL.md`` from ``skill.md``
    on case-insensitive filesystems (macOS, Windows).
    Returns the exact filename or None if neither exists.
    """
    if not skill_dir.is_dir():
        return None
    filenames = {f.name for f in skill_dir.iterdir() if f.is_file()}
    if "SKILL.md" in filenames:
        return "SKILL.md"
    if "skill.md" in filenames:
        return "skill.md"
    return None


def _builtin_skills_dir() -> Path:
    """Return the path to built-in skills shipped with homeclaw."""
    return Path(__file__).resolve().parent.parent.parent / "skills"


def discover_skills(
    workspaces: Path,
    person: str,
    *,
    include_builtin: bool = True,
) -> list[SkillLocation]:
    """Discover all skills visible to *person*.

    Scans built-in skills (unless *include_builtin* is False),
    ``workspaces/household/skills/``, and ``workspaces/{person}/skills/``
    for subdirectories containing ``SKILL.md`` or ``skill.md``.
    Hidden directories (starting with ``.``) are skipped.

    User skills override built-in skills with the same name.

    Returns a list of :class:`SkillLocation` objects sorted by scope then name
    (builtin first, then household, then personal).
    """
    seen_names: set[str] = set()

    scopes: list[tuple[str, Path]] = []
    if include_builtin:
        scopes.append(("builtin", _builtin_skills_dir()))
    scopes.append(("household", workspaces / "household" / "skills"))
    if person != "household":
        scopes.append((person, workspaces / person / "skills"))

    # Scan in reverse order so user skills override builtins
    found: list[SkillLocation] = []
    for scope, skills_dir in reversed(scopes):
        if not skills_dir.is_dir():
            continue
        for child in sorted(skills_dir.iterdir()):
            if not child.is_dir() or child.name.startswith("."):
                continue
            skill_file = _find_skill_file(child)
            if skill_file and child.name not in seen_names:
                seen_names.add(child.name)
                found.append(SkillLocation(
                    name=child.name, scope=scope, skill_dir=child, skill_file=skill_file,
                ))

    # Sort: builtin first, then household, then personal
    scope_order = {"builtin": 0, "household": 1}
    found.sort(key=lambda loc: (scope_order.get(loc.scope, 2), loc.name))
    return found


def _migrate_skill_data(skill_dir: Path) -> None:
    """Migrate legacy skills that stored data alongside skill.md.

    Moves all non-directory files (except ``skill.md`` and ``SKILL.md``) from
    the skill root into a ``data/`` subdirectory.  Idempotent — does nothing if
    ``data/`` already exists and contains files, or if there's nothing to migrate.
    """
    data_dir = skill_dir / "data"
    if data_dir.is_dir() and any(data_dir.iterdir()):
        return  # Already migrated

    skip = {"skill.md", "SKILL.md"}
    files_to_move = [
        f for f in skill_dir.iterdir()
        if f.is_file() and f.name not in skip
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
    """Load a skill from *skill_dir*.

    Tries ``SKILL.md`` first (new YAML frontmatter format), falls back to
    ``skill.md`` (legacy). Auto-migrates legacy format to SKILL.md.
    """
    _migrate_skill_data(skill_dir)

    # Try SKILL.md first, then skill.md
    skill_file = _find_skill_file(skill_dir)
    if skill_file is None:
        raise FileNotFoundError(f"No SKILL.md or skill.md found in {skill_dir}")

    path = skill_dir / skill_file
    content = path.read_text()
    definition = parse_skill_file(content)

    # Auto-migrate legacy skill.md → SKILL.md
    if skill_file == "skill.md":
        migrate_legacy_skill(skill_dir)

    return SkillPlugin(definition, skill_dir, scope)


def load_all_skills(
    workspaces: Path,
    person: str,
    registry: PluginRegistry,
    *,
    include_builtin: bool = True,
) -> list[PluginEntry]:
    """Discover, load, and register all skills visible to *person*.

    Loads household skills and the person's private skills.  Errors for
    individual skills are logged but do not prevent others from loading.
    Returns the list of ``PluginEntry`` objects that were registered.
    """
    entries: list[PluginEntry] = []
    locations = discover_skills(workspaces, person, include_builtin=include_builtin)

    for loc in locations:
        try:
            plugin = load_skill(loc.skill_dir, loc.scope)
            entry = registry.register(plugin, PluginType.SKILL)
            entries.append(entry)
            logger.info("Loaded skill plugin '%s' (scope: %s)", loc.name, loc.scope)
        except Exception:
            logger.exception("Failed to load skill '%s'", loc.name)

    return entries


# ---------------------------------------------------------------------------
# Skill catalog — lightweight summaries for system prompt injection
# ---------------------------------------------------------------------------


def build_skill_catalog(
    workspaces: Path,
    person: str,
    *,
    include_builtin: bool = True,
) -> list[SkillCatalogEntry]:
    """Build a catalog of all skills visible to *person*.

    Returns lightweight entries (name + description) suitable for system prompt
    injection. Errors parsing individual skills are logged and skipped.
    """
    catalog: list[SkillCatalogEntry] = []

    for loc in discover_skills(workspaces, person, include_builtin=include_builtin):
        try:
            skill_file = _find_skill_file(loc.skill_dir)
            if not skill_file:
                continue
            content = (loc.skill_dir / skill_file).read_text()
            defn = parse_skill_file(content)
            catalog.append(SkillCatalogEntry(
                name=defn.name,
                description=defn.description,
                scope=loc.scope,
                has_scripts=(loc.skill_dir / "scripts").is_dir(),
                has_references=(loc.skill_dir / "references").is_dir(),
                has_data=(loc.skill_dir / "data").is_dir(),
            ))
        except Exception:
            logger.warning("Skipping skill '%s' in catalog — parse failed", loc.name)

    return catalog
