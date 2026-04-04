---
name: skill-creator
description: >-
  Create and edit homeclaw skills. Use when someone asks to add a new skill,
  teach homeclaw something new, create an automation, or set up a recurring
  workflow. Also use when editing or improving an existing skill.
metadata:
  builtin: "true"
---

# Creating a skill

A skill is a self-contained capability that teaches homeclaw how to handle a
specific domain — budgets, meal planning, workout tracking, API integrations, etc.

## When to create a skill

Create a skill when:
- Someone asks you to "learn" or "remember how to" do something repeatedly
- A task needs specific instructions that go beyond general knowledge
- A workflow needs data persistence (budget tracking, habit logs, etc.)
- An external API integration is needed (weather, transit, etc.)

Do NOT create a skill when:
- A simple memory_save covers it (one-off facts, preferences)
- A reminder handles it (time-based triggers)
- A bookmark is more appropriate (saving links/places)

## Skill structure

Every skill is a directory containing a `SKILL.md` file:

```
skill-name/
├── SKILL.md          # Required: YAML frontmatter + instructions
├── .env              # Optional: secrets (HA_URL, API keys) — loaded automatically
├── data/             # Optional: persistent data files
├── scripts/          # Optional: executable scripts
├── references/       # Optional: reference docs
└── assets/           # Optional: templates, resources
```

**IMPORTANT**: The `.env` file MUST be in the skill root, not in `data/`.
Use `skill_edit_file(name='x', file='.env', content='KEY=value')` to create it.
Do NOT use `data_write` for `.env` — that puts it in the wrong place.

## SKILL.md format

Use YAML frontmatter followed by markdown instructions:

```markdown
---
name: skill-name
description: What this skill does and when to use it. Be specific — this is what determines when the skill gets activated.
allowed-domains:
  - api.example.com
metadata:
  key: value
---

Instructions for how to use this skill go here.
Include step-by-step guidance, edge cases, and examples.
```

### Frontmatter fields

| Field | Required | Notes |
|-------|----------|-------|
| name | Yes | Lowercase letters, numbers, hyphens. Must match directory name. |
| description | Yes | What + when. Be specific — this triggers activation. |
| allowed-domains | No | Domains for http_call (homeclaw extension). |
| license | No | License name. |
| compatibility | No | Environment requirements (bins, network, etc.). |
| metadata | No | Arbitrary key-value pairs (can be nested). |

### Writing good descriptions

The description determines when the skill gets activated. Include:
- What the skill does
- Keywords that match user intent
- When to use it vs alternatives

Good: "Track household spending, categorize expenses, and show budget summaries. Use when someone mentions money, spending, bills, budget, or expenses."

Bad: "Budget helper."

### Writing good instructions

Instructions are loaded into context when the skill is activated. Keep them:
- Under 500 lines (move detailed reference to `references/`)
- Action-oriented (tell the agent what to do, not what the skill is)
- Specific about data formats and file conventions

Include:
1. Step-by-step usage instructions
2. Data file conventions (what files to create, how to structure them)
3. Edge cases and error handling
4. Examples of inputs and expected behavior

## How tools work

Every skill automatically gets these tools, namespaced with the skill name:
- `{name}__data_list` — list files in data/
- `{name}__data_read` — read a data file
- `{name}__data_write` — write a data file
- `{name}__data_delete` — delete a data file

If `allowed-domains` is set, the skill also gets:
- `{name}__http_call` — make HTTP requests to the allowed domains

You do NOT define these tools manually — they are registered automatically.
To make API calls, just set `allowed-domains` to the API hosts and use
`{name}__http_call` with the full URL.

If the skill has a `scripts/` directory, use `run_skill_script` to execute
bundled scripts (30s timeout, path-traversal protected).

After creating or installing a skill, call `read_skill` to see the exact
tool names and available resources.

## Installing and adapting existing skills

