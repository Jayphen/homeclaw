<svelte:head>
  <title>Configuration — homeclaw docs</title>
</svelte:head>

# Configuration

All configuration is managed through the **web UI** at Settings. This includes API keys, model selection, Telegram, and WhatsApp setup.

Settings are persisted to `workspaces/household/config.json` and loaded via pydantic-settings.

## Environment variables

Environment variables and `.env` files are supported as overrides — useful for Docker deployments or CI:

| Variable | Description |
|----------|-------------|
| `ANTHROPIC_API_KEY` | Anthropic API key |
| `OPENAI_API_KEY` | OpenAI or OpenRouter API key |
| `OPENAI_BASE_URL` | Custom endpoint (OpenRouter, Ollama, etc.) |
| `MODEL` | Model name (e.g. `anthropic/claude-sonnet-4-6`) |
| `TELEGRAM_TOKEN` | Telegram bot token |
| `TELEGRAM_ALLOWED_USERS` | Comma-separated Telegram user IDs |
| `WEB_PASSWORD` | Web UI password |
| `HOMECLAW_CORS_ORIGINS` | Allowed origins for production |
| `JINA_API_KEY` | Jina AI API key (web search & read) |
| `TAVILY_API_KEY` | Tavily API key (web search & read) |

## LLM providers

homeclaw supports two provider types through a provider-agnostic agent loop:

- **Anthropic-compatible** — set `ANTHROPIC_API_KEY` (and optionally `ANTHROPIC_BASE_URL`). Works with Anthropic, MiniMax, and any Anthropic-compatible endpoint
- **OpenAI-compatible** — set `OPENAI_API_KEY` and optionally `OPENAI_BASE_URL`. Works with OpenAI, OpenRouter, Ollama, LiteLLM, and any OpenAI-compatible endpoint

## Model routing

homeclaw uses three model tiers:

- **Primary model** — used for conversations (more capable)
- **Fast model** — used for routines, tool-only calls, and background tasks (cheaper)
- **Vision model** — used for image inputs (photos sent via Telegram/WhatsApp). Can be a different provider than primary — e.g. use OpenAI for vision while using Anthropic for conversation

Each tier can use a different provider, API key, and base URL. This is configured in the web UI under Settings.

## Web providers

homeclaw uses pluggable providers for web search (`web_search` tool) and page fetching (`web_read` tool). Two providers are built-in (Jina and Tavily), and four more ship as plugins:

### Built-in providers

| Provider | Search | Read | Config key |
|----------|--------|------|-----------|
| **Jina** (`jina`) | `s.jina.ai` | `r.jina.ai` | `JINA_API_KEY` |
| **Tavily** (`tavily`) | `api.tavily.com/search` | `api.tavily.com/extract` | `TAVILY_API_KEY` |

### Plugin providers

These ship with homeclaw in `plugins/` and are enabled via the Plugins UI. Each reads its configuration from a `.env` file in the plugin directory or from system environment variables.

| Provider | Search | Read | Env var | Plugin |
|----------|--------|------|---------|--------|
| **Brave** (`brave`) | `api.search.brave.com` | — | `BRAVE_API_KEY` | `plugins/brave` |
| **Exa** (`exa`) | `api.exa.ai/search` | `api.exa.ai/contents` | `EXA_API_KEY` | `plugins/exa` |
| **SearXNG** (`searxng`) | Self-hosted instance | — | `SEARXNG_BASE_URL` | `plugins/searxng` |
| **Firecrawl** (`firecrawl`) | `api.firecrawl.dev/v2/search` | `api.firecrawl.dev/v2/scrape` | `FIRECRAWL_API_KEY` | `plugins/firecrawl` |

Brave and SearXNG are **search-only** — pair them with a read provider like Jina or Firecrawl.

SearXNG is free and self-hosted — run it alongside homeclaw on Unraid (Docker: `searxng/searxng`). Set `SEARXNG_BASE_URL` to its address (e.g. `http://searxng:8080`). Ensure JSON format is enabled in the SearXNG `settings.yml`.

Each capability (search, read) has a **primary** and optional **fallback** provider. If the primary fails or runs out of credits (HTTP 402/429), the fallback is tried automatically.

| Setting | Default | Description |
|---------|---------|-------------|
| `web_search_provider` | `jina` | Primary search provider |
| `web_search_fallback` | — | Fallback search provider |
| `web_read_provider` | `jina` | Primary page-fetch provider |
| `web_read_fallback` | — | Fallback page-fetch provider |

### Custom providers

Custom web providers are added via [Python plugins](/guides/plugins#custom-web-providers). A plugin implements the `WebSearchProvider` or `WebReadProvider` protocol and declares providers via `web_providers()`. See the [Plugins guide](/guides/plugins#custom-web-providers) for a full example.

Then set `web_search_provider: "your-provider"` in config. The Settings UI dynamically lists all registered providers.

## Browser automation

homeclaw can browse JavaScript-rendered pages and verify skill UIs using the [agent-browser](https://github.com/vercel-labs/agent-browser) CLI.

### Setup

1. Install agent-browser and Chrome:
   - macOS: `brew install agent-browser` (Chrome is detected automatically)
   - npm: `npm i -g agent-browser`
   - Docker: add `chromium` and `npm` to `workspaces/household/packages.txt`, and add `agent-browser` to `workspaces/household/npm-packages.txt`

2. Enable browser automation in Settings or `config.json`:

```json
{ "browser_enabled": true }
```

### `web_browse` tool

When enabled, the agent gains a `web_browse` tool:

| Parameter | Type | Description |
|-----------|------|-------------|
| `url` | string | URL to open |
| `action` | `snapshot` \| `screenshot` \| `click` \| `fill` | Action to perform (default: `snapshot`) |
| `selector` | string | CSS selector (required for `click`/`fill`) |
| `value` | string | Text to type (required for `fill`) |

`snapshot` returns the page's accessibility tree — a structured text representation ideal for LLM reasoning. `screenshot` returns base64-encoded image data.

### Skill mini-apps

Skills can ship an embedded mini-app that renders inline in the web UI's **Apps**
section. Mini-apps run in a sandboxed WASM VM (`@arrow-js/sandbox`): the app is
Arrow source (`app/main.ts` + optional `app/main.css`), declared via `ui-app:` in
the skill frontmatter. The sandboxed code is isolated — it cannot read the session
token, cannot make network requests, and cannot touch the host page. It reads
skill data only through a host bridge (`import { query, schema } from 'homeclaw'`),
which runs read-only SELECTs server-side on the app's behalf.

The agent authors these with the `skill_enable_ui_app` tool (writes the source and
the `ui-app:` block). A compile, mount, or runtime error surfaces as a banner in
the panel and via the `skill_render_status` tool. The agent can discover a skill
database's tables and columns with `skill_db_schema` (or
`GET /api/skills/{owner}/{name}/db/schema`) before writing a query.
