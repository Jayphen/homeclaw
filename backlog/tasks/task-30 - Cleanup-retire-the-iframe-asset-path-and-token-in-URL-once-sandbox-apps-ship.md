---
id: TASK-30
title: 'Cleanup: retire the iframe asset path and token-in-URL once sandbox apps ship'
status: To Do
assignee: []
created_date: '2026-05-29 11:37'
labels:
  - skills
  - security
  - cleanup
dependencies:
  - TASK-28
priority: medium
ordinal: 30000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Remove the obsolete HTML-iframe mini-app machinery after the sandbox path is live.

Changes:
- Remove assets/index.html iframe serving for mini-apps + the ?token= query-param auth (deps.py _parse_auth query branch, skillAppSrc in ui/src/lib/api.ts).
- Remove the detail-page iframe embed in Skills.svelte and the render-boundary HTML injection in skills.py (superseded by sandbox onError).
- Keep db/query + db/schema (used by the host bridge). Audit for any remaining URL-token usage.

Depends on TASK-28 (sandbox rendering must be live first).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 ?token= query-param auth and skillAppSrc removed; session token never in a URL
- [ ] #2 iframe asset serving + render-boundary HTML injection removed; db endpoints retained
- [ ] #3 no remaining URL-token usage (verified)
<!-- AC:END -->
