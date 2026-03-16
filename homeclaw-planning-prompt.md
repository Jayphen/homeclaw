# homeclaw — Planning Prompt

> Use this prompt with Claude Code after running `bd init` in your project
> directory. Do not start writing code until beads issues are created.

---

You are helping plan and build a project called **homeclaw** — an open source AI
assistant for households. It knows your home, your family, and the people in your
lives, and helps you stay on top of all of it. It is not a personal assistant
(one person) and not a home automation tool (one building) — it understands the
household as a coherent unit: the people, the space, the routines, and the
relationships inside and outside it.

Use `bd` (beads) for ALL task tracking. Do not create markdown TODO files or task
lists. Every piece of work goes into beads.

---

## Product Summary

homeclaw is inspired by the lightweight "claw" agent ecosystem (NanoClaw, nanobot,
PicoClaw) but targeted specifically at families rather than developers. Core
principles:

- The assistant knows the whole household — schedules, home state, family
  relationships, and people outside the home
- Privacy-first when self-hosted; convenience-first when hosted
- Non-technical users are the target — setup must be achievable without a terminal
- Open source (MIT), with a hosted paid tier as the commercial path
- Plugin ecosystem is a first-class goal — community contributions extend
  the assistant's capabilities

The one-sentence description:
> "An AI that knows your whole household — your home, your family, and the people
> in your lives."

---

## Language and Runtime

**Python 3.12** with strict type annotations throughout.

Type tooling:
- **Pydantic v2** for all data models — validates at the JSON boundary,
  serialises/deserialises automatically, used natively by FastAPI
- **Pyright** (standard mode) for static type checking — fast, works in VS Code
  via Pylance, run in CI
- **Protocol** classes for plugin and tool interfaces — structural typing,
  no inheritance required from plugin authors

`pyproject.toml` configuration:

```toml
[tool.pyright]
pythonVersion = "3.12"
typeCheckingMode = "standard"
include = ["homeclaw"]
exclude = ["workspaces"]
```

Key libraries:
- `anthropic` — Anthropic provider implementation
- `openai` — OpenAI-compatible provider implementation (also covers Ollama,
  Groq, OpenRouter, Mistral, Together AI, and most self-hosted models)
- `pydantic` + `pydantic-settings` — data models and config
- `python-telegram-bot` — Telegram channel adapter
- `fastapi` + `uvicorn` — REST API and static file serving for web UI
- `httpx` — async HTTP for skills and MCP clients
- `apscheduler` — cron scheduler
- `docker` — Docker SDK for Python (MCP sidecar management)
- `memsearch[onnx]` — semantic memory (optional, enables enhanced recall mode)

LLM providers (user configures one):
- Anthropic API (`ANTHROPIC_API_KEY`) — default, recommended
- OpenAI API (`OPENAI_API_KEY`)
- OpenRouter (`OPENAI_API_KEY` + `OPENAI_BASE_URL=https://openrouter.ai/api/v1`)
- Ollama (`OLLAMA_URL=http://localhost:11434`) — fully local, no API key needed
- Any OpenAI-compatible endpoint via `OPENAI_BASE_URL`

---

## Deployment Targets (in priority order)

1. **Railway** (primary for non-technical users)
   - One-click deploy button in README
   - `railway.json` configures the service
   - Persistent volume for `workspaces/`
   - HTTPS out of the box (needed for OAuth callbacks)
   - User fills in env vars in Railway's UI — no terminal required

2. **Docker Compose** (home lab users)
   - `docker-compose.yml` + `.env` file
   - `./workspaces` bind-mounted for persistence
   - Port 8080 exposed for web UI

3. **Unraid**
   - Community Apps template XML
   - Same Docker image as above

4. **Raspberry Pi**
   - Curl installer script for stock Raspberry Pi OS
   - Installs as systemd service
   - Opens browser to setup wizard on first run

5. **macOS via Docker Sandboxes** (primary macOS path)
   - Single curl command: `curl -fsSL https://homeclaw.dev/install.sh | bash`
   - homeclaw runs inside a Docker Sandbox MicroVM — own kernel, no host access
   - `~/homeclaw-workspace` bind-mounted as the only visible filesystem
   - Docker's credential proxy handles API keys — they never exist inside the sandbox
   - MCP sidecar plugins run in their own nested sandboxes (two isolation layers)
   - Currently macOS Apple Silicon and Windows (x86); Linux support coming
   - Config option: `plugin_isolation: sandbox | container` for MCP sidecars

