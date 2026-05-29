# Agent Instructions

Use [Backlog.md](https://backlog.md) (`backlog`) for all task tracking. Check `backlog task list --plain` at the start of each session.
This project is called homeclaw. Read HOMECLAW.md before starting any work.
All Python code must pass Pyright (standard mode): run `make typecheck`.
All data models use Pydantic BaseModel. All interfaces use Protocol classes.
Memory has two layers: structured facts (memory.json) and semantic recall (memsearch).
Do not conflate them. Layer 1 is always on. Layer 2 requires enhanced memory mode.
When ending a session, land the plane: file remaining work, close completed
issues, push.

This project uses **Backlog.md** for issue tracking. Tasks live as markdown files under `backlog/`.

## Quick Reference

```bash
backlog task list --plain                       # Find available work
backlog task <id> --plain                        # View task details
backlog task edit <id> -s "In Progress" -a @me   # Claim and start work
backlog task edit <id> -s Done                   # Complete work
backlog task create "Title" -d "..."             # File new work
```

## Non-Interactive Shell Commands

**ALWAYS use non-interactive flags** with file operations to avoid hanging on confirmation prompts.

Shell commands like `cp`, `mv`, and `rm` may be aliased to include `-i` (interactive) mode on some systems, causing the agent to hang indefinitely waiting for y/n input.

**Use these forms instead:**
```bash
# Force overwrite without prompting
cp -f source dest           # NOT: cp source dest
mv -f source dest           # NOT: mv source dest
rm -f file                  # NOT: rm file

# For recursive operations
rm -rf directory            # NOT: rm -r directory
cp -rf source dest          # NOT: cp -r source dest
```

**Other commands that may prompt:**
- `scp` - use `-o BatchMode=yes` for non-interactive
- `ssh` - use `-o BatchMode=yes` to fail instead of prompting
- `apt-get` - use `-y` flag
- `brew` - use `HOMEBREW_NO_AUTO_UPDATE=1` env var

## Issue Tracking with Backlog.md

**IMPORTANT**: This project uses **Backlog.md** for ALL issue tracking. Do NOT use ad-hoc
markdown TODOs, scratch task lists, or other tracking methods. Tasks are markdown files
committed under `backlog/`, so they version with the code.

### Quick Start

**Check for available work:**

```bash
backlog task list --plain
```

**Create new tasks:**

```bash
backlog task create "Task title" -d "Detailed context" --priority high
backlog task create "Found bug" -d "What was found" --priority high --dep <parent-id>
```

**Claim and update:**

```bash
backlog task edit <id> -s "In Progress" -a @me
backlog task edit <id> --priority high
```

**Complete work:**

```bash
backlog task edit <id> -s Done
```

### Statuses

- `To Do` - Not started (default)
- `In Progress` - Being worked on
- `Done` - Completed

### Priorities

- `high` - Critical / important (security, data loss, broken builds, major bugs)
- `medium` - Default, nice-to-have
- `low` - Polish, optimization, future ideas

### Workflow for AI Agents

1. **Check available work**: `backlog task list --plain`
2. **Read the task**: `backlog task <id> --plain`
3. **Claim it**: `backlog task edit <id> -s "In Progress" -a @me`
4. **Work on it**: Implement, test, document
5. **Discover new work?** File a linked task: `backlog task create "..." -d "..." --dep <parent-id>`
6. **Complete**: `backlog task edit <id> -s Done`

### Important Rules

- ✅ Use Backlog.md for ALL task tracking
- ✅ Use `--plain` for non-interactive / programmatic output
- ✅ Link discovered work with `--dep <parent-id>`
- ✅ Check `backlog task list --plain` before asking "what should I work on?"
- ❌ Do NOT create ad-hoc markdown TODO lists
- ❌ Do NOT use external issue trackers
- ❌ Do NOT duplicate tracking systems

## Landing the Plane (Session Completion)

**When ending a work session**, you MUST complete ALL steps below. Work is NOT complete until `git push` succeeds.

**MANDATORY WORKFLOW:**

1. **File tasks for remaining work** - Create backlog tasks for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update task status** - Mark finished work Done, update in-progress items
4. **PUSH TO REMOTE** - This is MANDATORY:
   ```bash
   git pull --rebase
   git add backlog/
   git commit -m "chore: update backlog tasks"
   git push
   git status  # MUST show "up to date with origin"
   ```
5. **Clean up** - Clear stashes, prune remote branches
6. **Verify** - All changes committed AND pushed
7. **Hand off** - Provide context for next session

**CRITICAL RULES:**
- Work is NOT complete until `git push` succeeds
- NEVER stop before pushing - that leaves work stranded locally
- NEVER say "ready to push when you are" - YOU must push
- If push fails, resolve and retry until it succeeds
