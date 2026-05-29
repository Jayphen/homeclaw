---
id: TASK-4
title: >-
  Decompose loop.py into history_store / history_window / system_prompt /
  activity_feed
status: To Do
assignee: []
created_date: '2026-05-29 05:01'
labels:
  - tier-2
  - decomposition
  - agent-loop
dependencies:
  - TASK-1
priority: medium
ordinal: 4000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
loop.py (1411 lines) mixes five responsibilities. Extract: history_store.py (JSONL+pointer protocol — the home for the TASK-1 atomic/lock fix), history_window.py (truncation/token math, pure fns), system_prompt.py (the 116-line prompt literal + builders), activity_feed.py (observability side-effects). Also collapse the three duplicated _run_inner exit epilogues and the duplicated initial/re-route routing block. Leaves a ~450-line file that is only the loop.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 history_store, history_window, system_prompt, activity_feed extracted as modules
- [ ] #2 Duplicated _run_inner exit epilogues collapsed to one; routing logic extracted to one helper
- [ ] #3 loop.py is ~450 lines; behavior unchanged; tests + typecheck pass
<!-- AC:END -->
