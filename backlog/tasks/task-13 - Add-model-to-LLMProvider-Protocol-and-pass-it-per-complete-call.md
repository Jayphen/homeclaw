---
id: TASK-13
title: Add model to LLMProvider Protocol and pass it per complete() call
status: To Do
assignee: []
created_date: '2026-05-29 05:02'
labels:
  - tier-4
  - typing
  - agent-loop
dependencies: []
priority: medium
ordinal: 13000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The loop mutates a shared provider instance's model per turn (active_provider.model = model at loop.py:834,962 and consolidation 671), forcing four # type: ignore[attr-defined], hasattr guards, getattr(provider,'model',...) fallbacks, and a copy.copy(provider) workaround (loop.py:663) — plus a latent mid-request mutation race. Add 'model' to the LLMProvider Protocol and pass model= as a parameter to complete() instead of mutating the instance. Deletes the ignores, the guards, the copy hack, and the race class.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 LLMProvider Protocol declares model; complete() accepts model param
- [ ] #2 No provider.model mutation remains; type: ignore[attr-defined] for provider.model removed
- [ ] #3 Both providers updated; tests + typecheck pass
<!-- AC:END -->