**Always prefer installing over recreating.** If a skill already exists online:
1. Use `skill_install` with the URL to download it
2. Use `skill_edit_file` with find/replace to adapt specific parts
3. Never try to reproduce a large skill via `skill_create` — the instructions
   will be truncated. Install first, then make targeted edits.

`skill_install` accepts:
- GitHub repo URLs (downloads SKILL.md + scripts/, references/, assets/, data/)
- GitHub gist URLs
- Any URL serving a SKILL.md file directly

Example workflow to fork a skill:
```
skill_install(url="https://github.com/user/some-skill")
skill_edit_file(name="some-skill", file="SKILL.md", find="old text", replace="new text")
```

## Creating a skill from scratch

Call `skill_create` with:
- **name**: Slug-style (e.g. "budget-tracker", "meal-planner")
- **description**: What + when (see Writing good descriptions)
- **scope**: "household" (shared) or "private" (one person)
- **instructions**: Markdown body of the SKILL.md
- **allowed_domains**: Domains for http_call (optional)
- **initial_files**: Seed data files as `[{filename, content}]` (optional)
- **source_notes**: Copy memory topics into skill data (optional)
- **source_bookmarks**: Export bookmarks into skill data (optional)

Note: if skill approval is enabled and you're not an admin, the skill goes
to a pending queue. An admin must approve it with `skill_approve` before
it becomes active. Check pending skills with `skill_pending_list`.

## Data management

Skills with persistent state use the `data/` directory:
- Use one canonical file per topic (e.g., `spending.md`)
- Append new entries — don't create date-suffixed files
- Always call `data_list` before `data_write` to check for existing files
- Consolidate duplicates if found

## All skill tools

| Tool | Purpose |
|------|---------|
| `read_skill` | Load a skill's instructions and see its tools + resources |
| `skill_list` | List all available skills |
| `skill_create` | Create a new skill from scratch |
| `skill_install` | Install a skill from a URL (GitHub, gist, or direct) |
| `skill_edit_file` | Read, write, or find/replace a file in a skill |
| `skill_update` | Update a skill's description or instructions |
| `skill_remove` | Archive a skill (soft delete) |
| `skill_migrate` | Move a skill between scopes (household ↔ private) |
| `skill_pending_list` | List skills awaiting admin approval |
| `skill_approve` | Approve a pending skill (admin only) |
| `skill_reject` | Reject and delete a pending skill (admin only) |
| `run_skill_script` | Execute a script in a skill's scripts/ directory |

## Setting up .env for API skills

Skills that need API keys or URLs use a `.env` file in the skill root:

```
# workspaces/household/skills/homeassistant-skill/.env
HA_URL=http://home.local:8123
HA_TOKEN=eyJhbGciOiJIUzI1NiIs...
```

Create it with:
```
skill_edit_file(name="homeassistant-skill", file=".env", content="HA_URL=http://...\nHA_TOKEN=eyJ...")
```

The env vars are automatically substituted in `http_call`:
- `${HA_URL}` in URLs → replaced with the value from .env
- `${HA_TOKEN}` in headers → replaced with the value from .env

Example http_call:
```
http_call(url="${HA_URL}/api/states", headers={"Authorization": "Bearer ${HA_TOKEN}"})
```

NEVER use `data_write` for `.env` — it goes in `data/` which is wrong.
ALWAYS use `skill_edit_file` with `file=".env"`.

## Common patterns

### Data-only skill (no API)
Budget tracker, habit log, reading list — just needs data files.
Set `allowed-domains` to empty, focus instructions on data file conventions.

### API integration skill
Weather, transit, Home Assistant — calls external APIs.
Set `allowed-domains` to the API hosts, include API usage in instructions.
If the service is on LAN, the admin needs to enable "Allow local network"
in the Skills settings.

### Workflow skill
Morning briefing, weekly review — orchestrates multiple tools.
Instructions describe the workflow steps and what to include.

