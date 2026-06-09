---
id: TASK-36
title: 'refactor: split loop.py god module into cohesive submodules'
status: Done
assignee: []
created_date: '2026-06-09 04:15'
updated_date: '2026-06-09 04:24'
labels: []
dependencies: []
ordinal: 36000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
loop.py is 1598 lines mixing 7+ concerns. Extract into: history.py (persistence/windowing/tokens), prompts.py (system prompt + assembly), tool_policy.py (observability policy), activity_log.py (feed + chat logs), interim.py (heuristics), extend consolidation.py (SessionConsolidator). Update all call sites. Pure extraction, no logic changes.
<!-- SECTION:DESCRIPTION:END -->
