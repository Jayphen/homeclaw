---
id: TASK-2
title: Fix history truncation silently shrinking persisted unconsolidated history
status: Done
assignee:
  - '@me'
created_date: '2026-05-29 05:01'
updated_date: '2026-05-29 05:23'
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

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Root cause: _save_history rewrote the post-pointer history from the truncated in-memory window, so any unconsolidated message outside that window (dropped by _truncate_history or the _load_history 200-cap) was deleted before consolidation could fold it into memory. Fix: replaced _save_history with append-only _append_turn(workspaces, person, new_messages) — it retains every on-disk message and appends only this turn's new user/assistant/tool messages. Threaded a new_messages list through _run_inner (user/assistant/tool creation sites) and pointed all three exit paths at _append_turn. Invariant documented in the _append_turn docstring. Tests: unit (test_unconsolidated_history_beyond_the_window_is_never_lost, append-only semantics) + integration (test_truncated_turns_are_not_dropped_from_persisted_history — 5 turns under the tiny-context-window mock). 633 unit + 15 integration pass; typecheck + lint clean.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
History persistence is now append-only (_append_turn): the bounded/truncated LLM context window no longer drives what is saved, so unconsolidated turns outside the window are retained for consolidation instead of being silently dropped.
<!-- SECTION:FINAL_SUMMARY:END -->
