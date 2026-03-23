<svelte:head>
  <title>Plugins — homeclaw docs</title>
</svelte:head>

# Plugins

homeclaw has a three-tier plugin system. All tiers conform to the same `Plugin` Protocol defined in `homeclaw/plugins/interface.py`.

## Tier 1: Python plugins

Full Python plugins loaded via importlib at startup.

- Location: `workspaces/plugins/{name}/plugin.py`
- Can define tools, routines, and persistent storage
- See `plugins/plants/` for a reference implementation

## Tier 2: Skill plugins

Lightweight markdown-based skills using the [AgentSkills](https://agentskills.io/specification) `SKILL.md` format.

- Location: `workspaces/skills/`
- Use the `http_call` tool for external API access
- Support progressive disclosure, `.env` per skill, and approval flows
- Can be installed from GitHub, gist, or URL

## Tier 3: MCP sidecars

Docker containers that communicate via HTTP/SSE, following the Model Context Protocol.

- Run as separate containers alongside homeclaw
- Communicate over HTTP/SSE
- Useful for capabilities that need their own runtime (e.g., browser automation)

## Installing plugins

Plugins can be installed through:
- The web UI under Extensions
- The marketplace index
- Direct file placement in the appropriate directory
