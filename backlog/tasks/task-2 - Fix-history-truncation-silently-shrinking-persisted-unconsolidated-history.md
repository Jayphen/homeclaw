---
id: TASK-2
title: Fix history truncation silently shrinking persisted unconsolidated history
status: To Do
assignee: []
created_date: '2026-05-29 05:01'
labels:
  - tier-1
  - correctness
  - agent-loop
dependencies:
  - TASK-1
priority: high
ordinal: 2000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
After _truncate_history (loop.py:813) the in-memory list is shorter than the on-disk post-pointer slice. _save_history reconstructs consolidated=old[:pointer] then appends the truncated tail, so long conversations can drop unconsolidated history on save. Needs a clearer invariant (ideally once history persistence is its own module, see tools/loop decomposition task) and a regression test proving truncation never deletes unconsolidated-but-unsaved messages.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Invariant documented: persisted post-pointer history is never shrunk by in-memory context truncation
- [ ] #2 Regression test covers a conversation long enough to trigger truncation and asserts no unconsolidated message loss
<!-- AC:END -->
