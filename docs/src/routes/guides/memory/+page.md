<svelte:head>
  <title>Knowledge — homeclaw docs</title>
</svelte:head>

# Knowledge

The Knowledge system is how homeclaw remembers things. It combines several types of stored information, all searchable via semantic recall.

## Memory topics

Memory is stored as **markdown files** at `workspaces/{person}/memory/{topic}.md`, one file per topic (e.g. `food.md`, `health.md`, `routines.md`). Entries are append-only with timestamps.

Household-wide memory goes under `workspaces/household/memory/`.

The agent writes memory via the `memory_save` tool (append to topic file) and reads via `memory_read` (list topics or read a specific one). Writes are always appends — no read-then-merge needed.

## Notes

Daily notes live at `workspaces/{person}/notes/{date}.md`. The agent appends to these via `note_save` when a household member mentions something worth recording — a thought, an event, a decision.

Notes are separate from memory topics: **memory** is long-lived knowledge (preferences, facts, routines), while **notes** are daily logs of what happened or was discussed.

## Contacts and bookmarks

Contacts and bookmarks can have **notes attached** — per-contact interaction notes, private annotations, and bookmark comments. These are all stored as markdown or JSON on disk and are indexed alongside everything else.

## Semantic recall with memsearch

[memsearch](https://github.com/zilliztech/memsearch) indexes all workspace content — memory topics, notes, contacts, and bookmarks — into a Milvus Lite vector DB for semantic recall.

- **On startup**: `index()` builds the initial index, then `watch()` monitors for file changes
- **During conversation**: the context builder queries memsearch for top-k relevant chunks
- **Privacy**: recall is scoped per-person — a member only sees their own workspace + household
- **Source of truth**: markdown files on disk. The vector DB is a derived index that can be rebuilt

## Privacy model

Each person's knowledge is private by default. The agent only retrieves:
- The authenticated person's own workspace content
- Household-shared content under `workspaces/household/`

Cross-person data is never surfaced unless explicitly shared to the household workspace.
