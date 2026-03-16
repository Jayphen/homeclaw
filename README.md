# homeclaw

An open source AI assistant for households. It knows your home, your family, and
the people in your lives. Not a personal assistant (one person) and not a home
automation tool (one building) — it understands the household as a coherent unit.

## Quick start (development)

```bash
# Install dependencies
uv sync --extra dev

# Start a REPL as Alice against dev fixtures
homeclaw chat --person alice --workspaces ./workspaces-dev

# Preview the context builder output without calling the LLM
homeclaw chat --person alice --workspaces ./workspaces-dev --dry-run

# LLM-only mode (no tool execution)
homeclaw chat --person alice --workspaces ./workspaces-dev --no-tools
```

You'll need an API key in your environment:

```bash
export ANTHROPIC_API_KEY=sk-...
# or
export OPENAI_API_KEY=sk-...
```

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
workspaces-dev/     # Dev fixture household (fake data for testing)
tests/              # pytest test suite
```

**Key design decisions:**

- **Pydantic v2** for all data models — validates at the JSON boundary
- **Protocol classes** for interfaces (LLMProvider, Plugin) — structural typing, no inheritance
- **Provider-agnostic agent loop** — never imports Anthropic/OpenAI SDK directly
- **Two-layer memory**: structured facts (always on) + semantic recall (opt-in)

## Running tests

```bash
# Unit tests (no LLM calls)
pytest tests/ -m "not integration"

# Type checking
pyright homeclaw/

# Lint
ruff check homeclaw/ tests/
```

## Status

Early development. The core agent loop, context builder, built-in tools, and CLI
REPL are working. See `bd list` for current issues and roadmap.

## License

MIT
