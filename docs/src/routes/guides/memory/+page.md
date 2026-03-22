<svelte:head>
  <title>Memory — homeclaw docs</title>
</svelte:head>

# Memory

Memory is stored as **markdown files** at `workspaces/{person}/memory/{topic}.md`, one file per topic (e.g. `food.md`, `health.md`, `routines.md`). Entries are append-only with timestamps.

Household-wide knowledge goes under `workspaces/household/memory/`.

## How it works

The agent writes memory via the `memory_save` tool (append to topic file) and reads via `memory_read` (list topics or read a specific one). Writes are always appends — no read-then-merge needed.

## Semantic recall with memsearch

[memsearch](https://github.com/zilliztech/memsearch) indexes all workspace content (notes, memory, contacts) into a Milvus Lite vector DB for semantic recall.

- **On startup**: `index()` builds the initial index, then `watch()` monitors for file changes
- **During conversation**: the context builder queries memsearch for top-k relevant chunks
- **Privacy**: recall is scoped per-person — a member only sees their own workspace + household
- **Source of truth**: markdown files on disk. The vector DB is a derived index that can be rebuilt

## Privacy model

Each person's memory is private by default. The agent only retrieves:
- The authenticated person's own workspace content
- Household-shared content under `workspaces/household/`

Cross-person memory is never surfaced unless explicitly shared to the household workspace.
