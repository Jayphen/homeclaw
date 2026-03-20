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
├── data/             # Optional: persistent data files
├── scripts/          # Optional: executable scripts
├── references/       # Optional: reference docs
└── assets/           # Optional: templates, resources
```

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
| metadata | No | Arbitrary key-value pairs. |

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

## Using the skill_create tool

Call `skill_create` with these arguments:

- **name**: Slug-style name (e.g., "budget-tracker", "meal-planner")
- **description**: Clear description of what and when (see above)
- **scope**: "household" (shared) or "private" (one person)
- **instructions**: The markdown body of the SKILL.md
- **allowed_domains**: List of API domains if needed (optional)
- **initial_files**: Seed data files (optional)
- **source_notes**: Copy memory topics into skill data (optional)
- **source_bookmarks**: Export bookmarks into skill data (optional)

## Data management

Skills with persistent state use the `data/` directory:
- Use one canonical file per topic (e.g., `spending.md`)
- Append new entries — don't create date-suffixed files
- Always call `data_list` before `data_write` to check for existing files
- Consolidate duplicates if found

## Editing existing skills

To modify a skill's instructions or description, use `skill_update`.
To move a skill between scopes, use `skill_migrate`.
To remove a skill (archived, not deleted), use `skill_remove`.

## Common patterns

### Data-only skill (no API)
Budget tracker, habit log, reading list — just needs data files.
Set `allowed_domains` to empty, focus instructions on data file conventions.

### API integration skill
Weather, transit, calendar — calls external APIs.
Set `allowed_domains` to the API hosts, include API usage in instructions.

### Workflow skill
Morning briefing, weekly review — orchestrates multiple tools.
Instructions describe the workflow steps and what to include.
