# CLAUDE.md — homeclaw

## What is this project?

homeclaw is an open source AI assistant for households. It knows your home, your
family, and the people in your lives. Not a personal assistant (one person) and
not a home automation tool (one building) — it understands the household as a
coherent unit.

Read `homeclaw-planning-prompt.md` for the full architecture and product spec.

## Task tracking

Use `bd` (beads) for ALL task tracking. Never create markdown TODO files or task
lists. Every piece of work goes into beads.

```bash
bd ready          # Find unblocked work
bd show <id>      # View issue details
bd update <id> --claim  # Claim work
bd close <id> --reason "..."  # Complete work
```

## Language and tooling

- **Python 3.12+** with strict type annotations throughout
- **Pydantic v2** for all data models — validates at the JSON boundary
- **Protocol** classes for plugin and tool interfaces — structural typing, no inheritance
- **Pyright** (standard mode) for static type checking: `make typecheck`
- **Ruff** for linting and formatting: `make lint`
- **pytest** for tests: `make test`

Run `make typecheck` before closing any issue. Zero errors required.

## Architecture rules

- All persistent data models use `pydantic.BaseModel`
- All interfaces (LLMProvider, Plugin) use `typing.Protocol` with `@runtime_checkable`
- Config uses `pydantic-settings` (`homeclaw/config.py`)
- The agent loop is provider-agnostic — never import Anthropic/OpenAI SDK directly in the loop
- Provider factory (`homeclaw/agent/providers/factory.py`) returns the correct provider from config

## Memory — two distinct layers

1. **Structured facts** (Layer 1, always on): `homeclaw/memory/facts.py`, stored as `workspaces/{person}/memory.json`
2. **Semantic recall** (Layer 2, opt-in): `homeclaw/memory/semantic.py`, uses memsearch with Milvus Lite

Do not conflate them. Layer 1 is injected in full into every context. Layer 2 returns top-k results only.

## Plugin system — three tiers

1. **Python plugins**: `workspaces/plugins/{name}/plugin.py`, loaded via importlib
2. **Skill plugins**: Markdown files in `workspaces/skills/`, use `http_call` tool
3. **MCP sidecars**: Docker containers, communicate via HTTP/SSE

All conform to the Plugin Protocol in `homeclaw/plugins/interface.py`.

## Key directories

```
homeclaw/           # Main Python package
  agent/            # LLM loop, context builder, tools, providers
  channel/          # Telegram adapter
  memory/           # Structured facts + semantic recall
  contacts/         # Contact models and store
  scheduler/        # APScheduler + ROUTINES.md parser
  api/              # FastAPI app + routes
  plugins/          # Registry, loaders, MCP client, marketplace
ui/                 # Svelte web UI (built to ui/dist/)
workspaces/         # All user data (bind-mounted in Docker)
plugins/            # Built-in reference plugins (e.g., plants)
tests/              # pytest test suite
```

## Landing the plane

When ending a session:
1. File remaining work as beads issues
2. Run `make typecheck` and `make lint`
3. Close completed issues with `bd close`
4. Commit and push
