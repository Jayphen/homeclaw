<svelte:head>
  <title>Development Guide — homeclaw docs</title>
</svelte:head>

# Development Guide

## Getting started

```bash
git clone https://github.com/Jayphen/homeclaw.git
cd homeclaw
uv sync --extra dev
```

Set at least one LLM provider key:

```bash
export ANTHROPIC_API_KEY=sk-...
# or
export OPENAI_API_KEY=sk-...
```

Bootstrap dev fixtures and launch the REPL:

```bash
make dev-setup   # creates workspaces-dev/ with deterministic fake data
make dev         # REPL as alice
```

No API key is needed for `make dev-setup` — it only writes local files.

## The three dogfooding stages

### Stage 1: REPL with dev fixtures

Available from day one. No Telegram bot, no server — just a terminal REPL talking to the LLM with fake household data.

```bash
make dev          # REPL as alice
make dev-bob      # REPL as bob
make dev-context  # dry-run: prints the assembled context, no LLM call
```

Use this stage to iterate on the agent loop, tools, context builder, and memory layers without any external dependencies.

### Stage 2: Telegram with dev fixtures

Point the Telegram adapter at the same dev fixtures with a test bot token:

```bash
export TELEGRAM_BOT_TOKEN=<test-bot-token>
make dev-serve    # full server (API + Telegram) against workspaces-dev/
```

### Stage 3: Real household

Genuine dogfooding. Point at a real `workspaces/` directory with your own household data and use homeclaw day-to-day.

## Running tests

```bash
make test              # unit tests only — zero LLM API calls
make test-integration  # integration tests (requires API key)
make typecheck         # pyright in standard mode
make lint              # ruff check + format
```

All unit tests mock the LLM. They replay recorded fixture responses from disk, so they are fast and free.

## Recording new LLM fixtures

When you add a test that needs a new LLM interaction:

```bash
make test-record
```

This runs the test suite with a live API key and captures real responses into `tests/fixtures/llm_responses/` as JSON files. In normal replay mode, tests load these files instead of calling the API.

Commit the new fixture files alongside your test.

## Dev fixtures

The `workspaces-dev/` directory is a self-contained fake household:

- **2 people**: alice and bob, each with their own memory and preferences
- **3 contacts**: deterministic fake contacts for testing
- **Fixed timestamps**: all dates are pinned so tests are reproducible

Reset with `make dev-setup` — it's idempotent and deterministic.

## Debugging context builder output

```bash
make dev-context
```

Prints exactly what the LLM sees: system prompt, injected facts, active reminders, person preferences, loaded plugins, and available tools. No LLM call is made.

## Issue tracking

All task tracking uses `bd` (beads). Never create markdown TODO files.

```bash
bd ready              # find unblocked work
bd show <id>          # view issue details
bd update <id> --claim  # claim an issue
bd close <id> --reason "..."  # mark done
```
