<svelte:head>
  <title>Plugins — homeclaw docs</title>
</svelte:head>

# Plugins

homeclaw has a three-tier plugin system. All tiers conform to the same `Plugin` Protocol defined in `homeclaw/plugins/interface.py`.

## Tier 1: Python plugins

Full Python plugins loaded via importlib at startup.

- Location: `workspaces/plugins/{name}/plugin.py`
- Can define tools, routines, web search/read providers, and persistent storage
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

## Custom web providers

Python plugins can register custom web search and read providers. Add a `web_providers()` method that returns a list of `WebProviderDefinition` objects:

```python
from homeclaw.plugins.interface import WebProviderDefinition

class SearxProvider:
    async def search(self, query: str) -> dict:
        # Must return {"query": ..., "results": [...], "provider": "searx"}
        ...

class Plugin:
    name = "searx"
    description = "SearXNG web search"

    def web_providers(self) -> list[WebProviderDefinition]:
        return [WebProviderDefinition(name="searx", instance=SearxProvider())]

    def tools(self): return []
    async def handle_tool(self, name, args): return {}
    def routines(self): return []
```

Provider instances must implement `WebSearchProvider` (with a `search()` method) and/or `WebReadProvider` (with a `read()` method) from `homeclaw.web.protocol`. Once registered, set `web_search_provider: "searx"` in config.

## Installing plugins

Plugins can be installed through:
- The web UI under Extensions
- The marketplace index
- Direct file placement in the appropriate directory
