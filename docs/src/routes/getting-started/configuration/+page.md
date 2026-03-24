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
