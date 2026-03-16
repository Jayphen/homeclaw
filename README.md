# homeclaw

An open source AI assistant for households. It knows your home, your family, and
the people in your lives. Not a personal assistant (one person) and not a home
automation tool (one building) — it understands the household as a coherent unit.

## Prerequisites

- **Python 3.12+**
- **[uv](https://docs.astral.sh/uv/)** (recommended) or pip
- An LLM API key — one of:
  - `ANTHROPIC_API_KEY` (direct Anthropic)
  - `OPENAI_API_KEY` + optional `OPENAI_BASE_URL` (OpenAI or OpenRouter)

## Installation

```bash
git clone https://github.com/yourorg/homeclaw.git
cd homeclaw
uv sync
```

For development (adds pyright, ruff, pytest):

```bash
uv sync --extra dev
```

## Configuration

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

Key settings:

```bash
# LLM provider — pick one:
ANTHROPIC_API_KEY=sk-ant-...
# or use OpenRouter:
OPENAI_API_KEY=sk-or-...
OPENAI_BASE_URL=https://openrouter.ai/api/v1
MODEL=anthropic/claude-sonnet-4-6

# Model routing (defaults shown):
CONVERSATION_MODEL=anthropic/claude-sonnet-4-6
ROUTINE_MODEL=anthropic/claude-haiku-4-5-20251001

# Optional — Telegram bot:
TELEGRAM_TOKEN=123456:ABC-...
# Optional — restrict bot to specific Telegram user IDs:
TELEGRAM_ALLOWED_USERS=123456789,987654321

# Optional — Home Assistant integration:
HA_URL=http://homeassistant.local:8123
HA_TOKEN=eyJ...

# Optional — web UI password:
WEB_PASSWORD=changeme
```

All config is loaded via pydantic-settings from environment variables or `.env`.

## Running

### Interactive chat (REPL)

```bash
# Chat as a household member
homeclaw chat --person alice

# Use a specific workspaces directory
homeclaw chat --person alice --workspaces ./workspaces

# Skip tool execution (LLM-only mode)
homeclaw chat --person alice --no-tools

# Preview the system prompt and tools without calling the LLM
homeclaw chat --person alice --dry-run
```

### Telegram bot

```bash
# Requires TELEGRAM_TOKEN in .env
homeclaw telegram
```

Users register via `/register <name>` in Telegram to link their account to a
household member.

### Development shortcuts

```bash
make dev          # Chat as alice with dev fixtures
make dev-bob      # Chat as bob with dev fixtures
make dev-context  # Dry-run: print system prompt and tools
make dev-setup    # Reset dev fixtures to a clean state
make dev-serve    # Start API server against dev fixtures
make dev-costs    # Show cumulative LLM cost from cost log
```

To set up the dev fixtures for the first time:

```bash
make dev-setup    # Creates workspaces-dev/ with sample household data
```

## Scheduler & routines

homeclaw runs recurring tasks defined in `workspaces/household/ROUTINES.md`:

```markdown
## Morning briefing
**Schedule:** Every weekday at 7:30am
**Action:** Summarize today's calendar, reminders, and weather for each person.
```

The scheduler starts automatically alongside any channel (REPL, Telegram, web).
Routines use the cheaper model by default to keep costs low.

## Architecture

```
homeclaw/           # Main Python package
  agent/            # LLM loop, context builder, tools, providers
  channel/          # Channel adapters (REPL, Telegram)
  memory/           # Structured facts + semantic recall
  contacts/         # Contact models and store
  scheduler/        # APScheduler + ROUTINES.md parser
  api/              # FastAPI app + routes
  plugins/          # Registry, loaders, MCP client
  cli.py            # CLI entry point
ui/                 # Svelte web UI (built to ui/dist/)
plugins/            # Built-in reference plugins (e.g., plants)
workspaces/         # All user data (bind-mounted in Docker)
workspaces-dev/     # Dev fixture household (fake data for testing)
tests/              # pytest test suite
```

**Key design decisions:**

- **Pydantic v2** for all data models — validates at the JSON boundary
- **Protocol classes** for interfaces (LLMProvider, Plugin) — structural typing, no inheritance
- **Provider-agnostic agent loop** — never imports Anthropic/OpenAI SDK directly
- **Two-layer memory**: structured facts (always on) + semantic recall (opt-in)
- **Cost-aware routing**: conversations use a capable model, routines and tool-only calls use a cheaper one
- **Prompt caching**: system prompts use Anthropic cache_control for 90% input token savings on cache hits

## Web UI

The web UI is built with Svelte 5 and served as static files by FastAPI — no
Node.js required at runtime.

```bash
cd ui && npm install && npm run build   # or: make ui-build
```

The build output lands in `ui/dist/` and is served automatically when running
`homeclaw serve`.

## Plugin system

Three tiers of plugins, all conforming to the same Protocol:

1. **Python plugins** — `plugins/{name}/plugin.py`, loaded via importlib
2. **Skill plugins** — Markdown files in `workspaces/skills/`, use sandboxed HTTP
3. **MCP sidecars** — Docker containers, communicate via HTTP/SSE

See `plugins/plants/` for a reference implementation covering tools, routines,
and persistent storage.

## Running tests

```bash
make test         # Unit tests (no LLM calls)
make typecheck    # Pyright strict type checking
make lint         # Ruff linting + formatting check
```

Or directly:

```bash
pytest tests/ -m "not integration"
pyright
ruff check homeclaw tests
ruff format --check homeclaw tests
```

## Status

Early development. Working: core agent loop, context builder, built-in tools,
scheduler, cost tracking, CLI REPL, Telegram bot, plugin system, web UI scaffold.

## License

MIT