---

## Architecture

### Repository structure

```
homeclaw/
├── homeclaw/                      # Main Python package
│   ├── agent/
│   │   ├── loop.py              # Core LLM loop, tool dispatch
│   │   ├── context.py           # Context builder (injects household state)
│   │   ├── tools.py             # Tool registry and ToolDefinition types
│   │   └── providers/
│   │       ├── base.py          # LLMProvider Protocol + shared types
│   │       ├── anthropic.py     # Anthropic SDK implementation
│   │       ├── openai.py        # OpenAI + any OpenAI-compatible endpoint
│   │       └── factory.py       # Instantiate correct provider from config
│   ├── channel/
│   │   └── telegram.py          # Telegram bot adapter
│   ├── memory/
│   │   ├── facts.py             # Structured facts store (memory.json read/write)
│   │   └── semantic.py          # Semantic recall layer (memsearch wrapper)
│   ├── contacts/
│   │   ├── models.py            # Pydantic models: Contact, Interaction etc
│   │   └── store.py             # Contact JSON read/write
│   ├── scheduler/
│   │   ├── scheduler.py         # APScheduler wrapper
│   │   └── routines.py          # ROUTINES.md parser
│   ├── config.py                # Pydantic Settings (env vars + config.json)
│   ├── api/
│   │   ├── app.py               # FastAPI app, mounts ui/dist/ as static files
│   │   ├── routes/
│   │   │   ├── dashboard.py
│   │   │   ├── calendar.py
│   │   │   ├── memory.py
│   │   │   ├── contacts.py
│   │   │   └── plugins.py
│   │   └── models.py            # Pydantic request/response models
│   └── plugins/
│       ├── interface.py         # Plugin and RoutineDefinition Protocol classes
│       ├── registry.py          # Unified registry (Python + skill + MCP)
│       ├── loader.py            # Dynamic Python plugin loader (importlib)
│       ├── skills/
│       │   ├── loader.py        # Skill markdown file loader
│       │   └── http_call.py     # Sandboxed http_call tool implementation
│       ├── mcp/
│       │   └── client.py        # MCP sidecar client (HTTP/SSE)
│       ├── marketplace/
│       │   ├── index.py         # Fetch and cache remote marketplace index
│       │   └── installer.py     # Route install by type (python/skill/mcp)
│       └── docker/
│           ├── client.py        # Docker socket wrapper
│           └── compose.py       # docker-compose.yml read/write
├── ui/                          # Web UI (Svelte, built to ui/dist/)
│   ├── src/
│   │   ├── App.svelte
│   │   ├── Dashboard.svelte     # Household overview (default view)
│   │   ├── Calendar.svelte      # Unified household calendar
│   │   ├── Memory.svelte        # Per-person memory viewer and editor
│   │   ├── Contacts.svelte      # Contact list and detail pages
│   │   └── Plugins.svelte       # Marketplace + installed plugins
│   ├── package.json
│   └── dist/                    # Compiled output — committed to repo
│                                # No Node required at Docker runtime
├── workspaces/                  # Bind-mounted in Docker — all user data
├── plugins/                     # Built-in plugin source (reference impls)
│   └── plants/
│       ├── plugin.py            # Implements Plugin Protocol
│       ├── manifest.json
│       └── README.md            # Documents plugin for contributors
├── tests/
├── Dockerfile
├── docker-compose.yml
├── railway.json
├── unraid-template.xml
├── install.sh                   # Pi curl installer
├── pyproject.toml               # Dependencies, Pyright config, Ruff config
└── Makefile                     # ui-build, docker-build, docker-push, typecheck
```

---

## Type System Design

### Pydantic models (`homeclaw/contacts/models.py` and `homeclaw/api/models.py`)

All persistent data models use Pydantic BaseModel. This gives automatic JSON
validation on load, serialisation on save, and native FastAPI integration.

