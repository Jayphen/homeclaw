---
name: logs
description: Read and search homeclaw application logs. Admin only.
metadata:
  admin_only: "true"
  builtin: "true"
---

# Logs

You can read homeclaw's own application logs using the `log_read` tool. This is
useful when an admin asks about errors, wants to debug an issue, or needs to
review what happened recently.

## Tool

**`log_read`** — query the persistent log file with filtering:
- `level`: filter by log level (DEBUG, INFO, WARNING, ERROR)
- `search`: text search across log messages and logger names
- `hours`: how far back to look (default 24)
- `limit`: max entries to return (default 100, max 500)

## When to use

- Admin asks "are there any errors?" or "what happened with X?"
- Debugging a failed tool call, channel connection, or scheduled routine
- Reviewing LLM responses and tool usage for a recent conversation
- Checking if a skill, plugin, or channel adapter started correctly

## Tips

- Start with a broad search (`hours=1, level=WARNING`) to find problems
- Use `search` to narrow down: `search="whatsapp"`, `search="tool failed"`
- DEBUG level shows individual tool calls and results — useful for tracing
- INFO level shows LLM responses, routing decisions, and consolidation
- Entries are returned newest first
