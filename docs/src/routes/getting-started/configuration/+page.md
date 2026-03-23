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