```python
from pydantic import BaseModel
from datetime import date, datetime

class Interaction(BaseModel):
    date: datetime
    type: str                          # "call" | "message" | "meetup" | "other"
    notes: str

class Reminder(BaseModel):
    interval_days: int | None = None   # recurring: check in every N days
    next_date: date | None = None      # one-shot: remind on this date
    note: str = ""

class Contact(BaseModel):
    id: str
    name: str
    relationship: str                  # "friend" | "family" | "colleague" | "other"
    birthday: date | None = None
    facts: list[str] = []
    interactions: list[Interaction] = []
    reminders: list[Reminder] = []
    last_contact: datetime | None = None

# Loading validates automatically — raises ValidationError if malformed
contact = Contact.model_validate_json(path.read_text())

# Saving is one line
path.write_text(contact.model_dump_json(indent=2))
```

### Plugin Protocol (`homeclaw/plugins/interface.py`)

Structural typing — plugin authors implement the shape, no imports from homeclaw
required.

```python
from typing import Protocol, runtime_checkable
from pydantic import BaseModel

class ToolDefinition(BaseModel):
    name: str
    description: str
    parameters: dict                   # JSON Schema

class RoutineDefinition(BaseModel):
    cron: str                          # APScheduler cron expression
    description: str

@runtime_checkable
class Plugin(Protocol):
    name: str
    description: str

    def tools(self) -> list[ToolDefinition]: ...
    async def handle_tool(self, name: str, args: dict) -> dict: ...
    def routines(self) -> list[RoutineDefinition]: ...
```

`isinstance(plugin, Plugin)` works at runtime via `@runtime_checkable`.
Pyright checks conformance statically.

### LLM Provider Abstraction (`homeclaw/agent/providers/`)

The agent loop is provider-agnostic. All LLM calls go through the
`LLMProvider` Protocol — the agent loop never imports the Anthropic or OpenAI
SDK directly.

```python
# homeclaw/agent/providers/base.py
from typing import Protocol
from pydantic import BaseModel

class Message(BaseModel):
    role: str                          # "user" | "assistant" | "tool"
    content: str | list

class LLMResponse(BaseModel):
    content: str
    tool_calls: list[ToolCall] = []
    stop_reason: str

class LLMProvider(Protocol):
    async def complete(
        self,
        messages: list[Message],
        tools: list[ToolDefinition],
        system: str,
    ) -> LLMResponse: ...
```

Two concrete implementations cover the full provider landscape:

**`anthropic.py`** — wraps the Anthropic SDK. Handles Anthropic's tool use
format, streaming, and prompt caching.

**`openai.py`** — wraps the OpenAI SDK with a configurable `base_url`. Because
Ollama, Groq, OpenRouter, Mistral, Together AI, and most self-hosted models
speak the OpenAI API format, this one implementation covers all of them:

```python
# Ollama (local, no API key)
OPENAI_BASE_URL=http://localhost:11434/v1
MODEL=llama3.2

# OpenRouter (cloud, access to many models)
OPENAI_API_KEY=sk-or-...
OPENAI_BASE_URL=https://openrouter.ai/api/v1
MODEL=anthropic/claude-sonnet-4-6

# Groq (fast inference)
OPENAI_API_KEY=gsk_...
OPENAI_BASE_URL=https://api.groq.com/openai/v1
MODEL=llama-3.3-70b-versatile
```

**`factory.py`** reads config and returns the correct provider instance.
The agent loop calls `factory.create_provider(config)` and never needs to
know which provider is active.

### Config (`homeclaw/config.py`)

Pydantic Settings reads from environment variables and config.json. Provider
config is mutually exclusive — exactly one block should be set:

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class homeclawConfig(BaseSettings):
    # LLM provider — set one of these:
    anthropic_api_key: str | None = None   # Anthropic (default)
    openai_api_key: str | None = None      # OpenAI or OpenAI-compatible
    openai_base_url: str | None = None     # omit for OpenAI, set for others

    # Model name — set to match your provider
    model: str = "claude-sonnet-4-6"

    # Telegram
    telegram_token: str

    # Home Assistant (optional)
    ha_url: str | None = None
    ha_token: str | None = None

    # Web UI
    web_port: int = 8080
    web_password: str
    workspaces_path: str = "./workspaces"

    model_config = SettingsConfigDict(
        env_file=".env",
        json_file="workspaces/config.json"
    )
