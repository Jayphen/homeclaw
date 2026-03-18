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
- Tool schemas in `homeclaw/agent/tools.py` must mirror the Pydantic models they wrap — when you add/change a Literal, enum, or field on a model, update the corresponding tool schema `enum`/`properties` to match
- **DM person enforcement**: Tools that write to a person's workspace (`_PERSONAL_WRITE_TOOLS` in `homeclaw/agent/loop.py`) have their `person` argument forced to the authenticated caller in DMs. If you add a new tool that writes to `workspaces/{person}/`, add it to `_PERSONAL_WRITE_TOOLS`. Read-only tools and cross-person tools like `message_send` are intentionally excluded.

## Memory — markdown + memsearch

Memory is stored as **markdown files** at `workspaces/{person}/memory/{topic}.md`, one file per
topic (e.g. `food.md`, `health.md`, `routines.md`). Entries are append-only with timestamps.
Household-wide knowledge goes under `workspaces/household/memory/`.

[memsearch](https://github.com/zilliztech/memsearch) (`homeclaw/memory/semantic.py`) indexes all
workspace content (notes, memory, contacts) into a Milvus Lite vector DB for semantic recall:

- **On startup**: `index()` builds the initial index, then `watch()` monitors for file changes
- **During conversation**: the context builder queries memsearch for top-k relevant chunks
- **Privacy**: recall is scoped per-person — a member only sees their own workspace + household
- **Source of truth**: markdown files on disk. The vector DB is a derived index that can be rebuilt

The agent writes memory via `memory_save` (append to topic file) and reads via `memory_read`
(list topics or read a specific one). No read-then-merge needed — writes are always appends.

Structured data (bookmarks, contacts) stays as JSON with its own search tools — memsearch only
indexes `.md` files.

## Plugin system — three tiers

1. **Python plugins**: `workspaces/plugins/{name}/plugin.py`, loaded via importlib
2. **Skill plugins**: Markdown files in `workspaces/skills/`, use `http_call` tool
3. **MCP sidecars**: Docker containers, communicate via HTTP/SSE

All conform to the Plugin Protocol in `homeclaw/plugins/interface.py`.

## Web UI — Svelte 5

The web UI lives in `ui/` and is built with **Svelte 5** (runes mode) + **Vite**. No heavy
component libraries — the design system uses CSS custom properties defined in `App.svelte`
(`--terracotta`, `--sage`, `--border`, `--surface`, etc.).

Reusable components go in `ui/src/lib/`:

- **`MarkdownEditor.svelte`** — markdown editor with formatting toolbar, keyboard shortcuts
  (`⌘B`, `⌘I`, `⌘K`, `⌘E`), and live preview toggle. Uses `marked` for rendering. Use this
  anywhere users need to edit markdown content.
- **`api.ts`** — fetch wrapper that injects the auth token.

Views live in `ui/src/views/` and are wired to routes in `App.svelte` via `svelte-spa-router`.

## Key directories

```
homeclaw/           # Main Python package
  agent/            # LLM loop, context builder, tools, providers
  channel/          # Telegram adapter
  memory/           # Markdown memory store + memsearch semantic recall
  contacts/         # Contact models and store
  scheduler/        # APScheduler + ROUTINES.md parser
  api/              # FastAPI app + routes
  plugins/          # Registry, loaders, MCP client, marketplace
ui/                 # Svelte web UI (built to ui/dist/)
workspaces/         # All user data (bind-mounted in Docker)
plugins/            # Built-in reference plugins (e.g., plants)
tests/              # pytest test suite
```

## Releasing

Releases are automated via [release-please](https://github.com/googleapis/release-please).

- Every push to `main` updates a release PR that tracks pending changes
- Merging the release PR creates a GitHub release and `v*` tag
- The `v*` tag triggers the Docker build workflow (`.github/workflows/docker.yml`)

**Commit messages matter.** release-please uses [Conventional Commits](https://www.conventionalcommits.org/) to determine the version bump:

```
feat: add data export API          → minor bump (0.1.0 → 0.2.0)
fix: handle empty contacts list    → patch bump (0.1.0 → 0.1.1)
feat!: redesign plugin protocol    → breaking (0.1.0 → 0.2.0, pre-1.0)
chore: update dev dependencies     → no release
```

Use `feat:` for new features, `fix:` for bug fixes, `chore:` / `docs:` / `refactor:` / `test:` for
non-release changes. Add `!` after the type for breaking changes.

The version in `pyproject.toml` is managed by release-please — do not bump it manually.

## Landing the plane

When ending a session:
1. File remaining work as beads issues
2. Run `make typecheck` and `make lint`
3. Close completed issues with `bd close`
4. Commit and push (use conventional commit prefixes)
