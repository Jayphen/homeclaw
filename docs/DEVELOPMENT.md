# Development Guide

This is the dogfooding workflow for homeclaw. It covers setup, testing, and the
progression from dev fixtures to real household use.

## Getting started

```bash
git clone <repo-url> && cd homeclaw
uv sync --extra dev
```

Set at least one LLM provider key:

```bash
export ANTHROPIC_API_KEY=sk-...
# or
export OPENAI_API_KEY=sk-...
```

Then bootstrap the dev fixtures and launch the REPL:

```bash
make dev-setup   # creates workspaces-dev/ with deterministic fake data
make dev         # REPL as alice
```

No API key is needed for `make dev-setup` — it only writes local files.

## The three dogfooding stages

### Stage 1: REPL with dev fixtures

Available from day one. No Telegram bot, no server — just a terminal REPL
talking to the LLM with fake household data.

```bash
make dev          # REPL as alice
make dev-bob      # REPL as bob
make dev-context  # dry-run: prints the assembled context, no LLM call
```

Use this stage to iterate on the agent loop, tools, context builder, and memory
layers without any external dependencies.

### Stage 2: Telegram with dev fixtures

Once the Telegram channel adapter works, point it at the same dev fixtures with
a test bot token:

```bash
export TELEGRAM_BOT_TOKEN=<test-bot-token>
make dev-serve    # full server (API + Telegram) against workspaces-dev/
```

This lets you test the real messaging flow while keeping data deterministic.

### Stage 3: Real household

Genuine dogfooding. Point at a real `workspaces/` directory with your own
household data and use homeclaw day-to-day through Telegram or the web UI.

## Running tests

```bash
make test              # unit tests only — zero LLM API calls
make test-integration  # integration tests (requires API key)
make typecheck         # pyright in standard mode
make lint              # ruff check + format
```

All unit tests mock the LLM. They replay recorded fixture responses from disk,
so they are fast and free.

## Recording new LLM fixtures

When you add a test that needs a new LLM interaction:

```bash
make test-record
```

This runs the test suite with a live API key and captures real responses into
`tests/fixtures/llm_responses/` as JSON files. In normal replay mode (the
default), tests load these files from disk instead of calling the API.

Commit the new fixture files alongside your test.

## Adding a new tool

1. Define a handler function in `homeclaw/agent/tools/`.
2. Create a `ToolDefinition` with name, description, parameters schema, and
   handler reference.
3. Register it in the tool registry.
4. Write a test in `tests/unit/test_tools/`.

Run `make typecheck` to confirm the handler signature satisfies the expected
protocol.

## Adding a new plugin

1. Implement the `Plugin` protocol defined in `homeclaw/plugins/interface.py`.
2. Place your module at `workspaces/plugins/{name}/plugin.py`.
3. The plugin registry discovers it via importlib at startup.
4. Write a test — plugins are loaded in isolation so unit testing is
   straightforward.

See the plants plugin in `plugins/plants/` for a reference implementation.

## Debugging context builder output

```bash
make dev-context
```

This performs a dry-run of the context builder and prints exactly what the LLM
would see: system prompt, injected facts, active reminders, person preferences,
loaded plugins, and available tools. No LLM call is made.

Use this to verify that memory facts, scheduled reminders, and contact data are
being assembled correctly before spending tokens on a real request.

## Working with dev fixtures

The `workspaces-dev/` directory is a self-contained fake household:

- **2 people**: alice and bob, each with their own `memory.json` and preferences
- **3 contacts**: deterministic fake contacts for testing the contact store
- **Fixed timestamps**: all dates are pinned so tests are reproducible

The structure mirrors a real `workspaces/` directory, so any code that works
against dev fixtures works against real data without changes.

## Resetting dev fixtures

```bash
make dev-setup
```

This runs `scripts/setup_dev_fixtures.py`. It is idempotent and deterministic —
running it twice produces the same output. No API keys are needed.

Use it whenever you want a clean slate or after pulling changes that modify the
fixture schema.

## Issue tracking

All task tracking uses `bd` (beads). Never create markdown TODO files.

```bash
bd ready              # find unblocked work
bd show <id>          # view issue details
bd update <id> --claim  # claim an issue
bd close <id> --reason "..."  # mark done
```