```

---

## Memory Architecture

homeclaw has two distinct memory layers that serve different purposes and are
implemented separately.

### Layer 1 — Structured facts (`homeclaw/memory/facts.py`)

Explicit facts the agent has learned about household members and preferences.
Fast key/value style lookup, always injected in full into every LLM context.
Stored as `workspaces/{person}/memory.json` (Pydantic model).
Displayed and editable in the web UI memory viewer — users can see exactly
what the agent knows and correct it by hand.

```python
class HouseholdMemory(BaseModel):
    facts: list[str] = []          # "Alice is vegetarian"
    preferences: dict = {}         # reminder_lead_time, preferred_channel etc
    last_updated: datetime | None = None
```

Written by the agent via `memory_update` tool. Read by the context builder
and injected into every system prompt.

### Layer 2 — Semantic recall (`homeclaw/memory/semantic.py`)

Searches past conversations, notes, and contact logs to surface relevant
context for the current conversation. Uses memsearch — a markdown-first
memory library that keeps human-readable files as the source of truth and
uses Milvus Lite as a derived, rebuildable index.

```python
from memsearch import MemSearch

class SemanticMemory:
    def __init__(self, workspaces_path: str):
        self.mem = MemSearch(
            paths=[
                f"{workspaces_path}/household/notes",
                f"{workspaces_path}/household/contacts",
            ],
            milvus_uri=f"{workspaces_path}/.index/milvus.db"
        )

    async def recall(self, query: str, top_k: int = 3) -> list[str]:
        results = await self.mem.search(query, top_k=top_k)
        return [r["content"] for r in results]
```

Indexes automatically: household notes, personal notes, contact interaction
logs (summarised to daily markdown), and conversation summaries.
Milvus Lite stores the vector index as a single file at
`workspaces/.index/milvus.db` — no server required, rebuildable from
markdown at any time by deleting the file.

**Embedding providers (user configures one):**
- ONNX BGE-M3 (default — local CPU, no API key, ~558MB one-time download)
- Ollama `nomic-embed-text` (if Ollama is already configured)
- OpenAI `text-embedding-3-small` (cloud, requires `OPENAI_API_KEY`)

**Two modes:**
- **Basic mode** (default): Layer 1 only — structured facts, no embedding
  model, no download. Good for low-powered Pi or users who don't need search.
- **Enhanced memory** (opt-in via config): Adds Layer 2. Prompts user during
  onboarding, downloads embedding model on first enable.

### Context builder (`homeclaw/agent/context.py`)

Every LLM call injects both layers:

```python
async def build_context(message: str, person: str) -> str:
    # Layer 1 — always inject structured facts in full
    facts = facts_store.load(person)

    # Layer 2 — inject only semantically relevant past context
    recalled = []
    if semantic_memory.enabled:
        recalled = await semantic_memory.recall(message, top_k=3)

    # Also inject: current time, today's events, HA state,
    # contacts with reminders due, household routines
    ...
```

The context builder never dumps all history — only the top-k semantically
relevant chunks, keeping context windows lean.

---

## Plugin System (two tiers — no WASM needed)

WASM is not needed in Python. Dynamic plugin loading is native via importlib.
The sandbox concern is documented clearly: plugins run with full Python access,
users should only install plugins they trust (same model as pip or Homebrew).

### Tier 1 — Python plugins (no network, file-local)

```python
# workspaces/plugins/plants/plugin.py

class Plugin:
    name = "plants"
    description = "Track plant watering schedules"

    def tools(self) -> list[ToolDefinition]:
        return [
            ToolDefinition(
                name="plant_log",
                description="Log a watering event for a plant",
                parameters={...}
            ),
            ToolDefinition(
                name="plant_status",
                description="List all plants and their watering schedules",
                parameters={}
            )
        ]

    async def handle_tool(self, name: str, args: dict) -> dict:
        if name == "plant_log":
            ...
        elif name == "plant_status":
            ...

    def routines(self) -> list[RoutineDefinition]:
        return [
            RoutineDefinition(
                cron="0 20 * * *",
                description="Check for overdue plant watering"
            )
        ]
