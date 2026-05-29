---
id: TASK-10
title: Thicken ui api.ts and extract shared UI primitives
status: To Do
assignee: []
created_date: '2026-05-29 05:01'
labels:
  - tier-3
  - duplication
  - ui
dependencies: []
priority: medium
ordinal: 10000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
api.ts returns a raw Response so ~35 call sites repeat 'if(!r.ok) throw / await r.json() / catch -> error', several with silent catch{}. Add apiJson<T>/apiBlob/downloadBlob with a typed ApiError. Then extract the missing primitive layer into ui/src/lib/: LoadingDots, ErrorCard, Button (variant prop), Field, Toggle, Card, Badge, SaveButton, DepWarnings — these CSS/markup blocks are currently duplicated byte-for-byte across Settings/Skills/Dashboard. Also add --surface-error/--surface-warn design tokens for the hardcoded hex backgrounds.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 apiJson/apiBlob/downloadBlob added; call sites migrated; no silent catch{} swallowing
- [ ] #2 Shared primitives extracted to lib/ and reused; duplicated CSS removed
<!-- AC:END -->
