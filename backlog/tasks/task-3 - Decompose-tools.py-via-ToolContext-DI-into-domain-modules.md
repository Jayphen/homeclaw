---
id: TASK-3
title: Decompose tools.py via ToolContext DI into domain modules
status: To Do
assignee: []
created_date: '2026-05-29 05:01'
labels:
  - tier-2
  - decomposition
  - agent
dependencies: []
priority: medium
ordinal: 3000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
tools.py is 2865 lines: all ~50 tools are nested inside register_builtin_tools, closing over 7 injected deps (accidental DI) so nothing is testable in isolation and the file cannot be split. Introduce a frozen ToolContext dataclass, make each tool a free 'async def handler(ctx, *, ...)', then split into ~10 domain modules: contacts, memory, reminders, bookmarks, web, messaging, routines, skills, admin. Behavior-preserving.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 ToolContext dataclass holds the injected deps; tools are module-level functions
- [ ] #2 tools.py is split into focused domain modules, each well under 1000 lines
- [ ] #3 Tool registration behavior and schemas are unchanged; full test suite + make typecheck pass
<!-- AC:END -->
