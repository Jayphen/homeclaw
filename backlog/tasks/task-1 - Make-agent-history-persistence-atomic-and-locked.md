---
id: TASK-1
title: Make agent history persistence atomic and locked
status: Done
assignee:
  - '@me'
created_date: '2026-05-29 05:00'
updated_date: '2026-05-29 05:08'
labels:
  - tier-1
  - correctness
  - agent-loop
dependencies: []
priority: high
ordinal: 1000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Background consolidation races the request path on history.jsonl. run() writes under self._lock_pool.lock_for(history_key) (loop.py:736) but _consolidate_session / _advance_consolidation_pointer (loop.py:615,703) take NO lock, and both _save_history (loop.py:1397) and the pointer-advance (loop.py:1411) rewrite the whole file via path.write_text — non-atomic. A consolidation pass concurrent with a _save_history can lose or resurrect messages; a crash mid-write corrupts the conversation. Same non-atomic write_text pattern exists in dispatcher.py:_save_prefs (105) and registration.py:save_user_map (32).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 _consolidate_session acquires lock_for(history_key) around its read + pointer-advance
- [ ] #2 All history writes use write-temp-then-os.replace (atomic)
- [ ] #3 A shared atomic_write_json/read_json_safe helper is introduced and reused by dispatcher.py and registration.py
- [ ] #4 Existing agent-loop and consolidation tests still pass; a concurrency regression test is added
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Added homeclaw/atomicio.py (atomic_write_text/atomic_write_json/read_json_safe). Switched _save_history and _advance_consolidation_pointer (loop.py) to atomic_write_text. Wrapped the consolidation pointer-advance in _consolidate_session under self._lock_pool.lock_for(history_key) so it can't race the request-path save; the advance re-reads fresh so a turn saved during LLM extraction is preserved. Migrated dispatcher.py prefs and registration.py user-map to the shared helpers (also gives dispatcher _load_prefs a safe fallback it lacked). Tests: tests/unit/test_atomicio.py (incl. threaded torn-read check) + TestConsolidationSaveInterleaving in test_history_pointer.py. 631 unit + 14 integration pass; typecheck + lint clean.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
History persistence is now atomic (temp+os.replace) and the consolidation pointer-advance is serialized against the request path via the per-key lock. Shared atomic_write_json/read_json_safe helper reused by dispatcher and registration.
<!-- SECTION:FINAL_SUMMARY:END -->