```

Install: download `plugin.py` + `manifest.json` to `workspaces/plugins/{name}/`.
Loader uses `importlib.import_module` and validates against Plugin Protocol.
No restart required — registry reloads on file change.

### Tier 2 — Skill plugins (REST APIs, markdown)

For stateless network integrations. Format is a markdown file with instructions
and API patterns. Uses the built-in `http_call` tool (domain allowlisted per
skill, all requests logged). Auth tokens stored in
`workspaces/plugins/{name}/tokens/`, managed by `homeclaw auth {skill-name}` CLI
command.

### Tier 3 — MCP sidecar plugins (network, OAuth, stateful)

For integrations needing persistent connections, webhooks, or complex OAuth.
Each is a Docker container. Web UI generates the docker-compose block, calls
Docker socket to pull and start the container, handles OAuth flow in browser.
Docker socket (`/var/run/docker.sock`) bind-mounted into homeclaw for sidecar
management.

### Optional: agent-browser sidecar

For household tasks requiring real browser interaction — checking a recipe site,
reading a page that blocks simple HTTP fetches, or handling OAuth flows that
require browser interaction. Runs as an optional MCP sidecar inside its own
Docker Sandbox, so Chrome never runs on the host.

```yaml
# Auto-added to docker-compose.yml when user installs browser plugin
services:
  homeclaw-browser:
    image: ghcr.io/community/homeclaw-browser:latest  # agent-browser + Chrome
    labels:
      homeclaw.plugin: "browser"
      homeclaw.mcp.port: "3200"
    volumes:
      - ./workspaces/plugins/browser:/workspace
```

Exposes a `web_browse` tool to the agent:
- `web_browse(url)` — navigate and return accessible text content
- `web_fill(url, fields)` — fill and submit a form

The agent-browser authentication vault stores any credentials needed for
authenticated browsing — credentials are encrypted locally and the LLM
never sees them.

### Marketplace index format

```json
{
  "plugins": [
    {
      "name": "plants",
      "type": "python",
      "version": "1.2.0",
      "description": "Track plant watering schedules",
      "plugin_url": "https://...",
      "checksum": "sha256:...",
      "has_ui_panel": true
    },
    {
      "name": "weather",
      "type": "skill",
      "version": "1.0.0",
      "description": "Current weather and forecasts",
      "skill_url": "https://...",
      "checksum": "sha256:..."
    },
    {
      "name": "google-calendar",
      "type": "mcp",
      "version": "1.0.0",
      "description": "Read and write Google Calendar",
      "image": "ghcr.io/community/homeclaw-gcal:latest",
      "port": 3100,
      "oauth_required": true,
      "has_ui_panel": true
    }
  ]
}
```

---

## workspaces/ layout

```
workspaces/
  config.json
  household/
    contacts/                    # one JSON file per external contact
    notes/                       # YYYY-MM-DD.md (shared household notes)
    ROUTINES.md                  # scheduled heartbeat tasks
  skills/                        # installed skill markdown files
  plugins/
    plants/                      # Python plugin data + plugin.py
      plugin.py
      manifest.json
      plants.json
    google-calendar/             # MCP sidecar tokens + data
      tokens/
  .index/
    milvus.db                    # Milvus Lite vector index (rebuildable)
  {person}/                      # one dir per household member
    memory.json                  # persistent facts (Layer 1)
    history.jsonl                # conversation history (rolling window)
    notes/                       # YYYY-MM-DD.md (personal notes, indexed by memsearch)
```

---

## Agent Context Builder (`homeclaw/agent/context.py`)

Every LLM call injects household-level ambient context automatically:

- Current time and date
- Today's events for all household members
- Current home state (HA entity states, if configured)
- Contacts with reminders due in the next 7 days
- The requesting person's memory.json facts and preferences

The agent is never a blank slate — it always knows the current state of the
household before the conversation starts.

---

## Scheduler / Heartbeat (`homeclaw/scheduler/`)

APScheduler reads `workspaces/household/ROUTINES.md` on startup.

```markdown
# Household Routines

## Every day at 7:30 AM
- Check today's calendar for all household members
- Check weather if anyone has outdoor plans
- Check shopping list and remind household if it has 10+ items

## Every Sunday at 6:00 PM
- Check contacts with overdue check-in reminders
- Send a nudge to the relevant household member

## Every day at 9:00 PM
- Check if any plants are overdue for watering
- Remind the relevant person if so
```

---

## Built-in tool surface

```
Home:     ha_call, ha_query
People:   contact_get, contact_update, contact_list,
          contact_remind, interaction_log
Memory:   memory_read, memory_update
Notes:    note_save, note_get
Utility:  reminder_set, message_send
Network:  http_call (sandboxed — domain allowlist per skill,
          no internal network addresses, all requests logged)
