<svelte:head>
  <title>Installation — homeclaw docs</title>
</svelte:head>

# Installation

You need an LLM API key — either `ANTHROPIC_API_KEY` (Anthropic) or `OPENAI_API_KEY` (OpenAI / OpenRouter).

## Docker (recommended)

Images are published to GitHub Container Registry on every release (linux/amd64 + linux/arm64).

```bash
docker run -d \
  --name homeclaw \
  -p 8080:8080 \
  -v ./workspaces:/data/workspaces \
  ghcr.io/jayphen/homeclaw:latest
```

Open `http://localhost:8080` — the web UI walks you through setup (API keys, password, Telegram, etc.). A one-time setup token is printed to the container logs:

```bash
docker logs homeclaw
```

### With docker-compose

```bash
docker compose up -d
```

This maps port 7399 to 8080 and bind-mounts `./workspaces` for persistent data.

### Building locally

```bash
docker build -t homeclaw .
docker run -d -p 8080:8080 -v ./workspaces:/data/workspaces homeclaw
```

## From source

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

## Volume and data

Mount `/data/workspaces` to persist all household data — contacts, notes, memory, bookmarks, and config. **Back this up regularly.**

The workspaces directory structure:

```
workspaces/
  household/          # Shared household data
    config.json       # Settings (managed via web UI)
    ROUTINES.md       # Scheduled routines
    memory/           # Household-wide memory
  alice/              # Per-person workspace
    memory/           # Alice's private memory
    notes/            # Alice's notes
  bob/                # Another person's workspace
```
