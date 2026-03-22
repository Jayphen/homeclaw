<svelte:head>
  <title>Configuration — homeclaw docs</title>
</svelte:head>

# Configuration

All configuration is managed through the **web UI** at Settings. This includes API keys, model selection, Telegram, WhatsApp, and Home Assistant setup.

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
| `HA_URL` | Home Assistant URL |
| `HA_TOKEN` | Home Assistant long-lived access token |
| `WEB_PASSWORD` | Web UI password |
| `HOMECLAW_CORS_ORIGINS` | Allowed origins for production |

## LLM providers

homeclaw supports multiple LLM providers through a provider-agnostic agent loop:

- **Anthropic** — set `ANTHROPIC_API_KEY`
- **OpenAI** — set `OPENAI_API_KEY`
- **OpenRouter** — set `OPENAI_API_KEY` and `OPENAI_BASE_URL=https://openrouter.ai/api/v1`
- **Ollama** — set `OPENAI_BASE_URL=http://localhost:11434/v1`
- **Any OpenAI-compatible API** — set `OPENAI_API_KEY` and `OPENAI_BASE_URL`

## Cost-aware routing

homeclaw uses two model tiers:

- **Primary model** — used for conversations (more capable)
- **Cheap model** — used for routines, tool-only calls, and background tasks

This is configured in the web UI under Settings. The default setup uses a capable model for conversations and a cheaper one for automated tasks to keep costs low.