```

---

## Web UI (Svelte + FastAPI)

Built with Svelte, output committed to `ui/dist/`. Served as static files by
FastAPI — no Node at runtime or in Docker. Auth: single shared household
password set in config.

Views:
- `/` — Household dashboard: today's overview, home state, upcoming events
- `/calendar` — Unified monthly calendar (all members + shared + interactions)
- `/memory` — Per-person memory viewer and editor
- `/contacts` — Contact list with history and upcoming reminders
- `/plugins` — Installed plugins, status, per-plugin data panels
- `/plugins/marketplace` — Browse and install from marketplace index

REST API (FastAPI, fully typed with Pydantic request/response models):

```
GET    /api/dashboard
GET    /api/calendar?month=YYYY-MM
GET    /api/memory
GET    /api/memory/{person}
PUT    /api/memory/{person}/facts
GET    /api/memory/{person}/recall?q=query  # semantic search UI
GET    /api/contacts
GET    /api/contacts/{id}
PUT    /api/contacts/{id}
GET    /api/plugins
GET    /api/plugins/marketplace
POST   /api/plugins/install
DELETE /api/plugins/{name}
GET    /api/plugins/{name}/data
```

---

## Open source and commercial model

- License: MIT
- Hosted service: separate private repo, imports homeclaw as a dependency,
  adds billing and multi-tenancy
- Monetization: freemium hosted tier (~$10-15/month), self-hosted always free
- LLM costs: bring-your-own API key for self-hosted; hosted tier proxies
  through homeclaw's key
- Plugin marketplace: community-contributed, MIT

---

## Reference plugin: plants (`plugins/plants/`)

The first plugin to build — covers the full plugin surface as a reference
implementation for community contributors.

- Type: Python
- Tools: `plant_log` (log a watering event), `plant_status` (list plants
  and watering schedule)
- Routine: nightly check — if any plant is overdue, message the owner
- Storage: `workspaces/plugins/plants/plants.json`
- UI panel: list of plants, last watered, next due, manual log button

---

## Your task

1. Run `bd quickstart` to verify beads is ready
2. Decompose the entire project into beads issues. Every meaningful unit of
   work gets an issue. Priorities 1 (highest) to 5 (lowest).
3. Set dependency chains carefully. Key ordering constraints:
   - Pyright and Ruff configured in pyproject.toml before any other code
   - Config loading (Pydantic Settings) blocks everything
   - Pydantic data models block agent loop, contacts store, memory store
   - Structured facts store (Layer 1) blocks agent loop
   - memsearch semantic layer (Layer 2) blocks enhanced memory mode
   - Semantic layer blocks context builder enhanced path
   - LLMProvider Protocol (`providers/base.py`) blocks Anthropic and OpenAI
     provider implementations
   - Provider factory blocks agent loop
   - Agent loop blocks Telegram channel adapter
   - Built-in tools block plugin registry
   - Plugin Protocol and registry block all plugin types
   - Python plugin loader blocks reference plants plugin
   - MCP client blocks Docker socket management
   - REST API (FastAPI app) blocks all web UI development
   - Svelte build pipeline blocks all UI views
   - Dashboard view blocks calendar, memory, contacts views (shared layout)
   - Plants reference plugin blocks marketplace (need something to list)
   - Marketplace index fetching blocks install flow
   - Docker Sandboxes macOS installer script blocks macOS deployment target
   - agent-browser sidecar blocks web_browse tool
4. Issue types: feature, task, chore, bug
5. After creating all issues, run `bd ready --json` and report which
   issues are unblocked and ready to start
6. Recommend a first session: what to build, acceptance criteria, and
   what "land the plane" looks like at the end of it

**Do not write any code yet. Planning and issue creation only.**

---

## AGENTS.md content

Add the following to `AGENTS.md` in the project root:

```markdown
Use `bd` for all task tracking. Run `bd quickstart` at the start of each session.
This project is called homeclaw. Read HOMECLAW.md before starting any work.
All Python code must pass Pyright (standard mode): run `make typecheck`.
All data models use Pydantic BaseModel. All interfaces use Protocol classes.
Memory has two layers: structured facts (memory.json) and semantic recall (memsearch).
Do not conflate them. Layer 1 is always on. Layer 2 requires enhanced memory mode.
When ending a session, land the plane: file remaining work, close completed
issues, push.
```
