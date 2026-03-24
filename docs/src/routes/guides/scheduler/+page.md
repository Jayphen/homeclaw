<svelte:head>
  <title>Scheduler & Routines — homeclaw docs</title>
</svelte:head>

# Scheduler & Routines

homeclaw runs recurring tasks defined in natural language in `workspaces/household/ROUTINES.md`.

## Defining routines

Each routine is a markdown section with a schedule, optional target, and action:

```markdown
## Morning briefing
- **Schedule**: Every weekday at 7:30am
- **Target**: each_member
- **Action**: Summarize today's calendar, reminders, and weather.

## Weekly grocery reminder
- **Schedule**: Every Sunday at 10am
- **Target**: household
- **Action**: Ask each person if they need anything from the store and compile a shared list.

## Stephen's exercise reminder
- **Schedule**: Every weekday at 6:00pm
- **Target**: stephen
- **Action**: Remind about today's exercise plan.
```

The scheduler parses natural language schedules into cron expressions using APScheduler.

## Targeting

The **Target** field controls who receives the routine's output:

| Target | Behaviour |
|--------|-----------|
| A person name (e.g. `stephen`) | Runs with that person's context and sends them a private DM |
| `each_member` | Runs once per household member with their personal context, DMs each |
| `household` (or omitted) | Runs as the household and sends to the shared group chat |

When creating a routine via chat, the agent will ask who the routine is for before saving it.

## How it works

- The scheduler starts automatically alongside any channel (REPL, Telegram, web)
- Routines use the **cheaper model** by default to keep costs low
- Missed routines are detected and can be triggered manually
- Per-routine cost tracking is available
- Targeted routines use the person's workspace for context (memory, contacts, notes)

## Managing routines

Routines can be managed through:
- Editing `ROUTINES.md` directly
- The web UI under Routines
- Asking the agent to create or modify routines
