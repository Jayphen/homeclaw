<svelte:head>
  <title>homeclaw — AI assistant for households</title>
</svelte:head>

# homeclaw

<p class="lead">An open source AI assistant for households. It knows your home, your family, and the people in your lives.</p>

Not a personal assistant (one person) and not a home automation tool (one building) — homeclaw understands the **household** as a coherent unit.

## What makes homeclaw different

- **Multi-person by design** — each household member gets their own workspace with private memory, notes, and contacts
- **Shared household knowledge** — common info (routines, household contacts, shared notes) lives in a shared workspace everyone can access
- **Channel-flexible** — talk to homeclaw via Telegram, WhatsApp, the web UI, or the terminal REPL
- **Privacy-scoped recall** — semantic search is scoped per person, so members only see their own data plus shared household knowledge

## Quick start

The fastest way to get running is Docker:

```bash
docker run -d \
  --name homeclaw \
  -p 8080:8080 \
  -v ./workspaces:/data/workspaces \
  ghcr.io/jayphen/homeclaw:latest
```

Open `http://localhost:8080` — the web UI walks you through setup.

See the [Installation guide](/getting-started/installation) for more options including docker-compose, from-source, and Unraid.

## Key features

| Feature | Description |
|---------|-------------|
| **Agent loop** | 40+ built-in tools, cost-aware model routing, prompt caching |
| **Memory** | Per-person markdown topics with semantic recall via memsearch |
| **Contacts** | Full CRM with interactions, reminders, per-person private notes |
| **Bookmarks** | Save, search, categorize, and annotate links |
| **Notes** | Daily markdown notes per person and shared household notes |
| **Reminders** | One-shot and recurring, delivered via preferred channel |
| **Scheduler** | Natural language routines in ROUTINES.md |
| **Plugins** | Python plugins, Skill markdown, MCP sidecars |
| **Web UI** | Dashboard, contacts, memory, notes, settings, and more |

## homeclaw vs openclaw

[openclaw](https://github.com/openclaw/openclaw) is a mature, widely-adopted personal AI assistant. homeclaw takes a different approach — built around the **household** as a unit, not a single person. If openclaw is your personal assistant, homeclaw is your family's.

See the [README](https://github.com/Jayphen/homeclaw#homeclaw-vs-openclaw) for a detailed comparison.
