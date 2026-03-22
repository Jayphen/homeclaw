# homeclaw

An open source AI assistant for households. It knows your home, your family, and
the people in your lives. Not a personal assistant (one person) and not a home
automation tool (one building) — it understands the household as a coherent unit.

## homeclaw vs openclaw

[openclaw](https://github.com/openclaw/openclaw) is a mature, widely-adopted
personal AI assistant. homeclaw takes a different approach — it's built around
the **household** as a unit, not a single person. If openclaw is your personal
assistant, homeclaw is your family's.

| | homeclaw | openclaw |
|---|---|---|
| **Focus** | Household (multi-person, shared context) | Personal (single user) |
| **Data model** | Per-person workspaces + shared household knowledge | Per-session, single workspace |
| **Memory** | Markdown files + semantic recall, scoped per person | Session-based |
| **Contacts & relationships** | First-class — tracks people in your lives with interactions, reminders | Not built-in |
| **Channels** | Telegram, WhatsApp, Web UI, REPL | 20+ (WhatsApp, Telegram, Slack, Discord, Signal, iMessage, etc.) |
| **LLM providers** | Anthropic, OpenAI, OpenRouter, Ollama, any OpenAI-compatible | OpenAI (primary), multi-profile failover |
| **Language** | Python 3.12 | TypeScript / Node.js |
| **Plugin system** | Python plugins, Skill markdown, MCP sidecars | ClawHub skills platform |
| **Scheduler** | ROUTINES.md — natural language cron for household tasks | Cron jobs, webhooks, Gmail Pub/Sub |
| **Device nodes** | No | macOS, iOS, Android companion apps |
| **Browser automation** | No (planned as MCP sidecar) | Built-in Chrome control |
| **Voice** | No | Voice Wake, push-to-talk, ElevenLabs TTS |
| **Deployment** | Docker, Railway, Unraid, Raspberry Pi | npm, Docker, Nix, WSL2 |
| **Maturity** | Early development | Mature (329k+ stars, 22k+ commits) |
| **License** | MIT | MIT |

**Choose homeclaw if** you want an assistant that understands your household —
multiple people, shared contacts, per-person memory and privacy, and routines
that coordinate across the family.

**Choose openclaw if** you want a battle-tested personal assistant with broad
platform support, device companions, voice control, and a large ecosystem.

## Getting started

You need an LLM API key — one of:

- `ANTHROPIC_API_KEY` (direct Anthropic)
- `OPENAI_API_KEY` + optional `OPENAI_BASE_URL` (OpenAI or OpenRouter)

### Docker (recommended)

Images are published to GitHub Container Registry on every release
(linux/amd64 + linux/arm64).

```bash
docker run -d \
  --name homeclaw \
  -p 8080:8080 \
  -v ./workspaces:/data/workspaces \
  ghcr.io/jayphen/homeclaw:latest
```

Open `http://localhost:8080` — the web UI walks you through setup (API keys,
password, Telegram, etc.). A one-time setup token is printed to the container
logs: `docker logs homeclaw`.

**With docker-compose:**

```bash
docker compose up -d
```

This maps port 7399 → 8080 and bind-mounts `./workspaces` for persistent data.

**Volume:** Mount `/data/workspaces` to persist all household data (contacts,
notes, memory, bookmarks, config). Back this up regularly.

**Building locally:**

```bash
docker build -t homeclaw .
docker run -d -p 8080:8080 -v ./workspaces:/data/workspaces homeclaw
```

### From source

Requires **Python 3.12+** and **[uv](https://docs.astral.sh/uv/)** (or pip).

```bash
git clone https://github.com/Jayphen/homeclaw.git
cd homeclaw
uv sync
```

Start the web UI and configure everything there:

```bash
homeclaw serve
```

Open `http://localhost:8080` to complete setup.

You can also use the CLI directly:

```bash
homeclaw chat --person alice     # Interactive REPL
homeclaw telegram                # Start Telegram bot
```

## Configuration

All configuration is managed through the **web UI** at Settings. This includes
API keys, model selection, Telegram, WhatsApp, and Home Assistant setup.

Settings are persisted to `workspaces/household/config.json` and loaded via
pydantic-settings. Environment variables and `.env` files are supported as
overrides — useful for Docker deployments or CI:

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

### Telegram

Users register via `/register <name>` in Telegram to link their account to a
household member.

### WhatsApp

Connect as a linked device — scan the QR code at Settings > WhatsApp in the web
UI, or check the container logs. No Meta Business API required.

## Development

```bash
uv sync --extra dev               # Install dev dependencies
make dev-setup                    # Create dev fixtures (sample household data)
```

```bash
make dev          # Chat as alice with dev fixtures
make dev-bob      # Chat as bob with dev fixtures
make dev-context  # Dry-run: print system prompt and tools
make dev-serve    # Start API server against dev fixtures
make dev-costs    # Show cumulative LLM cost from cost log
```

### Running tests

```bash
make test         # Unit tests (no LLM calls)
make typecheck    # Pyright strict type checking
make lint         # Ruff linting + formatting check
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

## Status

v0.12 — usable for daily household use, actively developed. What's working:

- **Agent loop** with 40+ built-in tools, cost-aware model routing, prompt
  caching, interim responses during long tool chains, and reasoning round-trip
- **Memory** — per-person markdown topics with semantic recall (memsearch),
  context consolidation for long conversations
- **Contacts** — full CRM with interactions, reminders, per-person private notes
- **Bookmarks** — save, search, categorize, and annotate links
- **Notes** — daily markdown notes per person and shared household notes
- **Reminders** — one-shot and recurring, delivered via preferred channel
- **Channels** — Telegram (with typing indicators, photo handling, group chats),
  WhatsApp (linked device via neonize, QR/pair code auth, group chats), REPL
- **Channel dispatcher** — outbound messages routed to each person's preferred
  channel
- **Scheduler** — ROUTINES.md with natural language schedules, missed routine
  detection, manual trigger, per-routine cost tracking
- **Skills** — AgentSkills SKILL.md format, progressive disclosure, .env per
  skill, approval flow, install from GitHub/gist/URL, web UI with file
  browser/editor
- **Plugins** — Python plugins via importlib, marketplace index, install/uninstall
- **Web UI** — dashboard, contacts, memory, notes, bookmarks, calendar, routines,
  extensions, settings, setup wizard, log viewer, data export/import
- **Auth** — per-member JWT sessions, admin role, bcrypt passwords
- **Docker** — multi-arch images (amd64 + arm64), one-click setup via web UI

Not yet built: MCP sidecars, Home Assistant integration, voice, browser
automation, Railway/Pi deployment targets.

## License

MIT