### Mini-app skill (Arrow.js embedded UI)

Skills can embed a small interactive web app in the homeclaw web UI.
Declare it with `ui-app:` in the frontmatter — the app appears as a live
panel on the skill's detail page, with a link to open in a new tab.

If the skill already exists, do NOT call `skill_create` again. Instead:
1. Call `read_skill` to inspect the existing skill and its files
2. Prefer `skill_enable_ui_app` to deterministically update `SKILL.md` and create `assets/index.html`
3. If you must edit manually, use `skill_write_file` for full writes, `skill_read_file` for inspection, and `skill_replace_in_file` for targeted edits
4. Update `SKILL.md` and write `assets/index.html` with the explicit file tools above
5. Keep the app inside the skill's `assets/` directory so the web UI can render it

Do NOT return raw HTML to the user and tell them to save or run it manually.
For embedded apps, the goal is a live skill panel in homeclaw, not a pasted HTML blob.
Never use `{name}__data_write` for `SKILL.md` or `assets/index.html` — `data_write`
only manages files inside `data/`. Prefer `skill_read_file` / `skill_write_file` /
`skill_replace_in_file` over `skill_edit_file` when the action is already known.

**SKILL.md frontmatter:**
```yaml
---
name: my-skill
description: Track items and show them in an interactive list.
ui-app:
  entry: assets/index.html   # default — can omit if using this path
  title: My App              # optional display title
---
```

**Arrow.js is the preferred framework** — zero build step, reactive,
tiny (~5KB). Load it from CDN or vendor it into `assets/`:

```html
<!-- assets/index.html -->
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body { font-family: sans-serif; padding: 1rem; margin: 0; }
  </style>
</head>
<body>
<script type="module">
  import { reactive, html } from 'https://cdn.jsdelivr.net/npm/@arrow-js/core/dist/index.mjs'

  // Read the auth token from localStorage (same origin as homeclaw)
  const token = localStorage.getItem('homeclaw_token') ?? ''
  const headers = { Authorization: `Bearer ${token}` }

  // Load skill data from the files API
  const state = reactive({ items: [], loading: true })

  fetch('/api/skills/household/my-skill/files/data/items.json', { headers })
    .then(r => r.ok ? r.json() : { items: [] })
    .then(d => { state.items = d.items ?? []; state.loading = false })

  html`
    ${() => state.loading
      ? html`<p>Loading…</p>`
      : html`<ul>${() => state.items.map(item => html`<li>${item}</li>`)}</ul>`
    }
  `(document.body)
</script>
</body>
</html>
```

**How to create a mini-app skill:**
```
skill_create(
  name="my-app",
  description="Interactive tracker with embedded UI.",
  scope="household",
  instructions="...",
  initial_files=[
    {
      "filename": "assets/index.html",
      "content": "<!-- Arrow.js app here -->"
    },
    {
      "filename": "data/items.json",
      "content": "{\"items\": []}"
    }
  ]
)
```

Then update `assets/index.html` via `skill_edit_file` with the full app.

**Converting an existing skill into a mini-app:**
```
read_skill(name="budget", person="alice")
skill_edit_file(
  name="budget",
  file="SKILL.md",
  find="description: ...",
  replace="description: ...\nui-app:\n  entry: assets/index.html\n  title: Budget Dashboard"
)
skill_edit_file(
  name="budget",
  file="assets/index.html",
  content="<!-- Arrow.js app here -->"
)
```

**Notes:**
- The app runs on the same origin as homeclaw, so `fetch('/api/...')` works
- Use `localStorage.getItem('homeclaw_token')` for the Bearer token
- Data lives in `data/` — read via `/api/skills/{owner}/{name}/files/data/filename`
- Write data back via the agent using `{name}__data_write`; the UI is read-only by default
- LAN-only installs: vendor Arrow.js into `assets/arrow.js` and use a relative import
