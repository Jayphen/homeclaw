<svelte:head>
  <title>Scheduler & Routines — homeclaw docs</title>
</svelte:head>

# Scheduler & Routines

homeclaw runs recurring tasks defined in natural language in `workspaces/household/ROUTINES.md`.

## Defining routines

Each routine is a markdown section with a schedule and action:

```markdown
## Morning briefing
**Schedule:** Every weekday at 7:30am
**Action:** Summarize today's calendar, reminders, and weather for each person.

## Weekly grocery reminder
**Schedule:** Every Sunday at 10am
**Action:** Ask each person if they need anything from the store and compile a shared list.
```

The scheduler parses natural language schedules into cron expressions using APScheduler.

## How it works

- The scheduler starts automatically alongside any channel (REPL, Telegram, web)
- Routines use the **cheaper model** by default to keep costs low
- Missed routines are detected and can be triggered manually
- Per-routine cost tracking is available

## Managing routines

Routines can be managed through:
- Editing `ROUTINES.md` directly
- The web UI under Routines
- Asking the agent to create or modify routines
