<svelte:head>
  <title>Architecture — homeclaw docs</title>
</svelte:head>

# Architecture

## Directory structure

```
homeclaw/           # Main Python package
  agent/            # LLM loop, context builder, tools, providers
  channel/          # Channel adapters (REPL, Telegram, WhatsApp)
  memory/           # Markdown memory store + memsearch semantic recall
  contacts/         # Contact models and store
  scheduler/        # APScheduler + ROUTINES.md parser
  api/              # FastAPI app + routes
  plugins/          # Registry, loaders, MCP client, marketplace
  web/              # Pluggable web search & read providers
  cli.py            # CLI entry point
ui/                 # Svelte 5 web UI (built to ui/dist/)
docs/               # This docs site (SvelteKit)
plugins/            # Built-in reference plugins (e.g., plants)
workspaces/         # All user data (bind-mounted in Docker)
workspaces-dev/     # Dev fixture household (fake data for testing)
tests/              # pytest test suite
```

## Key design decisions

### Pydantic v2 for all data models

All persistent data models use `pydantic.BaseModel`. Validation happens at the JSON boundary — data flowing in from APIs, files, or LLM tool calls is validated by Pydantic before entering the system.

### Protocol classes for interfaces

All interfaces (`LLMProvider`, `Plugin`) use `typing.Protocol` with `@runtime_checkable`. This gives structural typing — no inheritance required. A class satisfies a Protocol if it has the right methods, regardless of its class hierarchy.

### Provider-agnostic agent loop

The agent loop never imports Anthropic or OpenAI SDKs directly. Instead, the provider factory (`homeclaw/agent/providers/factory.py`) returns the correct provider based on config. This means switching LLM providers is a config change, not a code change.

### Two-layer memory

1. **Markdown files** — always-on, human-readable memory stored as topic files
2. **Semantic recall** — memsearch indexes markdown files into a vector DB for similarity search

The markdown files are the source of truth. The vector DB is a derived index that can be rebuilt at any time.

### Pluggable web providers

Web search and page-fetch capabilities use a registry-based provider system (`homeclaw/web/`). Providers implement the `WebSearchProvider` or `WebReadProvider` protocol — structural typing, no inheritance required. Jina and Tavily ship as built-ins. The registry handles primary/fallback dispatch with automatic credit-exhaustion detection. Custom providers can register at startup or via Python plugins.

### Cost-aware routing

Conversations use a capable model. Routines, tool-only calls, and background tasks use a cheaper model. This is configured per-deployment and keeps costs manageable for always-on household use.

### Prompt caching

System prompts use Anthropic `cache_control` for up to 90% input token savings on cache hits.

## DM person enforcement

Tools that write to a person's workspace have their `person` argument forced to the authenticated caller in DMs. This prevents one person from writing to another's workspace through the agent. The list of enforced tools is maintained in `_PERSONAL_WRITE_TOOLS` in `homeclaw/agent/loop.py`.
